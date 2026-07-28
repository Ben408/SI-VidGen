"""Rules-only Flare XHTML → OKF bundle converter."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from src.rag.chunker import NOISE_SELECTORS
from src.rag.image_library import (
    HelpImageLibrary,
    classify_asset,
    is_noise_url,
    module_from_url,
)
from src.rag.okf.format import (
    classify_section,
    dump_concept,
    module_from_page_url,
    slugify,
    topic_relpath_from_url,
)

CONTENT_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd", "th", "td"}


@dataclass
class ConvertSummary:
    pages_scanned: int = 0
    pages_converted: int = 0
    topics: int = 0
    procedures: int = 0
    screens: int = 0
    sections: int = 0
    assets: int = 0
    errors: list[str] = field(default_factory=list)


def convert_xhtml_cache_to_okf(
    cache_dir: Path,
    okf_dir: Path,
    *,
    library_dir: Path | None = None,
    max_pages: int | None = None,
) -> ConvertSummary:
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing help cache manifest: {manifest_path}")

    pages = json.loads(manifest_path.read_text(encoding="utf-8")).get("pages", [])
    if max_pages is not None:
        pages = pages[: max(0, max_pages)]

    library = HelpImageLibrary(library_dir) if library_dir and library_dir.is_dir() else None

    if okf_dir.exists():
        # Rebuild cleanly so Friday/quarterly runs do not leave stale concepts.
        for path in sorted(okf_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir() and path != okf_dir:
                path.rmdir()
    okf_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("topics", "procedures", "screens", "sections", "assets"):
        (okf_dir / sub).mkdir(parents=True, exist_ok=True)

    summary = ConvertSummary(pages_scanned=len(pages))
    catalog_entries: list[dict[str, Any]] = []
    asset_written: set[str] = set()

    for page in pages:
        try:
            entries = _convert_page(
                cache_dir=cache_dir,
                okf_dir=okf_dir,
                page=page,
                library=library,
                asset_written=asset_written,
            )
        except Exception as exc:  # noqa: BLE001 — continue full corpus
            summary.errors.append(f"{page.get('url', '?')}: {exc}")
            continue
        summary.pages_converted += 1
        for entry in entries:
            catalog_entries.append(entry)
            kind = entry.get("type")
            if kind == "HelpTopic":
                summary.topics += 1
            elif kind == "Procedure":
                summary.procedures += 1
            elif kind == "UIScreen":
                summary.screens += 1
            elif kind == "HelpSection":
                summary.sections += 1
            elif kind == "HelpAsset":
                summary.assets += 1

    catalog_entries.sort(key=lambda item: item.get("concept_id", ""))
    _write_json(
        okf_dir / "catalog.json",
        {
            "version": 1,
            "bundle_dir": str(okf_dir),
            "source": "flare_xhtml_cache",
            "pages_converted": summary.pages_converted,
            "concepts": catalog_entries,
            "counts": {
                "topics": summary.topics,
                "procedures": summary.procedures,
                "screens": summary.screens,
                "sections": summary.sections,
                "assets": summary.assets,
            },
            "errors": summary.errors[:50],
        },
    )
    _write_index(okf_dir, summary)
    return summary


def convert_xhtml_document(
    xhtml: str,
    *,
    source_url: str,
    source_hash: str,
    okf_dir: Path,
    library: HelpImageLibrary | None = None,
    asset_written: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Convert one XHTML document into OKF concept files. Returns catalog rows."""
    asset_written = asset_written if asset_written is not None else set()
    return _convert_parsed(
        xhtml=xhtml,
        source_url=source_url,
        source_hash=source_hash,
        okf_dir=okf_dir,
        library=library,
        asset_written=asset_written,
    )


def _convert_page(
    *,
    cache_dir: Path,
    okf_dir: Path,
    page: dict[str, Any],
    library: HelpImageLibrary | None,
    asset_written: set[str],
) -> list[dict[str, Any]]:
    cache_path = cache_dir / page["cache_path"]
    if not cache_path.is_file():
        raise FileNotFoundError(f"Missing cache file: {cache_path}")
    xhtml = cache_path.read_text(encoding="utf-8", errors="ignore")
    return _convert_parsed(
        xhtml=xhtml,
        source_url=str(page["url"]),
        source_hash=str(page.get("content_hash") or page.get("hash") or ""),
        okf_dir=okf_dir,
        library=library,
        asset_written=asset_written,
    )


