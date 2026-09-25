# Generic Attribute Backfill — Operator Guide

**Job:** `PW_SDG_FSR_Generic_Attribute_Backfill`
**Owner:** FSR pipeline team
**Audience:** Support / D&A operators triggering the job in prod

---

## 1. What this job does

A reusable framework for backfilling attributes on the FSR metadata table
(`biz_metadata_field_service_report`). One job, many strategies — pick the
strategy by name via `FSR_BACKFILL_NAME`.

Each strategy:
- reads documents from the metadata table,
- computes one or more attributes (e.g. document summary, TOC),
- MERGEs results back on `document_id` (idempotent — safe to re-run),
- writes status + counters to `fsr_run_log` and any failures to
  `fsr_data_quality_log`.

**Current strategies registered**

| `FSR_BACKFILL_NAME`     | What it does                                      |
| ----------------------- | ------------------------------------------------- |
| `document_summary_toc`  | Extracts TOC-based document summary (pdfplumber). |

---

## 2. When to run it

- A new attribute column was added to the metadata table and needs to be
  populated for existing rows.
- A bug-fix re-extraction is needed for a known set of documents.
- A new strategy was merged and needs a one-time gap-fill on prod.

**Not for** the daily incremental pipeline — that is `PW_SDG_FSR_Ingestion`.

---

## 3. Pre-flight checklist

Before triggering on prod:

1. Confirm the PR carrying the strategy is merged to `main` and the bundle
   has been deployed to the prod target.
2. If the PR added any new columns to the metadata / chunk tables, run
   **`FSR_DDL_Provision`** on prod first (with `FORCE_RESET=false`). The
   ALTER statements are idempotent — safe to re-run.
3. Confirm no other heavy job is running on the shared pool.
4. Note the latest `fsr_run_log` run_id for the strategy (so you can diff
   after the run).

---

## 4. Parameters

All parameters are exposed on the job. Defaults come from the bundle for the
deployed environment — only override the operator knobs per run.

### Environment-bound (do not override per run)
| Param                  | Source                       |
| ---------------------- | ---------------------------- |
| `jb_env`               | bundle var `jb_env`          |
| `FSR_METADATA_TABLE`   | bundle var `fsr_metadata_table` |
| `FSR_DQ_LOG_TABLE`     | bundle var `fsr_dq_log_table`   |
| `FSR_RUN_LOG_TABLE`    | bundle var `fsr_run_log_table`  |
| `FSR_CHUNK_TABLE`      | bundle var `fsr_chunk_table`    |

### Operator knobs (set per run via "Run with different parameters")
| Param                       | Default                | What to set                                       |
| --------------------------- | ---------------------- | ------------------------------------------------- |
| `FSR_BACKFILL_NAME`         | `document_summary_toc` | Strategy name from the table in §1.                |
| `FSR_BACKFILL_DRY_RUN`      | `false`                | `true` for preview (no writes), `false` to apply. |
| `FSR_BACKFILL_SAMPLE_LIMIT` | `0`                    | Cap on docs processed. `0` = no cap (full run).   |
| `FSR_BACKFILL_BATCH_SIZE`   | `200`                  | Commit batch size. Leave at 200 unless told.      |
| `FSR_DOCSUMMARY_MAX_PAGES`  | `200`                  | Per-doc page cap for the TOC strategy.            |

---

## 5. Run sequence (recommended)

Always run in three steps. Never go straight to full apply on prod.

### Step 1 — Dry-run on a small sample
- `FSR_BACKFILL_DRY_RUN` = `true`
- `FSR_BACKFILL_SAMPLE_LIMIT` = `50`

Confirms the strategy picks up rows, computes attributes, and reports the
expected status distribution. Nothing is written.

### Step 2 — Apply on the same small sample
- `FSR_BACKFILL_DRY_RUN` = `false`
- `FSR_BACKFILL_SAMPLE_LIMIT` = `50`

