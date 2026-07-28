from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config.settings import Settings, get_settings
from src.llm.client import OllamaClient
from src.models import (
    AskResult,
    IssueInput,
    ProgressEvent,
    RefreshResult,
    ReviewAction,
    RunResult,
    Script,
    ScriptEdit,
)
from src.orchestrator import Orchestrator
from src.qa.ask_agent import AskService
from src.rag.corpus_refresh import CorpusRefreshService
from src.rag.vector_store import VectorStore
from src.runtime_gate import WorkGate
from src.scriptgen.script_builder import GroundingError
from src.telemetry.logging import configure_logging
from src.telemetry.progress import ProgressTracker
from src.telemetry.run_store import JsonRunStore
from src.video.higgsfield_client import VideoGenerator
from src.video.payload_builder import read_payload


def create_app(
    settings: Settings | None = None,
    llm: OllamaClient | None = None,
    vector_store: VectorStore | None = None,
    video_generator: VideoGenerator | None = None,
    ask_service: AskService | None = None,
    refresh_service: CorpusRefreshService | None = None,
    work_gate: WorkGate | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_runtime_directories()
    configure_logging(settings.log_level)

    run_store = JsonRunStore(settings.runs_dir)
    tracker = ProgressTracker(run_store)
    gate = work_gate or WorkGate()
    orchestrator = Orchestrator(
        settings,
        run_store,
        tracker,
        llm,
        vector_store,
        video_generator,
        work_gate=gate,
    )
    ask = ask_service or AskService(
        settings,
        run_store,
        tracker,
        gate,
        llm=llm,
        vector_store=vector_store,
    )
    refresh = refresh_service or CorpusRefreshService(
        settings, run_store, tracker, gate
    )

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

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, object]:
        available = orchestrator.generation_available()
        backend = (settings.video_backend or "local_compositor").strip().lower()
        payload: dict[str, object] = {
            "higgsfield_generation": available,
            "video_generation": available,
            "video_backend": settings.video_backend,
            "workspace": gate.status(),
        }
        if backend not in {"higgsfield", "hf", "gemini_omni"}:
            from src.video.local_compositor import compositor_capability_defaults

            payload["compositor"] = compositor_capability_defaults(
                voice=settings.local_compositor_voice,
                rate=settings.local_compositor_tts_rate,
                captions=settings.local_compositor_captions,
            )
        return payload

    @app.get("/api/workspace")
    def workspace_status() -> dict[str, object]:
        return gate.status()

    @app.post("/api/ask", status_code=202)
    def create_ask(issue: IssueInput, background_tasks: BackgroundTasks) -> AskResult:
        ask_id = ask.create_ask_id()
        queued = ask.queue(ask_id)
        background_tasks.add_task(ask.run, ask_id, issue)
        return queued

    @app.get("/api/ask/{ask_id}", response_model=AskResult)
    def get_ask(ask_id: str) -> AskResult:
        result = ask.get_result(ask_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Ask not found")
        return result

    @app.get("/api/ask/{ask_id}/progress", response_model=list[ProgressEvent])
    def get_ask_progress(ask_id: str) -> list[ProgressEvent]:
        record = run_store.read(ask_id)
        if "result" not in record:
            raise HTTPException(status_code=404, detail="Ask not found")
        return [ProgressEvent.model_validate(item) for item in record.get("events", [])]

    @app.post("/api/corpus/refresh", status_code=202)
    def start_corpus_refresh(background_tasks: BackgroundTasks) -> RefreshResult:
        refresh_id = refresh.create_refresh_id()
        queued = refresh.queue(refresh_id)
        background_tasks.add_task(refresh.run, refresh_id)
        return queued

    @app.get("/api/corpus/refresh/{refresh_id}", response_model=RefreshResult)
    def get_corpus_refresh(refresh_id: str) -> RefreshResult:
        result = refresh.get_result(refresh_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Refresh not found")
        return result

    @app.get("/api/corpus/refresh/{refresh_id}/progress", response_model=list[ProgressEvent])
    def get_corpus_refresh_progress(refresh_id: str) -> list[ProgressEvent]:
        record = run_store.read(refresh_id)
        if "result" not in record:
            raise HTTPException(status_code=404, detail="Refresh not found")
        return [ProgressEvent.model_validate(item) for item in record.get("events", [])]

    @app.post("/api/runs", status_code=202)
    def create_run(issue: IssueInput, background_tasks: BackgroundTasks) -> RunResult:
        run_id = orchestrator.create_run_id()
        queued = orchestrator.queue(run_id, auto_generate=issue.auto_generate)
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

    @app.get("/api/runs/{run_id}/explainer-package")
    def download_explainer_package(run_id: str) -> FileResponse:
        result = orchestrator.get_result(run_id)
        if (
            result is None
            or result.status != "completed"
            or not result.explainer_package_path
        ):
            raise HTTPException(status_code=404, detail="Explainer package not available")
        path = Path(result.explainer_package_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Explainer package file not found")
        return FileResponse(path, media_type="application/json", filename=path.name)

    @app.get("/api/runs/{run_id}/medias")
    def list_medias(run_id: str) -> dict[str, object]:
        result = orchestrator.get_result(run_id)
        if result is None or result.status != "completed":
            raise HTTPException(status_code=404, detail="Run not ready")
        assets = _run_media_assets(result)
        return {
            "run_id": run_id,
            "count": len(assets),
            "visual_coverage": result.visual_coverage,
            "assets": [
                {
                    "asset_id": asset["asset_id"],
                    "asset_class": asset.get("asset_class"),
                    "alt_text": asset.get("alt_text") or "",
                    "page_title": asset.get("page_title") or "",
                    "page_url": asset.get("page_url") or "",
                    "source_url": asset.get("source_url") or "",
                    "preview_url": f"/api/runs/{run_id}/medias/{asset['asset_id']}",
                }
                for asset in assets
            ],
        }

    @app.get("/api/runs/{run_id}/medias/{asset_id}")
    def preview_media(run_id: str, asset_id: str) -> FileResponse:
        result = orchestrator.get_result(run_id)
        if result is None or result.status != "completed":
            raise HTTPException(status_code=404, detail="Run not ready")
        assets = _run_media_assets(result)
        match = next((item for item in assets if item.get("asset_id") == asset_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail="Media asset not found")
        path = Path(str(match.get("local_path") or ""))
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Media file not found")
        media_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "application/octet-stream")
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.get("/api/image-library/coverage")
    def image_library_coverage() -> dict[str, object]:
        library = orchestrator.image_library
        if library is None:
            return {"available": False, "message": "Help image library not built yet"}
        coverage = library.coverage()
        return {"available": True, **coverage}

    @app.get("/api/okf/status")
    def okf_status() -> dict[str, object]:
        store = orchestrator.okf_store
        if store is None:
            return {
                "available": False,
                "bundle_dir": str(settings.okf_dir),
                "message": "OKF bundle not built yet. Run: python -m src.rag.build_okf",
            }
        return store.status()

    @app.get("/api/okf/concepts")
    def list_okf_concepts(
        type: str | None = None,
        page_url: str | None = None,
        q: str | None = None,
        derived_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        store = orchestrator.okf_store
        if store is None or not store.available:
            raise HTTPException(status_code=404, detail="OKF bundle not available")
        concepts = store.list_concepts(
            concept_type=type,
            page_url=page_url,
            query=q,
            derived_only=derived_only,
            limit=min(max(limit, 1), 200),
            offset=max(offset, 0),
        )
        return {"count": len(concepts), "concepts": concepts}

    @app.get("/api/okf/concepts/{concept_id:path}")
    def get_okf_concept(concept_id: str) -> dict[str, object]:
        store = orchestrator.okf_store
        if store is None or not store.available:
            raise HTTPException(status_code=404, detail="OKF bundle not available")
        concept = store.get_concept(concept_id)
        if concept is None:
            raise HTTPException(status_code=404, detail="Concept not found")
        payload = concept.summary()
        payload["body"] = concept.body
        payload["frontmatter"] = concept.frontmatter or {}
        return payload

    @app.get("/api/runs/{run_id}/script", response_model=Script)
    def get_script(run_id: str) -> Script:
        script = orchestrator.get_script(run_id)
        if script is None:
            raise HTTPException(status_code=404, detail="Script not available")
        return script

    @app.put("/api/runs/{run_id}/script", response_model=RunResult)
    def update_script(run_id: str, edit: ScriptEdit) -> RunResult:
        try:
            return orchestrator.update_script(run_id, edit)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except GroundingError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/runs/{run_id}/video")
    def download_video(run_id: str) -> FileResponse:
        result = orchestrator.get_result(run_id)
        if result is None or result.generation_status != "ready" or not result.video_path:
            raise HTTPException(status_code=404, detail="Video not available")
        path = Path(result.video_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Video file not found")
        return FileResponse(path, media_type="video/mp4", filename=path.name)

    @app.post("/api/runs/{run_id}/approve", response_model=RunResult)
    def approve(
        run_id: str, action: ReviewAction, background_tasks: BackgroundTasks
    ) -> RunResult:
        try:
            result = orchestrator.approve(run_id, action=action)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if action.generate_video and result.generation_status == "submitted":
            background_tasks.add_task(orchestrator.finalize_generation, run_id)
        return result

    return app


def _run_media_assets(result: RunResult) -> list[dict[str, object]]:
    if not result.explainer_package_path:
        return []
    path = Path(result.explainer_package_path)
    if not path.is_file():
        return []
    payload = read_payload(path)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return []
    return [item for item in assets if isinstance(item, dict) and item.get("asset_id")]


app = create_app()
