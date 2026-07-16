from src.models import Classification, NormalizedIssue, Scene, Script


def build_script(issue: NormalizedIssue, classification: Classification) -> Script:
    """Phase 0 placeholder proving the artifact and UI flow."""
    feature = classification.feature
    return Script(
        title=f"Support guidance for {feature}",
        narration=(
            f"This draft explains how to address the reported {feature} issue. "
            "Retrieved Intacct Help steps will replace this placeholder in Phase 4."
        ),
        scenes=[
            Scene(
                action=f"Open the relevant {feature} area",
                visual=(
                    "Use an existing Intacct Help Center asset when available; "
                    "otherwise identify the UI element textually."
                ),
                voiceover=f"Start by opening the relevant {feature} area.",
            )
        ],
    )
