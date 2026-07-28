# API

Base path: `/api`

## Common

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health + version |
| GET | `/capabilities` | Video backend, compositor options, workspace busy state |
| GET | `/workspace` | `{ busy, holder }` — `video` \| `ask` \| `refresh` \| null |

## Create video

| Method | Path | Purpose |
|---|---|---|
| POST | `/runs` | Queue video/script run (`202`) |
| GET | `/runs/{run_id}` | Run result |
| GET | `/runs/{run_id}/progress` | Stage events |
| GET | `/runs/{run_id}/script` | Editable script |
| PUT | `/runs/{run_id}/script` | Save script version + rebuild payload |
| POST | `/runs/{run_id}/approve` | Approve; optional `generate_video` + compositor options |
| GET | `/runs/{run_id}/payload` | Payload JSON |
| GET | `/runs/{run_id}/explainer-package` | Explainer package |
| GET | `/runs/{run_id}/medias` | Bound Help medias |
| GET | `/runs/{run_id}/medias/{asset_id}` | Media preview |
| GET | `/runs/{run_id}/video` | MP4 when ready |

### POST `/runs` body

```json
{
  "text": "User-reported issue",
  "module": "General Ledger",
  "screen": null,
  "error_code": null,
  "auto_generate": false
}
```

Raw `text` is not persisted in telemetry.

## Ask Intacct

| Method | Path | Purpose |
|---|---|---|
| POST | `/ask` | Queue product Q&A (`202`) |
| GET | `/ask/{ask_id}` | Result (`completed` \| `refused` \| `failed`) |
| GET | `/ask/{ask_id}/progress` | Stage events |

Same `IssueInput` body as `/runs` (module optional). Refused answers use `error_code: INSUFFICIENT_HELP_COVERAGE`.

## Corpus + OKF

| Method | Path | Purpose |
|---|---|---|
| POST | `/corpus/refresh` | Start full re-ingest (`202`) |
| GET | `/corpus/refresh/{refresh_id}` | Refresh result |
| GET | `/corpus/refresh/{refresh_id}/progress` | Stages: `crawl_index`, `image_library`, `okf` |
| GET | `/okf/status` | Bundle availability + counts |
| GET | `/okf/concepts` | List/filter concepts |
| GET | `/okf/concepts/{concept_id}` | Concept body + frontmatter |
| GET | `/image-library/coverage` | Screenshot coverage stats |

While refresh (or video/ask) holds the work gate, other LLM pipelines fail with `WORKSPACE_BUSY`.
