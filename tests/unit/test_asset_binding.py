"""Unit tests for heading-aware Help asset binding."""

from pathlib import Path

from src.models import RetrievedChunk, Scene, Script, SourceReference
from src.rag.asset_binding import assign_library_assets
from src.rag.image_library import HelpImageLibrary


def test_assign_library_assets_prefers_heading_match(tmp_path: Path) -> None:
    files = tmp_path / "files"
    files.mkdir()
    match_path = files / "match.png"
    other_path = files / "other.png"
    match_path.write_bytes(b"png")
    other_path.write_bytes(b"png")

    catalog = {
        "version": 1,
        "library_dir": str(tmp_path),
        "assets": [
            {
                "asset_id": "a1",
                "source_url": "https://example/help/match.png",
                "local_path": str(match_path),
                "content_sha256": "x",
                "page_url": "https://example/help/page.htm",
                "page_title": "Import",
                "heading_path": "Prepare the CSV",
                "alt_text": "CSV header example",
                "caption": "",
                "module": "General_Ledger",
                "asset_class": "example",
                "filename": "EXAMPLE-match.png",
                "usable_for_video": True,
            },
            {
                "asset_id": "a2",
                "source_url": "https://example/help/other.png",
                "local_path": str(other_path),
                "content_sha256": "y",
                "page_url": "https://example/help/page.htm",
                "page_title": "Import",
                "heading_path": "Unrelated appendix",
                "alt_text": "Other image",
                "caption": "",
                "module": "General_Ledger",
                "asset_class": "example",
                "filename": "EXAMPLE-other.png",
                "usable_for_video": True,
            },
        ],
    }
    import json

    (tmp_path / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    library = HelpImageLibrary(tmp_path)

    chunk = RetrievedChunk(
        source_id="c1",
        source_url="https://example/help/page.htm",
        title="Import",
        heading_path="Import > Prepare the CSV",
        score=0.9,
        text="Prepare the CSV file.",
        asset_urls=[
            "https://example/help/other.png",
            "https://example/help/match.png",
        ],
    )
    script = Script(
        title="Import journals",
        narration="Import journals from CSV.",
        scenes=[
            Scene(
                action="Prepare the CSV",
                visual="Show CSV header layout for Prepare the CSV",
                voiceover="Prepare the CSV.",
                help_asset=None,
                source_ids=["c1"],
            )
        ],
        sources=[
            SourceReference(
                source_id="c1",
                source_url=chunk.source_url,
                title=chunk.title,
                heading_path=chunk.heading_path,
                score=chunk.score,
            )
        ],
        generation_model="test",
    )
    bound = assign_library_assets(script, [chunk], library)
    assert bound.scenes[0].help_asset == "https://example/help/match.png"
