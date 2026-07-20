# API

Base path: `/api`

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service health and version |
| GET | `/capabilities` | Report whether Higgsfield generation is enabled |
| POST | `/runs` | Queue a run from text issue input |
| GET | `/runs/{run_id}` | Read run result/status |
| GET | `/runs/{run_id}/progress` | Read ordered stage events |
| GET | `/runs/{run_id}/payload` | Download completed payload |
| GET | `/runs/{run_id}/script` | Read the current editable script |
| PUT | `/runs/{run_id}/script` | Save a new script version and rebuild payload |
| POST | `/runs/{run_id}/approve` | Approve, optionally requesting generation |

## POST `/runs`

```json
{
  "text": "User-reported issue",
  "module": "General Ledger",
  "screen": null,
  "error_code": null,
  "auto_generate": false
}
```

The raw `text` is processed in memory and excluded from run telemetry.
`auto_generate` defaults to `false` and only submits when the generation
capability is configured.
