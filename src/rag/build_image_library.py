"""CLI: build Help Center image library from the local XHTML cache."""

from __future__ import annotations

import argparse
import json

from config.settings import get_settings
from src.rag.image_library import build_image_library


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
    args = parser.parse_args(argv)
    settings = get_settings()
    summary = build_image_library(
        settings.help_cache_dir,
        settings.help_assets_dir,
        download=not args.no_download,
        max_downloads=args.max_downloads,
    )
    print(
        json.dumps(
            {
                "library_dir": str(settings.help_assets_dir),
                "pages_scanned": summary.pages_scanned,
                "pages_with_usable_assets": summary.pages_with_usable_assets,
                "assets_discovered": summary.assets_discovered,
                "assets_usable": summary.assets_usable,
                "assets_downloaded": summary.assets_downloaded,
                "assets_skipped_noise": summary.assets_skipped_noise,
                "download_errors": summary.download_errors,
                "by_class": summary.by_class,
            },
            indent=2,
        )
    )
    return 0 if summary.download_errors == 0 or args.no_download else 1


if __name__ == "__main__":
    raise SystemExit(main())
