"""CLI: build Help Center image library from the local XHTML cache."""

from __future__ import annotations

import argparse
import json

from config.settings import get_settings
from src.rag.image_library import build_image_library
from src.rag.locales import assets_dir_for_locale, cache_dir_for_locale, parse_locales


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Harvest and catalog usable Help Center images for video payloads."
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Catalog only; do not download image bytes.",
    )
    parser.add_argument(
        "--max-downloads",
        type=int,
        default=None,
        help="Optional cap on newly downloaded assets (for smoke runs).",
    )
    parser.add_argument(
        "--locales",
        default=None,
        help="Comma list or 'all' (default: HELP_LOCALES / en_US).",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    locales = parse_locales(args.locales) if args.locales else parse_locales(settings.help_locales)
    exit_code = 0
    reports: list[dict[str, object]] = []
    for locale in locales:
        cache_dir = cache_dir_for_locale(settings.help_cache_dir, locale)
        library_dir = assets_dir_for_locale(settings.help_assets_dir, locale)
        if not (cache_dir / "manifest.json").is_file():
            reports.append(
                {
                    "locale": locale,
                    "skipped": True,
                    "reason": f"missing cache manifest at {cache_dir}",
                }
            )
            continue
        library_dir.mkdir(parents=True, exist_ok=True)
        summary = build_image_library(
            cache_dir,
            library_dir,
            download=not args.no_download,
            max_downloads=args.max_downloads,
        )
        reports.append(
            {
                "locale": locale,
                "library_dir": str(library_dir),
                "cache_dir": str(cache_dir),
                "pages_scanned": summary.pages_scanned,
                "pages_with_usable_assets": summary.pages_with_usable_assets,
                "assets_discovered": summary.assets_discovered,
                "assets_usable": summary.assets_usable,
                "assets_downloaded": summary.assets_downloaded,
                "assets_skipped_noise": summary.assets_skipped_noise,
                "download_errors": summary.download_errors,
                "by_class": summary.by_class,
            }
        )
        if summary.download_errors and not args.no_download:
            exit_code = 1
    print(json.dumps({"locales": reports}, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
