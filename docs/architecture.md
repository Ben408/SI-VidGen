# Architecture

## V0 runtime

- React + Vite operator UI
- FastAPI backend
- Local Ollama inference (implemented in later phases)
- Flare-published XHTML crawler → embeddings → Chroma (implemented in Phase 1)
- Higgsfield payload JSON written to `output/payloads/`
- Metadata-only run telemetry under `data/runs/`

## Boundaries

Provider and storage interfaces must preserve future migration paths:

- Chroma → Pinecone
- Local Ollama → hosted model inference
- Local FastAPI → hosted API
- Local filesystem artifacts → managed object storage

Vercel is a future full-cloud target, not a production UI connected to a local backend.
