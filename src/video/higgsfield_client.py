from typing import Protocol

from src.models import HiggsfieldPayload


class VideoGenerator(Protocol):
    @property
    def configured(self) -> bool: ...

    def generate(self, payload: HiggsfieldPayload) -> dict[str, object]: ...


class HiggsfieldClient:
    """V0.1 boundary; implementation awaits account access and API contract."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def generate(self, _payload: HiggsfieldPayload) -> dict[str, object]:
        raise NotImplementedError("Higgsfield generation begins in V0.1")
