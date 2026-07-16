from pathlib import Path

from src.rag.chunker import chunk_xhtml

FIXTURE = Path("data/help_fixtures/gl_posting_error.xhtml")


def test_chunker_preserves_steps_headings_and_existing_assets() -> None:
    chunks = chunk_xhtml(
        FIXTURE.read_text(encoding="utf-8"),
        source_url=(
            "https://www.intacct.com/ia/docs/en_US/help_action/"
            "General_Ledger/gl_posting_error.htm"
        ),
        source_hash="fixture-hash",
        target_tokens=80,
        max_tokens=120,
    )

    combined = "\n".join(chunk.text for chunk in chunks)
    assert "Navigation content" not in combined
    assert "- Compare total debits and total credits." in combined
    assert any("Correct the entry" in chunk.heading_path for chunk in chunks)
    assert chunks[0].asset_urls == (
        "https://www.intacct.com/ia/docs/en_US/help_action/images/gl-journal-entry.png",
    )
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_chunker_rejects_invalid_token_range() -> None:
    try:
        chunk_xhtml("<html />", "https://example", "hash", target_tokens=20, max_tokens=10)
    except ValueError as error:
        assert "target_tokens" in str(error)
    else:
        raise AssertionError("Expected invalid token range to fail")
