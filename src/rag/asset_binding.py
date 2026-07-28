"""Bind Help image-library assets into scripts and estimate visual coverage."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from src.models import RetrievedChunk, Script, ScriptEdit
from src.rag.image_library import HelpImageAsset, HelpImageLibrary

VisualCoverage = Literal["green", "yellow", "red"]

CLASS_PRIORITY = {
    "example": 0,
    "screenshot": 1,
    "concept": 2,
    "illustration": 3,
}


def filter_retrieved_to_library(
    retrieved: list[RetrievedChunk],
    library: HelpImageLibrary | None,
) -> list[RetrievedChunk]:
    if library is None:
        return retrieved
    usable = library.usable_urls()
    if not usable:
        return [
            chunk.model_copy(update={"asset_urls": []}) for chunk in retrieved
        ]
    return [
        chunk.model_copy(
            update={"asset_urls": [url for url in chunk.asset_urls if url in usable]}
        )
        for chunk in retrieved
    ]


def assign_library_assets(
    script: Script,
    retrieved: list[RetrievedChunk],
    library: HelpImageLibrary | None,
) -> Script:
    if library is None:
        return script
    chunks_by_id = {chunk.source_id: chunk for chunk in retrieved}
    usable_by_source: dict[str, list[str]] = {}
    for chunk in retrieved:
        ranked: list[tuple[int, int, str]] = []
        for url in chunk.asset_urls:
            asset = library.get_by_url(url)
            if (
                asset is None
                or not asset.usable_for_video
                or not Path(asset.local_path).is_file()
            ):
                continue
            heading_boost = _heading_rank(chunk.heading_path, asset.heading_path)
            ranked.append(
                (heading_boost, CLASS_PRIORITY.get(asset.asset_class, 9), url)
            )
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        usable_by_source[chunk.source_id] = [url for _, _, url in ranked]

    used: set[str] = set()
    scenes = []
    for scene in script.scenes:
        selected = scene.help_asset
        if selected and _asset_available(library, selected):
            used.add(selected)
            scenes.append(scene)
            continue
        candidate = None
        scored: list[tuple[int, int, str]] = []
        for source_id in scene.source_ids:
            chunk = chunks_by_id.get(source_id)
            for url in usable_by_source.get(source_id, []):
                if url in used or not _asset_available(library, url):
                    continue
                asset = library.get_by_url(url)
                visual_boost = _heading_rank(
                    scene.visual,
                    asset.heading_path if asset else "",
                )
                class_rank = CLASS_PRIORITY.get(
                    asset.asset_class if asset else "",
                    9,
                )
                chunk_boost = _heading_rank(
                    chunk.heading_path if chunk else "",
                    asset.heading_path if asset else "",
                )
                scored.append((min(visual_boost, chunk_boost), class_rank, url))
        scored.sort(key=lambda item: (item[0], item[1], item[2]))
        if scored:
            candidate = scored[0][2]
        if candidate:
            used.add(candidate)
        scenes.append(scene.model_copy(update={"help_asset": candidate}))
    return script.model_copy(update={"scenes": scenes})


def collect_package_assets(
    script: Script,
    retrieved: list[RetrievedChunk] | None,
    library: HelpImageLibrary | None,
    *,
    max_medias: int = 14,
) -> list[HelpImageAsset]:
    if library is None:
        return []
    picks: list[HelpImageAsset] = []
    seen: set[str] = set()

    def add_url(url: str | None) -> None:
        if not url or url in seen or len(picks) >= max_medias:
            return
        asset = library.get_by_url(url)
        if asset is None or not _asset_available(library, url):
            return
        seen.add(url)
        picks.append(asset)

    for scene in script.scenes:
        add_url(scene.help_asset)

    candidates: list[HelpImageAsset] = []
    for chunk in retrieved or []:
        for url in chunk.asset_urls:
            asset = library.get_by_url(url)
            if (
                asset is None
                or asset.source_url in seen
                or not _asset_available(library, url)
            ):
                continue
            candidates.append(asset)
    candidates.sort(
        key=lambda asset: (
            CLASS_PRIORITY.get(asset.asset_class, 9),
            asset.filename,
        )
    )
    for asset in candidates:
        add_url(asset.source_url)
        if len(picks) >= max_medias:
            break
    return picks


def visual_coverage(
    script: Script,
    retrieved: list[RetrievedChunk],
    library: HelpImageLibrary | None,
) -> VisualCoverage:
    retrieved_assets = [url for chunk in retrieved for url in chunk.asset_urls]
    bound = [
        scene.help_asset
        for scene in script.scenes
        if scene.help_asset and library and _asset_available(library, scene.help_asset)
    ]
    if bound:
        return "green"
    if retrieved_assets:
        return "yellow"
    return "red"


def library_urls_for_script(
    script: Script | ScriptEdit,
    library: HelpImageLibrary | None,
) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for scene in script.scenes:
        url = scene.help_asset
        if not url or url in seen:
            continue
        if library is None or not _asset_available(library, url):
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _heading_rank(left: str, right: str) -> int:
    """Lower is better. 0 = strong overlap, 50 = none."""
    if not left or not right:
        return 40
    a = left.lower()
    b = right.lower()
    if a == b or a in b or b in a:
        return 0
    left_parts = {part.strip() for part in a.replace(">", " ").split() if part.strip()}
    right_parts = {part.strip() for part in b.replace(">", " ").split() if part.strip()}
    shared = left_parts & right_parts
    if len(shared) >= 2:
        return 5
    if shared:
        return 15
    return 50


def _asset_available(library: HelpImageLibrary, url: str) -> bool:
    asset = library.get_by_url(url)
    return bool(
        asset
        and asset.usable_for_video
        and Path(asset.local_path).is_file()
    )
