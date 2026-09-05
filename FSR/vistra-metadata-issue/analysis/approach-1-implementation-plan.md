# Approach 1 — Vistra Cross-Train Repair: Implementation Plan

**Date:** 2026-06-03  
**Updated:** 2026-06-05  
**Status:** Implementation complete. Single-ESN smoke test passed and reverted. Ready for the agreed dev run: load all 47 confirmed rows, repair the 32 currently present in dev, and leave the 15 missing PDFs unprocessed in dev.  
**Summary of changes vs. plan:** Two design decisions were revised during implementation. (1) Idempotency was extended to handle partial state — if the target metadata row exists but chunks are missing (e.g. from a prior crashed run), the notebook now recovers by running the chunk cloning step only rather than skipping the row entirely. (2) Chunk `metadata` JSON is built in Python from known field values (base metadata row + IBAT lookup), matching the pattern in `nb_sdg_fsr_chunks.py`, instead of the originally planned `REGEXP_REPLACE` approach on the base chunk's JSON. Both changes are documented in the design notes under §4.  
**Working branch:** `repair/697310-vistra-cross-train-generator-gap` (from `dev`).
**Overview:** A one-shot, auditable repair pipeline that inserts the missing Generator metadata and chunk rows for the 47 confirmed Vistra cross-train gaps identified in Jon's enriched workbook. Each run is fully reversible by `REPAIR_RUN_ID` and operates off a staging table that tracks per-row status independently for dev and prod.  
**Scope:** One-shot, auditable, reversible repair for the 47 confirmed `(PDF, missing Generator ESN)` rows from Jon's enriched workbook. Approach 2 (structural train-sibling expansion) is tracked separately in [`../../ESN-resolution/design/proposed-multi-ESN-design.md`](../../ESN-resolution/design/proposed-multi-ESN-design.md).
**Parent docs:** [`findings-and-plan.md`](findings-and-plan.md) (exec summary), [`../input/Vistra_Generator_FSR_Tagging_Solution_2026-05-31.md`](../input/Vistra_Generator_FSR_Tagging_Solution_2026-05-31.md) (Jon's spec), [`../input/FSR_Cross_Tag_Gap_Logic 1.md`](<../input/FSR_Cross_Tag_Gap_Logic 1.md>) (gap-finder logic: identifies FSR PDFs where one train-linked asset is tagged in metadata but the Generator row is missing, surfaces generator-scope evidence from chunk text, and links a potential sibling generator event via IBAT + Event Vision).

---

## 1. Artifacts to create

All under `pw_sdg_ai_ser_repo/gold/`. Core pipeline notebooks remain flat; these one-off operational utilities live under `etl/repairs/` and `ddl/repairs/` for easier navigation. No edits to existing files.

| # | File | Purpose |
|---|---|---|
| 1 | `gold/src/ddl/repairs/nb_sdg_fsr_repair_vistra_xtrain_ddl.py` | Creates the staging table and the two repair-specific audit tables needed before any load or repair run can start. Mirrors the pattern in `nb_sdg_fsr_repair_ddl.py`, but scoped to this Vistra batch. |
| 2 | `gold/src/etl/repairs/nb_sdg_fsr_load_vistra_gap_staging.py` | Loads Jon's enriched xlsx into the staging table, resolves `pdf_stem` to the current `document_id`, validates each row against metadata + IBAT, and initializes dev/prod run status fields. |
| 3 | `gold/src/etl/repairs/nb_sdg_fsr_repair_vistra_xtrain.py` | Reads eligible rows from staging and performs the actual repair: insert the missing Generator metadata row, fan out the chunk copies, write audit rows, and mark staging status. |
| 4 | `gold/src/etl/repairs/nb_sdg_fsr_revert_vistra_xtrain.py` | Undoes a specific repair run by `run_id`: removes the inserted metadata/chunk rows, resets staging state, and leaves a clean rollback trail. |
| 5 | `silver/src/workflows/fsr/repairs/pw_sdg_fsr_repair_vistra_xtrain.yml` | Dedicated Databricks workflow for this ad hoc package, following the existing FSR workflow pattern in `silver/src/workflows/fsr/`. Orchestrates the one-time run sequence (DDL → loader → repair → optional verify / VS sync) with named parameters and run history. |
| 6 | `silver/src/workflows/fsr/repairs/pw_sdg_fsr_revert_vistra_xtrain.yml` | Dedicated Databricks workflow for controlled rollback, paired with the repair workflow. Runs revert notebook + verify path with explicit `REVERT_RUN_ID` handling and the same operational traceability pattern used by existing FSR revert workflows. |
| 7 | `gold/src/validation/repairs/nb_sdg_fsr_repair_vistra_xtrain_verify.py` | Post-repair verification notebook wired as the final task of the repair workflow. Gates on four checks (staging-done vs audit-meta parity, audited `document_id`s present in metadata, audited `chunk_id`s present in chunks, inserted metadata rows carry the expected ESN + `equipment_type='Generator'`) and reports two more (chunk distribution per `(pdf_name, esn)`, sample VS round-trip). Auto-picks the latest `REPAIR_RUN_ID` from the chunk audit when not passed. |

VS sync reuses existing [`nb_sdg_fsr_vs_sync.py`](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_vs_sync.py) — no change.

## 2. Staging table

**Name:** `<env>.ai_sot_field_service_report.staging_vistra_gap`
(`vaid` for dev, `vaip` for prod — catalog comes from existing `fsr_config.py`, not hardcoded.)

### Why we need it

The xlsx is the input, but we can't drive a repair job directly off a spreadsheet. The staging table is the durable, queryable, per-row work ledger that sits between Jon's workbook and the production tables. Specifically it gives us:

1. **A single source of truth for the batch.** The 47 confirmed rows (and the 205 weak rows later) land in one table with the same shape. Loader runs once per xlsx drop; everything downstream reads from the table.
2. **Row-level validation before any write.** The loader resolves `pdf_stem → document_id` against current metadata and verifies `missing_esn` against IBAT. Bad rows are marked at load time, not discovered mid-run. The repair notebook only touches rows that already passed validation.
3. **Idempotency and resumability.** Each row carries `dev_status` / `prod_status` (`pending` → `done` / `skipped` / `failed`) plus a `run_id` and timestamp. A re-run picks up only `pending` rows; a failed row keeps its error and can be retried after a fix without re-processing the rows that already landed.
4. **Separate dev and prod accounting on the same row.** Same row, same input, two independent status sets. Dev can be `done` while prod is still `pending`. Avoids maintaining parallel tables or a separate prod-run list.
5. **Confidence-gated rollout in one table.** `confidence='confirmed'` runs first (the 47); the same staging table holds the 205 weak rows with `confidence='weak'` for the follow-up batch. Repair notebook filters on `CONFIDENCE_FILTER` — no schema change, no second pipeline.
6. **Audit and SME handback.** Carrying the xlsx columns that aren't used by the insert (`tagged_event_type`, `matched_event_date`, `gap_confirmed`, `keywords_found`, etc.) means SMEs can review what was acted on without joining back to the original spreadsheet. After each environment completes, the table exports back to xlsx with status columns filled — that's Jon's handback artifact.
7. **Revert input.** The revert notebook reads the same staging table to know exactly which `document_id`s this batch added, scoped by `run_id`. No guessing, no separate "what did we insert" list.

### Schema

| column | type | source |
|---|---|---|
| `pdf_stem` | STRING | xlsx `PDF (stem)` |
| `document_id` | STRING | resolved from `pdf_stem` via metadata lookup (lowercase, no `.pdf`) |
| `plant` | STRING | xlsx `Plant` |
| `tagged_esn` | STRING | xlsx `Tagged ESN` |
| `tagged_equipment_type` | STRING | xlsx `Tagged Equipment Type` (`GT` / `ST`) |
| `tagged_event_type` | STRING | xlsx `Event Type` (tagged side) — audit only |
| `matched_event_date` | STRING | xlsx `Matched Event Date` — audit only |
| `missing_esn` | STRING | xlsx `Missing ESN` — drives the insert |
| `missing_equipment_type` | STRING | xlsx `Missing Equipment Type` (always `'Generator'` this batch) |
| `sibling_event_type` | STRING | xlsx `Sibling Event Type` |
| `sibling_event_id` | STRING | xlsx `Sibling Event ID` — maps to `ev_equipment_event_id` (no sibling project ID in xlsx; `ev_project_id` inherited from base row) |
| `keyword_count` | INT | xlsx `Keyword Matches` |
| `keywords_found` | STRING | xlsx `Keywords Found` (raw, kept for traceability) |
| `gap_confirmed` | STRING | xlsx `Gap Confirmed` (`YES`/`NO`) — audit only |
| `report_date` | STRING | xlsx `Report Date` |
| `confidence` | STRING | derived: `'confirmed'` if `gap_confirmed='YES'`, else `'weak'` |
| `source` | STRING | constant `'cross_tag_gap_v1'` |
| `dev_status` | STRING | `'pending'` → `'done'` / `'skipped'` / `'failed'` |
| `dev_processed_at` | TIMESTAMP | set by repair run |
| `dev_run_id` | STRING | set by repair run |
| `dev_error` | STRING | error message on failure |
| `prod_status` | STRING | same shape as dev |
| `prod_processed_at` | TIMESTAMP | |
| `prod_run_id` | STRING | |
| `prod_error` | STRING | |
| `loaded_at` | TIMESTAMP | loader |

Loader validates each row: `document_id` exists in metadata with `metadata_status='completed'`, `missing_esn` exists in `ibat_equipment_mst`. Rows that fail validation get a non-`pending` initial status and a reason so the repair notebook skips them cleanly.

**Re-load semantics (MERGE, not truncate-and-insert):** the loader MERGEs by `(pdf_stem, missing_esn)`. New rows are inserted; existing rows where **both** `dev_status` and `prod_status` are still in `{pending, invalid, NULL}` get their lookup + audit columns refreshed from the latest xlsx; rows where either env has already moved to `done` / `failed` are left untouched so completed work and error history are preserved. Re-running the loader against an updated xlsx is therefore safe and does not need a reset flag.

## 3. Audit tables

| table | purpose |
|---|---|
| `fsr_repair_vistra_chunk_inserts` | one row per chunk row inserted, keyed by `repair_run_id` + `chunk_id` |
| `fsr_repair_vistra_metadata_updates` | one row per metadata row inserted, keyed by `repair_run_id` + `document_id`. Stores the inserted `document_id`, `base_document_id`, and `inserted_esn` so verify/revert can scope the run cleanly |

Shape mirrors `fsr_repair_664196_chunk_inserts` / `fsr_repair_664196_metadata_updates_v2`, but these are Vistra-specific tables (`fsr_repair_vistra_*`) and must remain separate from the regular repair audit tables so rollback scope stays isolated.

## 4. Repair notebook contract

**Notebook:** `pw_sdg_ai_ser_repo/gold/src/etl/repairs/nb_sdg_fsr_repair_vistra_xtrain.py` (one of the four artifacts in §1).

"Contract" here means the agreed interface — parameters in, behavior per row, failure semantics, idempotency guarantees, dry-run behavior, and verification output — so a caller (a job, a re-run, a reviewer) knows what to expect without reading the implementation.

### Parameters

| name | default | purpose |
|---|---|---|
| `STAGING_TABLE` | — | full table name |
| `METADATA_TABLE` | from config | `biz_metadata_field_service_report` |
| `CHUNK_TABLE` | from config | `vec_field_service_report` |
| `IBAT_EQUIPMENT_TABLE` | from config | `ibat_equipment_mst` |
| `AUDIT_CHUNK_TABLE` | from config | `fsr_repair_vistra_chunk_inserts` |
| `AUDIT_META_TABLE` | from config | `fsr_repair_vistra_metadata_updates` |
| `REPAIR_RUN_ID` | auto-uuid | for audit + idempotency |
| `CONFIDENCE_FILTER` | `'confirmed'` | filters staging rows |
| `DRY_RUN` | `true` | no writes when true |
| `ENV_TAG` | required (`'dev'` / `'prod'`) | drives which `*_status` column on staging gets updated |

### Per-row flow

For each staging row where `confidence=CONFIDENCE_FILTER` and `{ENV_TAG}_status='pending'`:

1. **Lookup base metadata row** by `document_id`. Inherit `pdf_name`, `volume_path`, `title`, `customer`, `prepared_by`, `approved_by`, `document_summary`, `report_issued_date`, `outage_start_date`, `outage_end_date`, `outage_type`, `technology_type`, `fsr_number`, `page_count`, `file_size_bytes`, `file_last_modified`, `chunked_at`.
2. **IBAT lookup** on `missing_esn` → `equipment_sys_id`, `equipment_class_code`. `equipment_type = 'Generator'` literal.
3. **Insert new metadata row** with:
   - `document_id = f"{base_document_id}_{missing_esn}"` (matches existing multi-ESN convention; deterministic and idempotent)
   - `esn = missing_esn`
   - `esn_source = 'cross_tag_gap_v1'`
   - `equipment_type = 'Generator'`, `equipment_sys_id` + `equipment_class_code` from IBAT
   - `event_type = sibling_event_type` if non-null, else inherit
   - `ev_project_id` — always inherit from base row (no sibling project ID in xlsx)
   - `ev_equipment_event_id = sibling_event_id` if non-null, else inherit
   - `metadata_status='completed'`, `chunk_status='completed'`
   - `ingested_at` = `scraped_at` = `now()`
   - Skip with `status='skipped'` if a row with that `document_id` already exists.
4. **Insert per-chunk copies** — for every chunk of `base_document_id` in `vec_field_service_report`, insert a copy with:
   - `document_id = f"{base_document_id}_{missing_esn}"`
   - `chunk_id = md5(doc_id_ci || "__" || esn)` (matches existing chunk fan-out)
   - top-level `esn` → `missing_esn`
   - **`metadata` JSON:** built in Python from known fields (same pattern as `nb_sdg_fsr_chunks.py`), not inherited or regex-transformed from the base chunk. All document-level fields come from the base metadata row; `esn`, `equipment_sys_id`, `equipment_type`, `equipment_class_code` are overridden with the IBAT-sourced Generator values. Passed as a SQL string literal into the clone view. (See §4 design note.)
   - same `text`, same `embedding`, same `chunk_index` (no re-chunk, no re-embed)
   - Skip if target `chunk_id` already exists.
5. **Write audit rows** to both audit tables (always — even on partial success for traceability).
6. **Update staging row:** `{ENV_TAG}_status = 'done'`, `{ENV_TAG}_processed_at = now()`, `{ENV_TAG}_run_id = REPAIR_RUN_ID`.

### Failure handling

Per-row failure → mark `{ENV_TAG}_status='failed'`, write error to `{ENV_TAG}_error`, continue with next row. Don't abort the whole run. Failures are surfaced in the final summary.

### Idempotency guards

- `repair_run_id` already in audit table → refuse to run.
- Staging row `{ENV_TAG}_status='done'` → skip silently.
- Target metadata `document_id` already exists **and** chunks > 0 → skip with `status='skipped'`, log.
- Target metadata `document_id` already exists **but** chunks = 0 → **partial-state recovery**: skip metadata insert, proceed with chunk cloning only. Marks staging `done` when complete. (See §4 design note.)
- Target `chunk_id` already exists → skip the chunk (other chunks for the row still process).

### Design notes (updated during implementation)

**Partial-state idempotency:** The original plan's idempotency check only tested whether the target metadata `document_id` existed. During implementation it was found that a run could crash after inserting the metadata row but before inserting chunks, leaving the row in a partial state (metadata present, 0 chunks). The idempotency gate was extended to a two-branch check: metadata + chunks both present → skip; metadata present but chunks missing → recover by running the chunk cloning step only.

**Chunk metadata JSON construction:** The original plan described rewriting the base chunk's existing `metadata` JSON via `REGEXP_REPLACE` to update the four equipment fields. This was rejected during implementation because:
1. Spark SQL `REGEXP_REPLACE` does not support backreference substitution inside `CONCAT`, making the pattern fragile.
2. The chunk table's `metadata` column does not exist on the metadata table, ruling out a `CROSS JOIN` approach.
3. The correct pattern — already used by `nb_sdg_fsr_chunks.py` — is to build the JSON from scratch in Python using the known field values, then pass it as a SQL string literal. This is simpler, avoids any regex fragility, and is consistent with how the original chunk rows were created.

### DRY_RUN behavior

- No writes anywhere — including no staging-status update.
- Prints planned metadata-row count, total chunk-row count, per-doc chunk-count breakdown for first 10 docs.

### Final cell — verification

Runs against the processed `document_id`s only:

```sql
-- 1. Metadata catalog view
SELECT pdf_name, esn, esn_source, equipment_type
FROM <METADATA_TABLE>
WHERE document_id IN (<processed doc ids>)
   OR document_id IN (<processed base doc ids>);

-- 2. Chunk distribution per ESN
SELECT pdf_name, esn, COUNT(*) AS chunk_rows
FROM <CHUNK_TABLE>
WHERE pdf_name IN (<processed pdf names>)
GROUP BY pdf_name, esn;
```

Plus a sample Generator-ESN search call against the dev VS index (one ESN, top-5 hits printed) to confirm round-trip.

## 5. Dev run scope (manual decision, dev only)

The original dev plan assumed a parity-ingest pre-step for the PDFs missing in `vaid`. That is no longer the agreed path.

Current dev state, based on the latest validation:

1. 32 of the 47 confirmed PDFs are already present in dev metadata + chunks and are repairable now.
2. 15 of the 47 are missing from dev chunks; in the latest check, those same 15 are also missing from dev metadata by `pdf_name`.
3. Of those 15, only 1 currently maps to a `document_id` in the reference view; the remaining 14 do not yet map and are not targetable via `FSR_TARGET_PDF_NAMES`.

Agreed dev execution:

1. Run the loader on the full 47-row confirmed workbook.
2. Let the loader mark rows with unresolved `document_id` or other validation failures as `invalid`.
3. Run the repair notebook in dev against `CONFIDENCE_FILTER='confirmed'`; it will process only rows with `dev_status='pending'`.
4. Expected dev outcome: 32 rows repaired, 15 rows left `invalid` / unprocessed in staging.

So there is no separate parity-ingest step in dev for this run. Prod still targets the full confirmed set once its own prerequisites are satisfied.

### Before validation (dev)

Use this before running the repair to confirm the expected 32-PDF dev scope.

1. Run the baseline SQL in [`../testing/queries/missing_15_in_dev_test.md`](../testing/queries/missing_15_in_dev_test.md).
2. Use Query 1 and Query 3 there to confirm the current dev footprint for the 47 confirmed PDFs.
3. Expected pre-run result: 32 already present in dev metadata + chunks, 15 missing from dev chunks, and those same 15 missing from dev metadata by `pdf_name`.
4. After the loader step, validate the staging table outcome for this run: `confidence='confirmed'` should yield 32 rows with `dev_status='pending'` and 15 rows with `dev_status='invalid'`.
5. Do not proceed to `DRY_RUN=false` until the loader output matches that split, because the repair notebook only processes rows still marked `pending`.

### After validation (dev)

Use this after the repair run to confirm the 32 processed rows landed correctly.

1. The workflow's first post-run gate is the verify notebook [`../../../pw_sdg_ai_ser_repo/gold/src/validation/repairs/nb_sdg_fsr_repair_vistra_xtrain_verify.py`](../../../pw_sdg_ai_ser_repo/gold/src/validation/repairs/nb_sdg_fsr_repair_vistra_xtrain_verify.py).
2. Run it with the same `REPAIR_RUN_ID` and `ENV_TAG=dev` used by the repair job, or let the workflow invoke it automatically as step `3.5` below.
3. Required pass conditions are:
   - staging `done` count matches audit metadata-row count
   - every audited `document_id` exists in metadata
   - every audited `chunk_id` exists in chunks
   - every inserted metadata row has the expected ESN and `equipment_type='Generator'`
4. Expected post-run result for this dev batch: 32 rows `done`, 15 rows still `invalid` / unprocessed in staging.
5. After verify passes, run VS sync and then do the SME spot-check on 5 repaired docs.

## 6. Rollout sequence

| # | Step | Env | Gate |
|---|---|---|---|
| 1 | Upload [`../input/Vistra Generator Missing Reports 5.31.26 - ENRICHED.xlsx`](../input/Vistra%20Generator%20Missing%20Reports%205.31.26%20-%20ENRICHED.xlsx), use sheet `FSR Tagging Gaps`, then run loader (xlsx → staging) | dev | self |
| 2 | Repair `DRY_RUN=true, CONFIDENCE_FILTER='confirmed'` | dev | self review |
| 3 | Repair `DRY_RUN=false` | dev | self |
| 3.5 | Verify notebook (auto-runs as final task of repair workflow) | dev | gates fail → halt |
| 4 | VS sync | dev | self |
| 5 | SME spot-check 5 repaired docs | dev | Vistra SME ack |
| 6 | Upload the same workbook to the prod loader path, use sheet `FSR Tagging Gaps`, then run loader (same xlsx) | prod | SME sign-off |
| 7 | Repair `DRY_RUN=true` | prod | self |
| 8 | Repair `DRY_RUN=false` | prod | account-team go |
| 8.5 | Verify notebook (auto-runs as final task of repair workflow) | prod | gates fail → halt |
| 9 | VS sync | prod | account-team verify |

After step 9: export staging table back to xlsx with `Dev Status` / `Prod Status` columns filled → hand to Jon. In dev, expect the handback to show 32 repaired rows and 15 `invalid` / unprocessed rows. Optional: automate this export as a tiny utility cell; otherwise manual.

## 7. Future batches

The same notebooks handle the 205 weak rows as a separate run with `CONFIDENCE_FILTER='weak'` after SME triage. No code change — load the weak rows into the same staging table with `confidence='weak'` and rerun.

## 8. Open logistics

1. **xlsx location** — needs a Volumes path the loader can read. Alternative: loader accepts either Volumes xlsx OR a CSV intermediary uploaded manually. Choose before loader is written.
2. **Catalog names** — `vaid` for dev, `vaip` for prod, both sourced from existing `fsr_config.py`. No hardcoding.
3. **Sibling event fields in the workbook** — confirm `Sibling Event Type` and `Sibling Event ID` columns are present and populated for all 47 rows. If sparse, the inherit-on-null rule (step 3 in §4) covers `ev_equipment_event_id`; `ev_project_id` always inherits.
4. **Execution orchestration** — do we need only a dedicated Databricks workflow, or also a one-time Airflow job wrapper? Existing FSR operational patterns in the repo use Databricks workflow YAMLs under `silver/src/workflows/fsr/`, and broader platform runs often also have Airflow entrypoints. Decide before implementation whether this repair is run directly as a DBR workflow only, or whether prod expects an Airflow-triggered wrapper as well.

## 9. Decisions on record

- **Staging table as the work ledger:** the xlsx is the input, but the repair runs off a per-row staging table (`staging_vistra_gap`). Gives validation at load time, idempotent/resumable runs, separate dev and prod status on the same row, confidence-gated rollout (47 confirmed first, 205 weak later) in one table, an audit trail for SME handback, and a clean revert input scoped by `run_id`. See §2 for details.
- **`document_id` for the new metadata row:** `f"{base}_{esn}"` — matches existing multi-ESN convention, deterministic, idempotent. Pushed back on Jon's UUID proposal because the multi-ESN fan-out path in [`nb_sdg_fsr_metadata.py`](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) and [`nb_sdg_fsr_chunks.py`](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py) already uses this convention.
- **Dev run scope:** for the agreed dev execution, do not ingest the 15 missing PDFs first. Load all 47 confirmed rows into staging, let the unresolved dev rows remain `invalid`, and repair only the 32 rows already present in dev.
- **Sibling event fields:** added to staging schema and to per-row insert logic.
- **Sibling EV Project ID — not in xlsx:** Jon's workbook has one column `Sibling Event ID` that maps to `ev_equipment_event_id` only. There is no sibling project ID column. On the new metadata row, **`ev_project_id` is always inherited from the base row** (same FSR engagement, project ID is shared). Only `ev_equipment_event_id` comes from the xlsx `Sibling Event ID`, falling back to inherit on null.
- **Staging column names mirror Jon's xlsx headers (snake_case):** `tagged_equipment_type` (not `tagged_esn_type`), `missing_esn` + separate `missing_equipment_type` (not `missing_generator_esn`), `sibling_event_id` (not `sibling_ev_equipment_event_id`). Keeps the xlsx → staging mapping 1:1 and reviewable. `sibling_ev_project_id` removed entirely (see above).
- **Extra xlsx columns carried for audit traceability (not used by insert):** `tagged_event_type`, `matched_event_date`, `gap_confirmed`. Cheap to carry, useful for SME review and post-hoc joins.
- **IBAT lookup:** equipment_type literal `'Generator'`; sys_id + class from IBAT keyed on missing ESN. No inheritance for these three.
- **Audit tables:** clone fresh (`fsr_repair_vistra_*`), separate from `fsr_repair_664196_*` for clean rollback isolation.
- **Chunk metadata JSON:** built in Python from known fields (base metadata row + IBAT values), matching the pattern in `nb_sdg_fsr_chunks.py`. Passed as a SQL string literal into the chunk clone view. Initial plan described a `REGEXP_REPLACE` approach which was replaced during implementation (see §4 design notes).
- **Verification queries:** Jon's two queries (§1a + §1b of his spec) baked into the notebook's final cell, plus a sample VS search.
- **Workbook handback:** staging table has `dev_status` / `prod_status` columns; export back to xlsx after each environment is done.
- **Repo organization for ad hoc repair work:** core recurring pipeline notebooks stay flat in `etl/`; one-off operational utilities go in `etl/repairs/`; matching setup notebooks go in `ddl/repairs/`. Keeps repair logic easy to find without fragmenting the repo by ticket or customer.
- **Revert:** clone fresh (`gold/src/etl/repairs/nb_sdg_fsr_revert_vistra_xtrain.py`) rather than parameterize existing — cheaper to review, isolates blast radius.

## 10. Flag registry (current + proposed)

Use this as the single reference for FSR toggles that impact ESN behavior. Rule: every new global flag must include owner, rollout scope, and retirement condition.

| Flag | Default | Scope | Current use | Owner | Retirement / review rule |
|---|---|---|---|---|---|
| `FSR_MULTI_ESN_ENABLED` | `true` | P1 + P2 pipeline | Enables existing multi-ESN fan-out from `all_esns` / `fsr_pdf_ref` during normal ingestion. | FSR pipeline owner | Long-lived. Review quarterly; remove only if fan-out becomes unconditional code path. |
| `FSR_MULTI_ESN_DRY_RUN` | `false` | P1 + P2 pipeline | Preview mode for multi-ESN fan-out (logs intended writes, suppresses writes). | FSR pipeline owner | Keep as operational safety toggle; verify it is not left `true` in scheduled jobs. |
| `FSR_ESN_DETECT_ENABLED` | `false` | Tier-2 detection | Controls LLM frequency-based ESN extraction path (used in targeted/backfill flows). | FSR pipeline owner | Keep until Tier-2 behavior is finalized for daily ingestion; re-evaluate after rollout decision. |
| `FSR_TRAIN_SIBLING_EXPANSION` *(proposed in Approach 2)* | `false` | Approach 2 only | Train-sibling ESN expansion (Generator/GT/ST) before fan-out. Not used by Approach 1 repair. | FSR + SME owner | Temporary rollout flag. Remove after full cutover + one stable release cycle. |
| `FSR_TRAIN_SIBLING_REQUIRE_TEXT_EVIDENCE` *(proposed)* | `false` | Approach 2 only | Optional quality gate for sibling adds using keyword evidence threshold. | FSR + SME owner | Remove if evidence gate is accepted as always-on policy; otherwise keep with documented threshold owner. |
| `FSR_TRAIN_SIBLING_KEYWORD_THRESHOLD` *(proposed)* | `3` | Approach 2 only | Minimum keyword hits when evidence gate is enabled. | FSR + SME owner | Keep only while evidence gate is configurable; review with SME quarterly. |

**Approach 1 note:** this Vistra ad hoc repair introduces no new global feature flags. Run-time control is via notebook/workflow parameters (`DRY_RUN`, `CONFIDENCE_FILTER`, `ENV_TAG`, `REPAIR_RUN_ID`) rather than permanent config toggles.

---

## 11. Final design (as implemented)

This section describes the repair pipeline as it stands after implementation and smoke-test validation on 2026-06-04. It is the authoritative reference for the current behavior.

### Pipeline overview

```
xlsx (Jon's enriched workbook)
  │
  ▼
nb_sdg_fsr_load_vistra_gap_staging     — loads + validates rows into staging_vistra_gap
  │
  ▼
nb_sdg_fsr_repair_vistra_xtrain        — per-row: insert metadata, clone chunks, audit, mark done
  │
  ▼
nb_sdg_fsr_repair_vistra_xtrain_verify — gates: staging parity, audit completeness, metadata + chunk presence
  │
  ▼
nb_sdg_fsr_revert_vistra_xtrain        — (on-demand) delete by repair_run_id, reset staging
```

### Per-row logic (repair notebook)

For each `staging_vistra_gap` row where `confidence = CONFIDENCE_FILTER` and `{ENV_TAG}_status = 'pending'`:

1. Load base metadata row by `document_id`.
2. Look up `missing_esn` in IBAT → `equipment_sys_id`, `equipment_class_code`. `equipment_type = 'Generator'` is always a literal.
3. **Idempotency check (two-branch):**
   - Target `document_id` exists **and** chunks > 0 → mark staging `skipped`, continue to next row.
   - Target `document_id` exists **but** chunks = 0 → partial-state recovery: skip metadata insert, go straight to chunk cloning.
   - Target `document_id` does not exist → proceed normally (insert metadata + chunks).
4. **Build metadata JSON** in Python from known fields: document-level fields from the base metadata row, with `esn`, `equipment_sys_id`, `equipment_type`, `equipment_class_code` overridden to the new ESN's IBAT values. Uses `json.dumps()`, matching the pattern in `nb_sdg_fsr_chunks.py`. Passed as a SQL string literal.
5. **Insert new metadata row** (if not partial-state recovery) inheriting base fields, overriding: `document_id`, `esn`, `esn_source`, `equipment_type`, `equipment_sys_id`, `equipment_class_code`, `event_type`, `ev_equipment_event_id`.
6. **Clone chunks** — deduplicated by `chunk_index` (ROW_NUMBER to handle multi-ESN base docs), skipping any `chunk_id` that already exists. Each cloned chunk gets:
   - New `document_id` = `{base_doc_id}_{missing_esn}`
   - New `chunk_id` = `MD5(document_id + '_' + chunk_index + '__' + esn)`
   - Top-level `esn` = `missing_esn`
   - `metadata` JSON = the Python-built JSON from step 4 (same for all chunks in this row)
   - `chunk_text`, `chunk_embedding`, `chunk_index` unchanged from base
7. Materialize chunk clone plan to a temp Delta table (serverless-safe — no DataFrame persist/cache).
8. Insert chunks → write chunk audit rows → drop temp table.
9. Write metadata audit row.
10. Update staging: `{ENV_TAG}_status = 'done'`, `{ENV_TAG}_run_id`, `{ENV_TAG}_processed_at`.

On per-row exception: mark `failed`, write error, continue.

### Key tables

| Table | Catalog | Purpose |
|---|---|---|
| `staging_vistra_gap` | `ai_sot_field_service_report` | Work ledger: one row per `(pdf_stem, missing_esn)`, carries dev + prod status |
| `biz_metadata_field_service_report` | `ai_sot_field_service_report` | Target for new metadata rows |
| `vec_field_service_report` | `ai_std_con_field_service_report` | Target for cloned chunk rows |
| `fsr_repair_vistra_metadata_updates` | `ai_sot_field_service_report` | Audit: one row per metadata insert, keyed by `repair_run_id` |
| `fsr_repair_vistra_chunk_inserts` | `ai_std_con_field_service_report` | Audit: one row per chunk insert, keyed by `repair_run_id` |

### Runtime parameters

| Param | Default | Notes |
|---|---|---|
| `REPAIR_RUN_ID` | auto-uuid | Must be unique per run; passed to revert to scope rollback |
| `DRY_RUN` | `true` | No writes when true; must be explicitly set to `false` for real run |
| `ENV_TAG` | required | `'dev'` or `'prod'`; drives which `*_status` column is updated |
| `CONFIDENCE_FILTER` | `'confirmed'` | Filters staging rows; use `'weak'` for the future 205-row batch |
| `INPUT_PATH` | required | Volumes path to xlsx |
| `INPUT_SHEET` | `FSR Tagging Gaps` | Sheet name in xlsx |

### Revert

Scoped strictly by `REPAIR_RUN_ID`. Reads chunk and metadata audit tables → deletes inserted rows from chunk and metadata tables → resets staging `{ENV_TAG}_status` back to `pending`. Does not touch the audit rows themselves (they remain as a record of what was done and undone). VS index cleanup requires a manual resync after revert.

