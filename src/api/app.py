from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config.settings import Settings, get_settings
from src.models import IssueInput, ProgressEvent, RunResult
from src.orchestrator import Orchestrator
from src.telemetry.logging import configure_logging
from src.telemetry.progress import ProgressTracker
from src.telemetry.run_store import JsonRunStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_runtime_directories()
    configure_logging(settings.log_level)

    run_store = JsonRunStore(settings.runs_dir)
    tracker = ProgressTracker(run_store)
    orchestrator = Orchestrator(settings, run_store, tracker)

    app = FastAPI(title="SI VidGen API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": app.version}

    @app.post("/api/runs", status_code=202)
    def create_run(issue: IssueInput, background_tasks: BackgroundTasks) -> RunResult:
        run_id = orchestrator.create_run_id()
        queued = orchestrator.queue(run_id)
        background_tasks.add_task(orchestrator.run, run_id, issue)
        return queued

    @app.get("/api/runs/{run_id}", response_model=RunResult)
    def get_run(run_id: str) -> RunResult:
        result = orchestrator.get_result(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result

    @app.get("/api/runs/{run_id}/progress", response_model=list[ProgressEvent])
    def get_progress(run_id: str) -> list[ProgressEvent]:
        record = run_store.read(run_id)
        if "result" not in record:
            raise HTTPException(status_code=404, detail="Run not found")
        return [ProgressEvent.model_validate(item) for item in record.get("events", [])]

    @app.get("/api/runs/{run_id}/payload")
    def download_payload(run_id: str) -> FileResponse:
        result = orchestrator.get_result(run_id)
        if result is None or result.status != "completed" or not result.payload_path:
            raise HTTPException(status_code=404, detail="Payload not available")
        path = Path(result.payload_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Payload file not found")
        return FileResponse(path, media_type="application/json", filename=path.name)

    return app


app = create_app()
