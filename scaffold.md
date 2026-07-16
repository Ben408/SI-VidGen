# Demo Implementation Scaffold (Cursor-Ready)

Minimal project structure for **SI VidGen**: local venv, Ollama (≤ ~12B on RTX 4070), Flare **XHTML** → Chroma (Pinecone-ready), **V0 Higgsfield payload export**, **V0.1 Higgsfield API**, browser-agnostic web UI with in-UI progress.

See [`readme.md`](readme.md) for confirmed decisions and [`tasks.md`](tasks.md) for build order.

---

## Project structure

```text
/src
  /intake
    intake_handler.py
    mcp_stub.py
    file_ingest_stub.py
  /classifier
    classify_issue.py
  /rag
    xhtml_ingest.py
    chunker.py
    rag_retriever.py
    embeddings.py
    vector_store.py          # protocol
    chroma_store.py
    pinecone_store.py        # skeleton for later
  /scriptgen
    script_builder.py
    scene_planner.py
  /llm
    client.py
  /video
    payload_builder.py       # V0 primary deliverable
    higgsfield_client.py     # V0.1
  /publish
    publisher.py
  /analytics
    analytics_pipeline.py
  /telemetry
    logging.py
    progress.py              # events for web UI
    run_store.py
  /api
    app.py                   # FastAPI backend
  /web                       # React + Vite operator UI
  orchestrator.py
/config
  settings.py
/data
  /help_xhtml                # gitignored crawl cache
  /help_fixtures             # small CI samples
  /samples
  /vector_store
  /runs
/output
  /payloads                  # V0
  /videos                    # V0.1
  /published
/tests
  /unit
  /integration
  /e2e
main.py
```

---

## Module scaffolds

### `/src/intake/intake_handler.py`

```python
def normalize_issue(raw_issue: dict) -> dict:
    """Normalize web UI / stub connector input into a standard issue object."""
    return {
        "issue_id": raw_issue.get("id"),
        "user_id": raw_issue.get("user"),
        "raw_text": raw_issue.get("text"),
        "context": raw_issue.get("context", {}),
    }
```

### `/src/intake/mcp_stub.py`

```python
def fetch_issues_via_mcp(config: dict) -> list[dict]:
    """Stub: connect via MCP when configured. Prototype returns empty + status."""
    return []
```

### `/src/intake/file_ingest_stub.py`

```python
def load_issues_from_file(path: str) -> list[dict]:
    """Stub: ingest structured JSON/CSV of user feedback/issues."""
    raise NotImplementedError("Structured file ingest stub — wire in a later task")
```

### `/src/llm/client.py`

```python
class LocalLLMClient:
    """Ollama chat + embeddings. Prefer chat models ≤ ~12B on RTX 4070."""

    def __init__(self, base_url: str, chat_model: str, embed_model: str):
        self.base_url = base_url
        self.chat_model = chat_model
        self.embed_model = embed_model

    def chat_json(self, system: str, user: str) -> dict:
        raise NotImplementedError

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError
```

### `/src/classifier/classify_issue.py`

```python
def classify_issue(issue: dict, llm: "LocalLLMClient | None" = None) -> dict:
    """Classify issue with local LLM; return validated JSON metadata."""
    return {
        "feature": "General Ledger",
        "intent": "Resolve posting error",
        "error_type": "Unbalanced journal entry",
        "help_topics": ["gl_posting_errors"],
    }
```

### `/src/rag/xhtml_ingest.py`

```python
def crawl_xhtml_documents(
    start_url: str,
    allowed_prefix: str = "https://www.intacct.com/ia/docs/en_US/help_action/",
) -> list[dict]:
    """
    Crawl published Flare XHTML output. Follow only same-host links beneath
    allowed_prefix; never ingest Flare/MadCap authoring source.
    Returns [{path, title, html, metadata}, ...].
    """
    return []
```

### `/src/rag/chunker.py`

```python
def chunk_xhtml(doc: dict, target_tokens: tuple[int, int] = (512, 1024)) -> list[dict]:
    """Chunk XHTML preserving headings and step lists; attach metadata."""
    return []
```

### `/src/rag/embeddings.py`

```python
def embed_text(text: str, llm: "LocalLLMClient | None" = None) -> list[float]:
    if llm is None:
        return [0.0] * 768  # deterministic stub for offline tests
    return llm.embed(text)
```

### `/src/rag/vector_store.py`

