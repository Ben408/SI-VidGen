"""Ingest every named corpus listed in the Help catalog.

Runs crawl/index, image library, and OKF for each catalog row so clients can
be assigned via ``corpus_id`` from the catalog file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.settings import Settings, get_settings
from src.rag.corpus_catalog import load_catalog, overlay_help_urls
from src.rag.corpus_paths import normalize_corpus_id, resolve_corpus_paths
from src.rag.image_library import build_image_library
from src.rag.index_help import IndexSummary, build_index
from src.rag.locales import assets_dir_for_locale, cache_dir_for_locale, parse_locales
from src.rag.okf.convert import convert_xhtml_cache_to_okf


def ingest_catalog(
    *,
    catalog_path: Path,
    corpus_id: str | None = None,
    max_pages: int | None = 10,
    delete_stale: bool = False,
    from_cache: bool = False,
    reset_store: bool = False,
    locales: list[str] | None = None,
    settings: Settings | None = None,
    with_assets: bool = True,
) -> list[dict[str, object]]:
    settings = settings or get_settings()
    entries = load_catalog(catalog_path)
    wanted = normalize_corpus_id(corpus_id)
    if wanted is not None:
        entries = [item for item in entries if item.corpus_id == wanted]
        if not entries:
            raise ValueError(f"corpus_id {corpus_id!r} is not in catalog {catalog_path}")
    if not entries:
        raise ValueError(f"Corpus catalog is empty: {catalog_path}")

    reports: list[dict[str, object]] = []
    selected = locales or parse_locales(settings.help_locales)
    for entry in entries:
        crawl_settings = overlay_help_urls(
            settings, entry.start_url, entry.allowed_prefix
        ).model_copy(update={"corpus_catalog_path": Path(catalog_path)})
        index_summary: IndexSummary = build_index(
            max_pages=max_pages,
            delete_stale=delete_stale,
            from_cache=from_cache,
            reset_store=reset_store,
            locales=selected,
            corpus_id=entry.corpus_id,
            settings=crawl_settings,
        )
        report: dict[str, object] = {
            "corpus_id": entry.corpus_id,
            "start_url": entry.start_url,
            "allowed_prefix": entry.allowed_prefix,
            "index": index_summary.__dict__,
        }
        if with_assets:
            paths = resolve_corpus_paths(crawl_settings, entry.corpus_id)
            paths.ensure()
            library_reports: list[dict[str, object]] = []
            for locale in selected:
                cache_dir = cache_dir_for_locale(paths.help_cache_dir, locale)
                library_dir = assets_dir_for_locale(paths.help_assets_dir, locale)
                if not (cache_dir / "manifest.json").is_file():
                    continue
                library_dir.mkdir(parents=True, exist_ok=True)
                library_summary = build_image_library(
                    cache_dir,
                    library_dir,
                    download=True,
                )
                library_reports.append(
                    {
                        "locale": locale,
                        "pages_scanned": library_summary.pages_scanned,
                        "assets_usable": library_summary.assets_usable,
                        "assets_downloaded": library_summary.assets_downloaded,
                        "download_errors": library_summary.download_errors,
                    }
                )
            report["image_library"] = library_reports
            okf_cache = cache_dir_for_locale(paths.help_cache_dir, "en_US")
            okf_library = assets_dir_for_locale(paths.help_assets_dir, "en_US")
            if (okf_cache / "manifest.json").is_file():
                okf_summary = convert_xhtml_cache_to_okf(
                    okf_cache,
                    paths.okf_dir,
                    library_dir=okf_library,
                )
                report["okf"] = {
                    "pages_converted": okf_summary.pages_converted,
                    "topics": okf_summary.topics,
                    "error_count": len(okf_summary.errors),
                }
        reports.append(report)
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest every named Help corpus from a catalog file "
            "(start_url, allowed_prefix, corpus_id)."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Page cap per corpus (default: 10). Ignored with --full.",
    )
    mode.add_argument(
        "--full",
        action="store_true",
        help="Full crawl per catalog row; delete stale indexed pages",
    )
    mode.add_argument(
        "--from-cache",
        action="store_true",
        help="Rebuild indexes from existing Help caches",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help="Catalog path (default: CORPUS_CATALOG_PATH / config/corpus_catalog.txt)",
    )
    parser.add_argument(
        "--corpus-id",
        default=None,
        help="Ingest a single catalog row instead of every row",
    )
    parser.add_argument(
        "--reset-store",
        action="store_true",
        help="Delete each corpus Chroma store before indexing",
    )
    parser.add_argument(
        "--locales",
        default=None,
        help="Comma list or 'all' (default: HELP_LOCALES)",
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="Skip image library and OKF (same as index_help --catalog)",
    )
    args = parser.parse_args()
    settings = get_settings()
    catalog_file = (
        Path(args.catalog) if args.catalog else Path(settings.corpus_catalog_path)
    )
    selected = parse_locales(args.locales) if args.locales else None
    reports = ingest_catalog(
        catalog_path=catalog_file,
        corpus_id=args.corpus_id,
        max_pages=None if (args.full or args.from_cache) else args.max_pages,
        delete_stale=args.full or args.from_cache,
        from_cache=args.from_cache,
        reset_store=args.reset_store,
        locales=selected,
        settings=settings,
        with_assets=not args.index_only,
    )
    print(json.dumps(reports, indent=2, default=str))
    if args.full or args.from_cache:
        incomplete = [
            item["corpus_id"]
            for item in reports
            if not (item.get("index") or {}).get("complete")
        ]
        if incomplete:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