Verify the 50 docs land correctly in the metadata table (see §6).

### Step 3 — Full apply
- `FSR_BACKFILL_DRY_RUN` = `false`
- `FSR_BACKFILL_SAMPLE_LIMIT` = `0`

Optionally run in slices (e.g. 5000 at a time) by setting the sample limit
progressively. The MERGE is idempotent so overlap is safe.

---

## 6. Verification queries

Replace `<run_id>` with the run_id printed at the top of the driver log
(format: `backfill-<strategy>-<12hex>`).

**Run summary**
```sql
SELECT run_id, job_name, start_time, end_time, duration_seconds,
       docs_claimed, docs_succeeded, docs_failed, chunks_written, error_summary
FROM   vaip.ai_sot_field_service_report.fsr_run_log
WHERE  run_id = '<run_id>';
```

**Failures for this run** — backfill routes per-doc failures here.
```sql
SELECT pdf_name, failure_category, detail, created_at
FROM   vaip.ai_sot_field_service_report.fsr_data_quality_log
WHERE  run_id = '<run_id>'
  AND  check_name = 'doc_summary_extraction'
ORDER  BY created_at DESC;
```

**Failure breakdown by category**
Expected categories for `document_summary_toc`: `no_toc` (e.g. 1-page PDFs),
`no_summary_section` (TOC present but no summary heading), `too_large`
(over the page cap), `empty_after_extraction`, `failed` (pdfplumber error).
```sql
SELECT failure_category, COUNT(*) AS n
FROM   vaip.ai_sot_field_service_report.fsr_data_quality_log
WHERE  run_id = '<run_id>'
  AND  check_name = 'doc_summary_extraction'
GROUP  BY failure_category
ORDER  BY n DESC;
```

**Populated counts in the metadata table**
The backfill only writes `document_summary` to the metadata table. The
`_status` and `_error` per-doc values live in the DQ log (not as columns
on the metadata table).
```sql
SELECT COUNT(*)                                                       AS total,
       COUNT(document_summary)                                         AS populated,
       SUM(CASE WHEN document_summary IS NULL THEN 1 ELSE 0 END)       AS still_null
FROM   vaip.ai_sot_field_service_report.biz_metadata_field_service_report;
```

**Chunk-side check** — every successfully populated metadata row should
also have `document_summary` inside its chunk metadata JSON.
```sql
SELECT COUNT(*)                                                                          AS total_chunks,
       SUM(CASE WHEN get_json_object(metadata, '$.document_summary') IS NOT NULL
                 AND get_json_object(metadata, '$.document_summary') != ''
                THEN 1 ELSE 0 END)                                                       AS chunks_with_summary
FROM   vaip.ai_std_con_field_service_report.vec_field_service_report;
```

---

## 7. Troubleshooting

| Symptom                                       | Likely cause                             | Action                                                     |
| --------------------------------------------- | ---------------------------------------- | ---------------------------------------------------------- |
| `UNRESOLVED_COLUMN` on a new attribute column | DDL not provisioned on prod              | Run `FSR_DDL_Provision` (FORCE_RESET=false), then re-run.  |
| Job picks up 0 docs                           | Strategy gate already satisfied for all  | Check the populated-count query in §6. Likely nothing to do. |
| Many rows in DQ log with `pdfplumber` errors  | Corrupt or oversized PDFs                | Acceptable; failures are isolated per doc. Review sample.  |
| Job hangs / no progress                       | Cluster / pool contention                | Cancel run, check pool, retry off-peak.                    |
| Need to abort mid-run                         | —                                        | Cancel from UI. MERGE is idempotent; re-run resumes safely. |

---

## 8. Rollback

No explicit rollback needed. The strategy writes via MERGE on `document_id`,
so re-running with the same or different sample limit always converges to
the latest computed value. If a bad strategy version landed, revert the PR,
redeploy, and re-run.
