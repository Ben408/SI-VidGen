import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from config.settings import get_settings
from src.llm.client import OllamaClient
from src.rag.chroma_store import ChromaVectorStore
from src.rag.chunker import chunk_cached_document
from src.rag.xhtml_ingest import XhtmlCrawler


@dataclass
class IndexSummary:
    pages_crawled: int = 0
    pages_indexed: int = 0
    pages_unchanged: int = 0
    pages_deleted: int = 0
    chunks_indexed: int = 0


def build_index(max_pages: int | None = 10, delete_stale: bool = False) -> IndexSummary:
    settings = get_settings()
    crawler = XhtmlCrawler(
        start_url=settings.intacct_help_start_url,
        allowed_prefix=settings.intacct_help_allowed_prefix,
        cache_dir=settings.help_cache_dir,
        delay_seconds=settings.crawl_delay_seconds,
    )
    documents = crawler.crawl(max_pages=max_pages)
    store = ChromaVectorStore(settings.vector_store_dir)
    llm = OllamaClient(
        base_url=settings.ollama_base_url,
        chat_model=settings.ollama_chat_model,
        embed_model=settings.ollama_embed_model,
    )
    state_path = settings.vector_store_dir / "index_state.json"
    previous_state = _read_state(state_path)
    current_state: dict[str, str] = {}
    summary = IndexSummary(pages_crawled=len(documents))

    for document in documents:
        current_state[document.url] = document.content_sha256
        if previous_state.get(document.url) == document.content_sha256:
            summary.pages_unchanged += 1
            continue
        chunks = chunk_cached_document(
            settings.help_cache_dir,
            document.cache_path,
            document.url,
            document.content_sha256,
        )
        embeddings = _embed_batches(llm, [chunk.text for chunk in chunks])
        store.replace_source(document.url, chunks, embeddings)
        summary.pages_indexed += 1
        summary.chunks_indexed += len(chunks)

    if delete_stale:
        for stale_url in set(previous_state) - set(current_state):
            store.delete_source(stale_url)
            summary.pages_deleted += 1
    else:
        current_state = {**previous_state, **current_state}

    _write_state(state_path, current_state)
    return summary


def _embed_batches(
    llm: OllamaClient,
    texts: list[str],
    batch_size: int = 32,
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for index in range(0, len(texts), batch_size):
        embeddings.extend(llm.embed_many(texts[index : index + batch_size]))
    return embeddings


def _read_state(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl and index Intacct Help XHTML")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Page cap for a safe incremental/development run (default: 10)",
    )
    mode.add_argument(
        "--full",
        action="store_true",
        help="Crawl the full allowed scope and delete stale indexed pages",
    )
    args = parser.parse_args()
    summary = build_index(
        max_pages=None if args.full else args.max_pages,
        delete_stale=args.full,
    )
    print(json.dumps(summary.__dict__, indent=2))


if __name__ == "__main__":
    main()
