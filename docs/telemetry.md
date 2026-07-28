# Telemetry

## On disk

JSON run records under `data/runs/{id}.json` for:

- Video runs (`run-…`)
- Ask sessions (`ask-…`)
- Corpus refresh jobs (`refresh-…`)

Each record holds a `result` object plus ordered `events` (stage progress).

## Event fields

- `run_id`, `stage`, `status` (`started` \| `completed` \| `failed`)
- `timestamp`, optional `duration_ms`, optional `error_code`

## Privacy

Persist metadata, IDs, hashes, timings, model names, outcomes, and stable error codes.

**Do not** persist full issue/question text or retrieved Help chunk bodies in telemetry.

## UI

Create video and Ask panels poll `/progress` endpoints. Corpus refresh shows stages in the footer. `GET /api/workspace` exposes whether the work gate is held.
