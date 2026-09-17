"""Named Help corpus catalog: start URL + crawl prefix + corpus_id.

A catalog lets one SI-VidGen process ingest several Help sites. Named
``corpus_id`` rows overlay crawl URLs for ingest, refresh, and Ask URL
allowlisting. When ``corpus_id`` is omitted, the first catalog row is the
legacy default corpus (``data/`` roots).

File formats (same columns): ``start_url, allowed_prefix, corpus_id``

- CSV / comma-separated lines (``#`` comments; optional header)
- JSON Lines objects with those keys
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from config.settings import Settings
from src.rag.corpus_paths import normalize_corpus_id
from src.rag.xhtml_ingest import is_allowed_help_url

_HEADER_ALIASES = {
    "url": "start_url",
    "start_url": "start_url",
    "starturl": "start_url",
    "allowed_prefix": "allowed_prefix",
    "allowedprefix": "allowed_prefix",
    "prefix": "allowed_prefix",
    "corpus_id": "corpus_id",
    "corpusid": "corpus_id",
    "id": "corpus_id",
}


@dataclass(frozen=True)
class CorpusCatalogEntry:
    start_url: str
    allowed_prefix: str
    corpus_id: str


def catalog_path(settings: Settings) -> Path:
    return Path(settings.corpus_catalog_path)


def overlay_help_urls(settings: Settings, start_url: str, allowed_prefix: str) -> Settings:
    return settings.model_copy(
        update={
            "help_start_url": start_url,
            "help_allowed_prefix": allowed_prefix,
        }
    )


def help_settings_for_corpus(
    settings: Settings, corpus_id: str | None
) -> Settings:
    """Return settings whose Help URLs match the catalog row, if any."""
    cid = normalize_corpus_id(corpus_id)
    if cid is not None:
        entry = lookup_catalog_entry(settings, cid)
        if entry is not None:
            return overlay_help_urls(settings, entry.start_url, entry.allowed_prefix)
        if (settings.help_start_url or "").strip() and (
            settings.help_allowed_prefix or ""
        ).strip():
            return settings
        raise ValueError(
            f"corpus_id {cid!r} is not in catalog {catalog_path(settings)}"
        )
    if (settings.help_start_url or "").strip() and (
        settings.help_allowed_prefix or ""
    ).strip():
        return settings
    entries = load_catalog(catalog_path(settings), missing_ok=True)
    if entries:
        first = entries[0]
        return overlay_help_urls(settings, first.start_url, first.allowed_prefix)
    return settings


def lookup_catalog_entry(
    settings: Settings, corpus_id: str
) -> CorpusCatalogEntry | None:
    cid = normalize_corpus_id(corpus_id)
    if cid is None:
        return None
    for entry in load_catalog(catalog_path(settings), missing_ok=True):
        if entry.corpus_id == cid:
            return entry
    return None


def load_catalog(path: Path | str, *, missing_ok: bool = False) -> list[CorpusCatalogEntry]:
    target = Path(path)
    if not target.is_file():
        if missing_ok:
            return []
        raise FileNotFoundError(f"Corpus catalog not found: {target}")
    text = target.read_text(encoding="utf-8")
    return parse_catalog_text(text, source=str(target))


def parse_catalog_text(
    text: str, *, source: str = "<catalog>"
) -> list[CorpusCatalogEntry]:
    entries: list[CorpusCatalogEntry] = []
    seen: set[str] = set()
    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            if stripped.startswith("{"):
                parsed = _parse_jsonl_line(stripped)
            else:
                parsed = _parse_csv_line(stripped)
                if parsed is None:
                    continue
            entry = _validate_entry(parsed)
        except ValueError as error:
            raise ValueError(f"{source}:{line_no}: {error}") from error
        if entry.corpus_id in seen:
            raise ValueError(
                f"{source}:{line_no}: duplicate corpus_id {entry.corpus_id!r}"
            )
        seen.add(entry.corpus_id)
        entries.append(entry)
    return entries


def _parse_jsonl_line(line: str) -> dict[str, str]:
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise ValueError("JSON catalog line must be an object")
    mapped: dict[str, str] = {}
    for key, value in payload.items():
        alias = _HEADER_ALIASES.get(str(key).strip().lower())
        if alias is None:
            continue
        mapped[alias] = str(value).strip()
    return mapped


def _parse_csv_line(line: str) -> dict[str, str] | None:
    rows = list(csv.reader(StringIO(line), skipinitialspace=True))
    if not rows or not rows[0]:
        return None
    cells = [cell.strip() for cell in rows[0] if cell.strip()]
    if not cells:
        return None
    if len(cells) >= 3 and all(part.lower() in _HEADER_ALIASES for part in cells[:3]):
        return None
    if len(cells) < 3:
        raise ValueError(
            "expected start_url, allowed_prefix, corpus_id (3 columns)"
        )
    return {
        "start_url": cells[0],
        "allowed_prefix": cells[1],
        "corpus_id": cells[2],
    }


def _validate_entry(raw: dict[str, str]) -> CorpusCatalogEntry:
    start = (raw.get("start_url") or "").strip()
    prefix = (raw.get("allowed_prefix") or "").strip()
    corpus_raw = (raw.get("corpus_id") or "").strip()
    if not start or not prefix or not corpus_raw:
        raise ValueError("start_url, allowed_prefix, and corpus_id are required")
    corpus_id = normalize_corpus_id(corpus_raw)
    if corpus_id is None:
        raise ValueError("corpus_id is required")
    if not is_allowed_help_url(start, prefix):
        raise ValueError(
            f"start_url {start!r} is outside allowed_prefix {prefix!r}"
        )
    return CorpusCatalogEntry(
        start_url=start,
        allowed_prefix=prefix,
        corpus_id=corpus_id,
    )