def _convert_parsed(
    *,
    xhtml: str,
    source_url: str,
    source_hash: str,
    okf_dir: Path,
    library: HelpImageLibrary | None,
    asset_written: set[str],
) -> list[dict[str, Any]]:
    parser = "lxml-xml" if xhtml.lstrip().startswith("<?xml") else "lxml"
    soup = BeautifulSoup(xhtml, parser)
    for selector in NOISE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()

    title = _page_title(soup)
    module = module_from_page_url(source_url)
    topic_rel = topic_relpath_from_url(source_url)
    topic_id = topic_rel.removesuffix(".md")

    sections = _extract_sections(soup, source_url)
    page_asset_meta = _collect_images(soup, source_url, library)

    catalog: list[dict[str, Any]] = []
    child_links: list[str] = []
    topic_asset_ids: list[str] = []

    for meta in page_asset_meta:
        asset_id = meta["asset_id"]
        topic_asset_ids.append(asset_id)
        if asset_id in asset_written:
            continue
        asset_rel = f"assets/{asset_id}.md"
        asset_concept_id = asset_rel.removesuffix(".md")
        local_path = meta.get("local_path") or ""
        body_lines = [
            f"![{meta.get('alt_text') or meta['filename']}]({meta['source_url']})",
            "",
            f"Help Center image referenced from `{source_url}`.",
            f"Binary stored in shared library: `{local_path or 'data/help_assets/files'}` "
            "(not copied into OKF).",
        ]
        frontmatter = {
            "type": "HelpAsset",
            "title": meta.get("alt_text") or meta["filename"],
            "description": meta.get("caption") or meta.get("alt_text") or "",
            "page_url": source_url,
            "source_url": meta["source_url"],
            "asset_id": asset_id,
            "asset_class": meta["asset_class"],
            "usable_for_video": meta["usable_for_video"],
            "heading_path": meta.get("heading_path") or "",
            "alt_text": meta.get("alt_text") or "",
            "caption": meta.get("caption") or "",
            "module": module,
            "filename": meta["filename"],
            "local_path": local_path,
            "library_ref": "data/help_assets",
            "status": "active",
            "generated": "process:okf_convert_rules",
        }
        body = "\n".join(body_lines)
        _write_text(
            okf_dir / asset_rel,
            dump_concept(frontmatter=frontmatter, body=body),
        )
        asset_written.add(asset_id)
        catalog.append(
            {
                "concept_id": asset_concept_id,
                "type": "HelpAsset",
                "title": frontmatter["title"],
                "page_url": source_url,
                "path": asset_rel,
                "asset_id": asset_id,
                "source_url": meta["source_url"],
                "usable_for_video": meta["usable_for_video"],
            }
        )

    for section_index, section in enumerate(sections):
        heading = section["heading"]
        heading_path = section["heading_path"]
        body_md = section["body_md"]
        section_assets = [
            meta
            for meta in page_asset_meta
            if _heading_overlap(heading_path, meta.get("heading_path") or "")
            or _heading_overlap(heading, meta.get("heading_path") or "")
        ]
        # Fallback: unscoped images attach to the last section (screenshots usually follow steps).
        if not section_assets and section_index == len(sections) - 1:
            section_assets = [
                meta for meta in page_asset_meta if not meta.get("heading_path")
            ]

        asset_classes = [meta["asset_class"] for meta in section_assets]
        concept_type = classify_section(heading, section["body_lines"], asset_classes)
        folder = {
            "Procedure": "procedures",
            "UIScreen": "screens",
            "HelpSection": "sections",
        }[concept_type]
        stem = slugify(heading)
        # Keep paths unique per page.
        page_stem = Path(topic_rel).stem
        rel = f"{folder}/{module}/{page_stem}__{stem}.md"
        concept_id = rel.removesuffix(".md")
        asset_ids = [meta["asset_id"] for meta in section_assets]
        asset_urls = [meta["source_url"] for meta in section_assets]
        asset_links = "\n".join(
            f"- [{meta.get('alt_text') or meta['filename']}](../assets/{meta['asset_id']}.md)"
            for meta in section_assets
        )
        body = body_md
        if asset_links:
            body = f"{body_md}\n\n## Screenshots\n\n{asset_links}\n"
        frontmatter = {
            "type": concept_type,
            "title": heading,
            "description": body_md.split("\n", 1)[0][:240] if body_md else heading,
            "page_url": source_url,
            "parent_topic": f"/{topic_id}",
            "heading_path": heading_path,
            "module": module,
            "source_hash": source_hash,
            "asset_ids": asset_ids,
            "asset_urls": asset_urls,
            "status": "active",
            "generated": "process:okf_convert_rules",
            "tags": [module, concept_type.lower()],
        }
        _write_text(okf_dir / rel, dump_concept(frontmatter=frontmatter, body=body))
        child_links.append(f"- [{heading}](/{concept_id})")
        catalog.append(
            {
                "concept_id": concept_id,
                "type": concept_type,
                "title": heading,
                "page_url": source_url,
                "path": rel,
                "heading_path": heading_path,
                "asset_urls": asset_urls,
                "parent_topic": topic_id,
            }
        )

    topic_body_parts = [f"# {title}", "", f"Live Help: [{title}]({source_url})", ""]
    if child_links:
        topic_body_parts.extend(["## Derived concepts", "", *child_links, ""])
    topic_body_parts.extend(
        [
            "## Topic overview",
            "",
            sections[0]["body_md"] if sections else "_No extractable body._",
        ]
    )
    topic_frontmatter = {
        "type": "HelpTopic",
        "title": title,
        "description": f"Sage Intacct Help topic: {title}",
        "page_url": source_url,
        "module": module,
        "source_hash": source_hash,
        "asset_ids": topic_asset_ids,
        "status": "active",
        "generated": "process:okf_convert_rules",
        "tags": [module, "help-topic"],
    }
    _write_text(
        okf_dir / topic_rel,
        dump_concept(frontmatter=topic_frontmatter, body="\n".join(topic_body_parts)),
    )
    catalog.append(
        {
            "concept_id": topic_id,
            "type": "HelpTopic",
            "title": title,
            "page_url": source_url,
            "path": topic_rel,
            "module": module,
        }
    )
    return catalog


