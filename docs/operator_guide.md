# Operator Guide

## V0 workflow

1. Open the local SI VidGen web UI.
2. Enter the support issue and optional Intacct module.
3. Leave **Generate video automatically** off for the normal review flow.
4. Select **Generate video draft**.
5. Follow stage progress in the run panel.
6. Review the official Help sources and editable script.
7. Edit the title, narration, scene actions, visuals, or voiceover.
8. Select **Save new version**. This preserves the prior script and rebuilds the
   Higgsfield payload from the edited script.
9. Select **Approve script**, or **Approve & send to Higgsfield** after live
   generation is configured.

Scene source IDs and Help assets remain constrained to the generated grounded
script. Unsupported source IDs or newly invented asset URLs are rejected.

The automatic-generation toggle is off by default and remains unavailable until
the Higgsfield API integration is enabled. When enabled, it bypasses manual
review only for scripts that pass normal schema and grounding validation.

Use [`sample_query.md`](sample_query.md) while representative test data is
pending.
