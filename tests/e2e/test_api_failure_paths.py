from fastapi.testclient import TestClient

from config.settings import Settings
from src.api.app import create_app
from tests.fakes import FakePipelineLLM, FakeVectorStore


def test_run_fails_cleanly_when_retrieval_evidence_is_weak(tmp_path) -> None:
    settings = Settings(
        runs_dir=tmp_path / "runs",
        output_dir=tmp_path / "output",
        scripts_dir=tmp_path / "output" / "scripts",
        payloads_dir=tmp_path / "output" / "payloads",
        videos_dir=tmp_path / "output" / "videos",
        published_dir=tmp_path / "output" / "published",
    )
    client = TestClient(
        create_app(
            settings,
            llm=FakePipelineLLM(),
            vector_store=FakeVectorStore(score=0.01),
        )
    )

    response = client.post(
        "/api/runs",
        json={"text": "How do I post an unbalanced journal?", "module": "General Ledger"},
    )
    run_id = response.json()["run_id"]
    result = client.get(f"/api/runs/{run_id}").json()
    progress = client.get(f"/api/runs/{run_id}/progress").json()

    assert result["status"] == "failed"
    assert result["error_code"] == "RUN_INSUFFICIENTEVIDENCEERROR"
    assert "retrieve" in {event["stage"] for event in progress}
    assert client.get(f"/api/runs/{run_id}/script").status_code == 404
    assert client.get(f"/api/runs/{run_id}/payload").status_code == 404
