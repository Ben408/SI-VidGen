"""Ask answer grounding should not flap on hash citations or coverage flags."""

from src.models import RetrievedChunk
from src.qa.ask_agent import _draft_to_answer, resolve_cited_source_id


HASH_ID = "8a028f10f549fa7ae07dfa0379beb322bd61427530556fc8dab86223364275f1"


class _DraftLLM:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def generate_structured(self, _system, _user, response_model):
        return response_model.model_validate(self.payload), "fake-local-model"


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        source_id=HASH_ID,
        source_url="https://www.intacct.com/ia/docs/en_US/help_action/gl.htm",
        title="Correct an unbalanced journal entry",
        heading_path="Correct the entry",
        score=0.9,
        text="Open the journal entry. Compare total debits and total credits.",
        asset_urls=[],
    )


def test_resolve_cited_source_id_accepts_alias_and_prefix() -> None:
    alias_to_id = {"src-1": HASH_ID, HASH_ID: HASH_ID, HASH_ID.lower(): HASH_ID}
    allowed = {HASH_ID}
    assert (
        resolve_cited_source_id("src-1", alias_to_id=alias_to_id, allowed_ids=allowed)
        == HASH_ID
    )
    assert (
        resolve_cited_source_id(HASH_ID[:12], alias_to_id=alias_to_id, allowed_ids=allowed)
        == HASH_ID
    )


def test_draft_keeps_grounded_steps_when_coverage_flag_is_false() -> None:
    llm = _DraftLLM(
        {
            "summary": "Correct unbalanced journal totals before posting.",
            "steps": [
                {
                    "instruction": "Open the journal entry.",
                    "detail": "Compare total debits and total credits.",
                    "source_ids": ["src-1"],
                }
            ],
            "notes": [],
            "coverage_sufficient": False,
            "coverage_gap": "Model felt unsure",
        }
    )
    answer, gap = _draft_to_answer(
        llm,
        question="How do I correct an unbalanced journal entry?",
        grounded=[_chunk()],
    )
    assert gap is None
    assert answer is not None
    assert answer.steps[0].source_ids == [HASH_ID]


def test_draft_maps_truncated_hash_citations() -> None:
    llm = _DraftLLM(
        {
            "summary": "Correct unbalanced journal totals before posting.",
            "steps": [
                {
                    "instruction": "Open the journal entry.",
                    "detail": "",
                    "source_ids": [HASH_ID[:16]],
                }
            ],
            "notes": [],
            "coverage_sufficient": True,
            "coverage_gap": "",
        }
    )
    answer, gap = _draft_to_answer(
        llm,
        question="How do I correct an unbalanced journal entry?",
        grounded=[_chunk()],
    )
    assert gap is None
    assert answer is not None
    assert answer.steps[0].source_ids == [HASH_ID]
