# Gamma Presentation Brief — AI-Generated Support Videos

## Generation guidance

Create a polished 10-slide client presentation for business, support, and content-leadership stakeholders at an enterprise accounting software company.

- Tone: credible, practical, forward-looking, and outcome-focused.
- Visual style: modern enterprise technology; clean layouts; restrained blue, white, and charcoal palette; subtle accounting-software UI motifs.
- Avoid: futuristic robots, excessive AI imagery, unsupported ROI claims, and dense technical diagrams.
- Use short headlines and minimal body copy. Turn supporting details into diagrams, process graphics, and metric cards.
- Clearly distinguish the local-first prototype from the future production vision.
- Refer to the product as **SI VidGen** where a product name is useful.

---

## Slide 1 — AI-Generated Support Videos for Accounting Software

### Subtitle
Turn trusted help content and real user issues into clear, reviewable video guidance.

### Supporting line
Reducing the effort required to create support videos while improving speed, consistency, and customer experience.

### Visual direction
Show a simple transformation: support question + trusted help article → polished instructional video. Use a clean accounting-software interface motif, not a generic AI robot.

### Speaker note
Support teams already know which questions customers repeatedly ask, and content teams already maintain the approved answers. The opportunity is to connect those assets through a governed AI workflow that produces useful video guidance in minutes rather than through a fully manual production cycle.

---

## Slide 2 — The Support Content Gap

### Headline
Customers need visual guidance, but traditional video production cannot keep pace.

### Key points
- Complex accounting workflows are difficult to explain through text alone.
- The same navigation, configuration, and error-resolution questions recur across support channels.
- Valuable Help Center content is often underused when customers cannot quickly find or apply it.
- Manual scripting, recording, editing, captioning, and publishing make video expensive to create and update.
- Frequent product and documentation releases create an ongoing content-maintenance burden.

### Closing statement
The result: customers wait longer, support teams repeat known answers, and high-value documentation does not reach its full potential.

### Visual direction
Use a four-part problem graphic: complex workflows, repeated tickets, underused help content, and slow video production. Connect them to a central “support content gap.”

### Speaker note
This is not primarily a shortage of knowledge. The approved knowledge already exists. The constraint is converting it into a format that is easy for customers to consume and practical for content teams to maintain.

---

## Slide 3 — The Opportunity: Reuse Trusted Knowledge at Video Speed

### Headline
AI can transform existing support knowledge into a scalable video-production system.

### Key points
- Start with authorized, published Intacct Help Center content as the source of truth.
- Match a user issue to the most relevant procedures through retrieval-augmented generation.
- Generate structured narration and scene instructions with a local language model.
- Bind real Help Center screenshots from a harvested image library—never invent product UI.
- Render a reviewable walkthrough video locally (screenshots + narration + captions), with optional cloud video providers later.
- Keep information developers and project managers in control through review and approval.

### Value statement
Create more support videos, respond to emerging issues faster, and maintain consistent messaging—without replacing editorial governance.

### Visual direction
Show a flywheel: trusted documentation → user need → AI-assisted draft → human approval → video → engagement insights → content priorities.

### Speaker note
The differentiator is grounded generation. The system does not ask a model to invent a support answer. It retrieves approved content first, then uses AI to adapt that content into a structured instructional format.

---

## Slide 4 — The Solution: A Governed Content-to-Video Pipeline

### Headline
From a support issue to a reviewable video package in one guided workflow.

### Pipeline
1. **Capture** — An operator enters a representative user issue in a browser-based interface.
2. **Understand** — A local Ollama model classifies the feature area, intent, and likely error type.
3. **Ground** — RAG retrieves relevant content from authorized Flare XHTML Help Center output.
4. **Author** — AI generates narration, actions, and a scene plan grounded in the retrieved source.
5. **Attach visuals** — Usable Help Center screenshots are bound from the local image library.
6. **Render** — The default path composes a local MP4 (Ken Burns + neural voice + captions) that preserves Help pixels; optional Higgsfield packages remain available.
7. **Review and approve** — Information developers or project managers inspect the script, scenes, sources, and play the video in the UI.
8. **Publish locally and measure** — Approved artifacts are stored locally with privacy-safe run telemetry.

### Guardrails
- Local LLM processing for the prototype
- Existing Help Center assets preferred and preserved in the demo video path
- No invented product screenshots
- No full issue text or retrieved help chunks retained in telemetry
- API secrets stored outside source control

