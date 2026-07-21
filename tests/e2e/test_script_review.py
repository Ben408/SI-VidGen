from fastapi.testclient import TestClient

from config.settings import Settings
from src.api.app import create_app
from tests.fakes import FakePipelineLLM, FakeVectorStore, FakeVideoGenerator


def make_client(tmp_path, generator: FakeVideoGenerator) -> TestClient:
    settings = Settings(
        runs_dir=tmp_path / "runs",
        output_dir=tmp_path / "output",
        scripts_dir=tmp_path / "output" / "scripts",
        payloads_dir=tmp_path / "output" / "payloads",
        videos_dir=tmp_path / "output" / "videos",
        published_dir=tmp_path / "output" / "published",
    )
    return TestClient(
        create_app(
            settings,
            llm=FakePipelineLLM(),
            vector_store=FakeVectorStore(),
            video_generator=generator,
        )
    )


def create_completed_run(client: TestClient, *, auto_generate: bool = False) -> str:
    response = client.post(
        "/api/runs",
        json={
            "text": "My journal will not post because it is unbalanced.",
            "module": "General Ledger",
            "auto_generate": auto_generate,
        },
    )
    assert response.status_code == 202
    return response.json()["run_id"]


def test_edit_regenerates_versioned_script_and_payload_then_approves(tmp_path) -> None:
    generator = FakeVideoGenerator()
    client = make_client(tmp_path, generator)
    run_id = create_completed_run(client)
    original = client.get(f"/api/runs/{run_id}").json()
    script = client.get(f"/api/runs/{run_id}/script").json()

    script["title"] = "Reviewed journal correction"
    script["narration"] = "Reviewed narration grounded in the cited source."
    script["scenes"][0]["voiceover"] = "Review debits and credits before posting."
    edit = {
        "title": script["title"],
        "narration": script["narration"],
        "scenes": script["scenes"],
    }
    response = client.put(f"/api/runs/{run_id}/script", json=edit)

    assert response.status_code == 200
    updated = response.json()
    assert original["script_version"] == 1
    assert updated["script_version"] == 2
    assert updated["review_status"] == "draft"
    assert updated["script_path"].endswith("-v2.json")
    assert updated["payload_path"].endswith("-v2.json")
    assert client.get(f"/api/runs/{run_id}/payload").json()["script"] == edit["narration"]

    approval = client.post(
        f"/api/runs/{run_id}/approve",
        json={"generate_video": True},
    )
    assert approval.status_code == 200
    assert approval.json()["review_status"] == "approved"
    assert approval.json()["generation_status"] == "submitted"
    assert approval.json()["generation_id"] == "video-test-1"
    assert generator.payloads[0].script == edit["narration"]

    ready = client.get(f"/api/runs/{run_id}")
    assert ready.json()["generation_status"] == "ready"
    assert ready.json()["video_path"]
    assert client.get(f"/api/runs/{run_id}/video").status_code == 200
    assert generator.waited == ["video-test-1"]


def test_edit_rejects_unknown_grounding_source(tmp_path) -> None:
    client = make_client(tmp_path, FakeVideoGenerator())
    run_id = create_completed_run(client)
    script = client.get(f"/api/runs/{run_id}/script").json()
    script["scenes"][0]["source_ids"] = ["invented-source"]

    response = client.put(
        f"/api/runs/{run_id}/script",
        json={
            "title": script["title"],
            "narration": script["narration"],
            "scenes": script["scenes"],
        },
    )

    assert response.status_code == 422
    assert "unknown sources" in response.json()["detail"]


def test_auto_generate_is_default_off_and_can_bypass_manual_approval(tmp_path) -> None:
    generator = FakeVideoGenerator()
    client = make_client(tmp_path, generator)

    manual_run = create_completed_run(client)
    manual = client.get(f"/api/runs/{manual_run}").json()
    assert manual["auto_generate"] is False
    assert manual["review_status"] == "draft"
    assert generator.payloads == []

    automatic_run = create_completed_run(client, auto_generate=True)
    automatic = None
    for _ in range(50):
        automatic = client.get(f"/api/runs/{automatic_run}").json()
        if automatic["generation_status"] in {"ready", "failed"}:
            break
        import time

        time.sleep(0.05)
    assert automatic is not None
    assert automatic["auto_generate"] is True
    assert automatic["review_status"] == "approved"
    assert automatic["generation_status"] == "ready"
    assert len(generator.payloads) == 1
    assert automatic["video_path"]
