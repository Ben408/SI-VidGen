# DEVELOPMENT_STATUS.md

Living status for **SI VidGen**. Update whenever a phase/task moves.

| Field | Value |
|---|---|
| **Last updated** | 2026-07-16 |
| **Current phase** | Phase 1 core complete → metadata enrichment / Phase 2 next |
| **Overall status** | XHTML crawl/chunk/embed/Chroma path verified; awaiting Higgsfield account |
| **Prototype posture** | Local venv · `gemma3:12b` / `llama3.2:latest` · `nomic-embed-text` · React+FastAPI · V0 payload export |
| **Primary users** | Information developers, project managers |
| **Prototype exit** | Verified baseline pushed to GitHub `main` |

---

## Summary

Phase 0 and the Phase 1 core are implemented locally:

- Python 3.11 venv, FastAPI API, React/Vite UI
- Deterministic smoke pipeline that writes a provisional Higgsfield payload
- Metadata-only JSON run telemetry with UI progress polling
- Docs stubs, GitHub Actions CI workflow, local `git init`
- `nomic-embed-text` pulled into Ollama
- Scoped, conditional XHTML crawler with local cache and content hashes
- XHTML-aware heading/step chunker with existing asset references
- Ollama embedding batches + persistent Chroma adapter + index CLI
- One-page live crawl/index/retrieval smoke-tested successfully

Still waiting on the operator: Higgsfield API access/docs for schema validation and V0.1.

---

## Confirmed product decisions (short)

| ID | Decision |
|---|---|
| D1 | Crawl authorized published XHTML under `www.intacct.com/ia/docs/en_US/help_action/`; quarterly majors, Friday minors |
| D2 | Ollama: `gemma3:12b` primary, `llama3.2:latest` fallback, `nomic-embed-text` embeddings |
| D3 | Chroma now; Pinecone-ready interface for later |
| D4 | V0 = valid Higgsfield **payload** to disk; V0.1 = Higgsfield **video API** |
| D5 | **React + Vite** browser UI with **FastAPI** backend |
| D6 | Text entry; MCP + structured file ingest **stubbed** |
| D7 | V0/V0.1 write to **local** `output/` |
| D8 | Python 3.11+ venv (`py -3.11`) |
| D9 | Structured JSON + UI progress; metadata only, no full issue/help text |
| D10 | Full test pyramid; GitHub-ready tree to exit prototype |
| D11 | No reliance on screenshots **not** already in Help Center |
| D12 | GitHub Actions now; Vercel as future full-cloud deployment |

---

## Phase checklist

| Phase | Name | Status |
|---|---|---|
| 0 | Project foundation + GitHub prep | **Complete** |
| 1 | RAG: Flare XHTML → Chroma | **Core complete**; module/task/UI metadata enrichment remains |
| 2 | Issue classification (Ollama) | Not started |
| 3 | Retrieval pipeline | Not started |
| 4 | Script generation (Help Center–safe visuals) | Not started |
| 5 | V0 payload export → V0.1 Higgsfield API | Payload path scaffolded; schema validation pending API docs |
| 6 | Review + local publish + UI progress | Progress + download done; formal review later |
| 7 | Analytics + feedback | Stub only |
| 8 | Intake stubs + E2E | Stubs + e2e smoke test present |
| 9 | Quality gates + GitHub/Vercel path | Local lint/tests/CI workflow present |
| 10 | Docs freeze & demo | Not started |

---

## Verification (2026-07-16)

| Check | Result |
|---|---|
| `ruff check .` | Pass |
| `pytest --cov=src` | 11 passed · ~73% statement coverage on current modules; no warnings |
| `npm run lint` | Pass |
| `npm run build` | Pass |
| `npm audit` | 0 vulnerabilities |
| Ollama models | `gemma3:12b`, `llama3.2:latest`, `nomic-embed-text`, `dolphin-mixtral:8x7b` (excluded by default) |
| Live RAG smoke | 1 XHTML page → 1 chunk → Ollama embedding → Chroma → retrieval; pass |
| Git | `main` pushed to `Ben408/SI-VidGen` (`157bf9a`) |

---

## Test coverage (target vs actual)

| Layer | Target | Actual |
|---|---|---|
| Unit | Chunking, payload, schemas | Crawler boundary/cache, chunker, payload, Ollama-client tests present |
| Contract (LLM JSON) | Classifier + scriptgen | Not started |
| Integration | XHTML fixtures → vector storage | Chroma upsert/query/source-replacement test present |
| E2E | Orchestrator + UI API + fake LLM | API smoke test present (placeholder stages) |
| CI (GitHub Actions) | Lint + tests on PR | Workflow pushed; GitHub status API temporarily returned HTTP 503 |

---

## Telemetry coverage (target vs actual)

| Signal | Target | Actual |
|---|---|---|
| Structured JSON stage logs | All pipeline stages | Present for intake/classify/script/payload |
| Run records (`data/runs/`) | Every orchestration | Present |
| In-UI progress | Live stage feedback | Polling present |
| Latencies / model ids | Classify, embed, script, payload/video | Latencies present; model ids when LLM stages land |
| Review outcomes | approve / reject / revise | Not started |
| Secret redaction checks | Automated test | Issue-text exclusion covered in e2e |

---

## Blockers / risks

| Item | Notes |
|---|---|
| Higgsfield schema | Align payload with live API docs when account/access is ready |
| Corporate TLS | npm needs Windows root CA export; pip needs `PIP_CERT` set to that bundle |
| Full corpus run | Not launched yet; one-page capped live validation passed |

---

## Recent changes

| Date | Change |
|---|---|
| 2026-07-16 | Initial planning rewrite and D1–D12 confirmation |
| 2026-07-16 | Phase 0 implementation: FastAPI + React shell, payload smoke path, docs, CI, tests, Ollama embed model |
| 2026-07-16 | Phase 1 core: scoped XHTML crawler/cache, chunker, Ollama embeddings, Chroma, index CLI, live one-page retrieval verification |
| 2026-07-16 | GitHub baseline pushed to private `Ben408/SI-VidGen` repository |
