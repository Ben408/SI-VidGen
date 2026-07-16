# Cursor Task List
### SI VidGen — AI-Generated Support Video System

Ordered work for a **local-first prototype** (Python venv, Ollama ≤ ~12B on RTX 4070, GitHub).
Corpus: authorized **Intacct Support** content via **Flare XHTML build output**.
Primary operators: **information developers** and **project managers**.
Status: [`DEVELOPMENT_STATUS.md`](DEVELOPMENT_STATUS.md) · Spec: [`readme.md`](readme.md) · Stubs: [`scaffold.md`](scaffold.md)

**Legend:** `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked

**Prototype versions**
- **V0:** Web UI → classify → RAG → script/scenes → **valid Higgsfield payload** on local disk + review + JSON/UI telemetry
- **V0.1:** Same path + **Higgsfield API** video asset generation to local disk
- **Prototype exit:** Directory fully prepped for GitHub check-in (tests, docs, status, CI stubs); Vercel path documented/scaffolded as desirable

---

## Phase 0 — Project foundation (GitHub prep starts here)

### Task 0.1: Repository hygiene
- [x] Initialize git (if needed) + `.gitignore` (`.venv/`, `.env`, `data/vector_store/`, `data/help_xhtml/`, `output/`, `__pycache__/`)
- [x] Add `.env.example` (`gemma3:12b` primary, `llama3.2:latest` fallback, planned local embed model, paths, optional Higgsfield key, log level)
- [x] Add `requirements.txt` + `requirements-dev.txt`
- [x] Confirm Python 3.11+ venv workflow in README
- [x] Add GitHub remote and push initial commit (`Ben408/SI-VidGen`)

### Task 0.2: Documentation skeleton
- [x] `readme.md` — confirmed decisions D1–D12
- [x] `DEVELOPMENT_STATUS.md`
- [x] `scaffold.md`
- [x] `docs/` stubs: `architecture.md`, `developer_guide.md`, `operator_guide.md`, `api.md`, `telemetry.md`, `corpus_flare_xhtml.md`

### Task 0.3: Telemetry + UI progress baseline
- [x] Structured JSON logger + `data/runs/` persistence
- [x] Pipeline `run_id` + stage timing helper
- [x] Progress event channel for web UI (poll)

### Task 0.4: Package layout from scaffold
- [x] Create `src/` modules from [`scaffold.md`](scaffold.md)
- [x] `src/llm/client.py` (Ollama)
- [x] `src/video/payload_builder.py` (V0 primary)
- [x] `src/video/higgsfield_client.py` (V0.1)
- [x] FastAPI shell + React/Vite text-entry UI page
- [x] Smoke orchestrator path writing a sample payload
- [x] Pull approved `nomic-embed-text` model

---

## Phase 1 — RAG infrastructure (Flare XHTML → Chroma)

### Task 1.1: XHTML corpus ingest
- [x] Crawl from the authorized XHTML start URL
- [x] Restrict traversal to `www.intacct.com/ia/docs/en_US/help_action/`
- [x] Cache fetched XHTML under gitignored `data/help_xhtml/`
- [x] Commit small **fixtures** under `data/help_fixtures/` for CI
- [x] Document: do **not** ingest Flare source/MadCap markup
- [x] Document re-index for **quarterly majors** and **Friday minors** (`docs/corpus_flare_xhtml.md`)

### Task 1.2: Chunk XHTML
- [x] XHTML-aware chunker (512–1024 tokens target)
- [x] Preserve headings + step lists; strip noise that harms retrieval
- [~] Metadata: title, heading, assets, URL/hash done; module/task/UI enrichment remains

### Task 1.3: Local embeddings
- [x] Pull/approve a dedicated local embedding model (`nomic-embed-text`)
- [x] Ollama embed model (config-driven)
- [x] Deterministic stub embedder for unit tests

### Task 1.4: Vector store interface
- [x] `VectorStore` protocol
- [x] **Chroma** implementation (prototype default)
- [x] Pinecone stub/adapter skeleton for later deployment
- [x] Rebuild-index CLI for Friday/quarterly drops

---

## Phase 2 — Issue classification (local LLM)

### Task 2.1: Classifier
- [ ] Prompt templates (JSON-only)
- [ ] Schema validation
- [ ] Map issues → help topics
- [ ] Fake-LLM contract tests; real Ollama optional local test

### Task 2.2: Classify API
- [ ] `POST /classify_issue` (or equivalent under orchestrated run)
- [ ] Input validation + telemetry

---

## Phase 3 — Retrieval pipeline

### Task 3.1: RAG retriever
- [ ] Classification-aware query
- [ ] Top-K + scores + low-confidence handling
- [ ] Integration tests on XHTML fixtures

---

## Phase 4 — Script generation (Help Center–safe visuals)

### Task 4.1: Script generator
- [ ] Help content → narration + scenes JSON
- [ ] UI references; **no dependency on missing screenshots**
- [ ] Prefer asset URLs/paths already present in Help Center / XHTML when available
- [ ] Schema validation + one repair retry

### Task 4.2: Scene planner
- [ ] Provider-ready scene list + branding defaults from config

---

## Phase 5 — Higgsfield payload (V0) then API (V0.1)

### Task 5.1: V0 payload export
- [ ] Align payload schema with current Higgsfield API docs
- [ ] `payload_builder` writes `output/payloads/{run_id}.json`
- [ ] Schema validation tests (golden files)
- [ ] UI: download / view payload

### Task 5.2: V0.1 Higgsfield client
- [ ] API wrapper using `HIGGSFIELD_API_KEY`
- [ ] Submit payload; store assets under `output/videos/`
- [ ] Error handling + telemetry; CI skips live call without secret

---

## Phase 6 — Review + local publishing

### Task 6.1: Review workflow (web UI)
- [ ] Approve / reject / request changes
- [ ] Versioning + audit log
- [ ] In-UI progress during processing

### Task 6.2: Local publish (V0 / V0.1)
- [ ] Write approved artifacts to `output/published/`
- [ ] Stub adapters for future help center / portal / LMS

---

## Phase 7 — Analytics + feedback

### Task 7.1: Analytics pipeline
- [ ] Stub view/completion events; operator feedback; link to `run_id`

### Task 7.2: Content-gap hints
- [ ] Aggregate low-confidence retrieval + rejects → topic suggestions report

---

## Phase 8 — Intake stubs + E2E

### Task 8.1: Orchestrator
- [ ] Full path: intake → classify → RAG → script → payload [(→ Higgsfield)] → review
- [ ] Logging, error codes, safe retries

### Task 8.2: Web UI (primary)
- [ ] Text entry box
- [ ] Stage inspection, approve/reject, download payload/assets
- [ ] Browser-agnostic operator flows

### Task 8.3: Stubbed intake connectors
- [ ] MCP connection stub (interface + “not configured” behavior)
- [ ] Structured file ingest stub (JSON/CSV of issues)

### Task 8.4: E2E tests
- [ ] Fake LLM → assert payload file + run JSON + progress events

---

## Phase 9 — Quality gates (required)

### Task 9.1: Comprehensive tests
- [ ] Unit / contract / integration / e2e
- [ ] Coverage tracking in CI
- [ ] Regression fixtures for XHTML samples

### Task 9.2: Telemetry completeness
- [ ] Fields per `docs/telemetry.md`
- [ ] UI progress covered
- [ ] Do not retain full issue text or retrieved help chunks
- [ ] Secret redaction test

### Task 9.3: GitHub + CI/CD path
- [ ] GitHub Actions: lint + tests on PR (no paid APIs)
- [ ] Document **future full-cloud Vercel deployment** after hosted API/model/storage migration
- [ ] **Prototype exit checklist:** repo ready for initial GitHub check-in

---

## Phase 10 — Docs freeze & demo

### Task 10.1: Local demo
- [ ] PowerShell one-command demo (venv + UI)
- [ ] Sample issue → payload on disk

### Task 10.2: Documentation completion
- [ ] Operator guide (info developers / PMs)
- [ ] Developer onboarding
- [ ] API + corpus + telemetry docs
- [ ] `DEVELOPMENT_STATUS.md` reflects V0 / V0.1 readiness

---

## Explicitly deferred (post-prototype)

- Ingesting Flare **source** / MadCap topic files (use XHTML builds only)
- Pinecone cutover (interface ready earlier)
- Real help-center / LMS publishing
- Cloud LLM providers
- Production auth, multi-tenant SaaS
- Screenshots not already available in the Intacct Help Center
