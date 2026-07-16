import hashlib
import json
import ssl
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "SI-VidGen/0.1 authorized-help-indexer"
HTML_SUFFIXES = {"", ".htm", ".html", ".xhtml"}


@dataclass(frozen=True)
class XhtmlDocument:
    url: str
    cache_path: str
    content_sha256: str
    fetched_at: str
    etag: str | None = None
    last_modified: str | None = None


def is_allowed_help_url(url: str, allowed_prefix: str) -> bool:
    """Enforce the authorized same-host/path crawl boundary."""
    candidate = urlparse(url)
    allowed = urlparse(allowed_prefix)
    return (
        candidate.scheme in {"http", "https"}
        and candidate.netloc == allowed.netloc
        and candidate.path.startswith(allowed.path)
    )


def normalize_help_url(url: str, base_url: str, allowed_prefix: str) -> str | None:
    absolute, _fragment = urldefrag(urljoin(base_url, url))
    parsed = urlparse(absolute)
    normalized = parsed._replace(query="", fragment="").geturl()
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in HTML_SUFFIXES or not is_allowed_help_url(normalized, allowed_prefix):
        return None
    return normalized


def extract_scoped_links(xhtml: str, base_url: str, allowed_prefix: str) -> list[str]:
    soup = BeautifulSoup(xhtml, _parser_for(xhtml))
    links = {
        normalized
        for anchor in soup.find_all("a", href=True)
        if (normalized := normalize_help_url(anchor["href"], base_url, allowed_prefix))
    }
    return sorted(links)


class XhtmlCrawler:
    """Polite, same-scope crawler with conditional requests and a local cache."""

    def __init__(
        self,
        start_url: str,
        allowed_prefix: str,
        cache_dir: Path,
        delay_seconds: float = 0.25,
        timeout_seconds: float = 30,
        client: httpx.Client | None = None,
    ) -> None:
        if not is_allowed_help_url(start_url, allowed_prefix):
            raise ValueError("Start URL must be inside the configured crawl boundary")
        self.start_url = start_url
        self.allowed_prefix = allowed_prefix
        self.cache_dir = cache_dir
        self.delay_seconds = max(delay_seconds, 0)
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/xhtml+xml,text/html"},
            verify=ssl.create_default_context(),
        )
        self.pages_dir = cache_dir / "pages"
        self.manifest_path = cache_dir / "manifest.json"
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    def crawl(self, max_pages: int | None = None) -> list[XhtmlDocument]:
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages must be positive")

        previous = self._read_manifest()
        queue = deque([self.start_url])
        queued = {self.start_url}
        visited: set[str] = set()
        documents: list[XhtmlDocument] = []

        try:
            while queue and (max_pages is None or len(visited) < max_pages):
                url = queue.popleft()
                visited.add(url)
                prior = previous.get(url, {})
                document, xhtml = self._fetch(url, prior)
                if document is None or xhtml is None:
                    continue
                documents.append(document)
                for link in extract_scoped_links(xhtml, url, self.allowed_prefix):
                    if link not in visited and link not in queued:
                        queue.append(link)
                        queued.add(link)
                if self.delay_seconds:
                    time.sleep(self.delay_seconds)
        finally:
            if self._owns_client:
                self.client.close()

        self._write_manifest(documents)
        return documents

    def _fetch(
        self,
        url: str,
        prior: dict[str, object],
    ) -> tuple[XhtmlDocument | None, str | None]:
        headers: dict[str, str] = {}
        if etag := prior.get("etag"):
            headers["If-None-Match"] = str(etag)
        if last_modified := prior.get("last_modified"):
            headers["If-Modified-Since"] = str(last_modified)

        response = self.client.get(url, headers=headers)
        if response.status_code == 304:
            cached_path = self.cache_dir / str(prior["cache_path"])
            if cached_path.is_file():
                xhtml = cached_path.read_text(encoding="utf-8")
                return XhtmlDocument(**prior), xhtml
            response = self.client.get(url)

        response.raise_for_status()
        final_url = normalize_help_url(str(response.url), url, self.allowed_prefix)
        if final_url is None:
            return None, None
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type and "xhtml" not in content_type:
            return None, None

        xhtml = response.text
        digest = hashlib.sha256(response.content).hexdigest()
        relative_path = Path("pages") / f"{hashlib.sha256(final_url.encode()).hexdigest()}.xhtml"
        cache_path = self.cache_dir / relative_path
        cache_path.write_text(xhtml, encoding="utf-8")
        fetched_at = response.headers.get("date", "")
        document = XhtmlDocument(
            url=final_url,
            cache_path=relative_path.as_posix(),
            content_sha256=digest,
            fetched_at=fetched_at,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
        return document, xhtml

    def _read_manifest(self) -> dict[str, dict[str, object]]:
        if not self.manifest_path.is_file():
            return {}
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return {page["url"]: page for page in data.get("pages", [])}

    def _write_manifest(self, documents: list[XhtmlDocument]) -> None:
        payload = {
            "start_url": self.start_url,
            "allowed_prefix": self.allowed_prefix,
            "pages": [asdict(document) for document in documents],
        }
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.manifest_path)


def _parser_for(content: str) -> str:
    return "lxml-xml" if content.lstrip().startswith("<?xml") else "lxml"
