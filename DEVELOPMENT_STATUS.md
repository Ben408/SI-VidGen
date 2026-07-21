# DEVELOPMENT_STATUS.md

Living status for **SI VidGen**. Update whenever a phase/task moves.

| Field | Value |
|---|---|
| **Last updated** | 2026-07-20 |
| **Current phase** | Help image library + Higgsfield explainer media packaging |
| **Overall status** | V0 path is script/payload review only — no Higgsfield generation credits |
| **Prototype posture** | Local venv · `gemma3:12b` / `llama3.2:latest` · `nomic-embed-text` · React+FastAPI · grounded script + Help image library + payload |
| **Primary users** | Information developers, project managers |
| **Prototype exit** | Verified baseline on GitHub; multilingual decision pending |

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
- Ollama structured-output schemas flattened for grammar compatibility
- UI review of classification confidence, sources, script, visual coverage, and payload
- Editable, versioned scripts with automatic payload regeneration
- Explicit approval plus a default-off, capability-gated auto-generation path
- Script generation limited to the top three retrieval sources with grounding repair
- Rebuild-from-cache indexer (`--from-cache --reset-store`) after Chroma compaction recovery
- **No Higgsfield API generation calls**

Decision pending:

- Multilingual FR / DE / ES-ES strategy with Phrase TMS — recommended **Option C (Hybrid)** in `docs/multilingual.md`

---

## Phase checklist

| Phase | Name | Status |
|---|---|---|
| 0 | Project foundation + GitHub prep | **Complete** |
| 1 | RAG: Flare XHTML → Chroma | **Complete for English** |
| 2 | Issue classification (Ollama) | **Complete** |
| 3 | Retrieval pipeline | **Complete** |
| 4 | Script generation (Help Center–safe visuals) | **Complete for English V0** + Help image library |
| 5 | V0 payload export → V0.1 Higgsfield API | Explainer media package ready; API generation blocked until review |
| 6 | Review + local publish + UI progress | Edit/version/approve complete; reject/request-changes later |
| 7 | Analytics + feedback | Stub only |
| 8 | Intake stubs + E2E | Stubs + expanded e2e present |
| 9 | Quality gates + GitHub/Vercel path | Local suite green; CI workflow present |
| 10 | Docs freeze & demo | Multilingual decision doc ready for team review |

---

## Verification

| Check | Result |
|---|---|
| `ruff check .` | Pass |
| `pytest` | 36 passed |
| `npm run lint` / `npm run build` | Pass |
| Live classify (`gemma3:12b`) | Pass |
| Live classify → retrieve → script → payload | Pass (`scripts/live_pipeline_smoke.py`) |
| Live sample → edit v2 → rebuild payload → approve | Pass (`scripts/live_review_workflow_smoke.py`) |
| Live CSV-import sample → library medias → explainer package | Pass (`scripts/live_image_library_smoke.py`) |
| Browser UI sample/edit/save/approve | Pass |
| Full corpus index | **Complete** — 3,324 pages / 8,015 chunks |
| Help image library | **Complete** — 756 usable assets / 361 pages |
| Higgsfield API generation | Intentionally not called |

---

## Multilingual note

Intacct Help exists in English, French, German, and European Spanish. Phrase TMS is the localization system and has an MCP server.

**Working recommendation:** Option C (Hybrid) — author/review in English, localize narration/scenes via Phrase TMS, QA against localized Help before non-English payload approval. See `docs/multilingual.md`.

---

## Recent changes

| Date | Change |
|---|---|
| 2026-07-20 | Local screenshot compositor default (Ken Burns + TTS); Higgsfield optional |
| 2026-07-20 | Higgsfield CLI submit/wait/download (`gemini_omni`) + UI ready/local video link |
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
