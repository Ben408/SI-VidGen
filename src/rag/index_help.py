import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from config.settings import Settings, get_settings
from src.llm.client import OllamaClient
from src.rag.chroma_store import ChromaVectorStore
from src.rag.chunker import chunk_cached_document
from src.rag.locales import (
    HELP_LOCALES,
    cache_dir_for_locale,
    locale_spec,
    parse_locales,
)
from src.rag.xhtml_ingest import XhtmlCrawler, XhtmlDocument


@dataclass
class IndexSummary:
    pages_crawled: int = 0
    pages_indexed: int = 0
    pages_unchanged: int = 0
    pages_deleted: int = 0
    chunks_indexed: int = 0
    crawl_errors: int = 0
    pages_skipped: int = 0
    index_errors: int = 0
    complete: bool = False
    locales: list[str] = field(default_factory=list)
    by_locale: dict[str, dict[str, int]] = field(default_factory=dict)


def build_index(
    max_pages: int | None = 10,
    delete_stale: bool = False,
    *,
    from_cache: bool = False,
    reset_store: bool = False,
    locales: list[str] | None = None,
    settings: Settings | None = None,
    crawler: XhtmlCrawler | None = None,
    store: ChromaVectorStore | None = None,
    llm: OllamaClient | None = None,
) -> IndexSummary:
    """Crawl/index one or more Help locales into the shared Chroma store.

    When ``crawler`` is passed (tests), behavior matches the legacy single-locale path
    using ``settings.intacct_help_*`` / ``help_cache_dir``.
    """
    settings = settings or get_settings()
    if reset_store:
        _reset_vector_store(settings.vector_store_dir)
    store = store or ChromaVectorStore(settings.vector_store_dir)
    llm = llm or OllamaClient(
        base_url=settings.ollama_base_url,
        chat_model=settings.ollama_chat_model,
        embed_model=settings.ollama_embed_model,
    )

    if crawler is not None:
        return _build_index_single(
            max_pages=max_pages,
            delete_stale=delete_stale,
            from_cache=from_cache,
            settings=settings,
            crawler=crawler,
            store=store,
            llm=llm,
            locale="en_US",
            cache_dir=settings.help_cache_dir,
            start_url=settings.intacct_help_start_url,
            allowed_prefix=settings.intacct_help_allowed_prefix,
        )

    selected = locales or parse_locales(settings.help_locales)
    combined = IndexSummary(locales=list(selected))
    for locale in selected:
        spec = locale_spec(locale)
        cache_dir = cache_dir_for_locale(settings.help_cache_dir, locale)
        cache_dir.mkdir(parents=True, exist_ok=True)
        part = _build_index_single(
            max_pages=max_pages,
            delete_stale=delete_stale,
            from_cache=from_cache,
            settings=settings,
            crawler=None,
            store=store,
            llm=llm,
            locale=locale,
            cache_dir=cache_dir,
            start_url=spec.start_url,
            allowed_prefix=spec.allowed_prefix,
        )
        combined.pages_crawled += part.pages_crawled
        combined.pages_indexed += part.pages_indexed
        combined.pages_unchanged += part.pages_unchanged
        combined.pages_deleted += part.pages_deleted
        combined.chunks_indexed += part.chunks_indexed
        combined.crawl_errors += part.crawl_errors
        combined.pages_skipped += part.pages_skipped
        combined.index_errors += part.index_errors
        combined.by_locale[locale] = {
            "pages_crawled": part.pages_crawled,
            "pages_indexed": part.pages_indexed,
            "chunks_indexed": part.chunks_indexed,
            "crawl_errors": part.crawl_errors,
            "complete": int(part.complete),
        }
    combined.complete = bool(selected) and all(
        combined.by_locale[loc].get("complete") for loc in selected
    )
    return combined


