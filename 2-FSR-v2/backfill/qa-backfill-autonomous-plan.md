# FSR v2 — QA Backfill Recovery & Re-run: Autonomous Plan

**Read this and [equipment-map-gap-analysis.md](equipment-map-gap-analysis.md)
before touching QA.** Modelled on
[`../automation/autonomous.md`](../automation/autonomous.md), which covers dev.
This file covers the QA recovery only.

**Live status — what is done and what is next — is in
[qa-backfill-tracker.md](qa-backfill-tracker.md).** This file is the method;
the tracker is the state. Update the tracker as you go, not this file.

**Status:** written 2026-09-08. **Nothing in it has been executed.** Every QA
number quoted anywhere in this folder is reported, not measured — see §3.

---

## 1. The decision this plan encodes

**Repair the existing QA data and continue the backfill. Do not reset.**

An earlier draft of this file said reset-and-re-run-clean, on the reasoning that
nobody consumes QA so a clean run proves more. That was wrong, and the cost
makes it obviously wrong: ~8,000 completed docs is roughly **27 hours of P1 wall
clock** at the measured ~300 docs/hr, plus the LLM spend that produced them.
Throwing that away buys nothing, because **nothing in QA is irreparably
corrupted.** Going damage by damage:

| Data | State | Recoverable? |
|---|---|---|
| `fsr_metadata_v2` rows | **Correct.** P1's per-doc metadata MERGE was never the bug, and none of the fixes change what a metadata row contains — only *when* surrounding writes happen. | nothing to fix |
| Equipment map | Rows missing | **Yes, exactly.** Rebuilt from `preprocessor_regions` + the doc-level ESN columns. Same inputs `_build_map_rows` used, so the result is identical apart from `created_at`/`updated_at`. |
| `chunk_retry_count` | Inflated by the `embed_failures` leak | **Yes** — reset the failed docs and let the fixed code re-decide |
| `fsr_chunks_v2` rows | **Not corrupted.** Partial chunk sets are only possible with `embed_fail_threshold > 0`; it defaults to `0.0` (verified in `nb_sdg_fsr_v2_chunks.py`), so a doc either got all its chunks or was marked failed. | nothing to fix |
| P1 failures from those runs | Never written — still sitting as `pending` | self-healing; the next run retries them |
| DQ log rows for those runs | **Lost.** Never written, because the run never reached the end-of-run cell. | **No** — and resetting does not recover them either, so this is not an argument for reset |

The fixed pipeline is validated just as well by continuing: the remaining ~42K
docs are a clean run on the fixed code, and every new slice exercises the
per-batch equipment-map write. Repairing also **is** the prod rehearsal — prod
may carry the same gap and cannot be reset, so running the repair for real here
is worth more than running it on data about to be discarded.

### The one condition that would have justified a reset — settled, it does not apply

`databricks.yaml` carries `TODO: confirm QA ingestion catalog (likely viuq)` and
QA's `fsr_source_volume_paths` point at `viud/*`. **Decision 2026-09-08: QA
reads `viud` deliberately. This is correct, not drift.** The existing ~8,000
docs therefore came from the intended source and are keepers.

That removes the only reset trigger. **Phase 4 does not apply.** The stale TODO
in `databricks.yaml` should be cleared separately so the next reader does not
re-litigate this.

---

## 2. Authorization

Same posture as `../automation/autonomous.md` §2.

| Action | Allowed |
|---|---|
| Read/query QA tables | yes |
| Trigger / poll / cancel QA jobs | yes |
| Run the validation + repair notebooks | yes |
| `RESET_FSR_V2=true` against QA | **do not** — §1 settles that it is not needed |
| `git commit` / `git push` / merge to `dev` | **ask first** |

`RESET_FSR_V2=true` is called out because it is irreversible, discards ~27 hours
of completed work, and — per `../automation/autonomous.md` §8 — **also wipes
`fsr_run_log_v2` and `fsr_data_quality_log_v2`**, not just
metadata/chunks/equipment-map. Under this plan it never runs.

---

## 3. What is verified vs assumed

Be honest about this; the whole point of the dev `autonomous.md` is that it
records what was actually run.

