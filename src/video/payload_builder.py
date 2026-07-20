import json
from pathlib import Path

from src.models import (
    HiggsfieldExplainerPackage,
    HiggsfieldPayload,
    RetrievedChunk,
    Script,
)
from src.rag.asset_binding import collect_package_assets, library_urls_for_script
from src.rag.image_library import HelpImageLibrary

PRESERVE_VISUALS = (
    "Use the attached Sage Intacct Help screenshots as authoritative product UI. "
    "Do not restyle, redraw, or invent alternate Intacct screens."
)


def build_higgsfield_payload(
    script: Script,
    library: HelpImageLibrary | None = None,
    *,
    visual_coverage: str = "red",
    retrieved: list[RetrievedChunk] | None = None,
) -> HiggsfieldPayload:
    assets = collect_package_assets(script, retrieved, library)
    media_paths = [str(Path(asset.local_path).resolve()) for asset in assets][:14]
    if not media_paths:
        media_urls = library_urls_for_script(script, library)
        media_paths = (
            [str(path.resolve()) for path in library.resolve_local_paths(media_urls)]
            if library is not None
            else []
        )[:14]
    coverage = "green" if media_paths else visual_coverage
    return HiggsfieldPayload(
        script=script.narration,
        scenes=script.scenes,
        medias=media_paths,
        preserve_source_visuals=True,
        visual_coverage=coverage,  # type: ignore[arg-type]
    )


def build_explainer_package(
    script: Script,
    library: HelpImageLibrary | None,
    retrieved: list[RetrievedChunk] | None = None,
) -> HiggsfieldExplainerPackage:
    assets = collect_package_assets(script, retrieved, library)[:14]
    media_paths = [str(Path(asset.local_path).resolve()) for asset in assets]
    duration = estimate_duration_seconds(script.narration)
    return HiggsfieldExplainerPackage(
        prompt=_explainer_prompt(script),
        medias=media_paths,
        duration=duration,
        assets=[
            {
                "asset_id": asset.asset_id,
                "source_url": asset.source_url,
                "local_path": str(Path(asset.local_path).resolve()),
                "asset_class": asset.asset_class,
                "alt_text": asset.alt_text,
                "page_url": asset.page_url,
                "page_title": asset.page_title,
            }
            for asset in assets
        ],
    )


def write_payload(
    payload: HiggsfieldPayload,
    run_id: str,
    output_dir: Path,
    version: int | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-v{version}" if version is not None else ""
    path = output_dir / f"{run_id}{suffix}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def write_explainer_package(
    package: HiggsfieldExplainerPackage,
    run_id: str,
    output_dir: Path,
    version: int | None = None,
) -> tuple[Path, Path, Path]:
    """Write explainer JSON, medias array file, and prompt text for MCP/CLI use."""
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-v{version}" if version is not None else ""
    base = f"{run_id}{suffix}"
    package_path = output_dir / f"{base}-explainer.json"
    medias_path = output_dir / f"{base}-medias.json"
    prompt_path = output_dir / f"{base}-prompt.txt"

    package = package.model_copy(
        update={
            "medias_file": medias_path.name,
            "cli_example": (
                "higgsfield generate create video_explainer "
                f"--prompt @{prompt_path.name} --medias @{medias_path.name} "
                f"--duration {package.duration} --aspect_ratio {package.aspect_ratio}"
            ),
        }
    )
    _atomic_write_text(package_path, package.model_dump_json(indent=2))
    _atomic_write_text(medias_path, json.dumps(package.medias, indent=2))
    _atomic_write_text(prompt_path, package.prompt)
    return package_path, medias_path, prompt_path


def read_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def estimate_duration_seconds(narration: str) -> int:
    words = max(1, len(narration.split()))
    # ~150 words/minute → seconds, snapped to explainer multiples of 10.
    seconds = int(round((words / 2.5) / 10.0) * 10)
    return max(20, min(600, seconds or 20))


def _explainer_prompt(script: Script) -> str:
    scene_lines = []
    for index, scene in enumerate(script.scenes, start=1):
        asset = scene.help_asset or "textual UI description only"
        scene_lines.append(
            f"{index}. Action: {scene.action}\n"
            f"   Visual: {scene.visual}\n"
            f"   Voiceover: {scene.voiceover}\n"
            f"   Help asset: {asset}"
        )
    return (
        f"{script.title}\n\n"
        f"{PRESERVE_VISUALS}\n\n"
        f"Narration:\n{script.narration}\n\n"
        "Scenes:\n" + "\n".join(scene_lines)
    )


def _atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
