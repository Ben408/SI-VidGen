"""Live smoke: CSV journal-import sample → library medias → Higgsfield explainer package.

Does not call Higgsfield generation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from config.settings import get_settings
from src.classifier.classify_issue import classify_issue
from src.intake.intake_handler import normalize_issue
from src.llm.client import OllamaClient
from src.models import IssueInput
from src.rag.asset_binding import (
    assign_library_assets,
    filter_retrieved_to_library,
    visual_coverage,
)
from src.rag.chroma_store import ChromaVectorStore
from src.rag.image_library import HelpImageLibrary
from src.rag.rag_retriever import retrieve_help_content
from src.scriptgen.script_builder import build_script
from src.scriptgen.script_writer import write_script
from src.video.payload_builder import (
    build_explainer_package,
    build_higgsfield_payload,
    write_explainer_package,
    write_payload,
)

SAMPLE_TEXT = (
    "A business user needs to import General Ledger journal entries from a CSV file. "
    "Create a short instructional video showing how to prepare the CSV with journal "
    "header and line-item rows, how entries are grouped by date, and how to upload the "
    "prepared file into Sage Intacct. Use the official Help examples of the CSV layout."
)


def main() -> int:
    settings = get_settings()
    library_dir = settings.help_assets_dir
    if not (library_dir / "catalog.json").is_file():
        print(f"Missing image library catalog at {library_dir / 'catalog.json'}", file=sys.stderr)
        print("Run: python -m src.rag.build_image_library", file=sys.stderr)
        return 2

    library = HelpImageLibrary(library_dir)
    coverage = library.coverage()
    print("library_coverage", json.dumps(coverage, indent=2))

    store = ChromaVectorStore(settings.vector_store_dir)
    if store.count() < 1:
        print("No indexed chunks available", file=sys.stderr)
        return 2

    llm = OllamaClient(
        base_url=settings.ollama_base_url,
        chat_model=settings.ollama_chat_model,
        fallback_model=settings.ollama_fallback_model,
        embed_model=settings.ollama_embed_model,
        timeout_seconds=180,
    )
    issue = normalize_issue(
        IssueInput(text=SAMPLE_TEXT, module="General Ledger")
    )
    classification = classify_issue(issue, llm)
    print("classification", classification.model_dump_json())

    retrieved = retrieve_help_content(
        classification.search_query,
        store,
        llm,
        top_k=settings.rag_top_k,
        min_score=settings.rag_min_score,
    )
    retrieved = filter_retrieved_to_library(retrieved, library)
    print(
        "retrieved",
        json.dumps(
            [
                {
                    "source_id": chunk.source_id,
                    "title": chunk.title,
                    "score": chunk.score,
                    "url": chunk.source_url,
                    "asset_urls": chunk.asset_urls,
                }
                for chunk in retrieved
            ],
            indent=2,
        ),
    )
    if not any(chunk.asset_urls for chunk in retrieved):
        print("No library assets on retrieved sources", file=sys.stderr)
        return 3

    script = build_script(issue, classification, retrieved, llm)
    script = assign_library_assets(script, retrieved, library)
    coverage_flag = visual_coverage(script, retrieved, library)
    run_id = "live-image-library"
    script_path = write_script(script, run_id, settings.scripts_dir, version=1)
    package = build_explainer_package(script, library, retrieved)
    package_path, medias_path, prompt_path = write_explainer_package(
        package, run_id, settings.payloads_dir, version=1
    )
    payload = build_higgsfield_payload(
        script, library, visual_coverage=coverage_flag, retrieved=retrieved
    ).model_copy(
        update={
            "explainer_package_path": str(package_path),
            "medias": package.medias,
            "visual_coverage": "green" if package.medias else coverage_flag,
        }
    )
    payload_path = write_payload(payload, run_id, settings.payloads_dir, version=1)

    missing = [path for path in package.medias if not Path(path).is_file()]
    print(f"script_path={script_path}")
    print(f"payload_path={payload_path}")
    print(f"explainer_package_path={package_path}")
    print(f"medias_path={medias_path}")
    print(f"prompt_path={prompt_path}")
    print(f"visual_coverage={payload.visual_coverage}")
    print(f"media_count={len(package.medias)}")
    print(f"cli_example={package.cli_example}")
    print(
        "bound_assets",
        json.dumps(
            [scene.help_asset for scene in script.scenes if scene.help_asset],
            indent=2,
        ),
    )
    if missing:
        print(f"Missing media files: {missing}", file=sys.stderr)
        return 4
    if not package.medias:
        print("Explainer package has no medias", file=sys.stderr)
        return 5
    if len(package.medias) < 3:
        print(
            f"Expected multiple EXAMPLE medias, got {len(package.medias)}",
            file=sys.stderr,
        )
        return 8
    if payload.visual_coverage != "green":
        print("Expected green visual coverage", file=sys.stderr)
        return 6
    if package.job_set_type != "video_explainer":
        print("Unexpected job_set_type", file=sys.stderr)
        return 7
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
