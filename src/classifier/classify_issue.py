from src.models import Classification, NormalizedIssue


def classify_issue(issue: NormalizedIssue) -> Classification:
    """Phase 0 deterministic placeholder; Phase 2 replaces this with Ollama."""
    module = issue.context.get("module") or "Unspecified"
    return Classification(
        feature=module,
        intent="Create support guidance",
        error_type=issue.context.get("error_code"),
        help_topics=[module.lower().replace(" ", "_")],
    )
