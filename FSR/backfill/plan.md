# Post-deployment FSR — working plan

> **Scope of this folder.** Local-only working notes (this machine). The only git-tracked code is `pw_sdg_ai_ser_repo/`. Nothing in this folder is committed.

## How this folder is organized

| File | Purpose | Edited by |
|---|---|---|
| `plan.md` (this file) | Cross-session plan + workflow notes so we don't lose context between chats. | Me + you |
| `tracker.md` | Live UI-NN tracker. 9-column impact table (Critical + Should-have). One row per issue. | Me + you |
| `user-reported-issues/findings/<topic>.md` | Deep-dive findings, one file per topic. Contains internal refs (table names, code paths, tracker IDs) wrapped in `<!-- internal -->...<!-- /internal -->`. | Me + you |
| `user-reported-issues/findings/<topic>.share.md` | **Auto-generated.** Sanitized copy for external sharing. Never edit by hand — overwritten on every regen. | Generator |
| `user-reported-issues/findings/build_share_view.py` | Generator. Strips internal blocks, prepends "auto-generated" banner. | — |
| `user-reported-issues/validations/` | Validation notebooks for in-flight PRs (e.g., ESN PR validation harness). | Me + you |
| `user-reported-issues/user-shared-docs/` | Raw artifacts shared by end users (xlsx reports, screenshots). | Drop-in only |

Current findings docs:
- `user-reported-issues/findings/esn-quality.md` — ESN field-quality (corpus buckets + UAT-30 recheck). Headline: ~84% of docs have problematic ESN.
- `user-reported-issues/findings/equipment-type-quality.md` — equipment_type quality (95.5% populated, casing dupes, "Empty String" literal, 810 NULLs).
- `user-reported-issues/findings/UI-03-multi-serial-per-doc.md` — multi-serial-per-doc findings driving ADR-008.

## Share-view workflow

1. Edit the internal `.md`. Wrap any internal-only refs (table names, code line numbers, tracker IDs, ADR links, dev-vs-prod framing) in `<!-- internal -->...<!-- /internal -->`.
2. Before sharing externally: `cd user-reported-issues/findings && python build_share_view.py --all`.
3. Share the `.share.md`. Internal `.md` stays local.

`.share.md` files are build artifacts — overwrite freely, don't hand-edit, no need to delete them between sessions.

## Cross-doc invariants (don't forget these)

**ESN is denormalized in 3 places — every ESN fix must touch all 3:**
1. `vaip.ai_sot_field_service_report.biz_metadata_field_service_report.esn` (source of truth)
2. `vaip.ai_std_con_field_service_report.biz_chunks_field_service_report.esn` (top-level chunk column → VS filter)
3. `biz_chunks_field_service_report.metadata` JSON `"esn"` key (VS payload)

Code refs: [`nb_sdg_fsr_chunks.py` L246, L494](../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py) for the column; L428, L459 for the JSON key.

**equipment_type is denormalized in 2 places** (no top-level chunk column): metadata column + chunk `metadata` JSON `"equipment_type"` key.

**ESN resolver (single point in code):** [`nb_sdg_fsr_metadata.py` L677-679](../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py): `resolved_esn = llm_esn or page1_esn` (with IBAT layered).

**PKs:** `document_id` for metadata, `chunk_id = md5(document_id + "_" + chunk_index)` for chunks. `esn` is NOT a PK / FK / unique key.

## Open work — by stream

### ESN resolution (UI-15) — active workstream

Proper ESN extraction + many-to-many ESN↔doc data model. Replaces the parked UI-07/UI-13 fold-in plan after Pranesh's 2026-05-06 input. Lives in its own folder so the phased work + tracker don't crowd this file:

- [ESN-resolution/plan.md](../FSR/ESN-resolution/plan.md) — phased plan (Phase 0 ground truth → Phase 0b test DS code as-is → Phase 1 design → Phase 2-4 implementation/rollout → Phase 5 close-out).
- [ESN-resolution/tracker.md](../FSR/ESN-resolution/tracker.md) — `ESN-NN` items per phase.
- [ESN-resolution/esn-todos](../FSR/ESN-resolution/esn-todos) — raw input from Pranesh.
- [ESN-resolution/DS-ref-code/](../FSR/ESN-resolution/DS-ref-code/) — DS team scraping POC + `fsr_pipeline_dbr_final` reference.
- [ESN-resolution/design/1-esn-extractor-method.md](../FSR/ESN-resolution/design/1-esn-extractor-method.md) — extractor decision (option C: one LLM call, modified prompt).
- [ESN-resolution/design/2-multiple-esn-design.md](../FSR/ESN-resolution/design/2-multiple-esn-design.md) — cardinality / data model (row fan-out, `source_doc_id` column).
- [ESN-resolution/design/3-incremental-ingestion-and-watermark.md](../FSR/ESN-resolution/design/3-incremental-ingestion-and-watermark.md) — pipeline cursor / anti-join / watermark behaviour under fan-out.
- [ESN-resolution/design/Pranesh-multi-ESN-approach.md](../FSR/ESN-resolution/design/Pranesh-multi-ESN-approach.md) — Pranesh's raw 3-phase flow input.

**Current state:** Phase 0 (DS-code component map + Pranesh ref-doc inspection + corpus cardinality measurement). Old UI-07 single-fold-in plan below is **superseded** — keeping for context.

### Doc-summary (UI-04) — verified in dev, prod handoff parked

TOC-based summary extraction wired into both the new `generic_attribute_backfill` job and incremental P1. Branch `feature/661320-doc-summary-toc-flow` (HEAD `53daa7b`, pushed). Single PR covers both paths.

