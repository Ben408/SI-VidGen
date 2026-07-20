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
