"""E2E coverage for product Q&A and corpus refresh APIs."""

from uuid import uuid4

from fastapi.testclient import TestClient

from config.settings import Settings
from src.api.app import create_app
from src.models import ProgressEvent, RefreshResult
from src.runtime_gate import WorkGate
from src.telemetry.progress import ProgressTracker
from src.telemetry.run_store import JsonRunStore
from tests.fakes import FakePipelineLLM, FakeVectorStore


class FakeRefreshService:
    def __init__(self, run_store: JsonRunStore, tracker: ProgressTracker, gate: WorkGate) -> None:
        self.run_store = run_store
        self.tracker = tracker
        self.gate = gate

    def create_refresh_id(self) -> str:
        return f"refresh-{uuid4()}"

    def queue(self, refresh_id: str) -> RefreshResult:
        result = RefreshResult(refresh_id=refresh_id, status="queued")
        record = self.run_store.read(refresh_id)
        record["result"] = result.model_dump(mode="json")
        self.run_store.write(refresh_id, record)
        return result

    def run(self, refresh_id: str) -> RefreshResult:
        self.gate.acquire("refresh")
        try:
            self.tracker.push(
                ProgressEvent(run_id=refresh_id, stage="crawl_index", status="started")
            )
            self.tracker.push(
                ProgressEvent(
                    run_id=refresh_id,
                    stage="crawl_index",
                    status="completed",
                    duration_ms=1,
                )
            )
            result = RefreshResult(
                refresh_id=refresh_id,
                status="completed",
                message="Help corpus refresh completed (fake).",
                details={"fake": True},
            )
            record = self.run_store.read(refresh_id)
            record["result"] = result.model_dump(mode="json")
            self.run_store.write(refresh_id, record)
            return result
        finally:
            self.gate.release("refresh")

    def get_result(self, refresh_id: str) -> RefreshResult | None:
        record = self.run_store.read(refresh_id)
        result = record.get("result")
        return RefreshResult.model_validate(result) if result else None


def _settings(tmp_path) -> Settings:
    return Settings(
        runs_dir=tmp_path / "runs",
        output_dir=tmp_path / "output",
        scripts_dir=tmp_path / "output" / "scripts",
        payloads_dir=tmp_path / "output" / "payloads",
        videos_dir=tmp_path / "output" / "videos",
        published_dir=tmp_path / "output" / "published",
        help_cache_dir=tmp_path / "help_xhtml",
        help_assets_dir=tmp_path / "help_assets",
        help_locales="en_US",
        okf_dir=tmp_path / "okf",
        vector_store_dir=tmp_path / "vector_store",
    )


def test_ask_returns_structured_answer_with_sources(tmp_path) -> None:
    settings = _settings(tmp_path)
    client = TestClient(
        create_app(
            settings,
            llm=FakePipelineLLM(),
            vector_store=FakeVectorStore(),
        )
    )
    response = client.post(
        "/api/ask",
        json={"text": "How do I correct an unbalanced journal entry?"},
    )
    assert response.status_code == 202
    ask_id = response.json()["ask_id"]

    result = client.get(f"/api/ask/{ask_id}")
    progress = client.get(f"/api/ask/{ask_id}/progress")

    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["answer"]["summary"]
    assert payload["answer"]["steps"][0]["source_ids"] == ["chunk-1"]
    assert payload["sources"][0]["source_url"].startswith("https://")
    assert [event["stage"] for event in progress.json()][::2] == [
        "intake",
        "classify",
        "retrieve",
        "retrieve_followup",
        "answer",
    ]


def test_ask_refuses_when_evidence_is_weak(tmp_path) -> None:
    settings = _settings(tmp_path)
    client = TestClient(
        create_app(
            settings,
            llm=FakePipelineLLM(),
            vector_store=FakeVectorStore(score=0.01),
        )
    )
    response = client.post("/api/ask", json={"text": "How do I reverse a journal?"})
    ask_id = response.json()["ask_id"]
    result = client.get(f"/api/ask/{ask_id}").json()
    assert result["status"] == "refused"
    assert result["error_code"] == "INSUFFICIENT_HELP_COVERAGE"


def test_ask_reports_workspace_busy_when_gate_held(tmp_path) -> None:
    settings = _settings(tmp_path)
    gate = WorkGate()
    gate.acquire("refresh")
    client = TestClient(
        create_app(
            settings,
            llm=FakePipelineLLM(),
            vector_store=FakeVectorStore(),
            work_gate=gate,
        )
    )
    response = client.post("/api/ask", json={"text": "How do I post a journal?"})
    ask_id = response.json()["ask_id"]
    result = client.get(f"/api/ask/{ask_id}").json()
    assert result["status"] == "failed"
    assert result["error_code"] == "WORKSPACE_BUSY"
    gate.release("refresh")


def test_corpus_refresh_completes_with_progress(tmp_path) -> None:
    settings = _settings(tmp_path)
    run_store = JsonRunStore(settings.runs_dir)
    tracker = ProgressTracker(run_store)
    gate = WorkGate()
    client = TestClient(
        create_app(
            settings,
            llm=FakePipelineLLM(),
            vector_store=FakeVectorStore(),
            refresh_service=FakeRefreshService(run_store, tracker, gate),
            work_gate=gate,
        )
    )
    assert client.get("/api/workspace").json()["busy"] is False
    response = client.post("/api/corpus/refresh")
    assert response.status_code == 202
    refresh_id = response.json()["refresh_id"]
    result = client.get(f"/api/corpus/refresh/{refresh_id}").json()
    assert result["status"] == "completed"
    progress = client.get(f"/api/corpus/refresh/{refresh_id}/progress")
    assert progress.status_code == 200
    assert any(event["stage"] == "crawl_index" for event in progress.json())
