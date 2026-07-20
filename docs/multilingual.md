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

## Open questions for the Intacct / localization teams

1. Are French, German, and European Spanish Help Center XHTML builds complete and crawlable under the same authorization model as English?
2. Should operators choose language at intake, or generate English first and request localization later?
3. Who owns final approval for non-English scripts—local content specialists, localization, or both?
4. Should Phrase TMS receive scene JSON, plain narration only, or a dedicated localization package?
5. Are Help Center assets language-specific enough that English screenshots/assets must never appear in non-English videos?
6. Which Phrase project/workflow/MCP credentials should SI VidGen use in non-prod vs prod?

## Implementation gate

Do **not** implement multilingual generation until:

- English retrieval-grounded scripts are consistently reviewable
- Payload schema is validated against Higgsfield without spending generation credits unnecessarily
- The localization ownership model above is confirmed
- Authorized FR/DE/ES-ES Help URLs (or Phrase-only scope) are documented

## Provisional backlog (post-English)

1. Add `target_languages` to run metadata (default `["en_US"]`)
2. Add Phrase export package writer for approved English scripts
3. Add Phrase MCP client stub + config
4. Add localized Help crawler prefixes when authorized
5. Add language-aware retrieval filter + QA report
6. Extend review UI for language packages