**Dev results (2026-05-19, 2 × 50-doc real-write runs + 3 × 20-doc dry-runs):**
- Plumbing clean end-to-end — DQ rows, MERGE, chunk patch, run-log all OK.
- TOC yield = **0/100 extracted** (94 `no_toc`, 6 `too_large`). ecrt_reports PDFs don't carry a parseable TOC; they have a page-1 "JOB SUMMARY" block instead. FieldVision files are 1-page, no TOC by design.
- Baseline pre-PR: 87 / 20,515 metadata docs (~0.4%) already had a `document_summary` — all from the earlier PSOT `executive_summary` enrichment path (commit `7282011`, Apr 22). The TOC PR did not add to that.

**Today's commits (all pushed):**
- `1a491ac` — `.rdd.isEmpty()` → `.limit(1).count() == 0` (serverless compat).
- `607c518` — `uuid` module-level import (fixes NameError in tracer).
- `53daa7b` — P1 doc-summary failures route to DQ log with `check_name='doc_summary_extraction'`; shared `dq_log_schema()` helper in `common/fsr_config.py` now consumed by P1 + validation (single source of truth, backfill site kept its inline copy for now — `spark_python_task`, no confirmed `from common.*` import path).

**Operator-guide fix:** [generic-backfill-operator-guide.md](generic-backfill-operator-guide.md) §6 now queries `fsr_data_quality_log` with `check_name='doc_summary_extraction'` instead of a non-existent `document_summary_status` column on the metadata table.

**Decision (2026-05-19):** Hold the prod backfill. Yield doesn't justify a full-corpus run.

**Next:**
- [x] Slack update sent to Pranesh (Vince has visibility) EOD 2026-05-19. Draft: [comms/2026-05-19/doc-summary-dev-results-slack.md](comms/2026-05-19/doc-summary-dev-results-slack.md).
- [x] **2026-05-20 — Pranesh added ecrt_reports format handling on the same branch** (handles `JOB SUMMARY` + `INSPECTION SUMMARY` sections). Test run on `main.gp_services_sdg_poc.fsr_with_doc_summary_only`: 52 / ~2.7k ecrt files failed ("not in right format"); ~16k FieldVision files unaffected.
- [x] **2026-05-20 EOD — pulled Pranesh's `94475fe`, flagged P1 signature mismatch** in `nb_sdg_fsr_metadata.py` (`_extract_toc_entries` took `pdf_path: str` but caller passes opened `pdf` object → swallowed by broad except → every P1 doc came back `"failed"`). Backfill copy unaffected (signatures matched there), so the 52/2700 backfill number stands.
- [x] **2026-05-21 04:51 — Pranesh pushed fix `a544cb8`** ("added file object to be passed rather than file path"). Pulled locally, branch clean.
- [x] **2026-05-21 — both paths verified in dev.** Path A (P1 incremental smoke, 18-doc stratified sample via `nb_07_doc_summary_p1_smoke`): 0 failed, ecrt + FieldVision-with-TOC extracting cleanly. Path B (backfill DQ log from Pranesh's ~2.7k run): 47 `no_toc` + 3 `too_large` + 0 `failed` = ~1.85%, all explainable. **Green-light from our side.**
- [x] **2026-05-22 — PR approved** on `feature/661320-doc-summary-toc-flow`. Ready to hand off to D&A for prod deploy + backfill.
- [ ] **Today (2026-05-22):** follow up with D&A team for prod deploy + backfill scheduling. Slack draft + CCB evidence checklist kept at [comms/2026-05-21/doc-summary-prod-handoff-slack.md](comms/2026-05-21/doc-summary-prod-handoff-slack.md). Per [processes/Deployment Process - General CCB...pdf](processes/Deployment%20Process%20-%20General%20CCB_c5648dd5ac1844eeafb50a88bf37874f-210526-1310-15896.pdf) we'll need: PR link + DA approval (✅), dev/QA success logs, AWS CodePipeline screenshot, Aqua vuln screenshot, post-deploy Databricks job evidence (and Airflow DAG evidence if in scope).
- [ ] One-liner cleanup before prod run: stale `args.docsummary_max_pages` reference in `generic_attribute_backfill.py:491` (leftover from `94475fe`). Flag to Pranesh.
- [ ] Keep PR open during the above — framework + P1 incremental wiring stay valid.
- [ ] Separate decision: chunk-side re-patch for the 87 pre-existing PSOT-sourced summaries (or accept the existing carry-over).
- [ ] Backfill site DQ schema dedup (3rd consumer of `dq_log_schema()`) — deferred to a separate PR once import path is sorted.

**Validation outputs:** [validation/backfill-docsummary-results-dev/after-dryrun-true/](validation/backfill-docsummary-results-dev/after-dryrun-true/) (12 CSVs).

### Today (2026-05-20) — FSR cutoff 11 AM

FSR work timeboxed to 11 AM today; rest of day is Arch-Hive prep + session. Status:

1. **VS sync (UI-22)** — **PR APPROVED 2026-05-22.** Vinayaka call surfaced the Databricks-side warning: sync interval exceeded source table's `delta.deletedFileRetentionDuration` (7-day default). Hotfix branch `hotfix/vs-sync-retention-and-schedule` (HEAD `5322f8d`): (a) chunk-table retention bumped to 30 days via additive TBLPROPERTIES + idempotent `ALTER TABLE … SET TBLPROPERTIES`; (b) daily schedule at 11:00 ET added to `PW_SDG_FSR_VS_Sync` (live on deploy, `timezone_id: America/New_York`). CCB package at [comms/2026-05-20/](comms/2026-05-20/). **Pending on us:** manual `ALTER TABLE` SQL + **Sync now** on the index page in prod (recovers OFFLINE_FAILED index today, doesn't wait for merge); then watch first scheduled run at 11:00 ET post-deploy + fill data-validation evidence. CCB filing is D&A's lift.
2. **D&A DDL reply** — silver DDL is already alter-only in prod; reply confirming no PR needed from us (drop is gated by `FORCE_RESET` + prod block). **Pending:** send.
3. **Doc-summary (UI-04)** — verified both paths in dev, **PR APPROVED 2026-05-22**. Today: send the parked handoff to D&A for prod deploy + backfill scheduling. Slack draft + CCB evidence at [comms/2026-05-21/doc-summary-prod-handoff-slack.md](comms/2026-05-21/doc-summary-prod-handoff-slack.md).
7. **Prod access revoke (NEW 2026-05-22)** — follow up on revoking our team's standing prod access. Track owner + timeline. Likely a D&A / security thread.
4. **PR raises** — UI-16 (validation split; flag job rename to monitoring/Airflow before unpausing), UI-17/18 (DQ-log SRE-ready + P1 retry gate), UI-19 (ad-hoc doc repair).
5. **Monitoring/L1 ask** — split-by-owner reply sent. Tracked as **UI-23** for the Databricks-side alert wiring + L1 owner decision (separate org thread).
6. **Multi-ESN design pending** — review [ESN-resolution/design/2-multiple-esn-design.md](../FSR/ESN-resolution/design/2-multiple-esn-design.md) for many-to-many cardinality + `source_doc_id` shape; re-check [3-incremental-ingestion-and-watermark.md](../FSR/ESN-resolution/design/3-incremental-ingestion-and-watermark.md) under UI-14 row-duplication semantics. Folds under UI-15. If time only.

