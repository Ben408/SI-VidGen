import json

from pydantic import BaseModel, Field

from src.llm.client import StructuredLLM
from src.models import (
    Classification,
    NormalizedIssue,
    RetrievedChunk,
    Scene,
    Script,
    SourceReference,
)

SYSTEM_PROMPT = """You are an information developer creating a Sage Intacct support video script.
Use only the supplied official-help excerpts. Do not add product steps or UI behavior that the
sources do not support. Every scene must cite one or more supplied source IDs.
Always leave help_asset as an empty string; the application attaches Help screenshots after
script generation. Describe visuals textually in the visual field.
The sources are ordered by retrieval relevance. Prioritize the first source and do not substitute
a related but different task. Create a concise, task-focused English script (3-6 scenes) that
directly resolves the stated issue. Return structured data only."""


class SceneDraft(BaseModel):
    action: str = Field(min_length=1, max_length=500)
    visual: str = Field(min_length=1, max_length=500)
    voiceover: str = Field(min_length=1, max_length=1_000)
    # Prefer empty string over null so Ollama grammar parsing stays reliable.
    help_asset: str = ""
    source_ids: list[str] = Field(min_length=1)


class ScriptDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    narration: str = Field(min_length=1, max_length=5_000)
    scenes: list[SceneDraft] = Field(min_length=1, max_length=8)


class GroundingError(RuntimeError):
    pass


def build_script(
    issue: NormalizedIssue,
    classification: Classification,
    retrieved: list[RetrievedChunk],
    llm: StructuredLLM,
) -> Script:
    if not retrieved:
        raise GroundingError("Script generation requires retrieved official-help content")
    grounded_sources = retrieved[:3]
    source_payload = [
        {
            "source_id": chunk.source_id,
            "title": chunk.title,
            "heading": chunk.heading_path,
            "text": _truncate_text(chunk.text, 1_800),
            "has_help_screenshots": bool(chunk.asset_urls),
        }
        for chunk in grounded_sources
    ]
    user_prompt = (
        f"Issue: {issue.raw_text}\n"
        f"Classification: {classification.model_dump_json(exclude={'model'})}\n"
        f"Official help sources:\n{json.dumps(source_payload, ensure_ascii=False)}"
    )
    grounding_error: GroundingError | None = None
    for attempt in range(2):
        repair = ""
        if attempt and grounding_error:
            repair = (
                "\nThe prior draft failed grounding review: "
                f"{grounding_error}. Regenerate the complete script. Every scene must use "
                "the highest-relevance sources and directly solve the stated issue. "
                "Leave help_asset empty."
            )
        draft, model = llm.generate_structured(
            SYSTEM_PROMPT,
            f"{user_prompt}{repair}",
            ScriptDraft,
        )
        draft = _sanitize_assets(draft, grounded_sources)
        try:
            _validate_grounding(draft, grounded_sources)
            break
        except GroundingError as error:
            grounding_error = error
    else:
        raise grounding_error or GroundingError("Script grounding validation failed")
    references = [
        SourceReference(
            source_id=chunk.source_id,
            source_url=chunk.source_url,
            title=chunk.title,
            heading_path=chunk.heading_path,
            score=chunk.score,
        )
        for chunk in grounded_sources
    ]
    scenes = [
        Scene(
            action=scene.action,
            visual=scene.visual,
            voiceover=scene.voiceover,
            help_asset=scene.help_asset or None,
            source_ids=scene.source_ids,
        )
        for scene in draft.scenes
    ]
    return Script(
        title=draft.title,
        narration=draft.narration,
        scenes=scenes,
        sources=references,
        generation_model=model,
    )


def _sanitize_assets(
    draft: ScriptDraft, retrieved: list[RetrievedChunk]
) -> ScriptDraft:
    """Drop invented/partial asset URLs; binder attaches real library files later."""
    valid_assets = {asset for chunk in retrieved for asset in chunk.asset_urls}
    cleaned = []
    for scene in draft.scenes:
        asset = scene.help_asset.strip() if scene.help_asset else ""
        if asset and asset not in valid_assets:
            asset = ""
        cleaned.append(scene.model_copy(update={"help_asset": asset}))
    return draft.model_copy(update={"scenes": cleaned})


def _truncate_text(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


def _validate_grounding(draft: ScriptDraft, retrieved: list[RetrievedChunk]) -> None:
    valid_ids = {chunk.source_id for chunk in retrieved}
    priority_ids = {chunk.source_id for chunk in retrieved[:3]}
    cited_ids: set[str] = set()
    for scene in draft.scenes:
        cited_ids.update(scene.source_ids)
        unknown_ids = set(scene.source_ids) - valid_ids
        if unknown_ids:
            raise GroundingError(f"Scene cited unknown sources: {sorted(unknown_ids)}")
        if not set(scene.source_ids) & priority_ids:
            raise GroundingError("Scene did not cite a top-three retrieval source")
    if retrieved[0].source_id not in cited_ids:
        raise GroundingError("Script did not cite the highest-relevance retrieval source")
