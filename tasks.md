# Cursor Task List
### SI VidGen — AI-Generated Support Video System

Ordered work for a **local-first prototype** (Python venv, Ollama ≤ ~12B on RTX 4070, GitHub).
Corpus: authorized **Intacct Support** content via **Flare XHTML build output**.
Primary operators: **information developers** and **project managers**.
Status: [`DEVELOPMENT_STATUS.md`](DEVELOPMENT_STATUS.md) · Spec: [`readme.md`](readme.md) · Stubs: [`scaffold.md`](scaffold.md)

**Legend:** `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked

**Prototype versions**
- **V0:** Web UI → classify → RAG → script/scenes → reviewable package on local disk + JSON/UI telemetry
- **V0 demo video:** **Local compositor** MP4 (Help screenshots preserved; captions + TTS) — **current English deliverable**
- **V0.1:** Optional **Higgsfield** cloud generation (MCP/OAuth); generative restyle is secondary to Help fidelity
- **Prototype exit:** Directory fully prepped for GitHub check-in (tests, docs, status, CI); Vercel path documented as desirable

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
- [x] `src/video/higgsfield_client.py` (V0.1 / optional)
- [x] `src/video/local_compositor.py` (default demo video backend)
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
- [x] Prompt templates (JSON-only)
- [x] Schema validation
- [x] Map issues → help topics
- [x] Fake-LLM contract tests; real Ollama validation completed with `gemma3:12b`

### Task 2.2: Classify API
- [x] Classification stage under orchestrated run
- [x] Input validation + telemetry

---

## Phase 3 — Retrieval pipeline

### Task 3.1: RAG retriever
- [x] Classification-aware query (`search_query`)
- [x] Top-K + scores + low-confidence handling
- [x] Unit/integration tests for retrieval mapping and empty/low-score failure

---

## Phase 4 — Script generation (Help Center–safe visuals)

### Task 4.1: Script generator
- [x] Help content → narration + scenes JSON
- [x] UI references; **no dependency on missing screenshots**
- [x] Prefer asset URLs/paths already present in Help Center / XHTML when available
- [x] Schema validation + one repair retry + grounding checks

### Task 4.2: Scene planner / review artifacts
- [x] Provider-ready scene list + branding defaults from config
- [x] Grounded script JSON export + UI source/confidence review
- [x] Help image library harvest (`python -m src.rag.build_image_library`) + `docs/image_library.md`
- [x] Auto-bind library assets; visual coverage green/yellow/red in run + UI

---

## Phase 5 — Video package (V0) + render backends

### Task 5.1: V0 payload / explainer export
- [~] Align payload schema with current Higgsfield API docs
- [x] `payload_builder` writes `output/payloads/{run_id}.json`
- [x] Explainer MCP/CLI package: `*-explainer.json`, `*-medias.json`, `*-prompt.txt` (local paths, max 14)
- [ ] Schema validation tests (golden files)
- [x] UI: download / view payload + explainer package

### Task 5.2: Local compositor (default English demo)
- [x] Ken Burns over real Help screenshots (`LocalCompositorVideoGenerator`)
- [x] Edge neural TTS with SAPI/pyttsx3 fallback
- [x] Burn-in captions from scene voiceover
- [x] Per-run voice / narration pace / captions via Approve UI + `/api/capabilities`
- [x] Inline **Video ready** player + download MP4
- [x] Sample re-render (`scripts/render_sample_local_compositor.py`, `docs/sample_query.md`)

### Task 5.3: Optional Higgsfield client
- [x] MCP client path (`higgsfield_client`) + scene-chunked `gemini_omni` / stitch
- [~] In-app MCP OAuth (not Cursor-tied) — **next platform item**
- [ ] Error handling + telemetry polish; CI skips live call without secret
- [!] Trial/CLI may return `only_mcp_usage_on_trial_is_available`; generative restyle can invent UI text

---

## Phase 6 — Review + local publishing

### Task 6.1: Review workflow (web UI)
- [~] Approve implemented; reject / request changes remain
- [x] Editable script versions + metadata-only edit/approval audit events
- [x] Payload regeneration after each saved edit
- [x] Default-off automatic-generation toggle with availability gate
- [x] In-UI progress during processing
- [x] Local compositor options (voice, pace, captions) + video-ready panel

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
- [x] Full path: intake → classify → RAG → script → payload → local video (optional Higgsfield)
- [x] Logging, error codes, safe retries

### Task 8.2: Web UI (primary)
- [x] Text entry box
- [x] Stage inspection + editable script + approve + script/payload downloads
- [x] Browser-agnostic operator flows
- [x] Video options + inline player when generation is ready

### Task 8.3: Stubbed intake connectors
- [ ] MCP connection stub (interface + “not configured” behavior) — expand with shared OAuth client
- [ ] Structured file ingest stub (JSON/CSV of issues)

### Task 8.4: E2E tests
- [x] Fake LLM → assert payload file + run JSON + progress events
- [x] Failure path for weak retrieval evidence
- [x] Edit → version → payload rebuild → approve/generate gate

---

## Phase 9 — Quality gates (required)

### Task 9.1: Comprehensive tests
- [x] Unit / contract / integration / e2e (**47** local tests)
- [x] Coverage reporting via `pytest --cov=src` in CI
- [x] Regression fixtures for XHTML samples

### Task 9.2: Telemetry completeness
- [x] Fields per `docs/telemetry.md`
- [x] UI progress covered
- [x] Do not retain full issue text or retrieved help chunks
- [x] Secret redaction test

### Task 9.3: GitHub + CI/CD path
- [x] GitHub Actions: lint + tests on PR/push (no paid APIs)
- [x] Document **future full-cloud Vercel deployment** after hosted API/model/storage migration
- [x] **Prototype exit checklist:** repo ready for initial GitHub check-in
- [~] Quiet Node 20 deprecation warnings on Actions (checkout/setup-* bumps)

---

## Phase 10 — Docs freeze & demo

### Task 10.1: Local demo
- [x] PowerShell/BAT launcher (`start-si-vidgen.bat`)
- [x] Sample issue → grounded script + library medias (`docs/sample_query.md`)
- [x] Sample → captioned local compositor MP4 (`demo-sample-query-local-compositor.mp4`)

### Task 10.2: Documentation completion
- [~] Control docs refreshed 2026-07-21 (`DEVELOPMENT_STATUS`, `tasks`, `readme`, `pitch_deck`, `requirements`)
- [ ] Operator guide (info developers / PMs) — flesh out for demo
- [ ] Developer onboarding polish
- [ ] API + corpus + telemetry docs stay in sync with compositor options

### Task 10.3: Next after English demo (ordered)
- [ ] Shared MCP client + in-app OAuth (Higgsfield first)
- [ ] Confirm Phrase ownership questions (`docs/multilingual.md`)
- [ ] Phrase export package + MCP stub (FR/DE/ES-ES narration)
- [ ] Localized Help crawl/QA for Option C hybrid

---

## Explicitly deferred (post-prototype)

- Ingesting Flare **source** / MadCap topic files (use XHTML builds only)
- Pinecone cutover (interface ready earlier)
- Real help-center / LMS publishing
- Cloud LLM providers
- Production auth, multi-tenant SaaS
- Screenshots not already available in the Intacct Help Center
- Treating generative Higgsfield restyle as the primary Help walkthrough path
