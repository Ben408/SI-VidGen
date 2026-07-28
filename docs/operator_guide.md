# Operator Guide

## Surfaces

| UI | Use when |
|---|---|
| **Create video** | You need a grounded script and walkthrough MP4 |
| **Ask Intacct** | You need a how-to answer (no video) |
| **Footer → Re-ingest Help** | Admins refresh local Help after a publish |

Video and Ask share the local LLM; corpus refresh **blocks** both until finished.

---

## Create video

1. Open the web UI → **Create video**.
2. Enter the support issue and optional module.
3. Leave **Generate video automatically** off for review.
4. Select **Generate video draft**; watch pipeline stages.
5. Review live Help links, OKF concepts (if present), and medias.
6. Edit script as needed → **Save new version**.
7. Set voice / pace / captions if using the local compositor.
8. **Approve & generate video** (or approve only).
9. Play/download the MP4 when status is ready.

Visuals come only from the Help image library. Missing screenshots show as yellow/red coverage—do not invent UI.

Demo scenario: [`sample_query.md`](sample_query.md).

---

## Ask Intacct

1. Open **Ask Intacct**.
2. Enter a product-usage question (cross-module goals are OK).
3. Select **Get Help-grounded answer**; watch stages (`classify` → `retrieve` → `retrieve_followup` → `answer`).
4. Read **summary → steps → notes**.
5. Use **Help references** (live HREFs) and optional OKF concepts to learn more.

If Help coverage is weak, the system **refuses** with a coverage gap message—treat that as a documentation signal, not a failed tool.

---

## Re-ingest Help (footer)

1. Confirm the dialog (full crawl + rebuild is lengthy).
2. Wait for stages: crawl/index → image library → OKF.
3. On success, video and Ask use the updated corpus.

Do not start video or Ask while refresh is running.
