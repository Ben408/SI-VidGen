import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

CONTENT_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd", "th", "td"}
NOISE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    ".mc-breadcrumbs",
    ".menu",
    ".search-bar",
)


@dataclass(frozen=True)
class HelpChunk:
    chunk_id: str
    text: str
    source_url: str
    source_hash: str
    title: str
    heading_path: str
    asset_urls: tuple[str, ...]
    token_estimate: int

    def metadata(self) -> dict[str, str | int]:
        return {
            "source_url": self.source_url,
            "source_hash": self.source_hash,
            "title": self.title,
            "heading_path": self.heading_path,
            "asset_urls": "|".join(self.asset_urls),
            "token_estimate": self.token_estimate,
        }


def estimate_tokens(text: str) -> int:
    """Conservative tokenizer-independent estimate suitable for chunk sizing."""
    return max(1, (len(text) + 3) // 4)


def chunk_xhtml(
    xhtml: str,
    source_url: str,
    source_hash: str,
    target_tokens: int = 768,
    max_tokens: int = 1024,
) -> list[HelpChunk]:
    if not 0 < target_tokens <= max_tokens:
        raise ValueError("target_tokens must be positive and no greater than max_tokens")

    parser = "lxml-xml" if xhtml.lstrip().startswith("<?xml") else "lxml"
    soup = BeautifulSoup(xhtml, parser)
    for selector in NOISE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()

    title = _page_title(soup)
    assets = _asset_urls(soup, source_url)
    blocks = _content_blocks(soup)
    chunks: list[HelpChunk] = []
    current_parts: list[str] = []
    current_headings: list[str] = []
    active_headings: list[str] = []

    def flush() -> None:
        if not current_parts:
            return
        text = "\n\n".join(current_parts).strip()
        heading_path = " > ".join(current_headings or active_headings)
        identity = f"{source_url}\n{heading_path}\n{text}".encode()
        chunks.append(
            HelpChunk(
                chunk_id=hashlib.sha256(identity).hexdigest(),
                text=text,
                source_url=source_url,
                source_hash=source_hash,
                title=title,
                heading_path=heading_path,
                asset_urls=assets,
                token_estimate=estimate_tokens(text),
            )
        )
        current_parts.clear()
        current_headings.clear()

    for tag_name, text in blocks:
        if tag_name.startswith("h"):
            level = int(tag_name[1])
            active_headings[:] = active_headings[: level - 1]
            active_headings.append(text)
        pieces = _split_oversized_text(text, max_tokens)
        for piece in pieces:
            proposed = "\n\n".join([*current_parts, piece])
            if current_parts and estimate_tokens(proposed) > target_tokens:
                flush()
            if not current_parts:
                current_headings.extend(active_headings)
            current_parts.append(piece)
            if estimate_tokens("\n\n".join(current_parts)) >= max_tokens:
                flush()
    flush()
    return chunks


def chunk_cached_document(
    cache_root: Path,
    cache_path: str,
    source_url: str,
    source_hash: str,
) -> list[HelpChunk]:
    xhtml = (cache_root / cache_path).read_text(encoding="utf-8")
    return chunk_xhtml(xhtml, source_url, source_hash)


def _page_title(soup: BeautifulSoup) -> str:
    if heading := soup.find("h1"):
        return " ".join(heading.stripped_strings)
    if soup.title:
        return " ".join(soup.title.stripped_strings)
    return "Untitled help topic"


def _asset_urls(soup: BeautifulSoup, source_url: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                urljoin(source_url, str(image["src"]))
                for image in soup.find_all("img", src=True)
                if not str(image["src"]).startswith("data:")
            }
        )
    )


def _content_blocks(soup: BeautifulSoup) -> list[tuple[str, str]]:
    root = soup.find("main") or soup.find("article") or soup.body or soup
    blocks: list[tuple[str, str]] = []
    for element in root.find_all(CONTENT_TAGS):
        if not isinstance(element, Tag) or element.find_parent(CONTENT_TAGS):
            continue
        text = re.sub(r"\s+", " ", " ".join(element.stripped_strings)).strip()
        if text:
            prefix = "- " if element.name == "li" else ""
            blocks.append((element.name, f"{prefix}{text}"))
    return blocks


def _split_oversized_text(text: str, max_tokens: int) -> list[str]:
    if estimate_tokens(text) <= max_tokens:
        return [text]
    max_characters = max_tokens * 4
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_characters:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(
                sentence[index : index + max_characters]
                for index in range(0, len(sentence), max_characters)
            )
        elif current and len(current) + len(sentence) + 1 > max_characters:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces
