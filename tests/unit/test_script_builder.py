import pytest

from src.models import Classification, NormalizedIssue, RetrievedChunk
from src.scriptgen.script_builder import GroundingError, build_script
from tests.fakes import FakePipelineLLM


def classification() -> Classification:
    return Classification(
        feature="General Ledger",
        intent="Correct an unbalanced journal entry",
        task_type="Troubleshooting",
        error_type="Unbalanced journal",
        help_topics=["journal entries"],
        search_query="correct unbalanced General Ledger journal entry",
        confidence=0.93,
        model="fake-local-model",
    )


def source() -> RetrievedChunk:
    return RetrievedChunk(
        source_id="chunk-1",
        text="Compare total debits and total credits, then correct the affected line.",
        source_url="https://www.intacct.com/help/gl.htm",
        title="Correct an unbalanced journal entry",
        heading_path="Correct the entry",
        score=0.9,
        asset_urls=[],
    )


def issue() -> NormalizedIssue:
    return NormalizedIssue(
        issue_id="issue-1",
        raw_text="The journal will not post",
        context={"module": "General Ledger"},
    )


def test_builds_script_with_source_citations() -> None:
    script = build_script(issue(), classification(), [source()], FakePipelineLLM())

    assert script.scenes[0].source_ids == ["chunk-1"]
    assert script.sources[0].source_url.endswith("gl.htm")
    assert script.generation_model == "fake-local-model"


def test_rejects_unknown_source_citation() -> None:
    with pytest.raises(GroundingError, match="unknown sources"):
        build_script(
            issue(),
            classification(),
            [source()],
            FakePipelineLLM(invalid_source=True),
        )


def test_rejects_script_generation_without_sources() -> None:
    with pytest.raises(GroundingError, match="requires retrieved"):
        build_script(issue(), classification(), [], FakePipelineLLM())


def test_repairs_draft_that_ignores_top_retrieval_sources() -> None:
    sources = [
        source().model_copy(
            update={
                "source_id": f"chunk-{index}",
                "score": 1 - index / 10,
            }
        )
        for index in range(1, 5)
    ]

    class RepairingLLM:
        def __init__(self) -> None:
            self.calls = 0

        def generate_structured(self, _system, user, response_model):
            self.calls += 1
            cited_source = "chunk-4" if self.calls == 1 else "chunk-1"
            if self.calls == 2:
                assert "failed grounding review" in user
            return (
                response_model.model_validate(
                    {
                        "title": "Correct the journal",
                        "narration": "Review and correct the journal.",
                        "scenes": [
                            {
                                "action": "Review",
                                "visual": "Journal entry",
                                "voiceover": "Review the journal entry.",
                                "help_asset": "",
                                "source_ids": [cited_source],
                            }
                        ],
                    }
                ),
                "repairing-model",
            )

    llm = RepairingLLM()
    script = build_script(issue(), classification(), sources, llm)

    assert llm.calls == 2
    assert script.scenes[0].source_ids == ["chunk-1"]