| Fact | Status |
|---|---|
| QA table names | **verified** — read from `databricks.yaml` target `qa` |
| `fsr_v2_reset` is `"false"` for QA | **verified** — `databricks.yaml` line ~444 |
| QA source volumes | **decided** — `viud` by design (2026-09-08); the `databricks.yaml` TODO is stale |
| P1/P2/P3 **QA job IDs** | **unknown** — dev IDs in `autonomous.md` §3 do not apply |
| QA SQL warehouse ID | **unknown** |
| QA profile in `~/.databrickscfg` | **does not exist** — only `dev-dbr-profile`, `dev-oauth`, `ai-dev-fsr-test` |
| "~8,000 docs, zero map rows" | **reported, not measured** |
| `chunk_retry_count` inflation from the P2 bug | **inferred from code**, not observed |
| QA `fsr_run_log_v2` schema drift | **unchecked** — dev had it; QA never verified |

Phase 0 exists to close the first four rows. Do not skip it and guess.

---

## 4. QA environment facts

| Thing | Value |
|---|---|
| Host | `https://gevernova-ai-qa-dbr.cloud.databricks.com/` |
| Catalog | `vaiq` |
| Jobs run as | `service.globalopsfsso@gevernova.com` |

| Table | Full name |
|---|---|
| Metadata | `vaiq.ai_std_con_field_service_report.fsr_metadata_v2` |
| Chunks | `vaiq.ai_std_con_field_service_report.fsr_chunks_v2` |
| Equipment map | `vaiq.ai_std_con_field_service_report.fsr_document_equipment_map_v2` |
| Run log | `vaiq.ai_sot_field_service_report.fsr_run_log_v2` |
| DQ log | `vaiq.ai_sot_field_service_report.fsr_data_quality_log_v2` |
| VS index | `vaiq.ai_std_con_field_service_report.fsr_vs_index_v2` |
| VS endpoint | `pw-ser-sdg-vector-search-qa` |

> Note the schema split: metadata/chunks/equipment-map are in
> `ai_std_con_field_service_report`, but run log and DQ log are in
> `ai_sot_field_service_report`. This is **the opposite way round from dev**.
> Getting it wrong produces "table not found", not a wrong answer — but it
> wastes a cycle.

**Source volumes:** QA reads `viud/*` **by design** — see §1. The
`TODO: confirm QA ingestion catalog (likely viuq)` still sitting in
`databricks.yaml` is stale and should be removed so it stops raising the
question.

---

## 5. Phases

Each phase has a **gate**. Do not start the next phase until the gate passes.
Jobs stay stopped from Phase 1 through Phase 3. Phase 4 does not apply — see §1.

### Phase 0 — Access and facts

**Goal:** be able to query and trigger QA at all.

1. Add a QA profile to `~/.databrickscfg` (host above). Confirm with a trivial
   `SELECT 1`.
2. Find the QA SQL warehouse ID.
3. Find the QA job IDs for `PW_SDG_FSR_V2_Metadata`, `_Chunking`, `_VS_Index`,
   `_DDL`:
   ```bash
   databricks jobs list --profile <qa-profile> | grep -i FSR_V2
   ```
4. Confirm both FSR v2 jobs are actually stopped — the runs were cancelled, but
   verify rather than assume.
5. Source volumes: **already settled — QA reads `viud` by design** (§1). Nothing
   to resolve. Optionally confirm the existing docs match:
   ```sql
   SELECT DISTINCT regexp_extract(volume_path, '^/Volumes/([^/]+)/', 1) AS catalog,
          COUNT(*) AS docs
   FROM vaiq.ai_std_con_field_service_report.fsr_metadata_v2
   GROUP BY 1;
   ```

**Gate:** items 1–4 answered and written into §4. No reset decision needed —
it is settled in §1.

---

### Phase 1 — Measure

**Goal:** replace every reported number in §3 with a measured one.

Run against QA. These need no notebook deploy — plain SQL.

