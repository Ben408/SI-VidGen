# API

Base path: `/api`

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service health and version |
| POST | `/runs` | Queue a run from text issue input |
| GET | `/runs/{run_id}` | Read run result/status |
| GET | `/runs/{run_id}/progress` | Read ordered stage events |
| GET | `/runs/{run_id}/payload` | Download completed payload |

## POST `/runs`

```json
{
  "text": "User-reported issue",
  "module": "General Ledger",
  "screen": null,
  "error_code": null
}
```

The raw `text` is processed in memory and excluded from run telemetry.
