import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

from src.models import ProgressEvent
from src.telemetry.progress import ProgressTracker


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format="%(message)s")


def log_event(event: str, **fields: object) -> None:
    logging.getLogger("si_vidgen").info(json.dumps({"event": event, **fields}, default=str))


@contextmanager
def stage(run_id: str, name: str, tracker: ProgressTracker) -> Iterator[None]:
    started = perf_counter()
    start_event = ProgressEvent(run_id=run_id, stage=name, status="started")
    tracker.push(start_event)
    log_event("stage_started", **start_event.model_dump(mode="json"))
    try:
        yield
    except Exception as exc:
        duration_ms = int((perf_counter() - started) * 1000)
        error_code = f"{name.upper()}_{type(exc).__name__.upper()}"
        failed_event = ProgressEvent(
            run_id=run_id,
            stage=name,
            status="failed",
            duration_ms=duration_ms,
            error_code=error_code,
        )
        tracker.push(failed_event)
        log_event("stage_failed", **failed_event.model_dump(mode="json"))
        raise
    else:
        duration_ms = int((perf_counter() - started) * 1000)
        completed_event = ProgressEvent(
            run_id=run_id,
            stage=name,
            status="completed",
            duration_ms=duration_ms,
        )
        tracker.push(completed_event)
        log_event("stage_completed", **completed_event.model_dump(mode="json"))
