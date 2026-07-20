from src.llm.client import OllamaClient
from src.models import RetrievedChunk
from src.rag.vector_store import VectorStore


class InsufficientEvidenceError(RuntimeError):
    pass


def retrieve_help_content(
    query: str,
    store: VectorStore,
    llm: OllamaClient,
    top_k: int = 5,
    min_score: float = 0.2,
) -> list[RetrievedChunk]:
    if not query.strip():
        raise ValueError("Retrieval query cannot be empty")
    embedding = llm.embed(query)
    results = store.query(embedding, top_k=top_k)
    chunks: list[RetrievedChunk] = []
    for result in results:
        score = float(result["score"])
        if score < min_score:
            continue
        metadata = result["metadata"]
        if not isinstance(metadata, dict):
            continue
        chunks.append(
            RetrievedChunk(
                source_id=str(result["id"]),
                text=str(result["document"]),
                source_url=str(metadata["source_url"]),
                title=str(metadata["title"]),
                heading_path=str(metadata.get("heading_path", "")),
                score=score,
                asset_urls=[
                    asset for asset in str(metadata.get("asset_urls", "")).split("|") if asset
                ],
            )
        )
    if not chunks:
        raise InsufficientEvidenceError("No indexed help content met the relevance threshold")
    return chunks
