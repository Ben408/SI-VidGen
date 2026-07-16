import math

from src.rag.embeddings import DeterministicStubEmbedder


def test_stub_embeddings_are_deterministic_and_normalized() -> None:
    embedder = DeterministicStubEmbedder(dimensions=8)

    first, repeated, different = embedder.embed_many(["same", "same", "different"])

    assert first == repeated
    assert first != different
    assert len(first) == 8
    assert math.isclose(sum(value * value for value in first), 1.0)
