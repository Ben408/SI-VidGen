"""Chunk metadata includes language."""

from src.rag.chunker import chunk_xhtml


def test_chunk_xhtml_sets_language() -> None:
    xhtml = "<html><body><h1>Bienvenue</h1><p>Créer une écriture.</p></body></html>"
    chunks = chunk_xhtml(
        xhtml,
        "https://www.intacct.com/ia/docs/fr_FR/help_action/t.htm",
        "hash",
        language="fr_FR",
    )
    assert chunks
    assert chunks[0].language == "fr_FR"
    assert chunks[0].metadata()["language"] == "fr_FR"
