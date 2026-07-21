# DEVELOPMENT_STATUS.md

Living status for **SI VidGen**. Update whenever a phase/task moves.

| Field | Value |
|---|---|
| **Last updated** | 2026-07-21 |
| **Current phase** | Demo-harden local compositor (English deliverable); MCP/OAuth next |
| **Overall status** | English V0 demo path works end-to-end: grounded script → review → **local compositor MP4** (Help screenshots preserved). Higgsfield remains optional. |
| **Prototype posture** | Local venv · `gemma3:12b` / `llama3.2:latest` · `nomic-embed-text` · React+FastAPI · Help image library · `VIDEO_BACKEND=local_compositor` (default) |
| **Primary users** | Information developers, project managers |
| **Prototype exit** | GitHub baseline + green CI; multilingual (Phrase) deferred until English demo confidence |

---

## Summary

Implemented and verified:

- Full English Help Center crawl/cache: **3,324 pages**
- Full Chroma index: **8,015 chunks**, `complete: true`
- Help image library harvest: **756 usable assets** downloaded (`data/help_assets/`), **361/3324** pages with usable visuals (~10.9%)
- Validated Ollama classification (`gemma3:12b`)
- Retrieval with relevance threshold and failure on weak evidence
- Grounded script generation with source citations and library asset binding
- Higgsfield `video_explainer` package export (`*-explainer.json`, `*-medias.json`, `*-prompt.txt`) with local media paths
- **Default video backend: local screenshot compositor** (Ken Burns + Edge neural TTS + burn-in captions)
- UI: voice/pace/captions controls, inline **Video ready** player, download MP4
- Optional `VIDEO_BACKEND=higgsfield` (MCP / CLI token; trial may gate CLI generation)
- Ollama structured-output schemas flattened for grammar compatibility
- Editable, versioned scripts with automatic payload regeneration
- Explicit approval plus a default-off, capability-gated auto-generation path
- Script generation limited to the top three retrieval sources with grounding repair
- Rebuild-from-cache indexer (`--from-cache --reset-store`) after Chroma compaction recovery
- GitHub Actions CI green (`ruff` + `pytest` + web lint/build)

Decision pending / next:

- Multilingual FR / DE / ES-ES via Phrase TMS — recommended **Option C (Hybrid)** in `docs/multilingual.md` (after English demo)
- Shared MCP + OAuth in-app (Higgsfield first, Phrase later)

---

## Phase checklist

| Phase | Name | Status |
|---|---|---|
| 0 | Project foundation + GitHub prep | **Complete** |
| 1 | RAG: Flare XHTML → Chroma | **Complete for English** |
| 2 | Issue classification (Ollama) | **Complete** |
| 3 | Retrieval pipeline | **Complete** |
| 4 | Script generation (Help Center–safe visuals) | **Complete for English V0** + Help image library |
| 5 | V0 payload + video render | **Local compositor demo-ready**; Higgsfield optional / MCP OAuth later |
| 6 | Review + local publish + UI progress | Edit/version/approve + video options/player; reject/request-changes later |
| 7 | Analytics + feedback | Stub only |
| 8 | Intake stubs + E2E | Stubs + expanded e2e present |
| 9 | Quality gates + GitHub/Vercel path | Local suite green; **CI green on `main`** |
| 10 | Docs freeze & demo | Sample CSV-import demo + captioned local MP4; control docs refresh 2026-07-21 |

---

## Verification

| Check | Result |
|---|---|
| `ruff check .` | Pass |
| `pytest` | **47 passed** |
| `npm run lint` / `npm run build` | Pass |
| GitHub Actions (`CI` on `main`) | Pass (backend + web) |
| Live classify (`gemma3:12b`) | Pass |
| Live classify → retrieve → script → payload | Pass (`scripts/live_pipeline_smoke.py`) |
| Live sample → edit v2 → rebuild payload → approve | Pass (`scripts/live_review_workflow_smoke.py`) |
| Live CSV-import sample → library medias → explainer package | Pass (`scripts/live_image_library_smoke.py`) |
| Local compositor sample render (captions + TTS) | Pass (`scripts/render_sample_local_compositor.py` → `output/videos/demo-sample-query-local-compositor.mp4`) |
| Browser UI sample/edit/save/approve | Pass |
| Full corpus index | **Complete** — 3,324 pages / 8,015 chunks |
| Help image library | **Complete** — 756 usable assets / 361 pages |
| Higgsfield live generation | Optional; generative restyle is a poor fit for authoritative Help screenshots |

---

## Video backends

| Backend | When to use | Notes |
|---|---|---|
| `local_compositor` (**default**) | Stakeholder demos, English V0 | Preserves Help PNG pixels; Edge TTS; burn-in captions; voice/rate from UI |
| `higgsfield` | Optional cloud path | MCP / CLI; trial accounts may require connector OAuth; can invent UI text |

Config: `VIDEO_BACKEND`, `LOCAL_COMPOSITOR_TTS`, `LOCAL_COMPOSITOR_VOICE`, `LOCAL_COMPOSITOR_TTS_RATE`, `LOCAL_COMPOSITOR_CAPTIONS` (see `.env.example`).

---

## Multilingual note

Intacct Help exists in English, French, German, and European Spanish. Phrase TMS is the localization system and has an MCP server.

**Working recommendation:** Option C (Hybrid) — author/review in English, localize narration/scenes via Phrase TMS, QA against localized Help before non-English payload approval. See `docs/multilingual.md`.

**Gate:** Do not implement Phrase until English demo confidence and localization ownership questions are answered.

---

## Recent changes

| Date | Change |
|---|---|
| 2026-07-21 | Demo-harden local compositor: burn-in captions, voice/rate UI, inline video-ready player |
| 2026-07-21 | CI fix: pytest `pythonpath`, ruff clean; Actions green on `main` |
| 2026-07-20 | Edge neural TTS for local compositor narration |
| 2026-07-20 | Local screenshot compositor default (Ken Burns + TTS); Higgsfield optional |
| 2026-07-20 | Higgsfield scene-chunked MCP generation + UI video delivery |
| 2026-07-20 | Help image library harvest + script/payload binding + explainer MCP package |
| 2026-07-20 | Image-rich CSV journal-import sample (`docs/sample_query.md`) |
| 2026-07-16 | GitHub baseline push |
| 2026-07-16 | Classification + retrieval + grounded script/payload + review UI |
| 2026-07-16 | Full English Help index completed (3,324 pages / 8,015 chunks) |
| 2026-07-16 | Fixed Ollama nested schema grammar failures for script generation |
| 2026-07-16 | Added `--from-cache --reset-store` recovery path for Chroma rebuild |
| 2026-07-16 | Expanded tests + live pipeline smoke |
| 2026-07-16 | Multilingual decision frame documented with hybrid recommendation |
| 2026-07-16 | Editable script versions, approval, and safe auto-generation toggle |
| 2026-07-16 | Grounded journal-reversal sample passed API and browser workflows |
