"""Per-tenant Help corpus path layout (Slack ``corpus_id`` contract).

Default (no ``corpus_id``) keeps the legacy roots under ``data/``.
Named corpora live under ``data/corpora/{corpus_id}/`` so one SI-VidGen
process can isolate Ask/script/video retrieval per Slack tenant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings

_CORPUS_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def normalize_corpus_id(raw: str | None) -> str | None:
    """Return a safe corpus id, or ``None`` for the default (legacy) corpus."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if not _CORPUS_ID_RE.fullmatch(text):
        raise ValueError(
            "corpus_id must be 1–64 chars: start with alphanumeric, then "
            "letters, digits, '.', '_' or '-' (no path separators)."
        )
    return text


@dataclass(frozen=True)
class CorpusPaths:
    corpus_id: str | None
    help_cache_dir: Path
    help_assets_dir: Path
    okf_dir: Path
    vector_store_dir: Path

    def ensure(self) -> None:
        for path in (
            self.help_cache_dir,
            self.help_assets_dir,
            self.help_assets_dir / "files",
            self.okf_dir,
            self.vector_store_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


def resolve_corpus_paths(
    settings: Settings,
    corpus_id: str | None = None,
) -> CorpusPaths:
    """Map optional ``corpus_id`` to on-disk Help / Chroma / OKF roots."""
    cid = normalize_corpus_id(corpus_id)
    if cid is None:
        return CorpusPaths(
            corpus_id=None,
            help_cache_dir=settings.help_cache_dir,
            help_assets_dir=settings.help_assets_dir,
            okf_dir=settings.okf_dir,
            vector_store_dir=settings.vector_store_dir,
        )
    root = settings.data_dir / "corpora" / cid
    return CorpusPaths(
        corpus_id=cid,
        help_cache_dir=root / "help_xhtml",
        help_assets_dir=root / "help_assets",
        okf_dir=root / "okf",
        vector_store_dir=root / "vector_store",
    )
