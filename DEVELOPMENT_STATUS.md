# DEVELOPMENT_STATUS.md

Living status for **SI VidGen / Intacct Knowledge Studio**.

| Field | Value |
|---|---|
| **Last updated** | 2026-08-06 |
| **Current phase** | Knowledge Studio + Slack/Hermes T1 UAT; T2/T3 in parallel |
| **Overall status** | English Ask / script / video work; Slack channel-default T1; Hermes Slack path is skill-only (no LLM chat fallback) |
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
| Hermes agent (optional) | `qwen2.5-hermes` | Hermes-Local CLI only — **disabled as Slack `/hermes` fallback** |

Switching Ask/script/video to Qwen is a **separate experiment** and has **not** been manually retested. Keep `OLLAMA_CHAT_MODEL=gemma3:12b` until that is intentional.

Shared host: `OLLAMA_MODELS=F:\OllamaModels` (preferred). Do not delete the C: Ollama backup until you confirm other projects and Ollama itself do not still read C:.

---

## Major decisions (log)

| Date | Decision | Reason |
|---|---|---|
| 2026-08-06 | **Ask localization router (latency-bounded):** Help gate + optional Phrase TM + translategemma; Termweb off Ask critical path; Microsoft MT = T3 skill. Benchmarks in Hermes `docs/benchmarks.md`. | Slack conversation feel; baseline localize-ask was ~22s with Termweb. |
| 2026-08-06 | **Disable Slack `/hermes` → `hermes chat -q` LLM fallback.** Unrouted prompts: out-of-bounds, Ask Intacct redirect, or tip. | `/hermes` is **stateless**; chat caused multi-minute waits and fake tool narration. |
| 2026-08-06 | Non-English Ask: if localized Help refuse/miss, **retry grounding on English Help** while answering in the user language. Refuse UX: do not imply weak retrieval hits are the answer. | DE GAAP ask detected `de_DE` but retrieved off-topic DE pages → refuse + contradictory Help list; EN Help has strong GAAP topics. |
| 2026-08-06 | **Accounting / Sage Intacct conceptual questions on `/hermes` → Ask Intacct** (Help RAG). | Reasonable user asks; Hermes owns localization skills, not grounded product Q&A. Ask is the Help-backed path. |
| 2026-08-04 | **Slack T1 = any member of allowed channel**; T2/T3 require explicit user ID elevation. | UAT: invite IDs/linguists to the channel for default Ask/script/video/Hermes reads without per-user T1 allowlisting. |
| 2026-08-04 | **Ask free text: only Sage Help URLs; strip chunk hashes / `.htm` names.** | Model invented third-party links (mxtoolbox unfurl) and pasted internal `source_id` hex into Notes. |

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
| 2026-08-06 | Slack `/hermes`: no LLM chat fallback; OOB refuse; GAAP/Intacct → Ask redirect (see Major decisions) |
| 2026-08-04 | Ask scrub non-Help URLs + source_id hashes from free text |
| 2026-07-31 | Fix Ask/script/video refuse when Chroma rows lack `language` metadata |
| 2026-07-31 | Document Gemma vs Qwen ownership; sibling Slack/Hermes T1 pilot |
| 2026-07-29 | FR/DE/ES Help crawl/index progress |
| 2026-07-28 | Ask tab + corpus refresh footer + docs/archive hygiene |
| 2026-07-28 | OKF parallel layer + section-scoped screenshot grounding |
| 2026-07-21 | Local compositor captions / voice / video-ready UI |