```sql
-- 1.1 Queue state
SELECT metadata_status, chunk_status, COUNT(*) AS docs
FROM vaiq.ai_std_con_field_service_report.fsr_metadata_v2
GROUP BY 1, 2 ORDER BY 1, 2;

-- 1.2 The equipment-map gap, with the no-ESN floor separated out
WITH mapped AS (
  SELECT DISTINCT document_id
  FROM vaiq.ai_std_con_field_service_report.fsr_document_equipment_map_v2
)
SELECT
  COUNT(*)                                        AS completed_docs,
  COUNT(e.document_id)                            AS with_map_rows,
  SUM(CASE WHEN e.document_id IS NULL
            AND COALESCE(m.primary_esn,'')='' AND COALESCE(m.gt_esn,'')=''
            AND COALESCE(m.gen_esn,'')=''     AND COALESCE(m.st_esn,'')=''
       THEN 1 ELSE 0 END)                         AS missing_but_no_esn,
  SUM(CASE WHEN e.document_id IS NULL
            AND (COALESCE(m.primary_esn,'')<>'' OR COALESCE(m.gt_esn,'')<>''
              OR COALESCE(m.gen_esn,'')<>''   OR COALESCE(m.st_esn,'')<>'')
       THEN 1 ELSE 0 END)                         AS missing_map_rows_real
FROM vaiq.ai_std_con_field_service_report.fsr_metadata_v2 m
LEFT JOIN mapped e ON m.document_id = e.document_id
WHERE m.metadata_status = 'completed';

-- 1.3 P2 retry-count damage. Distribution matters more than the total:
--     max_retries is 3, so a genuine failure caps at 3. Any doc above 3 can
--     ONLY be the embed_failures leak — the failed-doc MERGE was unscoped, so
--     a doc that failed once was re-marked at the end of every later batch
--     (~400 batches over 8K docs at batch_size=20). Counts in the tens or
--     hundreds confirm the bug from the data alone.
SELECT chunk_retry_count, COUNT(*) AS docs
FROM vaiq.ai_std_con_field_service_report.fsr_metadata_v2
WHERE chunk_status = 'failed'
GROUP BY 1 ORDER BY 1;

-- 1.4 Do the failures look like one repeated cause?
SELECT substr(chunk_error, 1, 120) AS err, COUNT(*) AS n
FROM vaiq.ai_std_con_field_service_report.fsr_metadata_v2
WHERE chunk_status = 'failed'
GROUP BY 1 ORDER BY n DESC LIMIT 20;

-- 1.5 CAPTURE ANYWAY — the only record of the 26h/23h runs
SELECT * FROM vaiq.ai_sot_field_service_report.fsr_run_log_v2 ORDER BY start_time DESC;
SELECT severity, failure_category, COUNT(*) FROM vaiq.ai_sot_field_service_report.fsr_data_quality_log_v2 GROUP BY 1,2;

-- 1.6 Does QA have the run-log schema drift dev had?
DESCRIBE vaiq.ai_sot_field_service_report.fsr_run_log_v2;
--     expect p1_workers / llm_batch_count / docs_date_filtered to be present;
--     if missing, ALTER TABLE ... ADD COLUMNS (non-destructive) before Phase 5
```

Save 1.5's output to a file. It is the only record of the 26h/23h runs.

**Gate:** §3's "reported, not measured" rows are now measured, and the run-log
schema is either confirmed correct or fixed by `ALTER TABLE`.

**Stop if** `missing_map_rows_real` is 0 — then there is no equipment-map gap in
QA, the premise is wrong, and the analysis needs revisiting before proceeding.

---

### Phase 2 — Ship the code and the notebooks

**Goal:** get the fixes and the validation/repair notebooks into QA.

Uncommitted work to ship (all on `fsr_v2`):

| File | Change |
|---|---|
| `silver/src/etl/nb_sdg_fsr_v2_metadata.py` | per-batch equipment-map write; per-batch failure/DQ flush; future release (OOM); `FSR_V2_P1_MAX_DOCS`; targeted-batch guard |
| `gold/src/etl/fsr_v2/chunking.py` | `embed_failures` scoped per batch; batch-scoped failed write; `in_progress` guards; no partial chunk sets |
| `databricks.yaml`, both P1 workflow ymls | `fsr_v2_p1_max_docs` wiring |
| `validation/fsr_v2/nb_fsr_v2_01_pulse_check.py` | new |
| `validation/fsr_v2/nb_fsr_v2_02_data_correctness_full.py` | new |
| `validation/fsr_v2/nb_fsr_v2_repair_equipment_map.py` | new |

