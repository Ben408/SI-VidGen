from pathlib import Path

from src.models import HiggsfieldExplainerPackage, HiggsfieldPayload, Scene
from src.video.higgsfield_client import (
    MCP_TRIAL_HELP,
    _clip_duration,
    _extract_generation_id,
    _extract_result_url,
    _humanize_error,
    _looks_like_uuid,
    _tool_is_error,
    build_scene_prompt,
    images_for_scene,
    plan_scene_clips,
)


def test_extracts_generation_id_and_result_url() -> None:
    assert (
        _extract_generation_id(
            {
                "result": {
                    "structuredContent": {
                        "generation": {"id": "e9a806cc-fe9a-409b-b15c-1fb2e189c4b1"}
                    }
                }
            }
        )
        == "e9a806cc-fe9a-409b-b15c-1fb2e189c4b1"
    )
    assert (
        _extract_generation_id({"data": {"job_id": "24bae836-2c4a-48e0-89b6-49fcc0b21612"}})
        == "24bae836-2c4a-48e0-89b6-49fcc0b21612"
    )
    # Never treat MCP support request_id as a job id.
    assert (
        _extract_generation_id(
            {
                "result": {
                    "structuredContent": {
                        "error": "boom",
                        "request_id": "9e4f3549-e08b-47af-af11-f42a37988ebb",
                    }
                }
            }
        )
        is None
    )
    assert (
        _extract_result_url({"result_url": "https://cdn.example.com/a.mp4"})
        == "https://cdn.example.com/a.mp4"
    )
    assert (
        _extract_result_url({"results": [{"url": "https://cdn.example.com/b.mp4"}]})
        == "https://cdn.example.com/b.mp4"
    )


def test_clips_duration_for_gemini_omni() -> None:
    assert _clip_duration(20) == 10
    assert _clip_duration(8) == 8
    assert _clip_duration(4) == 4
    assert _clip_duration(0) == 8


def test_uuid_shape() -> None:
    assert _looks_like_uuid("e9a806cc-fe9a-409b-b15c-1fb2e189c4b1")
    assert not _looks_like_uuid("job-1")


def test_detects_structured_error_without_is_error_flag() -> None:
    trial_error = (
        "gemini_omni backend request failed (403): "
        "only_mcp_usage_on_trial_is_available"
    )
    payload = {
        "result": {
            "structuredContent": {
                "error": trial_error,
                "request_id": "24bae836-2c4a-48e0-89b6-49fcc0b21612",
            }
        }
    }
    assert _tool_is_error(payload)
    assert _humanize_error(payload["result"]["structuredContent"]["error"]) == MCP_TRIAL_HELP


def test_plan_scene_clips_builds_one_plan_per_scene(tmp_path: Path) -> None:
    image_a = tmp_path / "a.png"
    image_b = tmp_path / "b.png"
    image_a.write_bytes(b"png-a")
    image_b.write_bytes(b"png-b")
    help_a = "https://example.com/EXAMPLE-A.png"
    help_b = "https://example.com/EXAMPLE-B.png"
    scenes = [
        Scene(
            action="Show CSV header",
            visual="Spreadsheet header row",
            voiceover="Prepare the CSV header.",
            help_asset=help_a,
            source_ids=["s1"],
        ),
        Scene(
            action="Show date grouping",
            visual="Rows grouped by date",
            voiceover="Group journal entries by date.",
            help_asset=help_b,
            source_ids=["s1"],
        ),
        Scene(
            action="Import the file",
            visual="Import dialog",
            voiceover="Upload the prepared CSV.",
            help_asset=None,
            source_ids=["s1"],
        ),
    ]
    package = HiggsfieldExplainerPackage(
        prompt="Import GL journal entries\n\nNarration...",
        medias=[str(image_a), str(image_b)],
        duration=30,
        assets=[
            {
                "asset_id": "a",
                "source_url": help_a,
                "local_path": str(image_a),
                "asset_class": "example",
                "alt_text": "A",
                "page_url": "https://example.com/a",
                "page_title": "A",
            },
            {
                "asset_id": "b",
                "source_url": help_b,
                "local_path": str(image_b),
                "asset_class": "example",
                "alt_text": "B",
                "page_url": "https://example.com/b",
                "page_title": "B",
            },
        ],
    )
    payload = HiggsfieldPayload(
        script="Full narration",
        scenes=scenes,
        medias=[str(image_a), str(image_b)],
    )

    plans = plan_scene_clips(package, payload)
    assert len(plans) == 3
    assert plans[0].images == [image_a]
    assert plans[1].images == [image_b]
    assert plans[2].images  # falls back to shared medias
    assert "clip 1 of 3" in plans[0].prompt
    assert "Prepare the CSV header." in plans[0].prompt
    assert "Do not restyle" in plans[0].prompt or "authoritative" in plans[0].prompt


def test_images_for_scene_matches_help_asset(tmp_path: Path) -> None:
    image = tmp_path / "match.png"
    image.write_bytes(b"png")
    url = "https://www.intacct.com/EXAMPLE-match.png"
    package = HiggsfieldExplainerPackage(
        prompt="Title",
        medias=[str(image)],
        duration=20,
        assets=[
            {
                "asset_id": "1",
                "source_url": url,
                "local_path": str(image),
                "asset_class": "example",
                "alt_text": "",
                "page_url": "https://example.com",
                "page_title": "t",
            }
        ],
    )
    scene = Scene(
        action="a",
        visual="v",
        voiceover="vo",
        help_asset=url,
        source_ids=["s1"],
    )
    payload = HiggsfieldPayload(script="s", scenes=[scene], medias=[str(image)])
    assert images_for_scene(package, payload, scene, index=0, model="gemini_omni") == [
        image
    ]


def test_build_scene_prompt_includes_voiceover() -> None:
    scene = Scene(
        action="Open import",
        visual="Import page",
        voiceover="Navigate to Journal Entries and choose Import.",
        help_asset=None,
        source_ids=["s1"],
    )
    payload = HiggsfieldPayload(script="narration", scenes=[scene])
    prompt = build_scene_prompt(None, payload, scene, 2, 5)
    assert "clip 2 of 5" in prompt
    assert "Navigate to Journal Entries and choose Import." in prompt
