"""Evidence selection without Graph pack_concept_ids."""

from __future__ import annotations

from src.models import RetrievedChunk
from src.qa.evidence import DEFAULT_MAX_PAGES, _boost_chunk, select_coherent_pages
from src.qa.evidence import RankedChunk


def _chunk(source_id: str, title: str, score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(
        source_id=source_id,
        source_url=f"https://www.intacct.com/ia/docs/en_US/help_action/{source_id}.htm",
        title=title,
        heading_path=title,
        score=score,
        text="Click Save. " * 20,
        asset_urls=[],
    )


def test_boost_chunk_has_no_pack_concept_attribute() -> None:
    chunk = _chunk("Taxes/a", "Configure tax schedule")
    assert not hasattr(chunk, "pack_concept_ids") or getattr(chunk, "pack_concept_ids", None) in (
        None,
        [],
    )
    ranked = RankedChunk(chunk=chunk, rrf=1.0, provenance={"original"}, boost=0.0)
    boost = _boost_chunk("configure tax schedule", ranked)
    assert isinstance(boost, float)


def test_select_coherent_pages_caps_at_max_pages() -> None:
    fused = {
        f"id{i}": RankedChunk(
            chunk=_chunk(f"Mod/page{i}", f"Topic {i}", score=1.0 - i * 0.01),
            rrf=1.0 - i * 0.01,
            provenance={"original"},
            boost=0.0,
        )
        for i in range(8)
    }
    selected = select_coherent_pages("Topic help", fused, max_pages=DEFAULT_MAX_PAGES)
    pages = {c.source_url for c in selected}
    assert len(pages) <= DEFAULT_MAX_PAGES
