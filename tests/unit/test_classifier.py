from src.classifier.classify_issue import classify_issue
from src.models import NormalizedIssue
from tests.fakes import FakePipelineLLM


def test_classifier_uses_issue_and_context_without_inventing_model_metadata() -> None:
    llm = FakePipelineLLM()
    issue = NormalizedIssue(
        issue_id="issue-1",
        raw_text="My journal will not post because it is unbalanced",
        context={"module": "General Ledger", "screen": None, "error_code": None},
    )

    classification = classify_issue(issue, llm)

    assert classification.feature == "General Ledger"
    assert classification.search_query == "correct unbalanced General Ledger journal entry"
    assert classification.model == "fake-local-model"
    assert "My journal will not post" in llm.prompts[0][1]
    assert '"module": "General Ledger"' in llm.prompts[0][1]