def _extract_sections(soup: BeautifulSoup, _source_url: str) -> list[dict[str, Any]]:
    root = soup.find("main") or soup.find("article") or soup.body or soup
    title = _page_title(soup)
    sections: list[dict[str, Any]] = []
    current = {
        "heading": title,
        "heading_path": title,
        "level": 1,
        "body_lines": [],
        "body_md": "",
    }
    active: list[str] = [title]
    seen_h1 = False

    def flush() -> None:
        body_lines = list(current["body_lines"])
        if not body_lines and current["heading"] == title and sections:
            return
        current["body_md"] = "\n\n".join(body_lines).strip()
        sections.append(
            {
                "heading": current["heading"],
                "heading_path": current["heading_path"],
                "body_lines": body_lines,
                "body_md": current["body_md"],
            }
        )

    for element in root.find_all(True):
        if not isinstance(element, Tag):
            continue
        name = _local_tag_name(element)
        if name in CONTENT_TAGS:
            # Skip nested text containers already covered by a parent content tag.
            parent_content = False
            for parent in element.parents:
                if parent is root:
                    break
                if isinstance(parent, Tag) and _local_tag_name(parent) in CONTENT_TAGS:
                    parent_content = True
                    break
            if parent_content:
                continue
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            text = _norm_text(element)
            if not text:
                continue
            if name == "h1" and text == title and not seen_h1 and not current["body_lines"]:
                # Avoid duplicating the synthetic title section when the real h1 matches.
                seen_h1 = True
                active[:] = [title]
                current["heading"] = title
                current["heading_path"] = title
                continue
            flush()
            seen_h1 = seen_h1 or name == "h1"
            active[:] = active[: level - 1]
            active.append(text)
            current = {
                "heading": text,
                "heading_path": " > ".join(active),
                "level": level,
                "body_lines": [],
                "body_md": "",
            }
            continue
        if name == "img":
            continue
        if name not in CONTENT_TAGS:
            continue
        text = _norm_text(element)
        if not text:
            continue
        prefix = "- " if name == "li" else ""
        current["body_lines"].append(f"{prefix}{text}")
    flush()
    if not sections:
        sections.append(
            {
                "heading": title,
                "heading_path": title,
                "body_lines": [],
                "body_md": "",
            }
        )
    return sections


