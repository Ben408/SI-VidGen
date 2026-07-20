"""Help Center image library: catalog, classify, download, and query assets."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

NOISE_PATH_PARTS = (
    "/skins/",
    "/topnavimages/",
    "/transparent.gif",
    "logo-sage-intacct",
    "favicon",
    "sprite",
    "relatedtopics",
)

USER_AGENT = "SI-VidGen/0.1 authorized-help-asset-library"


@dataclass
class HelpImageAsset:
    asset_id: str
    source_url: str
    local_path: str
    content_sha256: str
    page_url: str
    page_title: str
    heading_path: str
    alt_text: str
    caption: str
    module: str
    asset_class: str
    filename: str
    usable_for_video: bool


@dataclass
class ImageLibrarySummary:
    pages_scanned: int = 0
    assets_discovered: int = 0
    assets_usable: int = 0
    assets_downloaded: int = 0
    assets_skipped_noise: int = 0
    download_errors: int = 0
    by_class: dict[str, int] = field(default_factory=dict)
    pages_with_usable_assets: int = 0


class HelpImageLibrary:
    def __init__(self, library_dir: Path) -> None:
        self.library_dir = library_dir
        self.files_dir = library_dir / "files"
        self.catalog_path = library_dir / "catalog.json"
        self.coverage_path = library_dir / "coverage.json"
        self._assets_by_url: dict[str, HelpImageAsset] = {}
        self._assets_by_id: dict[str, HelpImageAsset] = {}
        if self.catalog_path.is_file():
            self._load()

    def _load(self) -> None:
        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        for item in payload.get("assets", []):
            asset = HelpImageAsset(**item)
            self._assets_by_url[asset.source_url] = asset
            self._assets_by_id[asset.asset_id] = asset

    def get_by_url(self, url: str) -> HelpImageAsset | None:
        return self._assets_by_url.get(url)

    def get_by_id(self, asset_id: str) -> HelpImageAsset | None:
        return self._assets_by_id.get(asset_id)

    def usable_urls(self) -> set[str]:
        return {
            url
            for url, asset in self._assets_by_url.items()
            if asset.usable_for_video and Path(asset.local_path).is_file()
        }

    def resolve_local_paths(self, urls: list[str]) -> list[Path]:
        paths: list[Path] = []
        seen: set[str] = set()
        for url in urls:
            asset = self._assets_by_url.get(url)
            if asset is None or not asset.usable_for_video:
                continue
            path = Path(asset.local_path)
            if not path.is_file() or str(path) in seen:
                continue
            seen.add(str(path))
            paths.append(path)
        return paths

    def pick_for_urls(self, urls: list[str]) -> list[HelpImageAsset]:
        picks: list[HelpImageAsset] = []
        seen: set[str] = set()
        for url in urls:
            asset = self._assets_by_url.get(url)
            if (
                asset is None
                or not asset.usable_for_video
                or asset.asset_id in seen
                or not Path(asset.local_path).is_file()
            ):
                continue
            seen.add(asset.asset_id)
            picks.append(asset)
        return picks

    def coverage(self) -> dict[str, object]:
        if self.coverage_path.is_file():
            return json.loads(self.coverage_path.read_text(encoding="utf-8"))
        return {
            "pages_scanned": 0,
            "pages_with_usable_assets": 0,
            "assets_usable": 0,
            "by_class": {},
        }


def classify_asset(filename: str, alt_text: str) -> tuple[str, bool]:
    name = filename.upper()
    alt = alt_text.lower()
    if name.startswith("ICON") or "icon-" in filename.lower():
        return "icon", False
    if name.startswith("EXAMPLE"):
        return "example", True
    if name.startswith("CONCEPT"):
        return "concept", True
    if "SCREEN" in name or "DIALOG" in name or "WINDOW" in name:
        return "screenshot", True
    if any(token in alt for token in ("screenshot", "page", "dialog", "window", "form")):
        return "screenshot", True
    if len(alt_text.strip()) >= 24:
        return "illustration", True
    return "unknown", False


def is_noise_url(url: str, alt_text: str = "") -> bool:
    lower = url.lower()
    alt = alt_text.lower()
    if any(part in lower for part in NOISE_PATH_PARTS):
        return True
    if "logo" in alt or alt in {"related topics link icon"}:
        return True
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def module_from_url(page_url: str) -> str:
    parts = urlparse(page_url).path.split("/")
    if "help_action" in parts:
        index = parts.index("help_action")
        if index + 1 < len(parts):
            return parts[index + 1]
    return "unknown"


def build_image_library(
    cache_dir: Path,
    library_dir: Path,
    *,
    download: bool = True,
    max_downloads: int | None = None,
    timeout_seconds: float = 30,
) -> ImageLibrarySummary:
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing help cache manifest: {manifest_path}")
    pages = json.loads(manifest_path.read_text(encoding="utf-8")).get("pages", [])
    library_dir.mkdir(parents=True, exist_ok=True)
    files_dir = library_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    summary = ImageLibrarySummary(pages_scanned=len(pages))
    discovered: dict[str, HelpImageAsset] = {}
    pages_with_usable: set[str] = set()

    for page in pages:
        cache_path = cache_dir / page["cache_path"]
        if not cache_path.is_file():
            continue
        xhtml = cache_path.read_text(encoding="utf-8", errors="ignore")
        parser = "lxml-xml" if xhtml.lstrip().startswith("<?xml") else "lxml"
        soup = BeautifulSoup(xhtml, parser)
        title = _page_title(soup)
        for image in soup.find_all("img", src=True):
            src = str(image.get("src") or "")
            if not src or src.startswith("data:"):
                continue
            source_url = urljoin(page["url"], src).split("?")[0]
            alt_text = " ".join(str(image.get("alt") or "").split())
            if is_noise_url(source_url, alt_text):
                summary.assets_skipped_noise += 1
                continue
            filename = Path(urlparse(source_url).path).name
            asset_class, usable = classify_asset(filename, alt_text)
            heading = _nearest_heading(image)
            caption = _caption(image)
            asset_id = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:24]
            local_name = f"{asset_id}{Path(filename).suffix.lower() or '.png'}"
            local_path = files_dir / local_name
            asset = HelpImageAsset(
                asset_id=asset_id,
                source_url=source_url,
                local_path=str(local_path),
                content_sha256="",
                page_url=page["url"],
                page_title=title,
                heading_path=heading,
                alt_text=alt_text,
                caption=caption,
                module=module_from_url(page["url"]),
                asset_class=asset_class,
                filename=filename,
                usable_for_video=usable,
            )
            existing = discovered.get(source_url)
            if existing is None:
                discovered[source_url] = asset
            else:
                # Prefer richer metadata when the same asset appears on multiple pages.
                if not existing.alt_text and asset.alt_text:
                    existing.alt_text = asset.alt_text
                if not existing.heading_path and asset.heading_path:
                    existing.heading_path = asset.heading_path
                if not existing.caption and asset.caption:
                    existing.caption = asset.caption
                if asset.usable_for_video:
                    existing.usable_for_video = True
                    existing.asset_class = asset.asset_class
            if usable:
                pages_with_usable.add(page["url"])

    summary.assets_discovered = len(discovered)
    summary.assets_usable = sum(1 for asset in discovered.values() if asset.usable_for_video)
    summary.pages_with_usable_assets = len(pages_with_usable)
    summary.by_class = dict(
        Counter(asset.asset_class for asset in discovered.values()).most_common()
    )

    downloaded = 0
    if download:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=timeout_seconds,
        ) as client:
            for asset in discovered.values():
                if not asset.usable_for_video:
                    continue
                if max_downloads is not None and downloaded >= max_downloads:
                    break
                path = Path(asset.local_path)
                if path.is_file() and path.stat().st_size > 0:
                    asset.content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
                    continue
                try:
                    response = client.get(asset.source_url)
                    response.raise_for_status()
                    path.write_bytes(response.content)
                    asset.content_sha256 = hashlib.sha256(response.content).hexdigest()
                    downloaded += 1
                    summary.assets_downloaded += 1
                except httpx.HTTPError:
                    summary.download_errors += 1
                    asset.usable_for_video = False

    catalog = {
        "version": 1,
        "library_dir": str(library_dir),
        "assets": [
            asdict(asset)
            for asset in sorted(discovered.values(), key=lambda a: a.source_url)
        ],
    }
    _write_json(library_dir / "catalog.json", catalog)
    coverage = {
        "pages_scanned": summary.pages_scanned,
        "pages_with_usable_assets": summary.pages_with_usable_assets,
        "coverage_pct": round(
            100 * summary.pages_with_usable_assets / max(summary.pages_scanned, 1), 1
        ),
        "assets_discovered": summary.assets_discovered,
        "assets_usable": summary.assets_usable,
        "assets_downloaded": summary.assets_downloaded,
        "assets_skipped_noise": summary.assets_skipped_noise,
        "download_errors": summary.download_errors,
        "by_class": summary.by_class,
    }
    _write_json(library_dir / "coverage.json", coverage)
    return summary


def _page_title(soup: BeautifulSoup) -> str:
    if heading := soup.find("h1"):
        return " ".join(heading.stripped_strings)
    if soup.title:
        return " ".join(soup.title.stripped_strings)
    return "Untitled help topic"


def _nearest_heading(image) -> str:
    for parent in image.parents:
        previous = parent.find_previous(["h1", "h2", "h3", "h4"])
        if previous:
            return " ".join(previous.stripped_strings)
    return ""


def _caption(image) -> str:
    figure = image.find_parent("figure")
    if figure and figure.find("figcaption"):
        return " ".join(figure.find("figcaption").stripped_strings)
    return ""


def _write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