### Visual direction
Use a horizontal pipeline with a visible human approval gate between draft generation and publication; show a small “Help screenshot preserved” badge on the render step.

### Speaker note
The prototype intentionally begins with operator-entered issues and local publishing. The stakeholder demo emphasizes Help fidelity over generative video restyling. MCP, Phrase localization, structured-file intake, and production publishing are next-phase integration points once English output quality is proven.

---

## Slide 5 — Architecture: Local-First, Modular, and Deployment-Ready

### Headline
A modular prototype validates the workflow without requiring production-system changes.

```mermaid
flowchart TD
    A[Web UI text entry] --> B[Normalize intake]
    B --> C[Local LLM Classifier]
    C --> D[RAG over Flare XHTML]
    D --> E[Local LLM Script Generator]
    E --> F[Scene + Help medias]
    F --> G[Local compositor MP4]
    G --> J[Review in Web UI]
    J --> K[Local publish path]
    K --> L[JSON telemetry + UI progress]
```

### Technology callouts
- **Operator experience:** React + Vite web UI (script edit, voice/pace/captions, inline video player)
- **Application layer:** FastAPI + Python 3.11
- **Local AI:** Ollama with `gemma3:12b`; lightweight fallback available
- **Knowledge retrieval:** Flare XHTML → local embeddings → Chroma + Help image library
- **Future portability:** Pinecone-ready vector-store interface
- **Video (demo):** Local screenshot compositor — Help pixels preserved
- **Video (optional):** Higgsfield MCP / explainer packages
- **Operations:** Structured JSON telemetry, progress feedback, tests, and GitHub Actions

### Visual direction
Render the Mermaid flow as a clean architecture diagram. Visually group intake, understanding, knowledge, authoring, rendering, review, and telemetry. Highlight the human review gate and “screenshots preserved.”

### Speaker note
Each provider sits behind a defined module, reducing lock-in. The prototype runs on local RTX 4070-class hardware with models up to approximately 12B parameters. The design can later move model inference, vector storage, and application hosting to managed services without rewriting the full workflow.

---

## Slide 6 — Prototype Demo: One Issue, One Traceable Video

### Headline
Demonstrate the complete path using a real accounting support scenario.

### Example issue
“A business user needs to import General Ledger journal entries from a CSV file—show how to prepare the CSV and upload it into Sage Intacct.”

### Demo flow
1. Enter the issue in the SI VidGen web interface (module: General Ledger).
2. Watch live progress as the system classifies and retrieves Help topics with screenshots.
3. Review the grounded title, narration, scene plan, and visual coverage.
4. Optionally adjust narration voice, pace, and burn-in captions.
5. Approve and generate — play the local walkthrough video inline (Help screenshots preserved).
6. Download the MP4 and the grounded script / payload artifacts as needed.

### What the demo proves
- The answer is grounded in authorized support content.
- Help Center screenshots remain authoritative in the video (no invented UI).
- The workflow is traceable from issue to source to script to MP4.
- Human reviewers remain accountable for the final result.
- Video rendering is separable from content logic (local compositor today; cloud providers later).

### Visual direction
Use a storyboard with four large frames: issue, source-backed script with Help screenshot, captioned local video player, and reviewer approval. Add a small provenance line connecting each frame.

### Speaker note
The English demo path no longer stops at a JSON payload. Stakeholders can watch a finished walkthrough in the browser. Cloud generative video remains optional and is secondary when Help fidelity matters.

---

## Slide 7 — Business Value Across the Support Ecosystem

### Headline
One workflow creates value for customers, support teams, and content operations.

### Customer value
- Faster access to task-based, visual guidance
- Clearer explanations of complex accounting workflows
- Consistent captions and repeatable instructions
- Better self-service experience at any time

### Support value
- More opportunities to deflect repetitive “how-to” contacts
- Reusable video responses for common issues
- Faster escalation from emerging issue pattern to support asset
- More agent time available for complex cases

### Content-team value
- Less manual effort across scripting, storyboarding, and provider handoff
- Consistent terminology and brand treatment
- Easier refreshes when Help Center content changes
- Reviewable outputs with source traceability and audit history

### Visual direction
Use three columns—customers, support, content operations—with a shared center label: “faster, governed support content.”

### Speaker note
The goal is not fully autonomous publishing in the prototype. The value comes from automating the repetitive production steps while preserving the review standards required for financial software guidance.

