import json
from pathlib import Path

from fastapi.testclient import TestClient

from config.settings import Settings
from src.api.app import create_app
from src.models import RunResult
from src.telemetry.run_store import JsonRunStore
from tests.fakes import FakePipelineLLM, FakeVectorStore


def test_medias_preview_endpoints(tmp_path: Path) -> None:
    settings = Settings(
        runs_dir=tmp_path / "runs",
        output_dir=tmp_path / "output",
        scripts_dir=tmp_path / "output" / "scripts",
        payloads_dir=tmp_path / "output" / "payloads",
        videos_dir=tmp_path / "output" / "videos",
        published_dir=tmp_path / "output" / "published",
        help_assets_dir=tmp_path / "help_assets",
    )
    settings.ensure_runtime_directories()
    image = settings.help_assets_dir / "files" / "shot.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"\x89PNG\r\n\x1a\npreview")
    package = settings.payloads_dir / "run-preview-v1-explainer.json"
    package.write_text(
        json.dumps(
            {
                "job_set_type": "video_explainer",
                "prompt": "x",
                "medias": [str(image)],
                "duration": 20,
                "aspect_ratio": "16:9",
                "preserve_source_visuals": True,
                "instruction": "x",
                "assets": [
                    {
                        "asset_id": "shot1",
                        "asset_class": "example",
                        "alt_text": "CSV layout",
                        "page_title": "Import",
                        "page_url": "https://example.com",
                        "source_url": "https://example.com/a.png",
                        "local_path": str(image),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    store = JsonRunStore(settings.runs_dir)
    store.write(
        "run-preview",
        {
            "result": RunResult(
                run_id="run-preview",
                status="completed",
                explainer_package_path=str(package),
                visual_coverage="green",
                media_count=1,
            ).model_dump(mode="json")
        },
    )
    client = TestClient(
        create_app(
            settings,
            llm=FakePipelineLLM(),
            vector_store=FakeVectorStore(),
        )
    )

    listing = client.get("/api/runs/run-preview/medias")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] == 1
    assert body["assets"][0]["preview_url"].endswith("/medias/shot1")

    preview = client.get("/api/runs/run-preview/medias/shot1")
    assert preview.status_code == 200
    assert preview.content.startswith(b"\x89PNG")
