# Sample workflow query (image-rich)

Use this sample to verify Help image-library grounding and Higgsfield explainer media packaging.

## Operator input

**Module:** General Ledger

**Support issue:**

> A business user needs to import General Ledger journal entries from a CSV file. Create a short instructional video showing how to prepare the CSV with journal header and line-item rows, how entries are grouped by date, and how to upload the prepared file into Sage Intacct. Use the official Help examples of the CSV layout.

## Why this is grounded

The indexed Sage Intacct Help topics for **Import GL journal entries** / **Import journal entries** document CSV preparation and include multiple `EXAMPLE-*` screenshots of header/line layout and date grouping.

Primary sources:

- [Import GL journal entries](https://www.intacct.com/ia/docs/en_US/help_action/More/Uploading_Data/GL/import-GL-journal-entries.htm)
- [Import journal entries](https://www.intacct.com/ia/docs/en_US/help_action/General_Ledger/Journal_Entries/Create_or_edit_journal_entries/import-journal-entries-ns.htm)

## Expected test behavior

- Classification identifies General Ledger journal CSV import
- Retrieval ranks an import topic that has library screenshots
- Script scenes bind `help_asset` URLs from the Help image library
- Payload `medias` lists **local file paths** that exist on disk (max 14)
- Explainer package writes:
  - `*-explainer.json` (`job_set_type: video_explainer`)
  - `*-medias.json` (JSON array for `higgsfield ... --medias @file`)
  - `*-prompt.txt`
- `visual_coverage` is **green** when at least one media file is attached
- Approval does not spend Higgsfield credits unless generation is explicitly requested

## Higgsfield generation

With `higgsfield auth login` completed, **Approve & send** uploads attached Help screenshots through Higgsfield MCP (`gemini_omni`) and polls until a local MP4 is ready under `output/videos/`.

**Account gate:** some Plus/trial logins still return `only_mcp_usage_on_trial_is_available` for real generation when authenticated via the CLI OAuth token (upload + cost preflight may work). In that case generation must use Higgsfield’s official MCP connector OAuth, or API/CLI access must be unlocked on the plan ([mcp-credits](https://higgsfield.ai/mcp-credits)).

Packaging-only validation (no credits): inspect the written explainer files under `output/payloads/`. Do **not** restyle Intacct UI—Help screenshots are authoritative.

## Earlier sample (text-only visuals)

The journal-reversal sample remains valid for text grounding, but that Help page has no usable screenshots. Prefer this CSV-import sample when validating the image library.
