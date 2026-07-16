from uuid import uuid4

from src.models import IssueInput, NormalizedIssue


def normalize_issue(issue: IssueInput) -> NormalizedIssue:
    return NormalizedIssue(
        issue_id=f"issue-{uuid4()}",
        raw_text=issue.text.strip(),
        context={
            "module": issue.module,
            "screen": issue.screen,
            "error_code": issue.error_code,
        },
    )
