from src.rag.chunker import HelpChunk


class PineconeVectorStore:
    """Deployment adapter boundary; activate when Pinecone is selected."""

    def upsert(self, _chunks: list[HelpChunk], _embeddings: list[list[float]]) -> None:
        raise NotImplementedError("Pinecone is deferred until deployment")

    def replace_source(
        self,
        _source_url: str,
        _chunks: list[HelpChunk],
        _embeddings: list[list[float]],
    ) -> None:
        raise NotImplementedError("Pinecone is deferred until deployment")

    def delete_source(self, _source_url: str) -> None:
        raise NotImplementedError("Pinecone is deferred until deployment")

    def query(
        self,
        _embedding: list[float],
        top_k: int = 5,
        where: dict[str, str] | None = None,
    ) -> list[dict[str, object]]:
        raise NotImplementedError("Pinecone is deferred until deployment")
