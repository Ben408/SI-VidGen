# DEVELOPMENT_STATUS.md

Living status for **SI VidGen / Intacct Knowledge Studio**.

| Field | Value |
|---|---|
| **Last updated** | 2026-07-28 |
| **Current phase** | Knowledge Studio demo: video + Ask + corpus refresh + OKF |
| **Overall status** | English path works: Create video (local compositor), Ask Intacct (multi-hop Q&A with refuse-on-gap), footer full corpus refresh, OKF parallel bundle |
| **Prototype posture** | Local venv · Ollama · React+FastAPI · Chroma · OKF · Help image library · work gate |
| **Primary users** | Information developers, project managers, internal Sage staff (Ask) |
| **Prototype exit** | GitHub baseline + green CI; Phrase multilingual deferred |

---

## Implemented

- Full English Help cache/index (~3.3k pages / ~8k chunks)
- Help image library + local compositor MP4 (default)
- Rules-only OKF (`data/okf/`) with pipeline enrich + UI browse
- Tabbed UI: **Create video** · **Ask Intacct**
- Footer **Re-ingest Help** (crawl → Chroma → images → OKF)
- Work gate blocks overlapping LLM-heavy jobs
- Review/edit/approve video scripts; optional Higgsfield backend
- CI: ruff + pytest + web lint/build

## Deferred

- Phrase TMS multilingual (see `docs/multilingual.md`)
- Pinecone cutover
- In-app MCP OAuth
- Flare source ingest
- Production auth / multi-tenant SaaS

## Verification

| Check | Result |
|---|---|
| `ruff check .` | Expected green before commit |
| `pytest` | Expand with ask/refresh/OKF/work-gate coverage |
| Web lint/build | Expected green before commit |
| Full OKF convert | 3,324 topics converted (local) |

## Recent

| Date | Change |
|---|---|
| 2026-07-28 | Ask tab + corpus refresh footer + docs/archive hygiene |
| 2026-07-28 | OKF parallel layer + section-scoped screenshot grounding |
| 2026-07-21 | Local compositor captions / voice / video-ready UI |