def _collect_images(
    soup: BeautifulSoup,
    source_url: str,
    library: HelpImageLibrary | None,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for image in soup.find_all("img", src=True):
        src = str(image.get("src") or "")
        if not src or src.startswith("data:"):
            continue
        absolute = urljoin(source_url, src).split("?")[0]
        alt_text = " ".join(str(image.get("alt") or "").split())
        if is_noise_url(absolute, alt_text):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        filename = Path(absolute).name
        asset_class, usable = classify_asset(filename, alt_text)
        heading = _nearest_heading(image)
        caption = _caption(image)
        asset_id = hashlib.sha256(absolute.encode("utf-8")).hexdigest()[:24]
        local_path = ""
        if library is not None:
            lib_asset = library.get_by_url(absolute)
            if lib_asset is not None:
                asset_id = lib_asset.asset_id
                asset_class = lib_asset.asset_class
                usable = lib_asset.usable_for_video
                local_path = lib_asset.local_path
                if lib_asset.heading_path:
                    heading = lib_asset.heading_path
                if lib_asset.alt_text and not alt_text:
                    alt_text = lib_asset.alt_text
        found.append(
            {
                "asset_id": asset_id,
                "source_url": absolute,
                "filename": filename,
                "alt_text": alt_text,
                "caption": caption,
                "heading_path": heading,
                "asset_class": asset_class,
                "usable_for_video": usable,
                "local_path": local_path,
                "module": module_from_url(source_url),
            }
        )
    return found


def _nearest_heading(image: Tag) -> str:
    for element in image.find_all_previous(True):
        name = _local_tag_name(element)
        if name in {"h1", "h2", "h3", "h4"}:
            return " ".join(element.stripped_strings)
    return ""


def _local_tag_name(element: Tag) -> str:
    name = str(element.name or "").lower()
    if ":" in name:
        return name.split(":", 1)[1]
    if "}" in name:
        return name.rsplit("}", 1)[-1]
    return name


def _caption(image: Tag) -> str:
    figure = image.find_parent("figure")
    if figure is None:
        # Namespaced figure tags
        for parent in image.parents:
            if _local_tag_name(parent) == "figure":
                figure = parent
                break
    if figure is None:
        return ""
    for child in figure.find_all(True):
        if _local_tag_name(child) == "figcaption":
            return " ".join(child.stripped_strings)
    return ""


def _page_title(soup: BeautifulSoup) -> str:
    if heading := soup.find("h1"):
        return " ".join(heading.stripped_strings)
    if soup.title:
        return " ".join(soup.title.stripped_strings)
    return "Untitled help topic"


def _norm_text(element: Tag) -> str:
    return re.sub(r"\s+", " ", " ".join(element.stripped_strings)).strip()


def _heading_overlap(left: str, right: str) -> bool:
    if not left or not right:
        return False
    a = left.lower()
    b = right.lower()
    if a == b or a in b or b in a:
        return True
    left_parts = {part.strip() for part in re.split(r"\s*>\s*", a) if part.strip()}
    right_parts = {part.strip() for part in re.split(r"\s*>\s*", b) if part.strip()}
    return bool(left_parts & right_parts)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _write_index(okf_dir: Path, summary: ConvertSummary) -> None:
    body = "\n".join(
        [
            "# Sage Intacct Help OKF bundle",
            "",
            "Rules-only conversion from Flare-published XHTML.",
            "Help screenshots are referenced from `data/help_assets/` (not copied).",
            "",
            "## Counts",
            "",
            f"- Topics: {summary.topics}",
            f"- Procedures: {summary.procedures}",
            f"- UI screens: {summary.screens}",
            f"- Sections: {summary.sections}",
            f"- Assets: {summary.assets}",
            f"- Pages converted: {summary.pages_converted}/{summary.pages_scanned}",
            "",
            "## Browse",
            "",
            "- [Topics](topics/)",
            "- [Procedures](procedures/)",
            "- [Screens](screens/)",
            "- [Sections](sections/)",
            "- [Assets](assets/)",
            "",
        ]
    )
    _write_text(
        okf_dir / "index.md",
        dump_concept(
            frontmatter={
                "type": "BundleIndex",
                "title": "SI VidGen Help OKF",
                "status": "active",
                "generated": "process:okf_convert_rules",
            },
            body=body,
        ),
    )
