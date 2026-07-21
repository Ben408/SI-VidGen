from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IssueInput(BaseModel):
    text: str = Field(min_length=3, max_length=20_000)
    module: str | None = Field(default=None, max_length=100)
    screen: str | None = Field(default=None, max_length=200)
    error_code: str | None = Field(default=None, max_length=100)
    auto_generate: bool = False


class NormalizedIssue(BaseModel):
    issue_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_text: str = Field(exclude=True)
    context: dict[str, str | None]


class Classification(BaseModel):
    feature: str
    intent: str
    task_type: str
    error_type: str | None = None
    help_topics: list[str] = Field(default_factory=list)
    search_query: str
    confidence: float = Field(ge=0, le=1)
    model: str


class Scene(BaseModel):
    action: str
    visual: str
    voiceover: str
    help_asset: str | None = None
    source_ids: list[str] = Field(min_length=1)


class SourceReference(BaseModel):
    source_id: str
    source_url: str
    title: str
    heading_path: str
    score: float


class RetrievedChunk(SourceReference):
    text: str
    asset_urls: list[str] = Field(default_factory=list)


class Script(BaseModel):
    title: str
    narration: str
    scenes: list[Scene]
    sources: list[SourceReference]
    generation_model: str


class ScriptEdit(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    narration: str = Field(min_length=1, max_length=5_000)
    scenes: list[Scene] = Field(min_length=1, max_length=20)


class ReviewAction(BaseModel):
    generate_video: bool = False
    # Local compositor options (ignored by Higgsfield backend).
    tts_voice: str | None = None
    tts_rate: str | None = None
    captions: bool | None = None


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
    tts_voice: str | None = None
    tts_rate: str | None = None
    thumbnail: str = "auto"
    medias: list[str] = Field(default_factory=list)
    preserve_source_visuals: bool = True
    visual_coverage: Literal["green", "yellow", "red"] = "red"
    explainer_package_path: str | None = None


class HiggsfieldExplainerPackage(BaseModel):
    """Input package shaped for Higgsfield video_explainer CLI / MCP."""

    job_set_type: Literal["video_explainer"] = "video_explainer"
    prompt: str
    medias: list[str] = Field(default_factory=list, max_length=14)
    duration: int = Field(ge=20, le=600)
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"
    preserve_source_visuals: bool = True
    instruction: str = (
        "Use the attached Sage Intacct Help screenshots as authoritative product UI. "
        "Do not restyle, redraw, or invent alternate Intacct screens."
    )
    assets: list[dict[str, Any]] = Field(default_factory=list)
    medias_file: str | None = None
    cli_example: str | None = None


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
    explainer_package_path: str | None = None
    script_path: str | None = None
    script_version: int = 0
    review_status: Literal["not_ready", "draft", "approved"] = "not_ready"
    auto_generate: bool = False
    generation_status: Literal[
        "not_requested",
        "pending",
        "submitted",
        "ready",
        "failed",
        "unavailable",
    ] = "not_requested"
    generation_id: str | None = None
    generation_job_ids: list[str] | None = None
    video_path: str | None = None
    video_url: str | None = None
    classification: Classification | None = None
    sources: list[SourceReference] = Field(default_factory=list)
    visual_coverage: Literal["green", "yellow", "red"] = "red"
    media_count: int = 0
    error_code: str | None = None
    error_detail: str | None = None
