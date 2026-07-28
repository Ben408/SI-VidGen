"""Serialize local LLM-heavy work so video, Q&A, and corpus refresh do not overlap."""

from __future__ import annotations

from threading import Lock


class BusyError(RuntimeError):
    def __init__(self, holder: str) -> None:
        self.holder = holder
        super().__init__(f"Local workspace is busy with: {holder}")


class WorkGate:
    def __init__(self) -> None:
        self._lock = Lock()
        self._holder: str | None = None

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "busy": self._holder is not None,
                "holder": self._holder,
            }

    def acquire(self, holder: str) -> None:
        with self._lock:
            if self._holder is not None:
                raise BusyError(self._holder)
            self._holder = holder

    def release(self, holder: str | None = None) -> None:
        with self._lock:
            if holder is not None and self._holder not in {None, holder}:
                return
            self._holder = None
