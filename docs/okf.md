# OKF (Open Knowledge Format)

Rules-only conversion from the local Flare **XHTML cache** into a parallel knowledge bundle under `data/okf/`.

## Build

```powershell
python -m src.rag.build_okf
# smoke:
python -m src.rag.build_okf --max-pages 25
```

Also rebuilt by footer **Re-ingest Help** / `CorpusRefreshService`.

Images are **not** copied into OKF; concepts reference `data/help_assets/`.

## Concept types

| Type | Meaning |
|---|---|
| `HelpTopic` | One Help page; keeps live `page_url` |
| `Procedure` | Instructional section |
| `UIScreen` | UI-oriented section |
| `HelpSection` | Other section content |
| `HelpAsset` | Screenshot metadata + library ref |

## Pipeline use

Chroma still indexes XHTML. After retrieval, OKF:

1. Prefers procedure body text for script / Q&A grounding
2. Scopes `asset_urls` to the matching section
3. Supports heading-aware binder ranking

## Operator UI

- Official sources link to live Help
- Derived concepts browsable on Create video and Ask results
- `GET /api/okf/status`, `/api/okf/concepts`, `/api/okf/concepts/{id}`