---

## Slide 8 — Measuring Impact from Baseline to Pilot

### Headline
Success will be measured through workflow efficiency, content quality, and customer outcomes.

### Prototype measures
- **Pipeline completion rate:** issues that produce a reviewable script and local walkthrough video
- **Grounding quality:** retrieved sources judged relevant by reviewers
- **Visual fidelity:** Help screenshots preserved (no invented product UI in the demo path)
- **First-pass approval rate:** outputs approved without material rewrite
- **Production cycle time:** issue intake to approved video package
- **Reliability:** stage success rate, processing time, and recoverable errors

### Pilot business measures
- **Ticket deflection:** reduction in contacts for video-covered topics
- **Time to resolution:** change in handling or customer resolution time
- **Video engagement:** starts, completion rate, and drop-off points
- **Self-service success:** users who resolve the issue without opening a ticket
- **Onboarding effectiveness:** completion and support-contact rates for guided workflows
- **Content reuse:** number of videos created or refreshed per source topic

### Measurement approach
Establish a baseline first, run a controlled pilot on a small set of high-volume issues, and compare results by topic and release period. Set numeric targets only after baseline data is available.

### Visual direction
Create two rows of metric cards: “Prototype validation” and “Pilot business impact.” Include a simple baseline → pilot → scale progression.

### Speaker note
This avoids speculative ROI. The prototype establishes technical and editorial feasibility; a focused pilot then quantifies ticket, engagement, and production-efficiency impact using the client’s actual baseline.

---

## Slide 9 — Roadmap: Prove, Connect, Personalize, Scale

### Headline
Advance in controlled stages, with quality and governance gates at each step.

### Phase 1 — Core pipeline: prototype (current)
- Browser-based text intake
- Local classification and RAG over authorized Flare XHTML
- Script and scene generation with Help image library binding
- Local compositor video (screenshots + TTS + captions)
- Review workflow, voice/pace controls, inline player, telemetry, and tests
- GitHub baseline with green CI

### Phase 2 — Connect providers and intake
- In-app MCP OAuth (Higgsfield and later Phrase)
- Optional Higgsfield cloud generation where appropriate
- Structured issue-file connectors
- Help Center, portal, or LMS publishing adapters
- Content-change detection for Friday minors and quarterly releases

### Phase 3 — Expand reach
- Multi-language scripts, narration, captions via Phrase TMS (hybrid with localized Help QA)
- Reusable templates by module, task type, and audience
- Production analytics and content-gap recommendations

### Phase 4 — Personalize and automate
- Role-, workflow-, and context-aware video variants
- Managed cloud inference and vector storage
- Policy-based auto-generation for approved use cases
- Human approval thresholds based on confidence and risk

### Visual direction
Use a four-stage maturity curve. Mark the current prototype boundary after Phase 1 (local video demo) and MCP/Phrase connectors at the start of Phase 2.

### Speaker note
The roadmap deliberately separates content intelligence from production integrations. Each phase delivers usable value while creating evidence for the next investment decision.

---

## Slide 10 — Recommended Next Step: Validate with a Focused Prototype

### Headline
Prove the workflow on real support content and a small set of high-value issues.

### Proposed prototype outcome
An end-to-end, local-first demonstration that converts representative Intacct support issues into grounded scripts, Help-screenshot walkthrough videos (with narration and captions), and optional provider packages—ready for information-developer review in the browser.

### Client inputs needed
- Confirm access to the authorized Flare XHTML Help Center output
- Select 5–10 recurring, high-value support scenarios for evaluation
- Identify information developers and project managers for review
- Provide approved brand guidance and existing reusable visual assets
- Agree whether cloud generative video (e.g. Higgsfield) is needed beyond Help-faithful local composition
- Agree on baseline measures and prototype acceptance criteria

### Decision enabled
At the end of the prototype, determine whether to proceed to an integrated pilot based on quality, reviewer effort, reliability, and measurable support opportunity.

### Closing line
**Turn trusted support knowledge into scalable video guidance—without giving up accuracy, control, or editorial governance.**

### Visual direction
End with a clear “Prototype → Evidence → Pilot” path and a single call-to-action button-style element: “Select the first support scenarios.”

### Speaker note
The immediate ask is not a production rollout. It is a focused validation using real content, real support scenarios, and explicit acceptance criteria so the client can make the next decision with evidence.
