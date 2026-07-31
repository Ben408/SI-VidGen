# DEVELOPMENT_STATUS.md

Living status for **SI VidGen / Intacct Knowledge Studio**.

| Field | Value |
|---|---|
| **Last updated** | 2026-07-31 |
| **Current phase** | Knowledge Studio + Slack/Hermes T1 pilot |
| **Overall status** | English Ask / script / video work; RAG language-filter bug fixed; FR/DE/ES crawl/index in progress; Slack + Hermes-Local are siblings |
| **Prototype posture** | Local venv · Ollama · React+FastAPI · Chroma · OKF · Help image library · work gate |
| **Chat model (this app)** | **`gemma3:12b`** via Ollama — **not** Qwen |
| **Primary users** | Information developers, project managers, internal Sage staff (Ask) |
| **Prototype exit** | GitHub baseline + green CI; Phrase multilingual via Hermes (not inside this repo) |

---

## Models (do not confuse with Hermes)

| Role | Model | Where |
|---|---|---|
| Ask / classify / script | **`gemma3:12b`** | SI-VidGen (`.env` `OLLAMA_CHAT_MODEL`) |
| Embeddings | `nomic-embed-text` | SI-VidGen |
| Free MT (localize path) | `translategemma:12b` | Hermes-Local dispatcher |
| Hermes chat fallback | `qwen2.5-hermes` | Hermes-Local only — **not** wired into Ask/script/video |

Switching Ask/script/video to Qwen is a **separate experiment** and has **not** been manually retested. Keep `OLLAMA_CHAT_MODEL=gemma3:12b` until that is intentional.

Shared host: `OLLAMA_MODELS=F:\OllamaModels` (preferred). Do not delete the C: Ollama backup until you confirm other projects and Ollama itself do not still read C:.

---

## Implemented

- Full English Help cache/index (~3.3k pages)
- Help image library + local compositor MP4 (default)
- Rules-only OKF (`data/okf/`) with pipeline enrich + UI browse
- Tabbed UI: **Create video** · **Ask Intacct**
- Footer **Re-ingest Help** (crawl → Chroma → images → OKF)
- Multi-locale crawl hooks (`HELP_LOCALES` / `--locales`) + locale video guards
- Work gate blocks overlapping LLM-heavy jobs
- Review/edit/approve video scripts; optional Higgsfield backend
- CI: ruff + pytest + web lint/build
- RAG: empty Chroma `language=` filter falls back to unfiltered + URL locale post-filter

## Sibling stack

| Repo | Role |
|---|---|
| **SI-VidGen** (this) | Help RAG, Ask, script/video API + UI |
| **SI-VidGen-Slack** | Slack Socket Mode front door (tiers, `/hermes`, product slash commands) |
| **Hermes-Local** | Termweb / Phrase / free translate skills; deterministic T1 dispatcher |

## Deferred (this repo)

- Switching Ask/script primary chat model to Qwen (optional; retest required)
- Phrase TMS inside SI-VidGen (owned by Hermes + Slack)
- Pinecone cutover / Flare source ingest / multi-tenant SaaS

## Verification

| Check | Result |
|---|---|
| `ruff check .` | Expected green before commit |
| `pytest` | Unit/e2e including RAG language fallback |
| Web lint/build | Expected green before commit |
| T1 product smoke (via Hermes `verify_t1_skills.py`) | Ask + script + video **PASS** (2026-07-31) |
| Full OKF convert | 3,324 topics converted (local) |

## Recent

| Date | Change |
|---|---|
| 2026-07-31 | Fix Ask/script/video refuse when Chroma rows lack `language` metadata |
| 2026-07-31 | Document Gemma vs Qwen ownership; sibling Slack/Hermes T1 pilot |
| 2026-07-29 | FR/DE/ES Help crawl/index progress |
| 2026-07-28 | Ask tab + corpus refresh footer + docs/archive hygiene |
| 2026-07-28 | OKF parallel layer + section-scoped screenshot grounding |
| 2026-07-21 | Local compositor captions / voice / video-ready UI |
