"""Full Help corpus refresh: crawl → Chroma → image library → OKF."""

from __future__ import annotations

from threading import Lock
from uuid import uuid4

from config.settings import Settings
from src.models import RefreshResult
from src.rag.image_library import build_image_library
from src.rag.index_help import build_index
from src.rag.okf.convert import convert_xhtml_cache_to_okf
from src.runtime_gate import BusyError, WorkGate
from src.telemetry.logging import log_event, stage
from src.telemetry.progress import ProgressTracker
from src.telemetry.run_store import JsonRunStore


class CorpusRefreshService:
    def __init__(
        self,
        settings: Settings,
        run_store: JsonRunStore,
        tracker: ProgressTracker,
        gate: WorkGate,
    ) -> None:
        self.settings = settings
        self.run_store = run_store
        self.tracker = tracker
        self.gate = gate
        self._lock = Lock()

    def create_refresh_id(self) -> str:
        return f"refresh-{uuid4()}"

    def queue(self, refresh_id: str) -> RefreshResult:
        result = RefreshResult(refresh_id=refresh_id, status="queued")
        self._write_result(result)
        return result

    def run(self, refresh_id: str) -> RefreshResult:
        with self._lock:
            return self._run_locked(refresh_id)

    def get_result(self, refresh_id: str) -> RefreshResult | None:
        record = self.run_store.read(refresh_id)
        result = record.get("result")
        return RefreshResult.model_validate(result) if result else None

    def _run_locked(self, refresh_id: str) -> RefreshResult:
        try:
            self.gate.acquire("refresh")
        except BusyError as error:
            result = RefreshResult(
                refresh_id=refresh_id,
                status="failed",
                error_code="WORKSPACE_BUSY",
                error_detail=str(error),
            )
            self._write_result(result)
            return result

        self._write_result(RefreshResult(refresh_id=refresh_id, status="processing"))
        log_event("refresh_started", run_id=refresh_id)
        details: dict[str, object] = {}
        try:
            with stage(refresh_id, "crawl_index", self.tracker):
                index_summary = build_index(
                    max_pages=None,
                    delete_stale=True,
                    settings=self.settings,
                )
                details["index"] = {
                    "pages_crawled": index_summary.pages_crawled,
                    "pages_indexed": index_summary.pages_indexed,
                    "pages_unchanged": index_summary.pages_unchanged,
                    "pages_deleted": index_summary.pages_deleted,
                    "chunks_indexed": index_summary.chunks_indexed,
                    "crawl_errors": index_summary.crawl_errors,
                    "index_errors": index_summary.index_errors,
                    "complete": index_summary.complete,
                }
                if index_summary.index_errors or (
                    index_summary.crawl_errors and not index_summary.pages_crawled
                ):
                    raise RuntimeError(
                        "Help crawl/index did not complete cleanly; "
                        f"crawl_errors={index_summary.crawl_errors} "
                        f"index_errors={index_summary.index_errors}"
                    )

            with stage(refresh_id, "image_library", self.tracker):
                library_summary = build_image_library(
                    self.settings.help_cache_dir,
                    self.settings.help_assets_dir,
                    download=True,
                )
                details["image_library"] = {
                    "pages_scanned": library_summary.pages_scanned,
                    "assets_usable": library_summary.assets_usable,
                    "assets_downloaded": library_summary.assets_downloaded,
                    "download_errors": library_summary.download_errors,
                    "pages_with_usable_assets": library_summary.pages_with_usable_assets,
                }

            with stage(refresh_id, "okf", self.tracker):
                okf_summary = convert_xhtml_cache_to_okf(
                    self.settings.help_cache_dir,
                    self.settings.okf_dir,
                    library_dir=self.settings.help_assets_dir,
                )
                details["okf"] = {
                    "pages_converted": okf_summary.pages_converted,
                    "topics": okf_summary.topics,
                    "procedures": okf_summary.procedures,
                    "assets": okf_summary.assets,
                    "error_count": len(okf_summary.errors),
                }
                if okf_summary.pages_converted == 0:
                    raise RuntimeError("OKF conversion produced no topics")

            result = RefreshResult(
                refresh_id=refresh_id,
                status="completed",
                message=(
                    "Help corpus refresh completed. Video drafting and product Q&A "
                    "now use the updated local assets."
                ),
                details=details,
            )
            self._write_result(result)
            log_event("refresh_completed", run_id=refresh_id)
            return result
        except Exception as exc:
            error_code = f"REFRESH_{type(exc).__name__.upper()}"
            result = RefreshResult(
                refresh_id=refresh_id,
                status="failed",
                message="Help corpus refresh failed.",
                details=details,
                error_code=error_code,
                error_detail=str(exc)[:500],
            )
            self._write_result(result)
            log_event("refresh_failed", run_id=refresh_id, error_code=error_code)
            return result
        finally:
            self.gate.release("refresh")

    def _write_result(self, result: RefreshResult) -> None:
        record = self.run_store.read(result.refresh_id)
        record["result"] = result.model_dump(mode="json")
        self.run_store.write(result.refresh_id, record)