Carry (no action today): UI-21 consumer-search miss (deferred); incremental ingestion validation (blocked on P1 → D&A DDL); new-PDF ingestion runbook section.

### Tracker hygiene
- [ ] None pending. Tracker is current as of 2026-05-20 (UI-22 hotfix landed; UI-23 added for Databricks-side alert wiring).

### Ad-hoc doc repair tooling (UI-19) — built + dev-validated

Operator-driven single-doc repair across metadata + chunks tables for the ESN + equipment trio (`equipment_sys_id`, `equipment_type`, `equipment_class_code`). Whitelist-only, dry-run by default, full backup before any write, same notebook reverts via `FSR_REPAIR_REVERT_RUN_ID`. ADO ticket #667154.

- Branch `feat/667154-fsr-doc-repair-adhoc` on `pw_sdg_ai_ser_repo` — pushed.
- Notebook: [`gold/src/etl/data_fixes/nb_fsr_doc_repair.py`](../pw_sdg_ai_ser_repo/gold/src/etl/data_fixes/nb_fsr_doc_repair.py).
- Workflow: [`silver/src/workflows/fsr/pw_sdg_fsr_doc_repair.yml`](../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_doc_repair.yml).
- Design: [ESN-resolution/design/adhoc-doc-repair-job.md](../FSR/ESN-resolution/design/adhoc-doc-repair-job.md).
- Runbook: [ESN-resolution/runbook-doc-repair.md](../FSR/ESN-resolution/runbook-doc-repair.md).
- Next: open PR → dev redeploy → first prod use whenever a single-doc correction comes in. Bulk + extractor fixes stay separate (UI-14 / UI-15).

### Pipeline + DQ-log hardening (UI-16 / UI-17 / UI-18) — validated on dev, ready for PR

All three landed on git today and have been validated end-to-end on dev (against the real `vaid` tables). Ready to open PRs.

