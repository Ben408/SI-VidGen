"""CLI: convert local Help XHTML cache into an OKF bundle under data/okf/."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.settings import get_settings
from src.rag.okf.convert import convert_xhtml_cache_to_okf


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert Flare-published Help XHTML cache into a rules-only OKF bundle. "
            "Images are referenced from data/help_assets/ (not copied)."
        )
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional page cap for smoke conversion",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Override Help XHTML cache directory",
    )
    parser.add_argument(
        "--okf-dir",
        type=str,
        default=None,
        help="Override OKF output directory",
    )
    parser.add_argument(
        "--no-library",
        action="store_true",
        help="Do not read help_assets catalog for local_path / usable flags",
    )
    args = parser.parse_args()
    settings = get_settings()
    cache_dir = Path(args.cache_dir) if args.cache_dir else settings.help_cache_dir
    okf_dir = Path(args.okf_dir) if args.okf_dir else settings.okf_dir
    library_dir = None if args.no_library else settings.help_assets_dir

    summary = convert_xhtml_cache_to_okf(
        cache_dir,
        okf_dir,
        library_dir=library_dir,
        max_pages=args.max_pages,
    )
    print(
        json.dumps(
            {
                "okf_dir": str(okf_dir),
                "pages_scanned": summary.pages_scanned,
                "pages_converted": summary.pages_converted,
                "topics": summary.topics,
                "procedures": summary.procedures,
                "screens": summary.screens,
                "sections": summary.sections,
                "assets": summary.assets,
                "error_count": len(summary.errors),
                "errors_sample": summary.errors[:5],
            },
            indent=2,
        )
    )
    return 0 if summary.pages_converted else 1


if __name__ == "__main__":
    raise SystemExit(main())