Steps:

1. Review the diff. **Ask before committing.**
2. Before shipping, grep for the PEP 701 trap (`../automation/autonomous.md` §8)
   — nested same-type quotes in f-strings compile on 3.13 here and fail on
   serverless 3.10:
   ```bash
   grep -rn 'f"[^"]*"[^"]*"' silver/src/etl gold/src/etl validation/fsr_v2 | grep -v "'"
   ```
3. Commit → merge to `dev` → confirm CI/CD deployed to QA.
4. Verify `FSR_V2_P1_MAX_DOCS` is declared on the QA P1 job — an undeclared
   parameter is **rejected outright** by `run-now`, so this fails loudly in
   Phase 5 if missed:
   ```bash
   databricks jobs get --job-id <qa-p1-id> --profile <qa-profile> \
     | grep -A1 FSR_V2_P1_MAX_DOCS
   ```

**Gate:** all three validation notebooks are visible in the QA workspace and
`FSR_V2_P1_MAX_DOCS` appears in the QA P1 job's declared parameters.

---

### Phase 3 — Repair

**Goal:** bring the existing QA data to a correct state. This is the real
repair, not a rehearsal — and it doubles as the proving run for the prod repair
path, which is why it is worth doing carefully rather than quickly.

1. Run `validation/fsr_v2/nb_fsr_v2_repair_equipment_map` with
   `REPAIR_DRY_RUN=true` (default) against the QA tables.
2. Check its assessment against Phase 1.2. The numbers must agree. If they do
   not, one of the two queries is wrong — resolve that before writing anything.
3. Re-run with `REPAIR_DRY_RUN=false`.
4. Re-run Phase 1.2. **Gate:** `missing_map_rows_real = 0`.
5. Repair the retry-count damage. Inflated counts cannot be told apart from
   genuine ones after the fact, so reset all P2 failures and let the fixed code
   re-decide:
   ```sql
   UPDATE vaiq.ai_std_con_field_service_report.fsr_metadata_v2
   SET chunk_status = 'pending', chunk_retry_count = 0, chunk_error = NULL,
       updated_at = current_timestamp()
   WHERE chunk_status = 'failed';
   ```
6. Run `nb_fsr_v2_02_data_correctness_full` with `STRICT_QUEUE_DRAINED=false`
   — the corpus is a partial backfill, so the drained checks do not apply yet.

**Gate:** the map gap is closed and the correctness gate reports no FAIL other
than ones explained by the corpus being partial. **Record the elapsed time of
the repair** — that is the number needed to plan the prod repair.

**Stop if** the repair notebook errors or leaves a non-zero gap. That means the
prod repair path is broken, and finding out here is the point.

---

### Phase 4 — Reset (does not apply)

**Skip.** The only condition that would have justified a reset was QA reading
the wrong source volumes, and that was settled in §1 — `viud` is intentional.
Go straight from Phase 3 to Phase 5.

Kept here only so the reasoning is not lost: if a future situation does call for
a QA reset, trigger the DDL job with a `RESET_FSR_V2=true` **run-now override**,
never a `databricks.yaml` edit — a committed `"true"` means every subsequent
deploy wipes QA, which is how dev got wiped repeatedly before 2026-09-02. And
capture the run log and DQ log first; the reset destroys those too.

---

### Phase 5 — Continue the backfill, capped

**Goal:** drain the remaining queue on the fixed code, in slices. After Phase 3
this is a continuation, not a restart — the ~8,000 completed docs stay put and
are never re-processed.

Parameters:

| Param | Value | Why |
|---|---|---|
| `FSR_V2_P1_MAX_DOCS` | `5000` | ~17h per run at ~300 docs/hr; bounded memory and blast radius |
| `FSR_V2_P1_WORKERS` | `4` | swept 4/8/16 in dev — flat throughput, do not raise |
| `FSR_V2_P1_LLM_BATCH_SIZE` | `10` | |
| `FSR_V2_MIN_DOC_YEAR` | `2016` | |
| `FSR_TARGET_PDF_NAMES` | empty | |
| `RESET_FSR_V2` | `false` | never true — Phase 4 does not apply |

