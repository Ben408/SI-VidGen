class HiggsfieldClient:
    """V0.1 boundary; implementation awaits account access and API contract."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def generate(self, _payload: dict[str, object]) -> dict[str, object]:
        raise NotImplementedError("Higgsfield generation begins in V0.1")
