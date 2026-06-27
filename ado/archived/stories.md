# ADO stories & tasks

Track GE work that needs to show up on the ADO board. Update parent IDs once known.

## FSR prod-ops

**Parent epic:** `655509` — Data Ingestion Pipeline (Active)

### Stories under the epic

| ADO ID | Title | Status | Notes |
|---|---|---|---|
| 667154 | Ad-hoc FSR doc repair job | Closed | — |
| 661320 | Add document summary in metadata | **Active** | Pranesh wants to prioritize. Could fold doc-summary extraction into metadata scraping (single place). |
| 661325 | Clean up stale status from backfill job | Closed | — |
| 665713 | Decouple validation job | Closed | — |
| 664326 | ESN Repair patch for FSR Incremental Job | Closed | — |
| 665755 | ESN Resolution & Hardening | **Active** | — |
| 676369 | Missing FSR data — analysis (P0) | **Active** | Consumer-reported missing FSRs across 5 ESNs. Comms sent May 15, awaiting Vinayaka reply. See task row below. |
| 661322 | Separate VS Sync job | Closed | — |
| 661313 | Validate data correctness / Resolve data c… | Closed | — |

### My active items / tasks to create

| Title | Type | Parent story | ADO ID | Status | Notes |
|---|---|---|---|---|---|
| Doc summary script — prioritize for prod | Task | 661320 (Add document summary in metadata) | **661320** | **In progress** | Code + workflow updates done. Decision May 12: TOC flow only (Scenario B), drop PSOT exec-summary path. Next: Dev validation — run `PW_SDG_FSR_Generic_Attribute_Backfill` with `FSR_BACKFILL_NAME=document_summary_toc` (dry then apply) on a controlled sample, then P1 incremental smoke + checks 1.11–1.15. After sign-off: full backfill + promotion. Tracker ref: UI-04. |
| Multi-ESN logic implementation / ESN Resolution & Hardening | Task | 665755 (ESN Resolution & Hardening) | **665755** | **In progress** | Two parallel tracks: (a) **UI-14 interim patch** (`hotfix/664196-spark-connect-equip-cols`) — `fsr_pdf_ref`-driven row-duplication + mechanical metadata ESN fix, in review. (b) **UI-15 proper fix** — Phase 0/0b done; Phase 1 design split into 3 docs (extractor, multi-ESN data model, incremental ingestion + watermark) under [`../../FSR/ESN-resolution/design/`](../../FSR/ESN-resolution/design/). New direction (Pranesh May 6): many-to-many ESN↔doc via row fan-out `document_id = <uuid>_<esn>` + new `source_doc_id` column. UI-07 / UI-13 fold under this. |
| Missing FSR data — analysis (P0) | Task | (TBD — under 655509 epic) | **676369** | **In progress — comms sent May 15, awaiting reply** | Consumer-reported missing FSRs for 5 ESNs (290T505, 337X180, 337X790, 324X043, 338X415). Per-ESN verification done May 15 — revised finding: all 5 are short upstream in `fsr_pdf_ref` (DA-team scope). One file (`8fe0793d-...`) the consumer flagged as missing is actually fully ingested + in VS index — the original "10/1 split" was wrong (run-log gap was instrumentation lag, not a discovery skip). Vinayaka email + Rashmin Slack sent May 15 EOD. Two follow-ups opened for Mon: consumer-search miss dig (likely multi-ESN suffix mismatch) + VS index sync staleness (last commit May 7). Tracker refs: UI-20 / UI-21 / UI-22. Comms + outputs under [`../../fsr-prod-ops/comms/2026-05-15/`](../../fsr-prod-ops/comms/2026-05-15/) and [`../../fsr-prod-ops/prod-issues/missing-FSRs/`](../../fsr-prod-ops/prod-issues/missing-FSRs/). |
| Sync with Pranesh — agenda TBD | Sync | — | — | Tomorrow | Confirm topic before the call. |

## OSA

| Title | Type | Parent | ADO ID | Status | Notes |
|---|---|---|---|---|---|
| OSA — Review Step 8 and FSR dependency | Task | (TBD — ask Mayank for umbrella story) | **672431** | **In progress** | Step 8 review done + sent to Mayank May 11 (`OSA/comms/2026-05-11-slack-mayank-step8-review.md`). May 15: full WBS review on Kaif's data-pipelines xlsx — added 10 gap tasks (run log, DQ, UC perms, multi-env, multi-key fan-out, VS sync, design doc, runbook, cost monitoring) + per-task H/M/L hour estimates + per-source rollup + 24-week calendar + 8-item risk register. Estimation doc at [`../../OSA/estimation/wbs-review-and-estimates.md`](../../OSA/estimation/wbs-review-and-estimates.md). Hour table sent to Kaif for paste into xlsx. Risk flag sent to Sreedhar (centralization unclarity + DA-team landing-date dependency). Next: incorporate Kaif review + Sreedhar steer. |
| OSA discovery — ramp up + Step 8 review | Task | (same OSA umbrella) | — | Folded into 672431 | — |
| Step 8 doc-vs-demo gap surfaced to DS | Task | (same OSA umbrella) | — | Done May 11 | See `OSA/comms/2026-05-11-slack-mayank-step8-review.md`. |

## Asks open

- **Mayank (OSA):** is there an umbrella story I can park OSA discovery + Step 8 tasks under, or do I create one?
- **Pranesh (FSR):** what's the parent epic/story for doc-summary script + multi-ESN tasks?
