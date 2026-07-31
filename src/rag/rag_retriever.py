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
    language: str | None = None,
) -> list[RetrievedChunk]:
    if not query.strip():
        raise ValueError("Retrieval query cannot be empty")
    embedding = llm.embed(query)
    where = {"language": language} if language else None
    try:
        results = store.query(embedding, top_k=top_k, where=where)
    except Exception:
        # Older Chroma rows may lack language metadata — retry unfiltered then post-filter.
        results = store.query(embedding, top_k=max(top_k * 3, 15), where=None)
    # Chroma where-filter can return [] (no exception) when language metadata is missing.
    if where and not results:
        results = store.query(embedding, top_k=max(top_k * 3, 15), where=None)
    chunks: list[RetrievedChunk] = []
    for result in results:
        score = float(result["score"])
        if score < min_score:
            continue
        metadata = result["metadata"]
        if not isinstance(metadata, dict):
            continue
        meta_lang = str(metadata.get("language") or "")
        if language and meta_lang and meta_lang != language:
            continue
        if language and not meta_lang:
            # Legacy EN-only index: accept only when asking for English.
            from src.rag.locales import locale_from_help_url

            inferred = locale_from_help_url(str(metadata.get("source_url", ""))) or "en_US"
            if inferred != language:
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
        if len(chunks) >= top_k:
            break
    if not chunks:
        raise InsufficientEvidenceError("No indexed help content met the relevance threshold")
    return chunks
