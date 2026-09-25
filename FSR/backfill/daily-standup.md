# Daily standup log

Running log of what I worked on day-to-day. Newest entry on top. Each entry is what I'd say in standup — keep it short.

Format per day:
- **Yesterday:** what landed
- **Today:** what I'm picking up
- **Blockers:** anything waiting on someone else (or "none")

No internal table names / person names if there's a screen-share risk — paraphrase.

---

## 2026-05-12 (Tue)

- **Yesterday:**
  - Finalized and pushed PR for document summary (TOC-only, covers both backfill and incremental).
  - Cleaned up compliance, updated tracker/plan, and prepared for Dev validation.
- **Today:**
  - Validate document summary in Dev (dry run, apply, incremental smoke test, validation checks 1.11–1.15).
  - Collect any test cases/ESNs from Pranesh if provided.
  - Prep for ESN multi-design review with Pranesh/Abhijeet.
  - Going through OSA docs shared by Tao and building up understanding — FSR will be used across multiple OSA steps, may feed into ESN design.
  - Follow up with Databricks team on removing hardcoded LLM gateway API keys from `databricks.yaml` (UI-12) now that secret-scope path should be ready.
- **Blockers:**
  - None, pending Dev validation and feedback from Pranesh.

## 2026-05-07 (Wed)

- **Yesterday:** ESN smoke-test on a small dev cohort with the DS reference extractor. Sanitized notebook for sharing, captured findings + design draft.
- **Today:**
  - Re-ran the smoke test with the lower count threshold — top-1-by-count matches stored on 8/9 happy-path docs; one alpha-tiebreak loss to track.
  - Measured ESN quality across the prod corpus (18K completed docs). 0 redacted, 5 null. Confirmed ~166 docs with the suspect short-numeric pattern (sequential / multi-doc-duplicate IDs leaking into the ESN field) — that's the real prod failure mode, much smaller scope than the dev exercise implied.
  - Picked the extractor approach: single LLM call with a modified prompt that also returns a body-text count map; resolver picks top-1. Captured in design draft + tracker.
- **Tomorrow:**
  - Spot-check the 4 recovered ESNs from the dev cohort against source PDFs (blocking for sign-off).
  - Pull a 10-doc cohort from the prod suspect-numeric bucket and run the same smoke test to confirm body-text count beats the page-1 scrape.
  - Re-run the one error doc with a larger token budget.
- **Blockers:** none.

---

## 2026-05-06 (Tue)

