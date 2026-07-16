from typing import Protocol

from src.rag.chunker import HelpChunk


class VectorStore(Protocol):
    def upsert(self, chunks: list[HelpChunk], embeddings: list[list[float]]) -> None: ...

    def query(
        self,
        embedding: list[float],
        top_k: int = 5,
        where: dict[str, str] | None = None,
    ) -> list[dict[str, object]]: ...

    def replace_source(
        self,
        source_url: str,
        chunks: list[HelpChunk],
        embeddings: list[list[float]],
    ) -> None: ...

    def delete_source(self, source_url: str) -> None: ...
