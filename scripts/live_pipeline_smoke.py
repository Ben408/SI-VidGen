"""Live smoke against the local Ollama + current Chroma index.

Does not call Higgsfield video generation.
"""

from __future__ import annotations

import json
import sys

from config.settings import get_settings
from src.classifier.classify_issue import classify_issue
from src.intake.intake_handler import normalize_issue
from src.llm.client import OllamaClient
from src.models import IssueInput
from src.rag.chroma_store import ChromaVectorStore
from src.rag.rag_retriever import retrieve_help_content
from src.scriptgen.script_builder import build_script
from src.scriptgen.script_writer import write_script
from src.video.payload_builder import build_higgsfield_payload, write_payload


def main() -> int:
    settings = get_settings()
    store = ChromaVectorStore(settings.vector_store_dir)
    count = store.count()
    print(f"vector_store_chunks={count}")
    if count < 1:
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
        IssueInput(
            text=(
                "My General Ledger journal entry will not post because it is "
                "unbalanced. How do I correct the totals?"
            ),
            module="General Ledger",
        )
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
    print(
        "retrieved",
        json.dumps(
            [
                {
                    "source_id": chunk.source_id,
                    "title": chunk.title,
                    "score": chunk.score,
                    "url": chunk.source_url,
                }
                for chunk in retrieved
            ],
            indent=2,
        ),
    )
    script = build_script(issue, classification, retrieved, llm)
    script_path = write_script(script, "live-smoke", settings.scripts_dir)
    payload = build_higgsfield_payload(script)
    payload_path = write_payload(payload, "live-smoke", settings.payloads_dir)
    print(f"script_path={script_path}")
    print(f"payload_path={payload_path}")
    print(f"scenes={len(script.scenes)} sources={len(script.sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