- **Yesterday:** UI-14 interim ESN side-step patch in review on hotfix branch.
- **Today:**
  - Closed UI-08 (50 stuck `in_progress` docs from May 2 backfill blip) — verified daily ingestion's stale-claim recovery already cleaned them up; no manual SQL needed. Tracker + Slack update sent.
  - Landed defensive fix for the LLM `'content'` KeyError pattern (the one that took out 4 docs in a single batch on May 1) in the metadata extractor — bad LLM responses now surface a clear retryable error instead of failing the whole micro-batch.
  - Cleaned up the tracker: closed UI-09 (monitoring team owns), closed UI-10 (already fixed in source — just needs bundle redeploy by monitoring/Databricks team), parked UI-04 + remainder of UI-11.
  - Handed UI-12 (LiteLLM key rotation) to the Databricks team — Slack draft ready.
  - Drafted Slack note on terminal failures plan.
  - Added two new top-priority items: UI-15 (proper ESN resolution — UI-14 was only a patch) and UI-16 (split validation job out of incremental pipeline + smoke-test incremental ingestion after UI-14 lands).
  - UI-16(a) split DQ validation out of incremental ingestion: dropped inline `validate` task from ingestion job, renamed standalone job to `PW_SDG_FSR_DQ_Validation`, added paused daily schedule offset 3h from ingestion. Branch `chore/ui-16-split-validation-job` pushed.
  - UI-17 made the DQ log SRE-ready: de-dup recurring terminal-failure rows in 5.7, added `failure_category` enum column to `fsr_data_quality_log`, backfilled `pdf_name` on metadata-fail rows. Branch `chore/664259-dq-log-sre-ready` pushed.
  - UI-18 pipeline-side terminal-failure handling on the same branch: P1 lifetime retry gate (`metadata_retry_count` mirrors P2's `chunk_retry_count`) + per-batch P1 audit rows in `fsr_run_log`. Pushed.
  - Validated UI-17 + UI-18 end-to-end on dev against the real `vaid` tables: DDL idempotent ALTER added both columns without rewriting existing rows; P1 retry counter goes NULL→1 on first failure; P1 audit row lands in `fsr_run_log` with `job_name='PW_SDG_FSR_Metadata'`; `failure_category` populates correctly on insert; de-dup window skipped 829 of 830 standing terminals on the second run; classifier confirms `gateway_error` on a re-logged 502 doc.
  - Two follow-on fixes uncovered during dev validation, both folded into the same branch: (a) `FSR_TARGET_PDF_NAMES` was only scoping the volume *discovery* step — the work queue still pulled the full pending + retry-eligible backlog. Patched so the parameter actually means "only these docs" end-to-end. Backfill behavior unchanged. (b) `_classify_failure()` was only matching the `KeyError 'content'` shape — ~520 of 524 dev `unknown` rows today were raw HTTP 5xx gateway errors. Extended to also match `500/502/503/504 server error`, `Bad Gateway`, `Gateway Time-out`, `Service Temporarily Unavailable`, `Internal Server Error`, and `LLM call failed after all retries` → all routed to `gateway_error`.
  - Renamed UI-17/18 branch from `chore/ui-17-dq-log-sre-ready` to `chore/664259-dq-log-sre-ready` to carry the ADO ticket id.
- **Tomorrow:**
  - Start UI-15: write up the ESN problem space + options comparison; aim for a design doc draft under `internal/adr/`.
  - UI-16(b): smoke-test incremental ingestion on dev after UI-14 lands.
  - Open PRs for `chore/664259-dq-log-sre-ready` and `chore/ui-16-split-validation-job`. After merge: run `FSR_DDL_Provision` on prod (`FORCE_RESET=false`, additive ALTERs only), write the SRE runbook section "how to re-ingest a terminal failure", then unpause the daily DQ schedule.
- **Blockers:** none.

### Follow-up items uncovered during dev validation (separate tracker entries)

- [ ] 5.1 / 5.4 integrity check failures on dev: 174 chunk_ids with duplicate rows + 1 doc+page combo with >50 chunks. Likely UI-14 row-duplication artifact (different `chunk_id` format `MD5(doc_id + '_' + chunk_idx + '__' + esn)`). Needs a dedicated investigation under a new tracker item.
- [ ] 524 gateway-error FAILs on dev in one day means the in-call retry loop (`FSR_MAX_RETRIES=3`, exponential backoff) exhausted on each. With UI-18's lifetime gate, gateway-failed docs that hit 3 lifetime attempts get permanently quarantined even though gateway issues are transient. Need either a "don't increment counter on gateway_error" rule in the failure MERGE, or an SRE bulk-reset procedure for `metadata_retry_count=0 WHERE failure_category='gateway_error'` after a known gateway incident.

### ADO ticket to file (and close once raised)

- [x] **Pipeline + DQ log hardening (UI-16 / UI-17 / UI-18) — ADO #664259.** Three small PRs on `pw_sdg_ai_ser_repo`: (1) decouple validation job from incremental ingestion + rename to DQ validation, (2) make the DQ log table SRE-handoff-ready (de-dup recurring terminal-failure rows, add failure-category column, backfill pdf_name), (3) add P1 lifetime retry gate + P1 run-log audit rows. Plus two dev-validation follow-on fixes folded onto the same branch (TARGET work-queue filter + classifier 5xx coverage). No consumer impact; observability + run-loop hygiene only. Branch: `chore/664259-dq-log-sre-ready`.

---

## Template (copy for new day)

## YYYY-MM-DD (Day)

- **Yesterday:**
- **Today:**
- **Blockers:**
