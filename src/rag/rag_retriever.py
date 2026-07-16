from src.llm.client import OllamaClient
from src.rag.vector_store import VectorStore


def retrieve_help_content(
    query: str,
    store: VectorStore,
    llm: OllamaClient,
    top_k: int = 5,
) -> list[dict[str, object]]:
    if not query.strip():
        raise ValueError("Retrieval query cannot be empty")
    embedding = llm.embed(query)
    return store.query(embedding, top_k=top_k)
