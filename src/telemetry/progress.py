from collections import defaultdict
from threading import Lock

from src.models import ProgressEvent
from src.telemetry.run_store import JsonRunStore


class ProgressTracker:
    def __init__(self, run_store: JsonRunStore) -> None:
        self._events: dict[str, list[ProgressEvent]] = defaultdict(list)
        self._lock = Lock()
        self._run_store = run_store

    def push(self, event: ProgressEvent) -> None:
        with self._lock:
            self._events[event.run_id].append(event)
        self._run_store.append_event(event.run_id, event.model_dump(mode="json"))

    def get(self, run_id: str) -> list[ProgressEvent]:
        with self._lock:
            return list(self._events.get(run_id, []))
