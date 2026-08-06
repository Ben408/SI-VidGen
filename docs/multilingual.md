# Multilingual Video Content Decision

## Requirement

Sage Intacct Help is available in **four languages**, and the Intacct team needs instructional video content in:

- English (`en_US`)
- French
- German
- European Spanish

Localization currently uses **Phrase TMS**, which also exposes an MCP server that SI VidGen can integrate with later.

## Decision needed after English V0 grounding

English end-to-end grounding must work first: classify → retrieve → grounded script → reviewable payload. Only then choose a multilingual strategy.

## Candidate approaches

### Option A — Retrieve localized help, generate each language independently

1. Index English, French, German, and European Spanish help corpora separately (or with a language metadata filter).
2. Detect or require a target language at intake.
3. Retrieve only same-language help.
4. Generate script/payload in that language from those sources.

**Pros:** Highest fidelity to localized product wording and screenshots already present in Help Center.  
**Cons:** Requires complete, current localized help for every language; four times the indexing/QA surface; local LLM quality may vary by language.

### Option B — Generate English, then localize via Phrase TMS

1. Produce a reviewed English script/payload.
2. Send approved narration/scene text into Phrase TMS through MCP or API.
3. Rebuild language-specific payloads from localized strings.

**Pros:** Fits existing localization process and terminology control.  
**Cons:** Localized videos may lag English; UI/visual references still need language-aware validation against localized Help.

### Option C — Hybrid (recommended working assumption)

1. English is the authoring source of truth for V0/V0.1.
2. Phrase TMS localizes narration, voiceover, and on-screen callouts after English review.
3. Retrieval against localized Help is used as a QA pass to catch UI-label mismatches and wrong screenshots before non-English payload approval.
4. Operators choose target language(s) after English approval, not at first draft.

**Pros:** Balances speed and accuracy; matches how many content teams already work; reuses Phrase ownership.  
**Cons:** More orchestration complexity; needs clear ownership between content and localization.

## Recommended decision for SI VidGen

Adopt **Option C (Hybrid)** as the default plan unless Intacct content/localization requires fully independent localized authoring from day one.

### Why not A first?

Independent generation depends on crawlable, current FR/DE/ES-ES Help XHTML, language-aware retrieval metadata, and stronger non-English grounding QA. That is valuable, but it should not block English V0.

### Why not B alone?

Phrase-only localization without localized Help QA risks shipping English UI labels/screenshots into non-English videos.

### Phrase TMS MCP role

Use Phrase MCP after English script approval to:

1. Create/update a localization job from scene JSON (narration, voiceover, callouts).
2. Pull completed FR/DE/ES-ES strings.
3. Rebuild language-specific review payloads.
4. Optionally attach localized Help retrieval evidence for QA.

Do **not** send raw support-issue text or full help chunks into Phrase unless localization policy explicitly allows it.



DECISION: Adopt Option C. Privileged users (localization team members and testers) in the Slack channel may opt to incur costs by sending materials to Phrase or by calling **Microsoft / Azure trained MT** (T3). All other channel members receive translations from the local translated Help corpus, Phrase TM lookups (latency only), or `translategemma:12b`.

## Ask answer localization router (Slack)

See Hermes-Local [`docs/ask-localization-router.md`](../../Hermes-Local/docs/ask-localization-router.md) and [`docs/benchmarks.md`](../../Hermes-Local/docs/benchmarks.md).

**Pillars:** quality / speed / cost.

| Path | Tier | Notes |
|---|---|---|
| In-lang Help + lexical Help gate | T1 | Prefer published wording |
| Phrase TM content search | T1 | Free; ~1.7s baseline — one hop max on Ask |
| Termweb | T1 standalone | **Not** on Ask compose critical path (~7s baseline) |
| translategemma:12b | T1 | Free fill-in (~0.8s warm) |
| Microsoft trained MT | T3 | Explicit; Azure key in backend `.env` |
| Phrase NextMT / create-job | T3 deferred | Not Ask one-shots |

**Latency:** Ask compose additive budget ≤3s p50; skip hops when exhausted (`budget_partial`).

## Open questions for the Intacct / localization teams

1. Are French, German, and European Spanish Help Center XHTML builds complete and crawlable under the same authorization model as English?  
Yes
2. Should operators choose language at intake, or generate English first and request localization later?  
enable users to Ask Intacct in French, German or Spanish and receive answers in the same language, or to ask in English and specify the answer should be provided in French, German or Spanish (default to same language as asked is provided, allow for user to specifiy answer should be in a different language)
3. Who owns final approval for non-English scripts—local content specialists, localization, or both?  
Localization PMs and testers, the same users as can incur costs via the Phrase MCP interface. All users can do tasks like query translation memory or terminology for translated results, only Localization PMs and testers are allowed to call functions such as create a project, or localize content via Phrase.
4. Should Phrase TMS receive scene JSON, plain narration only, or a dedicated localization package?  
Dedicated localization package, my suggestion is that we transform the script portions that will appear on screen or be part of the audio into XLIFF 1.2 format. Conversions, cleaning, etc is a completed project, this code is available locally at: F:\Language Data Workbench and on Github: [Ben408/TMXmatic](https://github.com/Ben408/TMXmatic) 
5. Are Help Center assets language-specific enough that English screenshots/assets must never appear in non-English videos?  
Yes
6. Which Phrase project/workflow/MCP credentials should SI VidGen use in non-prod vs prod?  
This is TBD

## Implementation gate

Do **not** implement multilingual generation until:

- English retrieval-grounded scripts are consistently reviewable  
They are
- The localization ownership model above is confirmed  
It is
- Authorized FR/DE/ES-ES Help URLs (or Phrase-only scope) are documented  
They are avaalbe and active on the Intacct help web site, just under the specific local tags in the path, e.g. [Sage Intacct Hilfecenter](https://www.intacct.com/ia/docs/de_DE/help_action/Intacct_basics/welcome.htm)

## Provisional backlog (post-English)

1. Add `target_languages` / `answer_language` to Ask and runs — **done** (`IssueInput.source_language`, `answer_language`, `target_language`)
2. Add Phrase export package writer for approved English scripts — Hermes `localize-script` T3 path
3. Phrase MCP + Termweb skills — **done** in Hermes-Local
4. Localized Help crawler prefixes — **done** (`HELP_LOCALES=all` / `--locales`); caches under `data/help_xhtml/{locale}/` (EN may remain legacy root)
5. Language-aware retrieval filter + QA — **done** (`retrieve_help_content(..., language=)`)
6. Locale video: FR/DE/ES voices + block EN screenshots — **done** (asset filter + compositor voices)
7. Slack T1–T3 + `/help` + `@Hermes` — **done** in SI-VidGen-Slack

### Crawl

```bash
# smoke
python -m src.rag.index_help --max-pages 5 --locales fr_FR,de_DE,es_ES
# full
python -m src.rag.index_help --full --locales fr_FR,de_DE,es_ES
# or env HELP_LOCALES=all
```

Locale URL pattern (verified 200):

`https://www.intacct.com/ia/docs/{en_US|fr_FR|de_DE|es_ES}/help_action/...`

