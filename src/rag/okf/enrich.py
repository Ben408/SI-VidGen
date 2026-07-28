"""Enrich retrieved Help chunks using OKF section assets and procedure bodies."""

from __future__ import annotations

from src.models import RetrievedChunk, SourceReference
from src.rag.okf.store import OkfStore


def enrich_retrieved_with_okf(
    retrieved: list[RetrievedChunk],
    store: OkfStore | None,
) -> list[RetrievedChunk]:
    """Prefer section-scoped screenshots and procedure-shaped text when OKF exists."""
    if store is None or not store.available or not retrieved:
        return retrieved

    enriched: list[RetrievedChunk] = []
    for chunk in retrieved:
        updates: dict[str, object] = {}
        procedure = store.best_procedure(chunk.source_url, chunk.heading_path)
        section_urls = store.section_asset_urls(chunk.source_url, chunk.heading_path)
        if section_urls:
            # Prefer section-scoped OKF assets; library filter runs after this step.
            updates["asset_urls"] = section_urls
        if (
            procedure is not None
            and procedure.body.strip()
            and procedure.type in {"Procedure", "UIScreen", "HelpSection"}
        ):
            # Prefer procedure body for script outline fidelity; keep live Help URL.
            updates["text"] = procedure.body.strip()
            if procedure.heading_path:
                updates["heading_path"] = procedure.heading_path
        enriched.append(chunk.model_copy(update=updates) if updates else chunk)
    return enriched


def related_concepts_for_sources(
    sources: list[SourceReference],
    store: OkfStore | None,
    *,
    limit_per_source: int = 6,
) -> list[dict[str, object]]:
    """Derived OKF concepts for operator browse (not discrete Help pages)."""
    if store is None or not store.available:
        return []
    seen: set[str] = set()
    related: list[dict[str, object]] = []
    for source in sources:
        page_concepts = store.concepts_for_page(source.source_url)
        ranked = sorted(
            page_concepts,
            key=lambda item: (
                0 if item.get("type") == "Procedure" else 1,
                0 if item.get("type") == "UIScreen" else 1,
                0 if item.get("type") == "HelpSection" else 1,
                0 if item.get("type") == "HelpAsset" else 1,
                str(item.get("title") or ""),
            ),
        )
        # Skip HelpTopic itself — operators already have the live Help href.
        count = 0
        for item in ranked:
            if item.get("type") == "HelpTopic":
                continue
            concept_id = str(item.get("concept_id") or "")
            if not concept_id or concept_id in seen:
                continue
            seen.add(concept_id)
            related.append(
                {
                    "concept_id": concept_id,
                    "type": item.get("type"),
                    "title": item.get("title"),
                    "page_url": item.get("page_url") or source.source_url,
                    "heading_path": item.get("heading_path") or "",
                    "path": item.get("path"),
                    "source_id": source.source_id,
                    "help_title": source.title,
                }
            )
            count += 1
            if count >= limit_per_source:
                break
    return related
