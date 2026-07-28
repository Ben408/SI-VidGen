# Developer Guide

## Setup (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env

cd web
npm install
cd ..
```

### Corporate TLS / npm leaf-signature failures

If `npm install` fails with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, export Windows roots and set `NODE_EXTRA_CA_CERTS` / `PIP_CERT` (see historical notes in git history or corporate IT docs). Do not disable TLS verification.

## Build local knowledge assets

```powershell
# Safe 10-page index (dev)
python -m src.rag.index_help

# Full crawl + stale cleanup
python -m src.rag.index_help --full

# Screenshot library
python -m src.rag.build_image_library

# OKF parallel concepts (rules-only; refs help_assets)
python -m src.rag.build_okf
```

UI footer **Re-ingest Help** runs the full chain (crawl → index → library → OKF).

## Run

```powershell
# Terminal 1
python main.py

# Terminal 2
cd web
npm run dev
```

Open `http://localhost:5173`.

## Package map (high level)

| Path | Role |
|---|---|
| `src/api/` | FastAPI routes |
| `src/orchestrator.py` | Video/script pipeline |
| `src/qa/` | Ask Intacct agent |
| `src/rag/` | Crawl, chunk, Chroma, OKF, images, corpus refresh |
| `src/runtime_gate.py` | Serialize video / ask / refresh |
| `src/video/` | Payload + local compositor + optional Higgsfield |
| `web/src/` | Operator UI |

Gitignored runtime data: `data/help_xhtml/`, `data/help_assets/`, `data/okf/`, `data/vector_store/`. Local scratch under `archive/` is also gitignored.

## Verify

```powershell
ruff check .
pytest --cov=src
cd web
npm run lint
npm run build
```