```python
from typing import Protocol

class VectorStore(Protocol):
    def add(self, embedding: list[float], metadata: dict) -> None: ...
    def query(self, embedding: list[float], top_k: int = 5) -> list[dict]: ...
```

### `/src/rag/chroma_store.py`

```python
class ChromaVectorStore:
    """Prototype default persistence under data/vector_store/."""

    def __init__(self, persist_path: str = "data/vector_store"):
        self.persist_path = persist_path
        self.index: list[dict] = []

    def add(self, embedding: list[float], metadata: dict) -> None:
        self.index.append({"embedding": embedding, "metadata": metadata})

    def query(self, embedding: list[float], top_k: int = 5) -> list[dict]:
        return self.index[:top_k]
```

### `/src/rag/pinecone_store.py`

```python
class PineconeVectorStore:
    """Skeleton for eventual deployment; not required for prototype."""

    def add(self, embedding: list[float], metadata: dict) -> None:
        raise NotImplementedError("Pinecone adapter deferred")

    def query(self, embedding: list[float], top_k: int = 5) -> list[dict]:
        raise NotImplementedError("Pinecone adapter deferred")
```

### `/src/rag/rag_retriever.py`

```python
from .embeddings import embed_text

def retrieve_help_content(query: str, store, llm=None) -> dict:
    embedding = embed_text(query, llm=llm)
    results = store.query(embedding)
    return results[0]["metadata"] if results else {}
```

### `/src/scriptgen/script_builder.py`

```python
def build_script(help_content: dict, llm: "LocalLLMClient | None" = None) -> dict:
    """
    Build instructional script. Visuals must not require screenshots
    that are not already available from the Intacct Help Center.
    """
    return {
        "title": f"How to Fix: {help_content.get('title', 'Issue')}",
        "narration": "In this video, we'll walk through the steps...",
        "scenes": [
            {
                "action": "Open the General Ledger module",
                "visual": "Highlight navigation menu (textual; no missing screenshot dependency)",
                "voiceover": "Start by opening the General Ledger module...",
                "help_asset": help_content.get("existing_asset_url"),  # only if present in HC/XHTML
            }
        ],
    }
```

### `/src/scriptgen/scene_planner.py`

```python
def plan_scenes(script: dict) -> list:
    """Convert script into a scene list for the Higgsfield payload."""
    return script["scenes"]
```

### `/src/video/payload_builder.py`

```python
import json
from pathlib import Path

def build_higgsfield_payload(script: dict, scenes: list, brand: dict | None = None) -> dict:
    """V0: construct a schema-valid Higgsfield API payload (align with live API docs)."""
    return {
        "script": script.get("narration", ""),
        "scenes": scenes,
        "voice": "professional_support",
        "style": "clean_product_tutorial",
        "brand": brand or {
            "colors": ["#005EB8", "#FFFFFF"],
            "logo_url": "https://company.com/logo.png",
        },
        "captions": True,
        "thumbnail": "auto",
    }

def write_payload(payload: dict, run_id: str, out_dir: str = "output/payloads") -> str:
    """Persist payload JSON for operator download / V0.1 submission."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = Path(out_dir) / f"{run_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)
```

### `/src/video/higgsfield_client.py`

```python
def generate_video(payload: dict, api_key: str, out_dir: str = "output/videos") -> dict:
    """
    V0.1: submit payload to Higgsfield API; store assets under out_dir.
    Keep secrets out of logs.
    """
    return {
        "provider": "higgsfield",
        "video_path": f"{out_dir}/placeholder.mp4",
        "thumbnail_path": f"{out_dir}/placeholder.png",
        "metadata": payload,
    }
```

### `/src/publish/publisher.py`

```python
def publish_locally(artifacts: dict, out_dir: str = "output/published") -> dict:
    """V0/V0.1: write approved artifacts to a local publish path."""
    return {"status": "published_local", "path": out_dir, "artifacts": artifacts}
```

### `/src/analytics/analytics_pipeline.py`

```python
def record_metrics(run_id: str, metrics: dict) -> None:
    print(f"Metrics recorded for {run_id}: {metrics}")
```

### `/src/telemetry/logging.py`

