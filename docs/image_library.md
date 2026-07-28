# Help image library

Local catalog of usable Sage Intacct Help Center images for SI VidGen video payloads.

## Build

Requires a completed Help XHTML cache (`data/help_xhtml/manifest.json`).

```bash
python -m src.rag.build_image_library
```

Options:

- `--no-download` — catalog only
- `--max-downloads N` — cap newly downloaded files (smoke)

Outputs under `data/help_assets/` (gitignored):

| File | Purpose |
|---|---|
| `catalog.json` | Per-asset metadata + local paths |
| `coverage.json` | Aggregate coverage stats |
| `files/*` | Downloaded image bytes |

## What is covered

The harvester scans every cached Help page, drops chrome/noise (`skins`, logos, transparent GIFs, icons), and marks assets usable when they look like instructional media:

| Class | Usable for video | Typical filenames |
|---|---|---|
| `example` | yes | `EXAMPLE-*.png` |
| `concept` | yes | `CONCEPT-*.png` |
| `screenshot` | yes | screen/dialog naming or alt text |
| `illustration` | yes | longer descriptive alt text |
| `icon` / `unknown` | no | UI chrome |

Rough corpus expectations (full English Help):

- Most pages are text-first (~14% of pages have at least one usable image)
- Strong pockets: Reporting / IVE, CSV import (GL journals, AR payments), Cash Management checks, Inventory costing examples
- Weak pockets: many procedural GL topics (for example journal reverse) have **no** usable screenshots

Always check `coverage.json` after a harvest for exact counts.

How the tool uses it

1. Retrieval returns Help chunks from Chroma (OKF may narrow assets to the matching section).
2. Chunk `asset_urls` are filtered to library URLs that exist locally and are marked usable.
3. Script generation leaves `help_asset` empty; the binder assigns library screenshots (heading-aware).
4. Ask Intacct uses the same library only indirectly via OKF asset metadata; answers cite Help URLs.
5. Payload/compositor resolve local paths for video.

## Gaps

Help alone will not cover every Intacct screen. When coverage is yellow/red, keep narration text-accurate and treat missing screenshots as a documentation gap (future UI capture bot), not as license to invent UI.
