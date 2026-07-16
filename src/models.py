from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IssueInput(BaseModel):
    text: str = Field(min_length=3, max_length=20_000)
    module: str | None = Field(default=None, max_length=100)
    screen: str | None = Field(default=None, max_length=200)
    error_code: str | None = Field(default=None, max_length=100)


class NormalizedIssue(BaseModel):
    issue_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_text: str = Field(exclude=True)
    context: dict[str, str | None]


class Classification(BaseModel):
    feature: str
    intent: str
    error_type: str | None = None
    help_topics: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    action: str
    visual: str
    voiceover: str
    help_asset: str | None = None


class Script(BaseModel):
    title: str
    narration: str
    scenes: list[Scene]


class HiggsfieldPayload(BaseModel):
    """Provisional V0 contract pending validation against the live API."""

    script: str
    scenes: list[Scene]
    voice: str = "professional_support"
    style: str = "clean_product_tutorial"
    brand: dict[str, Any] = Field(
        default_factory=lambda: {
            "colors": ["#005EB8", "#FFFFFF"],
            "logo_url": None,
        }
    )
    captions: bool = True
    thumbnail: str = "auto"


class ProgressEvent(BaseModel):
    run_id: str
    stage: str
    status: Literal["started", "completed", "failed"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int | None = None
    error_code: str | None = None


class RunResult(BaseModel):
    run_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    payload_path: str | None = None
    classification: Classification | None = None
    error_code: str | None = None
