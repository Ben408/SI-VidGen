import json
from pathlib import Path
from threading import Lock
from typing import Any


class JsonRunStore:
    """Thread-safe JSON run storage that must receive metadata-only records."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _path(self, run_id: str) -> Path:
        safe_id = "".join(
            character for character in run_id if character.isalnum() or character in "-_"
        )
        return self.root / f"{safe_id}.json"

    def read(self, run_id: str) -> dict[str, Any]:
        path = self._path(run_id)
        if not path.exists():
            return {"run_id": run_id, "events": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, run_id: str, record: dict[str, Any]) -> None:
        path = self._path(run_id)
        with self._lock:
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
            temporary.replace(path)

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            path = self._path(run_id)
            record = (
                json.loads(path.read_text(encoding="utf-8"))
                if path.exists()
                else {"run_id": run_id, "events": []}
            )
            record.setdefault("events", []).append(event)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
            temporary.replace(path)