def _build_index_single(
    *,
    max_pages: int | None,
    delete_stale: bool,
    from_cache: bool,
    settings: Settings,
    crawler: XhtmlCrawler | None,
    store: ChromaVectorStore,
    llm: OllamaClient,
    locale: str,
    cache_dir: Path,
    start_url: str,
    allowed_prefix: str,
) -> IndexSummary:
    state_path = settings.vector_store_dir / f"index_state_{locale}.json"
    # Keep legacy EN state filename for backward compatibility.
    if locale == "en_US":
        legacy = settings.vector_store_dir / "index_state.json"
        if legacy.is_file() and not state_path.is_file():
            state_path = legacy
    previous_state = _read_state(state_path)
    current_state: dict[str, str] = {}
    summary = IndexSummary(locales=[locale])

    def index_document(document: XhtmlDocument) -> None:
        summary.pages_crawled += 1
        current_state[document.url] = document.content_sha256
        if previous_state.get(document.url) == document.content_sha256:
            summary.pages_unchanged += 1
            return
        chunks = chunk_cached_document(
            cache_dir,
            document.cache_path,
            document.url,
            document.content_sha256,
            language=locale,
        )
        if not chunks:
            return
        try:
            embeddings = _embed_batches(llm, [chunk.text for chunk in chunks])
            store.replace_source(document.url, chunks, embeddings)
        except Exception as error:  # noqa: BLE001
            summary.index_errors += 1
            print(
                f"index_error locale={locale} url={document.url} "
                f"error={type(error).__name__}: {error}",
                file=sys.stderr,
                flush=True,
            )
            current_state.pop(document.url, None)
            return
        summary.pages_indexed += 1
        summary.chunks_indexed += len(chunks)
        _write_state(state_path, {**previous_state, **current_state})
        if summary.pages_indexed == 1 or summary.pages_indexed % 10 == 0:
            print(
                (
                    f"locale={locale} indexed={summary.pages_indexed} "
                    f"unchanged={summary.pages_unchanged} chunks={summary.chunks_indexed}"
                ),
                file=sys.stderr,
                flush=True,
            )

    if from_cache:
        documents = load_cached_documents(cache_dir)
        if max_pages is not None:
            documents = documents[:max_pages]
        for document in documents:
            index_document(document)
            if summary.pages_crawled == 1 or summary.pages_crawled % 25 == 0:
                _crawl_progress(locale, summary.pages_crawled, 0, document.url)
        summary.crawl_errors = 0
        summary.pages_skipped = 0
        if delete_stale and summary.index_errors == 0:
            for stale_url in set(previous_state) - set(current_state):
                store.delete_source(stale_url)
                summary.pages_deleted += 1
        else:
            current_state = {**previous_state, **current_state}
        _write_state(state_path, current_state)
        summary.complete = summary.index_errors == 0 and bool(documents)
        if summary.complete:
            _mark_manifest_complete(cache_dir)
        return summary

    active = crawler or XhtmlCrawler(
        start_url=start_url,
        allowed_prefix=allowed_prefix,
        cache_dir=cache_dir,
        delay_seconds=settings.crawl_delay_seconds,
        on_progress=lambda crawled, queued, url: _crawl_progress(locale, crawled, queued, url),
        on_document=index_document,
    )
    if crawler is None:
        active.crawl(max_pages=max_pages)
    else:
        for document in active.crawl(max_pages=max_pages):
            index_document(document)

    summary.crawl_errors = len(active.errors)
    summary.pages_skipped = len(getattr(active, "skipped", []))

    if delete_stale and not active.errors and summary.index_errors == 0:
        for stale_url in set(previous_state) - set(current_state):
            store.delete_source(stale_url)
            summary.pages_deleted += 1
    else:
        current_state = {**previous_state, **current_state}

    _write_state(state_path, current_state)
    summary.complete = max_pages is None and not active.errors and summary.index_errors == 0
    return summary


def load_cached_documents(cache_dir: Path) -> list[XhtmlDocument]:
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing help cache manifest: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents: list[XhtmlDocument] = []
    for page in payload.get("pages", []):
        cache_path = cache_dir / str(page["cache_path"])
        if not cache_path.is_file():
            continue
        documents.append(XhtmlDocument(**page))
    return documents


def _mark_manifest_complete(cache_dir: Path) -> None:
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.is_file():
        return
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["complete"] = True
    if payload.get("errors"):
        skipped = list(payload.get("skipped") or [])
        remaining_errors = []
        for error in payload["errors"]:
            if int(error.get("status_code", 0)) in {404, 410}:
                skipped.append(error)
            else:
                remaining_errors.append(error)
        payload["errors"] = remaining_errors
        payload["skipped"] = skipped
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(manifest_path)


def _reset_vector_store(vector_store_dir: Path) -> None:
    if vector_store_dir.exists():
        shutil.rmtree(vector_store_dir)
    vector_store_dir.mkdir(parents=True, exist_ok=True)


def _crawl_progress(locale: str, crawled: int, queued: int, url: str) -> None:
    if crawled == 1 or crawled % 25 == 0:
        print(
            f"locale={locale} crawled={crawled} queued={queued} url={url}",
            file=sys.stderr,
            flush=True,
        )


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
    mode.add_argument(
        "--from-cache",
        action="store_true",
        help="Rebuild the vector index from the local help cache/manifest",
    )
    parser.add_argument(
        "--reset-store",
        action="store_true",
        help="Delete the local Chroma store before indexing",
    )
    parser.add_argument(
        "--locales",
        default=None,
        help="Comma list or 'all' (default: HELP_LOCALES / en_US). Example: fr_FR,de_DE,es_ES",
    )
    args = parser.parse_args()
    selected = parse_locales(args.locales) if args.locales else None
    if selected is None:
        # allow env default; if still en-only and user passed nothing, keep settings
        selected = None
    summary = build_index(
        max_pages=None if (args.full or args.from_cache) else args.max_pages,
        delete_stale=args.full or args.from_cache,
        from_cache=args.from_cache,
        reset_store=args.reset_store,
        locales=selected if args.locales else None,
    )
    print(json.dumps(summary.__dict__, indent=2))
    if (args.full or args.from_cache) and not summary.complete:
        raise SystemExit(2)


if __name__ == "__main__":
    # Silence unused import warning for HELP_LOCALES in CLI help text contexts
    _ = HELP_LOCALES
    main()
