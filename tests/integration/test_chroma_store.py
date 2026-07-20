from src.rag.chroma_store import ChromaVectorStore
from src.rag.chunker import HelpChunk


def make_chunk(chunk_id: str, text: str, source_url: str) -> HelpChunk:
    return HelpChunk(
        chunk_id=chunk_id,
        text=text,
        source_url=source_url,
        source_hash="hash",
        title="Title",
        heading_path="Heading",
        asset_urls=(),
        token_estimate=10,
    )


def test_chroma_upsert_query_and_source_replacement(tmp_path) -> None:
    store = ChromaVectorStore(tmp_path)
    source = "https://example/topic.htm"
    first = make_chunk("first", "first text", source)
    second = make_chunk("second", "second text", source)

    store.upsert([first], [[1.0, 0.0]])
    result = store.query([1.0, 0.0], top_k=1)

    assert store.count() == 1
    assert result[0]["id"] == "first"
    assert result[0]["score"] > 0.99

    store.replace_source(source, [second], [[0.0, 1.0]])

    assert store.count() == 1
    assert store.query([0.0, 1.0], top_k=1)[0]["id"] == "second"


def test_chroma_upsert_deduplicates_ids_in_batch(tmp_path) -> None:
    store = ChromaVectorStore(tmp_path)
    source = "https://example/dup.htm"
    first = make_chunk("same-id", "first text", source)
    second = make_chunk("same-id", "second text", source)

    store.upsert([first, second], [[1.0, 0.0], [0.0, 1.0]])

    assert store.count() == 2
    ids = {store.query([1.0, 0.0], top_k=2)[0]["id"], store.query([0.0, 1.0], top_k=2)[0]["id"]}
    assert "same-id" in ids
    assert any(str(item_id).startswith("same-id:") for item_id in ids)
