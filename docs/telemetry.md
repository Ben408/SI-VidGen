# Telemetry

## Privacy rule

Persistent telemetry is **metadata only**. It must not contain:

- Full issue text
- Retrieved help chunks
- API keys or authorization headers

## Run event fields

- `run_id`
- `stage`
- `status`
- `timestamp`
- `duration_ms`
- `error_code` (only on failure)

Run records also contain model identifiers, retrieval source IDs/hashes, scores, and final artifact paths as those stages are implemented.

The web UI polls the progress endpoint in Phase 0. Server-sent events may replace polling if needed.
