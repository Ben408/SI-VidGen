# Sample workflow query (image-rich)

Use this sample to verify Help image-library grounding and **local compositor** video (default). Optional Higgsfield packages remain exportable.

## Operator input (Create video)

**Module:** General Ledger

**Support issue:**

> A business user needs to import General Ledger journal entries from a CSV file. Create a short instructional video showing how to prepare the CSV with journal header and line-item rows, how entries are grouped by date, and how to upload the prepared file into Sage Intacct. Use the official Help examples of the CSV layout.

## Ask Intacct variant

Same topic without video intent:

> How do I prepare a CSV and import General Ledger journal entries into Sage Intacct?

Expect structured summary/steps/notes plus live Help links, or a coverage refusal if retrieval is weak.

## Why this is grounded

Indexed Help for **Import GL journal entries** includes `EXAMPLE-*` screenshots of CSV layout.

- [Import GL journal entries](https://www.intacct.com/ia/docs/en_US/help_action/More/Uploading_Data/GL/import-GL-journal-entries.htm)
- [Import journal entries](https://www.intacct.com/ia/docs/en_US/help_action/General_Ledger/Journal_Entries/Create_or_edit_journal_entries/import-journal-entries-ns.htm)

## Expected behavior (video)

- Classification → retrieval (OKF-enriched) → script with library `help_asset` URLs
- `visual_coverage` **green** when medias bind
- Local compositor MP4 under `output/videos/` after approve+generate
- Explainer/payload JSON still written for optional cloud backends

## Local render smoke

```powershell
python scripts/render_sample_local_compositor.py
```