| ID | Branch | Tip commit | What it does | Status |
|---|---|---|---|---|
| UI-16 | `chore/ui-16-split-validation-job` | `09e6f00` | Split DQ validation off `PW_SDG_FSR_Ingestion`; renamed standalone job to `PW_SDG_FSR_DQ_Validation`; added paused daily cron `0 0 9 * * ?` ET (3h after ingestion). | Pushed. Open PR. |
| UI-17 | `chore/664259-dq-log-sre-ready` | `2a15550` | DQ-log SRE handoff: de-dup recurring terminal-failure rows in 5.7; `failure_category` enum column on `fsr_data_quality_log`; `pdf_name` backfill on metadata-fail rows. Includes follow-on classifier extension to catch HTTP 5xx + retry-exhausted LLM errors as `gateway_error` (caught during dev validation; otherwise ~64% of FAILs would land in `unknown` and page on-call). | Pushed + dev-validated. Open PR. |
| UI-18 | `chore/664259-dq-log-sre-ready` | `2a15550` (same branch) | P1 lifetime retry gate (`metadata_retry_count` mirrors P2's `chunk_retry_count`); per-commit-batch `fsr_run_log` audit row from P1 (P1 was previously absent from the run log). Also folds in a fix to honor `FSR_TARGET_PDF_NAMES` in the work queue (was scoping discovery only — surprised operators on the dev re-ingestion test). | Pushed + dev-validated. Folds into UI-17 PR. |

Branch `chore/664259-dq-log-sre-ready` carries 5 commits in order: UI-17 main (`93e5546`) → UI-17 review fixes (`e6f8b88`) → UI-18 P1 retry gate + run-log (`3908b7a`) → P1 TARGET work-queue filter (`2651acc`) → DQ classifier 5xx coverage (`2a15550`).

**One ADO ticket (#664259)** filed/to be closed covering all three (per the 2026-05-06 standup note).

**Dev validation results (2026-05-06, against `vaid.ai_sot_field_service_report.biz_metadata_field_service_report`):**
- [x] **DDL idempotent ALTER** — re-ran `FSR_DDL_Provision` with `FORCE_RESET=false`. `metadata_retry_count` and `failure_category` columns added without rewriting any of the ~18K existing rows. Re-run logs "already exists — OK".
- [x] **UI-18a — P1 lifetime retry counter** — TARGET-mode P1 against the 3 `corrupt_source` docs (`090dbba18007f87e`, `090dbba1800a1cb0`, `090dbba1800b30cd`) → after the run, `metadata_status='failed'` and `metadata_retry_count=1` on all three (NULL → 1 on first failure under the new gate). Two more runs would walk them to 3 and the 4th run would not claim them.
- [x] **UI-18b — P1 audit row in `fsr_run_log`** — one row landed with `job_name='PW_SDG_FSR_Metadata'`, `docs_claimed=3, docs_succeeded=0, docs_failed=3`, error_summary populated. P1 telemetry now exists in the run log alongside P2's.
- [x] **UI-17 #2 — `failure_category` populated on insert** — confirmed `corrupt_source` for the 3 No-/Root docs and `gateway_error` for `eee21ec4` (502 Bad Gateway). Old rows from before today's deploy stayed NULL (expected; we don't backfill historical rows).
- [x] **UI-17 #3 — `pdf_name` backfilled on metadata-fail rows** — fell back to volume-path basename (`090dbba18007f87e.pdf` etc.) because these UUIDs aren't in `fsr_pdf_ref`.
- [x] **UI-17 #1 — De-dup window** — second validation run found 829 of 830 standing failed-doc pairs already logged in the last 2 days and skipped them; only 1 fresh row was written. SRE will see each terminal once when it lands, not every day forever.
- [x] **Classifier 5xx coverage** — verified `eee21ec4` re-logged with `failure_category='gateway_error'` after deleting today's row and re-running validation. Classifier extension is live.

**Things uncovered during dev validation (already addressed on the same branch):**
- `FSR_TARGET_PDF_NAMES` only scoped the volume *discovery* step — the work queue still pulled the full pending + retry-eligible backlog. Patched in commit `2651acc` so the parameter actually means "only these docs" end-to-end. Backfill behavior (TARGET empty) is unchanged.
- `_classify_failure()` only matched the `KeyError 'content'` shape — missed raw HTTP 5xx error strings (~520 of 524 `unknown` rows on dev today were gateway transport errors). Patched in commit `2a15550` to also match `500/502/503/504 server error`, `Bad Gateway`, `Gateway Time-out`, `Service Temporarily Unavailable`, `Internal Server Error`, and `LLM call failed after all retries`.

**Things flagged from validation but not in scope for this PR:**
- 5.1 / 5.4 integrity checks failed on dev: 174 chunk_ids with duplicate rows + 1 doc+page combo with >50 chunks. Likely UI-14 row-duplication artifact (different `chunk_id` format `MD5(doc_id + '_' + chunk_idx + '__' + esn)`). Worth a dedicated investigation under a new tracker item.
- 524 gateway-error FAILs on dev in one day — that many docs reaching `metadata_status='failed'` means the in-call retry loop (`FSR_MAX_RETRIES=3`, exponential backoff) exhausted on each. Either the dev gateway was down for sustained windows or the backoff isn't long enough. With UI-18's lifetime gate, gateway-failed docs that hit 3 lifetime attempts will be permanently quarantined even though gateway issues are transient. SRE will need a process to bulk-reset `metadata_retry_count=0 WHERE failure_category='gateway_error'` after a known gateway incident. Worth a follow-up tracker item.

**Remaining before unpausing the daily DQ schedule:**
- [ ] Open the PR for `chore/664259-dq-log-sre-ready`.
- [ ] Open the PR for `chore/ui-16-split-validation-job`.
- [ ] After both merge: run `FSR_DDL_Provision` on prod with `FORCE_RESET=false` (additive ALTERs only).
- [ ] Write the SRE runbook section "how to re-ingest a terminal failure" — `UPDATE … SET metadata_status='pending', metadata_retry_count=0 WHERE document_id IN (…)` (plus the chunk-side equivalent), and the gateway-error bulk-reset procedure called out above.
- [ ] Only then unpause the `PW_SDG_FSR_DQ_Validation` schedule.

**Background docs (local only):**
- [implementation/design/fsr-pipeline-design.md](../implementation/design/fsr-pipeline-design.md) — §1A key insights updated for UI-18; §2.1 job topology updated for UI-16; §3.3 ops tables updated for UI-17/18; §4 P1 Resiliency updated for UI-18; new **§7.1 SRE handoff** consolidates terminal-failure definitions, DQ log shape after UI-17, and the operational query.
- [comms/2026-05-06/dq-validation-monitoring-ownership.md](comms/2026-05-06/dq-validation-monitoring-ownership.md) — slimmed to the Slack ask; points at the design doc for background.

### Findings docs
- [x] `esn-quality.md` — written, internal markers added, share view generated.
- [x] `equipment-type-quality.md` — written, internal markers added, share view generated.
- [x] `UI-03-multi-serial-per-doc.md` — written, internal markers added, share view generated.
- [ ] **Optional:** rename `UI-03-multi-serial-per-doc.md` → `multi-serial-per-doc.md` for consistency (the other two findings don't carry a UI-NN prefix). Filename leak isn't critical since it's not in any link the consumer would see, but it's inconsistent.
- [ ] **Optional:** rewrite stale "UI-01 / UI-02" prose mentions in UI-03 to point at `esn-quality.md` instead of just hiding them. They're currently wrapped as internal so they don't leak, but the share view loses the corroboration narrative.

### Decisions waiting on others
- [ ] **ADR-008 (multi-ESN filterability):** decision needed from product on whether consumer wants to filter by alternate serials. Until then, issue #3 in UI-03 stays parked.
- [ ] **UI-12 (LiteLLM key rotation):** waiting on platform team confirmation.

### Quick wins available (no decision blocker)
- [ ] **equipment_type "Empty String" literal + casing dedupe:** SQL-only fix on metadata + chunk JSON.
- [ ] **Databricks ↔ VSCode integration setup** (GE Confluence: <https://confluence.apps.gevernova.net/devspace/spaces/HKPLL/pages/358842396/Integration+of+Databricks+With+VSCode>). Park for later — follow the page to wire up the local VSCode → Databricks dev workflow. Useful for faster iteration on notebooks/jobs.

### ESN fix — single fold-in PR (active)

> **2026-05-05 update — interim patch UI-14 takes priority.** A side-step `fsr_pdf_ref`-driven row-duplication patch (#664196) ships to production first so Abhinaya's 12 zero-doc ESNs return hits now. This stream (UI-07 + UI-13 on `fix/multiple-esns`) is **paused** until UI-14 stabilizes. Notes below remain the long-term plan.
>
> UI-14 artifacts: [`pw_sdg_fsr_repair_multi_esn.yml`](../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_repair_multi_esn.yml) · [`pw_sdg_fsr_revert_multi_esn.yml`](../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_revert_multi_esn.yml) · [`nb_sdg_fsr_repair_multi_esn.py`](../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_repair_multi_esn.py). Branch `hotfix/664196-spark-connect-equip-cols`.

**Driver:** Abhinaya's 2026-05-04 report confirms 12 of 30 ESNs unreachable in prod VS index. Same root cause as UI-01 + UI-03. Consumer query path uses `esn` as a hard equality pre-filter ([Query FSR Tool Spec](../poc/fsr-pipeline-dbr-candidate/docs/Query%20FSR%20Tool%20Spec.md)) — wrong stored ESN = zero results.

**Decision (2026-05-04):** fold wrong-primary-ESN fix (was UI-07 Sprint 1) and multi-ESN support (was UI-05) into **one branch `fix/multiple-esns`** off `dev`. UI-06 mechanical overwrite is dropped (superseded). UI-13 data-fix runs on the same branch using the new extractor. Design: [internal/adr/multi-esn-design.md](../internal/adr/multi-esn-design.md) (supersedes ADR-008).

**Reference checked:** DS team / Databricks team specs do not document per-equipment-family ESN regex; ESN is shared across GT, ST, HT, generator, boiler, env, aux, mech drive, aero gas with no format constraint. Validation = format regex (`^[A-Z0-9]{4,12}$`) + count threshold + in-text presence, not per-family regex.

**Dev test convention:** on the branch, append `_fix_esn` suffix to dev output tables (`biz_metadata_field_service_report_fix_esn`, `biz_chunks_field_service_report_fix_esn`) and to the dev VS index. Source tables and `databricks.yaml` for prod stay untouched. User has dev permissions to rebuild VS index — no D&A coordination needed in dev.

**8-step implementation plan:**

| # | Step | Where |
|---|---|---|
| 1 | Cut branch `fix/multiple-esns` from `dev` | git |
| 2 | New `esn_identifier.py` — pure-text input; format regex + LLM-count threshold (port from DS, drop PDF I/O) | `pw_sdg_ai_ser_repo/silver/src/etl/` |
| 3 | DDL: add `esns ARRAY<STRING>` + `esns_source` to metadata table; `esns ARRAY<STRING>` to chunks table (with `_fix_esn` test tables) | `silver/src/ddl/nb_sdg_fsr_ddl.py` |
| 4 | P1 refactor: open PDF once, extract page-1 + full text once, run combined LLM call + ESN-identifier in parallel, write `esn` (primary) + `esns` (all qualified) | `nb_sdg_fsr_metadata.py` |
| 5 | P2: copy `esns` array to chunk row column + chunk `metadata` JSON `"esns"` key (alongside existing `esn`) | `nb_sdg_fsr_chunks.py` |
| 6 | VS index rebuild on dev with `_fix_esn` suffix; expose `esns` as filterable column | DDL or ad-hoc |
| 7 | Validation harness wire-up — replace stub with new `esn_identifier`; add multi-ESN cohort (11 zero-doc + 5 UI-03 top-list) on top of 30 UAT + 14 known-bad + 100 regression | `validations/nb_esn_pr_validation.ipynb` |
| 8 | UI-13 generic data-fix job (dispatcher + ESN child). Migration tested on dev `_fix_esn` first, then dev real tables, then prod. See "UI-13 — generic data-fix job" section below. | `pw_sdg_ai_ser_repo/silver/src/etl/{nb_sdg_fsr_data_fix.py, data_fixes/nb_esn_adhoc_fix.py}` + `silver/src/workflows/fsr/pw_sdg_fsr_data_fix.yml` |

**Already landed:**
- [x] Negative-constraint ESN don't-list in `NORMALIZATION_PROMPT_SUFFIX` (was UI-07 Sprint 1 step a). Live in `nb_sdg_fsr_metadata.py` ~L362.
- [x] Validation harness scaffold — [validations/nb_esn_pr_validation.ipynb](user-reported-issues/validations/nb_esn_pr_validation.ipynb). 30 UAT + 14 known-bad UUIDs + 100-doc regression, dry-run, merge-gate, CSV export. Stub extractor in section 4 — replaced in step 7 above.

**Hard merge gate:** 30/30 UAT + 14/14 known-bad + zero regressions on 100-doc sample + multi-ESN cohort recovers (`esns` array contains the previously-unreachable serials).

**Deferred / dropped:**
- **(f) `fsr_pdf_ref` ref-view enrichment** — not needed once LLM-count lands; revisit only if residual after PR merges.
- **UI-06 mechanical overwrite of 1,427 single-serial-mismatch docs** — superseded; LLM-count handles these natively, UI-13 backfill repairs them.

**UI-13 — generic data-fix job (first user: ESN)**

Prod is already backfilled and live. We're not running anything in prod tomorrow. The new code only helps **new** docs out-of-the-box; existing docs need a separate ad-hoc fix.

Airflow team agreed to maintain **one** data-fix job (`PW_SDG_FSR_Data_Fix`). New fix types are added without an airflow ticket — drop a child notebook in `silver/src/etl/data_fixes/` and add one line to the dispatcher's `FIX_REGISTRY`. Future fixes (equipment_type, customer name, …) reuse the same job.

Layout (lives in `pw_sdg_ai_ser_repo/`, deployed via the same FSR bundle):

| File | Role |
|---|---|
| [`silver/src/workflows/fsr/pw_sdg_fsr_data_fix.yml`](../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_data_fix.yml) | Job definition. Generic params (`FSR_FIX_TYPE`, `FSR_DATA_FIX_*`). |
| [`silver/src/etl/nb_sdg_fsr_data_fix.py`](../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_data_fix.py) | Dispatcher. Routes to the child via `dbutils.notebook.run` based on `FSR_FIX_TYPE`. |
| [`silver/src/etl/data_fixes/nb_esn_adhoc_fix.py`](../pw_sdg_ai_ser_repo/silver/src/etl/data_fixes/nb_esn_adhoc_fix.py) | First child. ESN re-extraction (UI-13 scope). |

VS sync stays out-of-band — operators run the existing `PW_SDG_FSR_VS_Sync` job after a successful `APPLY=true` run.

Two scopes, both served by the same job (different param values):

| Approach | Scope | When to use |
|---|---|---|
| **A — Targeted fix** | List of `document_id`s via `FSR_DATA_FIX_DOC_IDS` (e.g. Abhinaya's 12 zero-doc UUIDs, future call-outs) | Default. Use whenever consumers report wrong/missing ESNs for specific docs. |
| **B — Bulk fix** | All ~18K existing docs in slices via `FSR_DATA_FIX_BULK_LIMIT` + `FSR_DATA_FIX_BULK_WHERE` | Only if we decide corpus-wide ESN quality justifies the LLM cost + VS sync window. Run in slices of 500–1000 docs. |

**Per-doc steps (ESN child, both modes):**
1. Read `volume_path` + current `esn` + `esns` from metadata table.
2. Open PDF once, extract full text.
3. Call new `esn_identifier` (`analyze_text_for_esn_counts` → `select_primary_and_array`).
4. Write to **audit table** `esn_fix_audit` (default = dry-run, no other writes). Audit row captures `old_esn`, `old_esns`, `new_esn`, `new_esns`, `raw_counts`, `decision`, `error`.
5. If `FSR_DATA_FIX_APPLY=true`: MERGE metadata (`esn`, `esns`, `esns_source='esn_identifier'`) → MERGE chunk table (top-level `esn`, `esns`) → rewrite chunk `metadata` JSON `"esn"` + `"esns"` keys (Python UDF, preserves nested values).
6. Operator runs `PW_SDG_FSR_VS_Sync` job to refresh the index.

**Selective overwrite policy** (avoid regressing currently-correct docs):
- New primary differs from current `esn` AND identifier qualified it → `overwrite` (write `esn` + `esns`).
- New primary equals current `esn` → `fill_esns_only` (only write `esns`).
- Identifier returns no qualified ESN → `low_confidence` (leave `esn` and `esns` alone, log for review).

### Migration sequence (dev = prod stand-in)

Dev has the same shape as prod (already-backfilled tables, real users hitting the dev VS index). Treat dev as the prod rehearsal: every step we want to take in prod, we take in dev first.

| Step | Where | What |
|---|---|---|
| M1 | dev `_fix_esn` tables + index | Smoke-test the full P1+P2 pipeline end-to-end on a small cohort (~12 docs from Abhinaya's list + 5 UI-03 multi-ESN). Validates code + DDL + VS index registration + the new `esns` filter without touching real dev tables. |
| M2 | dev `_fix_esn` index | Run `PW_SDG_FSR_Data_Fix` (`FSR_FIX_TYPE=esn`, Approach A) against the same 12 cohort. Verify dry-run audit, then APPLY=true, then `PW_SDG_FSR_VS_Sync`, then re-query. |
| M3 | dev real tables (`vaip_dev.*`) | DDL adds `esns` + `esns_source` columns idempotently (no rewrite, no downtime). VS index — open ticket-equivalent / use direct API call to register `esns` as filterable. |
| M4 | dev real tables | Run `PW_SDG_FSR_Data_Fix` (Approach A) on the same 12 cohort against real dev tables. Confirm Abhinaya-style heat-map test recovers. |
| M5 | dev real tables (optional) | If Approach B is greenlit, run a 500-doc slice as a soak test. Measure runtime, audit-table volume, VS sync lag. |
| M6 | prod real tables | DDL columns added (one-time, idempotent). VS index `esns` filter registration via D&A ticket. |
| M7 | prod real tables | Approach A on Abhinaya's 12 (dry-run → APPLY → VS sync → re-verify). |
| M8 | prod real tables (conditional) | Approach B in slices, only if M5 looked good and there's business demand for corpus-wide repair. |

**Approach A runtime (Abhinaya's 12 docs):** ~1–2 min per doc serial → ~5 min with parallelism. VS sync: minutes (incremental).

**Approach B runtime (full 18K).** ~3,750 LLM calls at `FSR_ESN_IDENTIFIER_CONCURRENCY=6` → **~30–60 min for the LLM pass**. Plus ~10–20 min for chunk-table 3-place MERGEs (~830K chunk rows touched), ~10–30 min VS index sync. **Total per full run: ~1–2 hours.** Slicing into 500-doc batches makes each window ~5–10 min — safer for prod.

**Audit table** (new, dev + prod) — created idempotently by the ESN child notebook:
```
esn_fix_audit (
    document_id   STRING NOT NULL,
    run_id        STRING NOT NULL,        -- UUID per notebook run
    env           STRING,                  -- jb_env at run time
    mode          STRING,                  -- 'A' (targeted) | 'B' (bulk)
    apply_flag    BOOLEAN,                 -- false = dry-run
    old_esn       STRING,
    old_esns      ARRAY<STRING>,           -- pre-run snapshot, supports full chunk rollback
    new_esn       STRING,
    new_esns      ARRAY<STRING>,
    raw_counts    STRING,                  -- JSON of {esn: count} from identifier
    decision      STRING,                  -- 'overwrite' | 'fill_esns_only' | 'low_confidence' | 'no_change' | 'error'
    error         STRING,
    processed_at  TIMESTAMP
)
```
Doubles as a rollback map (`old_esn` + `old_esns` preserved per `run_id`).

### Validation steps (run in dbr dev workspace, share results)

Two validation tracks — both runnable from the dev workspace once the bundle is deployed to dev. Each track has a **dry-run** stage that reports without touching anything, and an **apply** stage that writes. Share the marked outputs back from each stage.

#### Track 1 — pipeline code path (UI-07, P1+P2 on `_fix_esn` sandbox)

Validates the new `esn_identifier` + `esns` propagation through P1 and P2 against sandbox tables. No live-data risk.

| # | What | How | Share |
|---|---|---|---|
| T1.1 ✅ | DDL idempotent add | Ran job `FSR_DDL_ESN` (notebook `silver/src/ddl/nb_sdg_fsr_ddl`) with `_fix_esn` table overrides + VS endpoint/index. Idempotent re-run reported every column already present. | DESCRIBE confirmed: metadata 38 cols incl. `esns array<string>` + `esns_source string`; chunks 12 cols incl. `esns array<string>`. |
| T1.2 | P1 metadata extraction on small cohort | Create job `FSR_Metadata_ESN_fix_esn` (notebook `silver/src/etl/nb_sdg_fsr_metadata`, branch `fix/multiple-esns`). Same 6 table/VS params as T1.1, plus: `FSR_SOURCE_VOLUME_PATHS=/Volumes/viud/ing_ud_fieldvision/fv_field_service_report,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports`, `LITELLM_BASE_URL=https://dev-gateway.apps.gevernova.net`, `LITELLM_API_KEY=<dev>`, `FORCE_RESET=false`, `FSR_TARGET_PDF_NAMES=<13-doc cohort below>`. | Job run-id. SQL: `SELECT document_id, esn, esns, esns_source, esn_source, metadata_status FROM …_fix_esn ORDER BY document_id`. Plus log lines `[ESN-ID]` per doc. Expect `esns_source='esn_identifier'` where qualified. |

**T1.2 cohort (13 docs from `fsr-prod-ops/prod-issues/nb_uat30_esn_recheck.ipynb` `KNOWN_UUIDS` + xlsx Sheet6 lookup; covers all 3 failure patterns A/B/C):**

```
913433ad-6d19-472f-917c-5048f689a5ed,c020379c-93a4-49f6-b6a9-1388edd59d3a,03d3bef2-db2b-4311-b147-641025e3636b,36de1c13-acee-4633-8b76-8a262f738a20,34bc62b0-573c-4f43-bc62-b0573ccf43e9,348ddaa2-8c32-4646-9f17-c57f33256d82,3ef8d150-1225-4c62-ac5e-ae9166c73954,4b70aab1-e210-4d5b-9cbf-bfe690436861,d5334dce-9d7f-4fa1-b34d-ce9d7f7fa130,090dbba1800f4f5b,090dbba18003a23c,090dbba180100488,090dbba1800b5e28
```

_Skipped from notebook list: `5555aa82` (no full UUID found in sources). Multi-ESN UI-03 cohort deferred — primary path validates multi-ESN code (every doc gets `esns` populated regardless)._

| T1.3 | P1 log inspection | From the same run, capture log lines: `ESN-ID workers : N`, identifier progress, any per-doc identifier errors. | Snippet from job logs (no PDF content). |
| T1.4 | P2 chunk propagation | Run `PW_SDG_FSR_Chunks` with `_fix_esn` tables. | SQL: `SELECT document_id, COUNT(*) AS n_chunks, COUNT(DISTINCT esn) AS n_distinct_esn, COLLECT_SET(esns) AS esns_seen FROM …chunks_fix_esn WHERE document_id IN (…) GROUP BY document_id`. Confirm `esns` matches metadata for each doc. |
| T1.5 | Chunk JSON propagation | SQL spot-check: `SELECT chunk_id, get_json_object(metadata,'$.esn') AS json_esn, get_json_object(metadata,'$.esns') AS json_esns FROM …chunks_fix_esn WHERE document_id = '<one_uuid>' LIMIT 5`. | Output rows. Confirm `json_esn` + `json_esns` match top-level columns. |
| T1.6 | VS index sync + filter check | Run `PW_SDG_FSR_VS_Sync` against the `_fix_esn` index. Then issue a VS query with `filters={"esn": "<known_correct_esn>"}` and another with `filters={"esns": "<alt_serial>"}`. | Number of hits, sample chunk_ids. Confirm: alt-serial filter returns the expected docs. |
| T1.7 | Validation harness | Run [`validations/nb_esn_pr_validation.ipynb`](user-reported-issues/validations/nb_esn_pr_validation.ipynb) wired to the new `esn_identifier`. Cohorts: 30 UAT + 14 known-bad + 100-doc regression + multi-ESN cohort (11 zero-doc + 5 UI-03). | Notebook output CSV + the merge-gate summary cell. |

**Hard merge gate for the PR:** T1.1 idempotent · T1.2/T1.4/T1.5 100% propagation · T1.6 alt-serial recovers · T1.7 30/30 UAT + 14/14 known-bad + zero regressions.

#### Track 2 — ad-hoc data-fix job (UI-13, ESN child)

Validates the dispatcher + ESN child end-to-end. Run after Track 1 passes.

| # | What | How | Share |
|---|---|---|---|
| T2.1 | Dispatcher routing — bad input | Run `PW_SDG_FSR_Data_Fix` with `FSR_FIX_TYPE=` (empty) and again with `FSR_FIX_TYPE=bogus`. | Confirm both runs fail fast in the dispatcher with the registry list in the error message. Paste the error message. |
| T2.2 | Audit DDL idempotence | Run `PW_SDG_FSR_Data_Fix` with `FSR_FIX_TYPE=esn`, `FSR_METADATA_TABLE=…_fix_esn`, `FSR_CHUNK_TABLE=…_fix_esn`, `FSR_DATA_FIX_MODE=A`, `FSR_DATA_FIX_DOC_IDS=<one uuid>`, `FSR_DATA_FIX_APPLY=false`. Re-run. | `DESCRIBE TABLE EXTENDED` of `esn_fix_audit`. Confirm columns + that re-run did not error. |
| T2.3 | Mode A dry-run on 12 cohort | Same as T2.2 but `FSR_DATA_FIX_DOC_IDS=<12 Abhinaya UUIDs>`. | SQL: `SELECT decision, COUNT(*) FROM esn_fix_audit WHERE run_id='<id>' GROUP BY decision`. Plus full `SELECT document_id, decision, old_esn, new_esn, new_esns, error FROM esn_fix_audit WHERE run_id='<id>'`. |
| T2.4 | Selective-overwrite policy spot-check | From T2.3 audit rows, pick one of each: `overwrite`, `fill_esns_only`, `low_confidence`. | For each: paste the audit row + a manual confirmation that the decision matches the policy (e.g. for `fill_esns_only`, old/new primaries match). |
| T2.5 | Mode A apply on 12 cohort | Re-run with `FSR_DATA_FIX_APPLY=true`. | New `run_id`. SQL after the run: `SELECT a.document_id, a.decision, a.old_esn, a.new_esn, m.esn AS now_esn, m.esns AS now_esns, m.esns_source FROM esn_fix_audit a JOIN …_fix_esn m USING(document_id) WHERE a.run_id='<id>'`. Confirm metadata matches `decision`. |
| T2.6 | Chunk 3-place propagation post-apply | SQL: `SELECT document_id, COUNT(*) AS n, COUNT(DISTINCT esn) AS n_distinct_esn, COUNT(DISTINCT get_json_object(metadata,'$.esn')) AS n_distinct_json_esn FROM …chunks_fix_esn WHERE document_id IN (<12>) GROUP BY document_id` — all `n_distinct_*` should be 1. Plus a 5-row sample showing top-level `esn`/`esns` == JSON `esn`/`esns`. | Aggregate + sample output. |
| T2.7 | VS sync after apply | Run `PW_SDG_FSR_VS_Sync` against `_fix_esn` index. | Job run-id. Then a VS query for one of the previously-zero-doc UUIDs filtering on the new `esn` — confirm hits > 0. |
| T2.8 | Mode B small bulk (optional, if greenlit) | Same job, `FSR_DATA_FIX_MODE=B`, `FSR_DATA_FIX_BULK_LIMIT=50`, `FSR_DATA_FIX_APPLY=false`. | Decision histogram + run wall-clock. |
| T2.9 | Rollback rehearsal | On one doc from T2.5, run the rollback SQL using `old_esn`/`old_esns` from `esn_fix_audit` filtered to that `run_id`. Re-check metadata + chunks. | Before/after rows. |

**Promotion gate to dev real tables (M3+):** all of T1.* + T2.1–T2.7 green, plus T2.9 rollback verified.

**Pre-flight:**
- [ ] Pull source for the 3 Pattern A docs to confirm OCR vs source-of-truth digit error.

### Backfill follow-up (from `backfill-pulse-log.md`)
- [ ] **50 stuck `completed/in_progress`** docs — need a flip script (UI-08).
- [ ] **6 `completed/failed`** docs — investigate (UI-?).
- [ ] **71 `failed/pending`** docs — P1 retry pass (UI-?).

## Conventions

- No emojis in docs unless asked.
- No git commits without explicit ask.
- `local-scratch/` and `certs/` folders stay untouched across branch switches.
- No temporary patches in `pw_sdg_ai_ser_repo/` — fix root cause or fix the environment.
- Dev-vs-prod comparisons stay internal-only (consumers don't need to see "we migrated bucket C to bucket B" framing).

## Quick commands

```bash
# Regenerate all share views
cd /home/u560060992/dbx/fsr-prod-ops/user-reported-issues/findings
python build_share_view.py --all

# Regenerate one
python build_share_view.py esn-quality.md
```
