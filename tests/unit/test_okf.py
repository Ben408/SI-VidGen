"""Unit tests for rules-only OKF conversion and enrichment."""

from __future__ import annotations

import json
from pathlib import Path

from src.models import RetrievedChunk
from src.rag.okf.convert import convert_xhtml_document
from src.rag.okf.enrich import enrich_retrieved_with_okf, related_concepts_for_sources
from src.rag.okf.format import load_concept
from src.rag.okf.store import OkfStore

FIXTURE = Path("data/help_fixtures/gl_posting_error.xhtml")
PAGE_URL = (
    "https://www.intacct.com/ia/docs/en_US/help_action/"
    "General_Ledger/gl_posting_error.htm"
)


def _write_catalog_from_files(bundle: Path) -> None:
    concepts = []
    for path in bundle.rglob("*.md"):
        if path.name == "index.md":
            continue
        rel = path.relative_to(bundle).as_posix()
        concept_id = rel.removesuffix(".md")
        meta, _body = load_concept(path.read_text(encoding="utf-8"))
        concepts.append(
            {
                "concept_id": concept_id,
                "type": meta.get("type"),
                "title": meta.get("title"),
                "page_url": meta.get("page_url") or "",
                "path": rel,
                "heading_path": meta.get("heading_path") or "",
                "asset_urls": meta.get("asset_urls") or [],
                "source_url": meta.get("source_url"),
                "usable_for_video": meta.get("usable_for_video"),
            }
        )
    (bundle / "catalog.json").write_text(
        json.dumps({"concepts": concepts, "pages_converted": 1, "counts": {}}),
        encoding="utf-8",
    )


def test_convert_fixture_writes_topic_procedure_and_asset(tmp_path: Path) -> None:
    catalog = convert_xhtml_document(
        FIXTURE.read_text(encoding="utf-8"),
        source_url=PAGE_URL,
        source_hash="fixture-hash",
        okf_dir=tmp_path,
    )
    types = {row["type"] for row in catalog}
    assert "HelpTopic" in types
    assert "Procedure" in types
    assert "HelpAsset" in types

    topic = next(row for row in catalog if row["type"] == "HelpTopic")
    text = (tmp_path / topic["path"]).read_text(encoding="utf-8")
    assert PAGE_URL in text

    asset = next(row for row in catalog if row["type"] == "HelpAsset")
    asset_text = (tmp_path / asset["path"]).read_text(encoding="utf-8")
    assert "not copied into OKF" in asset_text
    assert "data/help_assets" in asset_text


def test_enrich_scopes_assets_and_prefers_procedure_body(tmp_path: Path) -> None:
    convert_xhtml_document(
        FIXTURE.read_text(encoding="utf-8"),
        source_url=PAGE_URL,
        source_hash="fixture-hash",
        okf_dir=tmp_path,
    )
    _write_catalog_from_files(tmp_path)

    store = OkfStore(tmp_path)
    chunk = RetrievedChunk(
        source_id="abc",
        source_url=PAGE_URL,
        title="Correct an unbalanced journal entry",
        heading_path="Correct an unbalanced journal entry > Correct the entry",
        score=0.9,
        text="original chunk text",
        asset_urls=[
            "https://www.intacct.com/ia/docs/en_US/help_action/images/other.png",
        ],
    )
    enriched = enrich_retrieved_with_okf([chunk], store)[0]
    assert enriched.text != "original chunk text"
    assert "Compare total debits" in enriched.text or "Open the journal" in enriched.text
    assert any("gl-journal-entry.png" in url for url in enriched.asset_urls)

    related = related_concepts_for_sources([chunk], store)
    assert related
    assert all(item["type"] != "HelpTopic" for item in related)


def test_enrich_noop_without_bundle() -> None:
    chunk = RetrievedChunk(
        source_id="abc",
        source_url=PAGE_URL,
        title="t",
        heading_path="h",
        score=0.5,
        text="keep",
        asset_urls=["https://example/a.png"],
    )
    assert enrich_retrieved_with_okf([chunk], None)[0].text == "keep"
