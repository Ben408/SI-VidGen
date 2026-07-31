import pytest

from src.rag.rag_retriever import InsufficientEvidenceError, retrieve_help_content
from tests.fakes import FakePipelineLLM, FakeVectorStore


def test_maps_vector_results_to_retrieved_chunks() -> None:
    chunks = retrieve_help_content(
        "correct journal",
        FakeVectorStore(score=0.85),
        FakePipelineLLM(),
        top_k=4,
        min_score=0.2,
    )

    assert chunks[0].source_id == "chunk-1"
    assert chunks[0].score == 0.85
    assert "total debits" in chunks[0].text


def test_rejects_low_confidence_retrieval() -> None:
    with pytest.raises(InsufficientEvidenceError):
        retrieve_help_content(
            "unrelated question",
            FakeVectorStore(score=0.05),
            FakePipelineLLM(),
            min_score=0.2,
        )


def test_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        retrieve_help_content("", FakeVectorStore(), FakePipelineLLM())


def test_falls_back_when_language_where_filter_empty() -> None:
    """Legacy Chroma rows often lack language metadata; where=language returns []."""

    class EmptyThenHitsStore:
        def __init__(self) -> None:
            self.calls: list[dict[str, str] | None] = []

        def query(
            self,
            embedding: list[float],
            top_k: int = 5,
            where: dict[str, str] | None = None,
        ) -> list[dict[str, object]]:
            self.calls.append(where)
            if where:
                return []
            return FakeVectorStore(score=0.9).query(embedding, top_k=top_k, where=None)

    store = EmptyThenHitsStore()
    chunks = retrieve_help_content(
        "vendor aging",
        store,  # type: ignore[arg-type]
        FakePipelineLLM(),
        language="en_US",
        min_score=0.2,
    )
    assert chunks
    assert store.calls[0] == {"language": "en_US"}
    assert store.calls[1] is None
