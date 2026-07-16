import json

from fastapi.testclient import TestClient

from config.settings import Settings
from src.api.app import create_app


def test_run_exports_payload_without_persisting_issue_text(tmp_path) -> None:
    settings = Settings(
        runs_dir=tmp_path / "runs",
        output_dir=tmp_path / "output",
        payloads_dir=tmp_path / "output" / "payloads",
        videos_dir=tmp_path / "output" / "videos",
        published_dir=tmp_path / "output" / "published",
    )
    client = TestClient(create_app(settings))
    secret_issue_text = "Sensitive issue content that must not appear in telemetry"

    response = client.post(
        "/api/runs",
        json={"text": secret_issue_text, "module": "General Ledger"},
    )

    assert response.status_code == 202
    run_id = response.json()["run_id"]

    result = client.get(f"/api/runs/{run_id}")
    progress = client.get(f"/api/runs/{run_id}/progress")
    payload = client.get(f"/api/runs/{run_id}/payload")

    assert result.json()["status"] == "completed"
    assert progress.status_code == 200
    assert [event["stage"] for event in progress.json()][::2] == [
        "intake",
        "classify",
        "script",
        "payload",
    ]
    assert payload.status_code == 200
    assert payload.json()["script"]

    telemetry = json.dumps(
        json.loads((settings.runs_dir / f"{run_id}.json").read_text(encoding="utf-8"))
    )
    assert secret_issue_text not in telemetry