```python
import json
import time
from contextlib import contextmanager

def log_event(event: str, **fields) -> None:
    """Emit one structured JSON log line (no secrets)."""
    print(json.dumps({"event": event, **fields}, default=str))

@contextmanager
def stage(run_id: str, name: str, on_progress=None):
    start = time.perf_counter()
    log_event("stage_start", run_id=run_id, stage=name)
    if on_progress:
        on_progress({"run_id": run_id, "stage": name, "status": "start"})
    try:
        yield
        duration_ms = int((time.perf_counter() - start) * 1000)
        log_event("stage_end", run_id=run_id, stage=name, duration_ms=duration_ms, status="ok")
        if on_progress:
            on_progress({"run_id": run_id, "stage": name, "status": "ok", "duration_ms": duration_ms})
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        log_event(
            "stage_end",
            run_id=run_id,
            stage=name,
            duration_ms=duration_ms,
            status="error",
            error_type=type(exc).__name__,
        )
        if on_progress:
            on_progress({"run_id": run_id, "stage": name, "status": "error", "error_type": type(exc).__name__})
        raise
```

### `/src/telemetry/progress.py`

```python
"""In-memory progress bus for web UI (SSE or poll)."""

_PROGRESS: dict[str, list[dict]] = {}

def push(run_id: str, event: dict) -> None:
    _PROGRESS.setdefault(run_id, []).append(event)

def get(run_id: str) -> list[dict]:
    return list(_PROGRESS.get(run_id, []))
```

### `main.py` / orchestrator smoke path (V0)

```python
from src.intake.intake_handler import normalize_issue
from src.classifier.classify_issue import classify_issue
from src.rag.chroma_store import ChromaVectorStore
from src.rag.rag_retriever import retrieve_help_content
from src.scriptgen.script_builder import build_script
from src.scriptgen.scene_planner import plan_scenes
from src.video.payload_builder import build_higgsfield_payload, write_payload
from src.publish.publisher import publish_locally
from src.telemetry.logging import log_event, stage
from src.telemetry.progress import push

def run_pipeline(raw_issue: dict, generate_video: bool = False):
    """V0 default: export Higgsfield payload. V0.1: set generate_video=True when keyed."""
    run_id = raw_issue.get("id", "run-unknown")
    on_progress = lambda e: push(run_id, e)
    log_event("run_start", run_id=run_id)

    with stage(run_id, "intake", on_progress):
        issue = normalize_issue(raw_issue)

    with stage(run_id, "classify", on_progress):
        classification = classify_issue(issue, llm=None)

    store = ChromaVectorStore()
    store.add([0.0] * 768, {
        "title": "Fix posting errors in General Ledger",
        "steps": ["Verify journal entry is balanced"],
    })

    with stage(run_id, "retrieve", on_progress):
        help_content = retrieve_help_content(issue["raw_text"], store)

    with stage(run_id, "script", on_progress):
        script = build_script(help_content)
        scenes = plan_scenes(script)

    with stage(run_id, "payload", on_progress):
        payload = build_higgsfield_payload(script, scenes)
        payload_path = write_payload(payload, run_id)

    artifacts = {"payload_path": payload_path, "classification": classification}

    if generate_video:
        with stage(run_id, "higgsfield_api", on_progress):
            from src.video.higgsfield_client import generate_video as hf_generate
            artifacts["video"] = hf_generate(payload, api_key="FROM_ENV")

    with stage(run_id, "publish_local", on_progress):
        published = publish_locally(artifacts)

    log_event("run_end", run_id=run_id, status="ok")
    return {"published": published, "payload_path": payload_path}

if __name__ == "__main__":
    demo_issue = {
        "id": "ISSUE-001",
        "user": "operator",
        "text": "I'm getting a posting error in GL",
        "context": {"module": "GL"},
    }
    print(run_pipeline(demo_issue, generate_video=False))
```

---

## Integration notes

- **Corpus:** crawl published Flare XHTML from the authorized start URL, scoped to
  `www.intacct.com/ia/docs/en_US/help_action/`; re-index for quarterly majors and Friday minors.
- **Embeddings:** pull approved `nomic-embed-text` before the first index build.
- **LLM:** Ollama via `src/llm/client.py`; chat ≤ ~12B.
- **Vectors:** Chroma default; Pinecone skeleton for later.
- **V0 success:** valid Higgsfield payload on disk + UI review path.
- **V0.1:** Higgsfield API video assets under `output/videos/`.
- **UI:** React + Vite with FastAPI; text entry; progress via `telemetry.progress`.
- **Telemetry privacy:** persist metadata/hashes/timings/errors only—no full issue text or help chunks.
- **Intake stubs:** MCP + structured file — interfaces only until wired.
- **Visuals:** do not require screenshots absent from Intacct Help Center.
- **Secrets:** `.env` only; never log API keys.
- **Exit:** GitHub-ready tree with Actions; Vercel is a later full-cloud target.
