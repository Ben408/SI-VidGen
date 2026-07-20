from pathlib import Path

from src.models import Scene, Script
from src.rag.image_library import HelpImageAsset, HelpImageLibrary
from src.video.payload_builder import (
    build_explainer_package,
    build_higgsfield_payload,
    read_payload,
    write_explainer_package,
    write_payload,
)


def _library_with_asset(tmp_path: Path, url: str) -> HelpImageLibrary:
    files = tmp_path / "files"
    files.mkdir(parents=True)
    local = files / "shot.png"
    local.write_bytes(b"png-bytes")
    catalog = {
        "version": 1,
        "library_dir": str(tmp_path),
        "assets": [
            HelpImageAsset(
                asset_id="abc",
                source_url=url,
                local_path=str(local),
                content_sha256="x",
                page_url="https://example.com/page.htm",
                page_title="Import",
                heading_path="Import",
                alt_text="CSV example",
                caption="",
                module="General_Ledger",
                asset_class="example",
                filename="EXAMPLE.png",
                usable_for_video=True,
            ).__dict__
        ],
    }
    import json

    (tmp_path / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    return HelpImageLibrary(tmp_path)


def test_builds_and_writes_payload(tmp_path) -> None:
    script = Script(
        title="Draft",
        narration="Narration",
        scenes=[
            Scene(
                action="Open",
                visual="Existing help asset",
                voiceover="Open it",
                source_ids=["source-1"],
            )
        ],
        sources=[],
        generation_model="fake",
    )

    payload = build_higgsfield_payload(script)
    path = write_payload(payload, "run-test", tmp_path)

    assert path.name == "run-test.json"
    assert read_payload(path)["script"] == "Narration"
    assert read_payload(path)["captions"] is True
    assert read_payload(path)["medias"] == []


def test_explainer_package_includes_local_medias(tmp_path) -> None:
    asset_url = "https://www.intacct.com/ia/docs/en_US/help_action/img/EXAMPLE.png"
    library = _library_with_asset(tmp_path / "lib", asset_url)
    script = Script(
        title="Import GL journals from CSV",
        narration="Prepare the CSV then import the journal entries into General Ledger.",
        scenes=[
            Scene(
                action="Prepare CSV",
                visual="Show header and line item example",
                voiceover="Prepare the CSV with header and line items.",
                help_asset=asset_url,
                source_ids=["source-1"],
            )
        ],
        sources=[],
        generation_model="fake",
    )

    package = build_explainer_package(script, library)
    package_path, medias_path, prompt_path = write_explainer_package(
        package, "run-media", tmp_path / "out", version=1
    )
    payload = build_higgsfield_payload(script, library, visual_coverage="yellow")
    payload_path = write_payload(payload, "run-media", tmp_path / "out", version=1)

    assert package.job_set_type == "video_explainer"
    assert len(package.medias) == 1
    assert Path(package.medias[0]).is_file()
    assert package.duration >= 20
    assert package_path.is_file()
    assert medias_path.is_file()
    assert prompt_path.is_file()
    assert "Do not restyle" in prompt_path.read_text(encoding="utf-8")
    written = read_payload(payload_path)
    assert written["visual_coverage"] == "green"
    assert written["medias"] == package.medias
