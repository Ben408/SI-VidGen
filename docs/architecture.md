# Architecture

## Runtime (current)

- **UI:** React + Vite — tabs **Create video** / **Ask Intacct**, footer **Re-ingest Help**
- **API:** FastAPI (`src/api/app.py`)
- **LLM:** Local Ollama (classify, script, Q&A, embeddings)
- **Corpus:** Flare-published XHTML → chunk/embed → **Chroma**
- **Parallel OKF:** rules-only concepts under `data/okf/` (procedure text + section-scoped assets)
- **Images:** shared `data/help_assets/` library (not copied into OKF)
- **Video:** default **local compositor** MP4; optional Higgsfield
- **Concurrency:** `WorkGate` serializes video / ask / corpus refresh on the local GPU/LLM
- **Telemetry:** metadata-only JSON under `data/runs/`

## Knowledge path

```text
Live Help (XHTML)
    ├─► data/help_xhtml/          cache
    ├─► Chroma                    semantic retrieval
    ├─► data/help_assets/         screenshots for video
    └─► data/okf/                 concept markdown (parallel)
         └─ enrich retrieved chunks → binder / Q&A
```

## Product surfaces

| Surface | Behavior |
|---|---|
| Create video | Issue → classify → retrieve+OKF → script → binder → review → local MP4 |
| Ask Intacct | Question → classify → multi-hop retrieve+OKF → structured answer or refuse |
| Footer refresh | Confirm → crawl → Chroma → image library → OKF (blocks other work) |

## Migration boundaries

- Chroma → Pinecone (`VectorStore` protocol)
- Local Ollama → hosted inference
- FastAPI → hosted API
- Local files → object storage
- Vercel only after API/model/storage are hosted (no split UI/local-backend production)