Loop until the queue drains:

1. Trigger P1. **Re-running continues, it does not restart** — discovery
   stub-registers the whole queue as `pending` before the cap applies, and the
   retry query re-claims whatever is still `pending`. No parameter changes
   between runs.
2. Run `nb_fsr_v2_01_pulse_check` every 1–2h. Append each to
   [backfill-pulse-log.md](backfill-pulse-log.md).
3. **After the first P1 run completes, before triggering the second:** confirm
   the equipment map kept pace. This is the direct test of the fix:
   ```sql
   -- expect: mapped tracks completed, hour by hour
   SELECT date_trunc('HOUR', m.scraped_at) AS hr,
          COUNT(*) AS completed, COUNT(DISTINCT e.document_id) AS mapped
   FROM vaiq.ai_std_con_field_service_report.fsr_metadata_v2 m
   LEFT JOIN vaiq.ai_std_con_field_service_report.fsr_document_equipment_map_v2 e
          ON m.document_id = e.document_id
   WHERE m.metadata_status = 'completed'
   GROUP BY 1 ORDER BY 1;
   ```
4. Start P2 once P1 has completed its first slice. Running them in parallel is
   supported and was not the cause of the incident — but keep P2 behind P1 for
   the first slice so the two fixes can be attributed separately if something
   goes wrong.
5. Run P3 (`INDEX_MODE=sync`) after P2 has drained at least once.

**Gate per slice:** consistency section of the pulse check reports OK. **Stop
the loop immediately if it reports FAIL** — that means a fix did not hold, and
continuing just makes more data to repair.

---

### Phase 6 — Sign-off

1. `nb_fsr_v2_02_data_correctness_full` with `STRICT_QUEUE_DRAINED=true` and
   `EXPECTED_COMPLETED_DOCS` set from the discovered corpus size.
2. Gate: zero FAIL. SKIPs are acceptable if explained.
3. Write a closing entry in [backfill-pulse-log.md](backfill-pulse-log.md):
   final counts, throughput, failure rate, total wall clock, and the repair
   elapsed time from Phase 3.
4. Carry forward to prod — see
   [backfill-monitoring-plan.md](backfill-monitoring-plan.md) §8 and §9.4.

---

## 6. Traps specific to this plan

- **Everything in `../automation/autonomous.md` §7 and §8 still applies.** The
  serverless-3.10 f-string trap, no driver logs, `date_filtered` not being an
  error, string date columns, `pdf_name` not being the source filename.
- **QA's run-log/DQ-log schema is the reverse of dev's** — `ai_sot_*`, not
  `ai_std_con_*`. See §4.
- **`RESET_FSR_V2=true` wipes the run log and DQ log too**, and discards ~27
  hours of completed work. It is not part of this plan.
- **If a QA reset is ever needed, do it via run-now override, never via
  `databricks.yaml`.** A committed `"true"` means every subsequent deploy wipes
  QA.
- **The dev job IDs in `autonomous.md` are dev-only.** Triggering a dev job ID
  against a QA profile fails or, worse, succeeds against the wrong workspace.
- **The validation notebooks need no credentials** — every widget is a table
  name or threshold. If a run asks for `LITELLM_API_KEY`, the wrong notebook is
  being run.
- **`FSR_V2_P1_MAX_DOCS` and `FSR_TARGET_PDF_NAMES` are mutually exclusive in
  practice.** P1 now raises if the cap would truncate a targeted batch. Clear
  the cap for targeted debug runs.
- **Do not treat a large `date_filtered` count as a problem.** Roughly half the
  corpus falls outside 2016+.

---

## 7. Rollback

Nothing in this plan is irreversible, because Phase 4 does not apply.

| Phase | If it goes wrong |
|---|---|
| 0–1 | read-only, nothing to undo |
| 2 | revert the merge to `dev`, redeploy |
| 3 | map repair is insert-only against an anti-join, so it cannot damage existing rows. The retry-count `UPDATE` is not reversible in place, but resetting a failed doc to `pending` only costs a re-chunk. |
| 5 | cancel the run; the queue stays `pending` and the next run continues |

No step in this plan is irreversible, because Phase 4 does not apply.
