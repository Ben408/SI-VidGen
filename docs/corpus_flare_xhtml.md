# Flare XHTML Corpus

## Authorized source and crawl boundary

Start URL:

`https://termweb.atlassian.net/wiki/spaces/TWKB/overview`

Follow only URLs on `termweb.atlassian.net` whose paths start with:

`/wiki/spaces/TWKB/`

Configure start URL and allowed prefix in `config/corpus_catalog.txt` (`start_url, allowed_prefix, corpus_id` per row). Omitting `corpus_id` uses the **first** catalog row as the legacy default corpus.

Named corpora with different Help sites belong in `config/corpus_catalog.txt` (see `config/corpus_catalog.example.txt`):

```text
https://help.example.com/welcome.htm, https://help.example.com/, acme-kb
```

```powershell
python -m src.rag.ingest_catalog --full
python -m src.rag.ingest_catalog --full --corpus-id acme-kb
```

Ask/runs then send `corpus_id`. Refresh `POST /api/corpus/refresh` with `{ "corpus_id": "acme-kb" }` uses that catalog row’s URLs. The default corpus (no id) uses the first catalog row.

## Update cadence

- Minor help updates: Friday
- Major help revisions: quarterly

The crawler is polite, conditionally cached (ETag / Last-Modified), and content-hashed. Changed pages are re-embedded; unchanged pages are skipped. CI uses committed XHTML fixtures and never crawls the live corpus.

## Index commands

Safe development run (10-page cap):

```powershell
python -m src.rag.index_help
```

Custom cap:

```powershell
python -m src.rag.index_help --max-pages 25
```

Explicit full refresh:

```powershell
python -m src.rag.index_help --full
```

Only `--full` removes stale indexed sources. Cached XHTML and Chroma data are gitignored under `data/help_xhtml/` and `data/vector_store/`.

**UI:** footer **Re-ingest Help** runs full crawl + index + image library + OKF and blocks video/Ask while running.

## Chunking

The XHTML chunker:

- Removes navigation, scripts, styles, breadcrumbs, and repeated menu elements
- Preserves heading context and ordered/unordered step text
- Targets 768 estimated tokens and caps chunks at 1,024
- Records URL, content hash, title, heading path, and existing Help Center image URLs

Module/task style metadata is partially expressed via OKF procedure/UI concepts; further enrichment remains optional.

## OKF parallel bundle

After the XHTML cache exists, build a rules-only Open Knowledge Format bundle for procedure-shaped grounding and section-scoped screenshots (shared `data/help_assets/` refs, no image copies):

```powershell
python -m src.rag.build_okf
```

See `docs/okf.md`. Chroma continues to index XHTML; OKF is a parallel artifact used at retrieve/bind time and browsable in the operator UI.
