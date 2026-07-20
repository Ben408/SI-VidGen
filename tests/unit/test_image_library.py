import json
from pathlib import Path

from src.models import RetrievedChunk, Scene, Script
from src.rag.asset_binding import (
    assign_library_assets,
    filter_retrieved_to_library,
    visual_coverage,
)
from src.rag.image_library import HelpImageAsset, HelpImageLibrary, classify_asset, is_noise_url


def test_classifies_example_and_noise() -> None:
    assert classify_asset("EXAMPLE-import.png", "CSV layout") == ("example", True)
    assert classify_asset("ICON-check.png", "icon") == ("icon", False)
    assert is_noise_url("https://example.com/skins/Default/Stylesheets/Images/transparent.gif")
    assert not is_noise_url(
        "https://www.intacct.com/ia/docs/en_US/help_action/Resources/Images/EXAMPLE.png",
        "CSV example",
    )


def test_build_library_from_fixture_cache(tmp_path: Path) -> None:
    from src.rag.image_library import build_image_library

    cache = tmp_path / "cache"
    cache.mkdir()
    page_dir = cache / "pages"
    page_dir.mkdir()
    xhtml = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Import</title></head>
  <body>
    <h1>Import GL journal entries</h1>
    <h2>CSV layout</h2>
    <img src="../../../Resources/Images/EXAMPLE-import.png" alt="CSV header and lines"/>
    <img src="/skins/Default/Stylesheets/Images/transparent.gif" alt=""/>
  </body>
</html>
"""
    (page_dir / "import.htm").write_text(xhtml, encoding="utf-8")
    manifest = {
        "pages": [
            {
                "url": (
                    "https://www.intacct.com/ia/docs/en_US/help_action/"
                    "More/Uploading_Data/GL/import-GL-journal-entries.htm"
                ),
                "cache_path": "pages/import.htm",
            }
        ]
    }
    (cache / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    library_dir = tmp_path / "lib"
    # Create a fake download by writing file after catalog-only path:
    # use no download then plant a file for binding tests via separate helper.
    summary = build_image_library(cache, library_dir, download=False)
    assert summary.assets_discovered == 1
    assert summary.assets_usable == 1
    assert summary.assets_skipped_noise == 1
    catalog = json.loads((library_dir / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["assets"][0]["asset_class"] == "example"


def _library(tmp_path: Path, url: str) -> HelpImageLibrary:
    files = tmp_path / "files"
    files.mkdir(parents=True)
    local = files / "a.png"
    local.write_bytes(b"img")
    asset = HelpImageAsset(
        asset_id="id1",
        source_url=url,
        local_path=str(local),
        content_sha256="h",
        page_url="https://example.com/p.htm",
        page_title="Import",
        heading_path="Import",
        alt_text="example",
        caption="",
        module="More",
        asset_class="example",
        filename="EXAMPLE.png",
        usable_for_video=True,
    )
    (tmp_path / "catalog.json").write_text(
        json.dumps({"version": 1, "library_dir": str(tmp_path), "assets": [asset.__dict__]}),
        encoding="utf-8",
    )
    return HelpImageLibrary(tmp_path)


def test_assign_and_coverage(tmp_path: Path) -> None:
    url = "https://www.intacct.com/ia/docs/en_US/help_action/Resources/Images/EXAMPLE.png"
    library = _library(tmp_path, url)
    retrieved = [
        RetrievedChunk(
            source_id="s1",
            source_url="https://example.com/p.htm",
            title="Import",
            heading_path="Import",
            score=0.9,
            text="Import journals",
            asset_urls=[url, "https://example.com/noise.png"],
        )
    ]
    filtered = filter_retrieved_to_library(retrieved, library)
    assert filtered[0].asset_urls == [url]
    script = Script(
        title="t",
        narration="n",
        scenes=[
            Scene(
                action="a",
                visual="v",
                voiceover="vo",
                help_asset=None,
                source_ids=["s1"],
            )
        ],
        sources=[],
        generation_model="fake",
    )
    bound = assign_library_assets(script, filtered, library)
    assert bound.scenes[0].help_asset == url
    assert visual_coverage(bound, filtered, library) == "green"
    from src.rag.asset_binding import collect_package_assets

    package_assets = collect_package_assets(bound, filtered, library)
    assert len(package_assets) == 1
    assert package_assets[0].source_url == url
