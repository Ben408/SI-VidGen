"""Read and query an OKF bundle on disk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.rag.okf.format import load_concept


@dataclass(frozen=True)
class OkfConcept:
    concept_id: str
    type: str
    title: str
    path: str
    page_url: str = ""
    heading_path: str = ""
    body: str = ""
    frontmatter: dict[str, Any] | None = None

    def summary(self) -> dict[str, Any]:
        meta = self.frontmatter or {}
        return {
            "concept_id": self.concept_id,
            "type": self.type,
            "title": self.title,
            "path": self.path,
            "page_url": self.page_url or str(meta.get("page_url") or ""),
            "heading_path": self.heading_path or str(meta.get("heading_path") or ""),
            "asset_urls": list(meta.get("asset_urls") or []),
            "asset_ids": list(meta.get("asset_ids") or []),
            "usable_for_video": meta.get("usable_for_video"),
            "source_url": meta.get("source_url"),
            "parent_topic": meta.get("parent_topic"),
            "module": meta.get("module"),
        }


class OkfStore:
    def __init__(self, bundle_dir: Path) -> None:
        self.bundle_dir = bundle_dir
        self.catalog_path = bundle_dir / "catalog.json"
        self._by_id: dict[str, dict[str, Any]] = {}
        self._by_page: dict[str, list[dict[str, Any]]] = {}
        if self.catalog_path.is_file():
            self._load_catalog()

    @property
    def available(self) -> bool:
        return self.catalog_path.is_file()

    def _load_catalog(self) -> None:
        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        for item in payload.get("concepts", []):
            concept_id = str(item.get("concept_id") or "")
            if not concept_id:
                continue
            self._by_id[concept_id] = item
            page_url = str(item.get("page_url") or "")
            if page_url:
                self._by_page.setdefault(page_url, []).append(item)

    def status(self) -> dict[str, Any]:
        if not self.available:
            return {
                "available": False,
                "bundle_dir": str(self.bundle_dir),
                "message": "OKF bundle not built yet. Run: python -m src.rag.build_okf",
            }
        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        return {
            "available": True,
            "bundle_dir": str(self.bundle_dir),
            "pages_converted": payload.get("pages_converted", 0),
            "counts": payload.get("counts", {}),
            "concept_count": len(self._by_id),
        }

    def list_concepts(
        self,
        *,
        concept_type: str | None = None,
        page_url: str | None = None,
        query: str | None = None,
        derived_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        items = list(self._by_id.values())
        if concept_type:
            items = [item for item in items if item.get("type") == concept_type]
        if page_url:
            items = [item for item in items if item.get("page_url") == page_url]
        if derived_only:
            items = [
                item
                for item in items
                if item.get("type") in {"Procedure", "UIScreen", "HelpSection", "HelpAsset"}
            ]
        if query:
            needle = query.lower()
            items = [
                item
                for item in items
                if needle in str(item.get("title") or "").lower()
                or needle in str(item.get("concept_id") or "").lower()
                or needle in str(item.get("heading_path") or "").lower()
            ]
        items.sort(key=lambda item: (str(item.get("type") or ""), str(item.get("title") or "")))
        return items[offset : offset + max(0, limit)]

    def get_concept(self, concept_id: str) -> OkfConcept | None:
        row = self._by_id.get(concept_id)
        if row is None:
            # Allow ids with or without leading path quirks.
            normalized = concept_id.lstrip("/")
            row = self._by_id.get(normalized)
        if row is None:
            return None
        rel = str(row.get("path") or f"{concept_id}.md")
        path = self.bundle_dir / rel
        if not path.is_file():
            return OkfConcept(
                concept_id=str(row.get("concept_id") or concept_id),
                type=str(row.get("type") or "Unknown"),
                title=str(row.get("title") or concept_id),
                path=rel,
                page_url=str(row.get("page_url") or ""),
                heading_path=str(row.get("heading_path") or ""),
                body="",
                frontmatter=dict(row),
            )
        meta, body = load_concept(path.read_text(encoding="utf-8"))
        return OkfConcept(
            concept_id=str(row.get("concept_id") or concept_id),
            type=str(meta.get("type") or row.get("type") or "Unknown"),
            title=str(meta.get("title") or row.get("title") or concept_id),
            path=rel,
            page_url=str(meta.get("page_url") or row.get("page_url") or ""),
            heading_path=str(meta.get("heading_path") or row.get("heading_path") or ""),
            body=body,
            frontmatter=meta,
        )

    def concepts_for_page(self, page_url: str) -> list[dict[str, Any]]:
        return list(self._by_page.get(page_url, []))

    def best_procedure(
        self,
        page_url: str,
        heading_path: str,
    ) -> OkfConcept | None:
        candidates = [
            item
            for item in self._by_page.get(page_url, [])
            if item.get("type") in {"Procedure", "UIScreen", "HelpSection"}
        ]
        if not candidates:
            return None
        scored: list[tuple[int, dict[str, Any]]] = []
        for item in candidates:
            score = _heading_score(heading_path, str(item.get("heading_path") or ""))
            scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("title") or "")))
        best_score, best = scored[0]
        if best_score <= 0 and heading_path:
            # Fall back to first procedure on the page when headings do not overlap.
            procedures = [item for item in candidates if item.get("type") == "Procedure"]
            best = procedures[0] if procedures else best
        return self.get_concept(str(best["concept_id"]))

    def section_asset_urls(self, page_url: str, heading_path: str) -> list[str]:
        concept = self.best_procedure(page_url, heading_path)
        if concept is None or not concept.frontmatter:
            # Page-level usable assets from HelpAsset concepts on this page.
            urls: list[str] = []
            for item in self._by_page.get(page_url, []):
                if item.get("type") != "HelpAsset":
                    continue
                if item.get("usable_for_video") is False:
                    continue
                url = item.get("source_url")
                if isinstance(url, str) and url:
                    urls.append(url)
            return urls
        urls = list(concept.frontmatter.get("asset_urls") or [])
        return [url for url in urls if isinstance(url, str) and url]


def _heading_score(left: str, right: str) -> int:
    if not left or not right:
        return 0
    a = left.lower().strip()
    b = right.lower().strip()
    if a == b:
        return 100
    if a in b or b in a:
        return 80
    left_parts = {part.strip() for part in a.split(">") if part.strip()}
    right_parts = {part.strip() for part in b.split(">") if part.strip()}
    overlap = left_parts & right_parts
    if overlap:
        return 40 + 10 * len(overlap)
    # Token overlap
    left_tokens = set(a.replace(">", " ").split())
    right_tokens = set(b.replace(">", " ").split())
    shared = left_tokens & right_tokens
    return len(shared)
