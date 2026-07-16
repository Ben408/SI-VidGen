from pathlib import Path
from uuid import uuid4

from config.settings import Settings
from src.classifier.classify_issue import classify_issue
from src.intake.intake_handler import normalize_issue
from src.models import IssueInput, RunResult
from src.scriptgen.script_builder import build_script
from src.telemetry.logging import log_event, stage
from src.telemetry.progress import ProgressTracker
from src.telemetry.run_store import JsonRunStore
from src.video.payload_builder import build_higgsfield_payload, write_payload


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        run_store: JsonRunStore,
        tracker: ProgressTracker,
    ) -> None:
        self.settings = settings
        self.run_store = run_store
        self.tracker = tracker

    def create_run_id(self) -> str:
        return f"run-{uuid4()}"

    def queue(self, run_id: str) -> RunResult:
        result = RunResult(run_id=run_id, status="queued")
        self._write_result(result)
        return result

    def run(self, run_id: str, issue_input: IssueInput) -> RunResult:
        self._write_status(run_id, "processing")
        log_event("run_started", run_id=run_id)
        try:
            with stage(run_id, "intake", self.tracker):
                issue = normalize_issue(issue_input)

            with stage(run_id, "classify", self.tracker):
                classification = classify_issue(issue)

            with stage(run_id, "script", self.tracker):
                script = build_script(issue, classification)

            with stage(run_id, "payload", self.tracker):
                payload = build_higgsfield_payload(script)
                payload_path = write_payload(payload, run_id, self.settings.payloads_dir)

            result = RunResult(
                run_id=run_id,
                status="completed",
                payload_path=str(payload_path),
                classification=classification,
            )
            self._write_result(result)
            log_event("run_completed", run_id=run_id, payload_path=str(payload_path))
            return result
        except Exception as exc:
            error_code = f"RUN_{type(exc).__name__.upper()}"
            result = RunResult(run_id=run_id, status="failed", error_code=error_code)
            self._write_result(result)
            log_event("run_failed", run_id=run_id, error_code=error_code)
            return result

    def get_result(self, run_id: str) -> RunResult | None:
        record = self.run_store.read(run_id)
        result = record.get("result")
        return RunResult.model_validate(result) if result else None

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
