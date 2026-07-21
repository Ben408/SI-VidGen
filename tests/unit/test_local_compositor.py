from pathlib import Path

from src.models import HiggsfieldExplainerPackage, HiggsfieldPayload, Scene
from src.video.local_compositor import (
    LocalCompositorVideoGenerator,
    _build_caption_overlay,
    _resolve_local_source,
    _scene_duration_seconds,
)


def test_scene_duration_bounds() -> None:
    assert _scene_duration_seconds("one two") == 5.0
    assert _scene_duration_seconds(" ".join(["word"] * 200)) == 20.0


def test_caption_overlay_draws_bar() -> None:
    overlay = _build_caption_overlay(
        640,
        360,
        "Prepare the CSV header and import the journal entries carefully.",
    )
    assert overlay.size == (640, 360)
    # Semi-transparent caption pixels should exist near the bottom.
    sample = overlay.getpixel((320, 340))
    assert sample[3] > 0


def test_local_compositor_renders_sample_scenes(tmp_path: Path) -> None:
    image_a = tmp_path / "a.png"
    image_b = tmp_path / "b.png"
    # Minimal valid PNGs via Pillow
    from PIL import Image

    Image.new("RGB", (640, 360), color=(20, 80, 160)).save(image_a)
    Image.new("RGB", (640, 360), color=(30, 120, 60)).save(image_b)

    help_a = "https://example.com/a.png"
    help_b = "https://example.com/b.png"
    scenes = [
        Scene(
            action="Show CSV",
            visual="CSV header",
            voiceover="Prepare the CSV header and line items.",
            help_asset=help_a,
            source_ids=["s1"],
        ),
        Scene(
            action="Import",
            visual="Import dialog",
            voiceover="Upload the prepared file into Sage Intacct.",
            help_asset=help_b,
            source_ids=["s1"],
        ),
    ]
    package = HiggsfieldExplainerPackage(
        prompt="Import GL journal entries\n\nNarration",
        medias=[str(image_a), str(image_b)],
        duration=20,
        assets=[
            {
                "asset_id": "a",
                "source_url": help_a,
                "local_path": str(image_a),
                "asset_class": "example",
                "alt_text": "",
                "page_url": "https://example.com",
                "page_title": "t",
            },
            {
                "asset_id": "b",
                "source_url": help_b,
                "local_path": str(image_b),
                "asset_class": "example",
                "alt_text": "",
                "page_url": "https://example.com",
                "page_title": "t",
            },
        ],
    )
    payload = HiggsfieldPayload(
        script="narration",
        scenes=scenes,
        medias=[str(image_a), str(image_b)],
        captions=True,
        tts_voice="en-US-AriaNeural",
        tts_rate="-10%",
        explainer_package_path=None,
    )
    # Write package so client can load assets via path if needed
    package_path = tmp_path / "explainer.json"
    package_path.write_text(package.model_dump_json(), encoding="utf-8")
    payload = payload.model_copy(update={"explainer_package_path": str(package_path)})

    generator = LocalCompositorVideoGenerator(
        jobs_dir=tmp_path / "jobs",
        enable_tts=False,
        enable_captions=True,
    )
    assert generator.configured
    submitted = generator.generate(payload)
    assert submitted["mode"] == "scene_chunked"
    job_id = str(submitted["generation_id"])
    job = (tmp_path / "jobs" / f"{job_id}.json").read_text(encoding="utf-8")
    assert "en-US-AriaNeural" in job
    assert "-10%" in job
    waited = generator.wait_for_result(job_id)
    local = Path(str(waited["local_path"]))
    assert local.is_file()
    assert local.stat().st_size > 1000
    dest = tmp_path / "out.mp4"
    copied = generator.download_video(str(waited["result_url"]), dest)
    assert copied.is_file()
    assert _resolve_local_source(str(waited["result_url"])) is not None
