from pathlib import Path
from threading import Lock
from uuid import uuid4
import json

from config.settings import Settings
from src.classifier.classify_issue import classify_issue
from src.intake.intake_handler import normalize_issue
from src.llm.client import OllamaClient
from src.models import IssueInput, RunResult, Script, ScriptEdit
from src.rag.asset_binding import (
    assign_library_assets,
    filter_retrieved_to_library,
    visual_coverage,
)
from src.rag.chroma_store import ChromaVectorStore
from src.rag.image_library import HelpImageLibrary
from src.rag.rag_retriever import retrieve_help_content
from src.rag.vector_store import VectorStore
from src.scriptgen.script_builder import GroundingError, build_script
from src.scriptgen.script_writer import read_script_model, write_script
from src.telemetry.logging import log_event, stage
from src.telemetry.progress import ProgressTracker
from src.telemetry.run_store import JsonRunStore
from src.video.higgsfield_client import HiggsfieldClient, VideoGenerator
from src.video.payload_builder import (
    build_explainer_package,
    build_higgsfield_payload,
    write_explainer_package,
    write_payload,
)


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        run_store: JsonRunStore,
        tracker: ProgressTracker,
        llm: OllamaClient | None = None,
        vector_store: VectorStore | None = None,
        video_generator: VideoGenerator | None = None,
        image_library: HelpImageLibrary | None = None,
    ) -> None:
        self.settings = settings
        self.run_store = run_store
        self.tracker = tracker
        self.llm = llm or OllamaClient(
            base_url=settings.ollama_base_url,
            chat_model=settings.ollama_chat_model,
            fallback_model=settings.ollama_fallback_model,
            embed_model=settings.ollama_embed_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
        self.vector_store = vector_store or ChromaVectorStore(settings.vector_store_dir)
        self.video_generator = video_generator or HiggsfieldClient(
            api_key=settings.higgsfield_api_key,
            workspace_id=settings.higgsfield_workspace_id,
            job_type=settings.higgsfield_job_type,
        )
        self.image_library = image_library
        if self.image_library is None and settings.help_assets_dir.joinpath(
            "catalog.json"
        ).is_file():
            self.image_library = HelpImageLibrary(settings.help_assets_dir)
        self._pipeline_lock = Lock()

    def create_run_id(self) -> str:
        return f"run-{uuid4()}"

    def queue(self, run_id: str, auto_generate: bool = False) -> RunResult:
        result = RunResult(
            run_id=run_id,
            status="queued",
            auto_generate=auto_generate,
        )
        self._write_result(result)
        return result

    def run(self, run_id: str, issue_input: IssueInput) -> RunResult:
        # Local Ollama is single-GPU; serialize pipeline work to avoid thrash/timeouts.
        with self._pipeline_lock:
            return self._run_locked(run_id, issue_input)

    def _run_locked(self, run_id: str, issue_input: IssueInput) -> RunResult:
        self._write_status(run_id, "processing")
        log_event("run_started", run_id=run_id)
        try:
            with stage(run_id, "intake", self.tracker):
                issue = normalize_issue(issue_input)

            with stage(run_id, "classify", self.tracker):
                classification = classify_issue(issue, self.llm)

            with stage(run_id, "retrieve", self.tracker):
                retrieved = retrieve_help_content(
                    classification.search_query,
                    self.vector_store,
                    self.llm,
                    top_k=self.settings.rag_top_k,
                    min_score=self.settings.rag_min_score,
                )
                retrieved = filter_retrieved_to_library(retrieved, self.image_library)

            with stage(run_id, "script", self.tracker):
                script = build_script(issue, classification, retrieved, self.llm)
                script = assign_library_assets(script, retrieved, self.image_library)
                script_path = write_script(
                    script, run_id, self.settings.scripts_dir, version=1
                )

            with stage(run_id, "payload", self.tracker):
                coverage = visual_coverage(script, retrieved, self.image_library)
                payload, package_path, media_count = self._write_payload_bundle(
                    script,
                    run_id,
                    version=1,
                    coverage=coverage,
                    retrieved=retrieved,
                )

            result = RunResult(
                run_id=run_id,
                status="completed",
                payload_path=str(payload),
                explainer_package_path=str(package_path) if package_path else None,
                script_path=str(script_path),
                script_version=1,
                review_status="approved" if issue_input.auto_generate else "draft",
                auto_generate=issue_input.auto_generate,
                classification=classification,
                sources=script.sources,
                visual_coverage=coverage,
                media_count=media_count,
            )
            self._write_result(result)
            if issue_input.auto_generate:
                result = self.submit_generation(run_id, allow_auto=True)
                if result.generation_status == "submitted":
                    from threading import Thread

                    Thread(
                        target=self.finalize_generation,
                        args=(run_id,),
                        daemon=True,
                        name=f"finalize-{run_id}",
                    ).start()
            log_event("run_completed", run_id=run_id, payload_path=str(payload))
            return result
        except Exception as exc:
            error_code = f"RUN_{type(exc).__name__.upper()}"
            result = RunResult(
                run_id=run_id,
                status="failed",
                error_code=error_code,
                error_detail=str(exc)[:500],
            )
            self._write_result(result)
            log_event(
                "run_failed",
                run_id=run_id,
                error_code=error_code,
                error_detail=str(exc)[:300],
            )
            return result

    def get_result(self, run_id: str) -> RunResult | None:
        record = self.run_store.read(run_id)
        result = record.get("result")
        return RunResult.model_validate(result) if result else None

    def get_script(self, run_id: str) -> Script | None:
        result = self.get_result(run_id)
        if result is None or not result.script_path:
            return None
        path = Path(result.script_path)
        return read_script_model(path) if path.is_file() else None

    def update_script(self, run_id: str, edit: ScriptEdit) -> RunResult:
        result = self._require_completed(run_id)
        current = self.get_script(run_id)
        if current is None:
            raise FileNotFoundError("Script file not found")
        self._validate_edited_grounding(edit, current)
        version = result.script_version + 1
        script = Script(
            **edit.model_dump(),
            sources=current.sources,
            generation_model=current.generation_model,
        )
        script_path = write_script(
            script, run_id, self.settings.scripts_dir, version=version
        )
        coverage = result.visual_coverage
        payload_path, package_path, media_count = self._write_payload_bundle(
            script,
            run_id,
            version=version,
            coverage=coverage,
            retrieved=None,
        )
        updated = result.model_copy(
            update={
                "script_path": str(script_path),
                "payload_path": str(payload_path),
                "explainer_package_path": str(package_path) if package_path else None,
                "script_version": version,
                "review_status": "draft",
                "generation_status": "not_requested",
                "generation_id": None,
                "generation_job_ids": None,
                "media_count": media_count,
                "visual_coverage": "green" if media_count else coverage,
            }
        )
        self._write_result(updated)
        log_event("script_edited", run_id=run_id, script_version=version)
        return updated

    def approve(self, run_id: str, generate_video: bool = False) -> RunResult:
        result = self._require_completed(run_id).model_copy(
            update={"review_status": "approved"}
        )
        self._write_result(result)
        log_event(
            "script_approved",
            run_id=run_id,
            script_version=result.script_version,
        )
        return self.submit_generation(run_id) if generate_video else result

    def submit_generation(self, run_id: str, *, allow_auto: bool = False) -> RunResult:
        result = self._require_completed(run_id)
        if result.review_status != "approved" and not (
            allow_auto and result.auto_generate
        ):
            raise PermissionError("Script must be approved before video generation")
        if not self.video_generator.configured:
            unavailable = result.model_copy(
                update={"generation_status": "unavailable"}
            )
            self._write_result(unavailable)
            return unavailable
        script = self.get_script(run_id)
        if script is None:
            raise FileNotFoundError("Script file not found")
        pending = result.model_copy(update={"generation_status": "pending"})
        self._write_result(pending)
        try:
            response = self.video_generator.generate(
                build_higgsfield_payload(
                    script,
                    self.image_library,
                    visual_coverage=result.visual_coverage,
                ).model_copy(
                    update={"explainer_package_path": result.explainer_package_path}
                )
            )
            generation_id = response.get("id") or response.get("generation_id")
            raw_job_ids = response.get("generation_job_ids")
            job_ids = (
                [str(item) for item in raw_job_ids]
                if isinstance(raw_job_ids, list)
                else None
            )
            submitted = pending.model_copy(
                update={
                    "generation_status": "submitted",
                    "generation_id": str(generation_id) if generation_id else None,
                    "generation_job_ids": job_ids,
                    "error_code": None,
                    "error_detail": None,
                }
            )
            self._write_result(submitted)
            log_event(
                "video_submitted",
                run_id=run_id,
                generation_id=generation_id,
                scene_count=len(job_ids or []),
                mode=response.get("mode"),
            )
            return submitted
        except Exception as exc:
            failed = pending.model_copy(
                update={
                    "generation_status": "failed",
                    "error_code": "VIDEO_SUBMIT_FAILED",
                    "error_detail": str(exc)[:500],
                }
            )
            self._write_result(failed)
            log_event("video_submit_failed", run_id=run_id, error=str(exc)[:300])
            return failed

    def finalize_generation(self, run_id: str) -> RunResult:
        """Poll Higgsfield until the job finishes, then download the video locally."""
        result = self._require_completed(run_id)
        if result.generation_status not in {"submitted", "pending"}:
            return result
        if not result.generation_id:
            failed = result.model_copy(
                update={
                    "generation_status": "failed",
                    "error_code": "VIDEO_MISSING_JOB_ID",
                    "error_detail": "No Higgsfield generation id to poll",
                }
            )
            self._write_result(failed)
            return failed
        try:
            aspect = "16:9"
            if result.explainer_package_path:
                package_path = Path(result.explainer_package_path)
                if package_path.is_file():
                    try:
                        package_data = json.loads(
                            package_path.read_text(encoding="utf-8")
                        )
                        if isinstance(package_data, dict):
                            ratio = package_data.get("aspect_ratio")
                            if ratio in {"16:9", "9:16"}:
                                aspect = ratio
                    except (OSError, json.JSONDecodeError):
                        pass
            waited = self.video_generator.wait_for_result(
                result.generation_id,
                timeout_seconds=self.settings.higgsfield_wait_timeout_seconds,
                scene_job_ids=result.generation_job_ids,
                aspect_ratio=aspect,
            )
            source_url = waited.get("result_url")
            if not isinstance(source_url, str) or not source_url.startswith("http"):
                raise RuntimeError(f"No result URL in wait response: {waited}")
            destination = self.settings.videos_dir / f"{run_id}.mp4"
            path = self.video_generator.download_video(source_url, destination)
            stitch_id = waited.get("id")
            ready = result.model_copy(
                update={
                    "generation_status": "ready",
                    "generation_id": (
                        str(stitch_id)
                        if isinstance(stitch_id, str) and stitch_id
                        else result.generation_id
                    ),
                    "video_path": str(path),
                    "video_url": source_url,
                    "error_code": None,
                    "error_detail": None,
                }
            )
            self._write_result(ready)
            log_event("video_ready", run_id=run_id, video_path=str(path))
            return ready
        except Exception as exc:
            failed = result.model_copy(
                update={
                    "generation_status": "failed",
                    "error_code": "VIDEO_WAIT_FAILED",
                    "error_detail": str(exc)[:500],
                }
            )
            self._write_result(failed)
            log_event("video_wait_failed", run_id=run_id, error=str(exc)[:300])
            return failed

    def generation_available(self) -> bool:
        return self.video_generator.configured

    def _write_payload_bundle(
        self,
        script: Script,
        run_id: str,
        *,
        version: int,
        coverage: str,
        retrieved=None,
    ) -> tuple[Path, Path | None, int]:
        payload = build_higgsfield_payload(
            script,
            self.image_library,
            visual_coverage=coverage,
            retrieved=retrieved,
        )
        package = build_explainer_package(script, self.image_library, retrieved)
        package_path, _, _ = write_explainer_package(
            package, run_id, self.settings.payloads_dir, version=version
        )
        payload = payload.model_copy(
            update={
                "explainer_package_path": str(package_path),
                "medias": package.medias,
                "visual_coverage": "green" if package.medias else coverage,
            }
        )
        payload_path = write_payload(
            payload, run_id, self.settings.payloads_dir, version=version
        )
        return payload_path, package_path, len(package.medias)

    def _require_completed(self, run_id: str) -> RunResult:
        result = self.get_result(run_id)
        if result is None:
            raise LookupError("Run not found")
        if result.status != "completed":
            raise RuntimeError("Run is not ready for review")
        return result

    @staticmethod
    def _validate_edited_grounding(edit: ScriptEdit, current: Script) -> None:
        valid_source_ids = {source.source_id for source in current.sources}
        existing_assets = {
            scene.help_asset for scene in current.scenes if scene.help_asset
        }
        for scene in edit.scenes:
            unknown_ids = set(scene.source_ids) - valid_source_ids
            if unknown_ids:
                raise GroundingError(
                    f"Edited scene cited unknown sources: {sorted(unknown_ids)}"
                )
            if scene.help_asset and scene.help_asset not in existing_assets:
                raise GroundingError(
                    "Edited scene added an asset not present in the grounded script"
                )

    def _write_status(self, run_id: str, status: str) -> None:
        record = self.run_store.read(run_id)
        record["result"] = RunResult(run_id=run_id, status=status).model_dump(mode="json")
        self.run_store.write(run_id, record)

    def _write_result(self, result: RunResult) -> None:
        record = self.run_store.read(result.run_id)
        record["result"] = result.model_dump(mode="json")
        self.run_store.write(result.run_id, record)


def payload_exists(result: RunResult) -> bool:
    return bool(result.payload_path and Path(result.payload_path).is_file())
