import hashlib
import math
from typing import Protocol


class Embedder(Protocol):
    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


class DeterministicStubEmbedder:
    """Stable, offline test double. It is not suitable for semantic retrieval."""

    def __init__(self, dimensions: int = 16) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [
            (digest[index % len(digest)] / 127.5) - 1
            for index in range(self.dimensions)
        ]
        magnitude = math.sqrt(sum(value * value for value in values)) or 1
        return [value / magnitude for value in values]
