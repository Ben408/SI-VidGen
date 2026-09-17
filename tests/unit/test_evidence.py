"""Evidence selection without Graph pack_concept_ids."""

from __future__ import annotations

from config.settings import Settings
from src.models import Classification, RetrievedChunk
from src.qa.evidence import (
    DEFAULT_MAX_PAGES,
    RankedChunk,
    _boost_chunk,
    retrieve_and_select_evidence,
    scope_refuse_reason,
    select_coherent_pages,
    usable_classifier_query,
)
from tests.fakes import FakePipelineLLM, FakeVectorStore


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


def test_scope_gate_does_not_refuse_on_classifier_confidence() -> None:
    classification = Classification(
        feature="Unknown",
        intent="unclear",
        task_type="unknown",
        help_topics=["help"],
        search_query="weather forecast",
        confidence=0.1,
        model="fake",
    )
    assert scope_refuse_reason("How do I reverse an AP payment?", classification) is None
    assert usable_classifier_query("How do I reverse an AP payment?", classification) == ""


def test_skips_followups_when_original_question_covers_goal() -> None:
    planned: list[int] = []

    def plan_followups(*_args, **_kwargs) -> list[str]:
        planned.append(1)
        return ["should not run"]

    selected, follow_ups = retrieve_and_select_evidence(
        FakePipelineLLM(),
        FakeVectorStore(),
        None,
        Settings(),
        question="How do I correct an unbalanced journal entry?",
        classification_query="unrelated classifier rewrite",
        help_language="en_US",
        plan_followups=plan_followups,
    )
    assert selected
    assert follow_ups == []
    assert planned == []


class _SequencedStore:
    def __init__(self) -> None:
        self.calls = 0

    def query(self, embedding, top_k=5, where=None):
        del embedding, top_k, where
        self.calls += 1
        if self.calls == 1:
            title = "Configure tax schedule"
            source_id = "tax-1"
            body = f"{title}. Set the tax rate and save the schedule. " * 8
        else:
            title = "Reverse an AP payment"
            source_id = "ap-1"
            body = f"{title}. Open the payment. Click Reverse. " * 8
        return [
            {
                "id": source_id,
                "document": body,
                "metadata": {
                    "source_url": (
                        f"https://www.intacct.com/ia/docs/en_US/help_action/{source_id}.htm"
                    ),
                    "title": title,
                    "heading_path": title,
                    "asset_urls": "",
                    "language": "en_US",
                },
                "distance": 0.1,
                "score": 0.9,
            }
        ]


def test_followups_run_only_after_original_misses() -> None:
    planned: list[list[str]] = []

    def plan_followups(*_args, **_kwargs) -> list[str]:
        planned.append(["Reverse an AP payment"])
        return planned[-1]

    selected, follow_ups = retrieve_and_select_evidence(
        FakePipelineLLM(),
        _SequencedStore(),
        None,
        Settings(),
        question="How do I reverse an AP payment?",
        classification_query="",
        help_language="en_US",
        plan_followups=plan_followups,
    )
    assert planned
    assert follow_ups == ["Reverse an AP payment"]
    assert selected
    assert selected[0].title == "Reverse an AP payment"
