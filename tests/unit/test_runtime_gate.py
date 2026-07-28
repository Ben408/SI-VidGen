"""Unit tests for the shared LLM work gate."""

import pytest

from src.runtime_gate import BusyError, WorkGate


def test_work_gate_acquire_release_and_busy_status() -> None:
    gate = WorkGate()
    assert gate.status() == {"busy": False, "holder": None}
    gate.acquire("video")
    assert gate.status() == {"busy": True, "holder": "video"}
    with pytest.raises(BusyError) as error:
        gate.acquire("ask")
    assert error.value.holder == "video"
    gate.release("video")
    assert gate.status()["busy"] is False
    gate.acquire("refresh")
    gate.release()
    assert gate.status()["holder"] is None
