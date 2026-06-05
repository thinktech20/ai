# promo/ — Sr Consultant → Principal

Working space for the promo package. Updated by the `check-in` chat mode and by hand.

## Active (top level — edit these)

| File | What |
|---|---|
| [`evidence-bank.md`](evidence-bank.md) | Source of truth: stories, metrics, quotes from 2023–2026 appraisals + peer feedback. Refer back here when drafting; don't re-mine sources. |
| [`user-inputs.md`](user-inputs.md) | Live working doc — Sections 2–4 (revenue numbers, sanity checks, self-ratings). User fills, agent stitches. |
| [`feedback-asks.md`](feedback-asks.md) | Slack DM drafts for Anytime-Feedback asks (Sreedhar, Pranesh, Tao). |

## Folders

| Folder | What | Touched? |
|---|---|---|
| [`input-docs/`](input-docs/) | Raw source material — Eric's templates (`Template - Promotion Plan.pptx`, `Template - Promotion Readiness Reflection.xlsx`), profile, IW, previous appraisals + recommendations, Eugene context dump. | Read-only. |
| [`extracted/`](extracted/) | Plain-text extractions of `input-docs/` produced by `_scripts/extract_inputs.py`. | Re-run script if inputs change. |
| [`output-docs/`](output-docs/) | Shipped / draft outputs. Current: `Promo-Reflection-and-Plan_DRAFT.xlsx` (shared with Eric May ~9), `01_*_DRAFT.md`, `02_*_DRAFT.md`, `build_xlsx.py`. | Active — needs conversion into Eric's exact template format. |
| [`conversations/`](conversations/) | Dated event notes — PL reviews, 1:1s, etc. Newest = `2026-05-13-pl-conversation.md`. | Append new dated files. |
| [`eugene-track/`](eugene-track/) | Eugene-specific workstream — artifact outline, future readiness doc, Slack drafts, meeting notes. | Active. |
| [`_scripts/`](_scripts/) | Utilities (`extract_inputs.py`). | Run when needed. |

## State (May 14, 2026)

- **PL review done May 13** → `conversations/2026-05-13-pl-conversation.md`. Headline: visibility/brand is #1 gap; Eugene is gatekeeper.
- **Eugene track active** → `eugene-track/artifact-outline.md`. Three commitments: (1) AI-in-production artifact (combined with Arch-Hive #2 talk), (2) readiness doc in Eric's template, (3) schedule meeting once (1)+(2) are in hand.
- Day-to-day status lives in [`../tracker.md`](../tracker.md) under §3 Slalom promo. Long-horizon plan in [`../roadmap.md`](../roadmap.md) under Goal #3.
