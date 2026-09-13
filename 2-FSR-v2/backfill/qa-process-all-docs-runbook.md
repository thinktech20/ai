# FSR v2 — Process All Documents in QA and Production

Use this runbook to remove the retired 2016 lower bound and process every FSR
document already discovered in QA and production. Run the procedure in QA first,
validate it, and only then repeat it in production.

The year filter was a one-time backfill rule. It has been removed from P1 and
the incremental ingestion job so new documents no longer incur a separate
page-1 date probe. The date parsing helpers and `doc_year` metadata remain
available if a future dedicated backfill needs a date-scoped implementation.

## Safety rules

- Do **not** run the DDL job or use `RESET_FSR_V2=true`.
- Do not delete, truncate, or recreate v2 tables or parsed-document volumes.
- Complete and validate QA before changing production.
- Run at most one P1 and one P2 job per environment. P1 and P2 may overlap.
- Do not reclaim rows while P1 or the chained ingestion job is active.
- Use the deployed reclaim job; interactive users may not have write access.
- Capture before/after counts and Databricks run URLs for the change record.

## Environment reference

| Item | QA | Production |
|---|---|---|
| CLI profile | `ai-qa-dbr` | `ai-prod-dbr` |
| Bundle target | `qa` | `prod` |
| Metadata table | `vaiq.ai_std_con_field_service_report.fsr_metadata_v2` | `vaip.ai_std_con_field_service_report.fsr_metadata_v2` |
| Chunk table | `vaiq.ai_std_con_field_service_report.fsr_chunks_v2` | `vaip.ai_std_con_field_service_report.fsr_chunks_v2` |
| Run-log table | `vaiq.ai_sot_field_service_report.fsr_run_log_v2` | `vaip.ai_sot_field_service_report.fsr_run_log_v2` |
| DQ-log table | `vaiq.ai_sot_field_service_report.fsr_data_quality_log_v2` | `vaip.ai_sot_field_service_report.fsr_data_quality_log_v2` |
| P1 Metadata job | `761501966564581` | `103677766258083` |
| P2 Chunking job | `281692486694630` | `577872903132134` |
| P3 VS Index job | `21697534238749` | `360645273957590` |
| Chained ingestion job | `1042416268045266` | `925971887269017` |
| DDL job, do not run | `334275972250035` | `434716953844549` |

The reclaim job ID is created by deployment. Resolve it afterward rather than
recording an environment-specific ID in this document.

## Reclaim job design

`PW_SDG_FSR_V2_Reclaim_Date_Filtered` is a manual, unscheduled bundle job that
runs as the service identity and updates only the configured environment's
metadata table.

- `RECLAIM_DRY_RUN=true` is the default and only reports the row count.
- `RECLAIM_DRY_RUN=false` changes `date_filtered` to `pending`, clears
  `metadata_error`, and updates `updated_at`.
- It does not change completed rows, chunk rows, equipment-map rows, or parsed
  documents.
- `max_concurrent_runs: 1` prevents overlapping reclaim executions.
- The apply run fails if any `date_filtered` rows remain afterward.

This job is separate from P1. Deployment does not mutate data; an operator must
explicitly run the job with dry-run disabled.

## 1. Deploy the code and job

From the repository root, validate both targets:

```bash
databricks bundle validate -t qa --profile ai-qa-dbr
databricks bundle validate -t prod --profile ai-prod-dbr
```

Deploy QA first:

```bash
databricks bundle deploy -t qa --profile ai-qa-dbr
```

Complete and validate the QA backfill before deploying production. Then run:

```bash
databricks bundle deploy -t prod --profile ai-prod-dbr
```

Deployment updates P1, chained incremental ingestion, validation, and creates
the reclaim job. It must not run the DDL job.

Resolve the reclaim job ID after each deployment:

```bash
databricks jobs list --profile <profile> --output json | jq -r \
  '.[] | select(.settings.name == "PW_SDG_FSR_V2_Reclaim_Date_Filtered") | .job_id'
```

## 2. Preflight one environment

Set these shell variables for QA or production:

```bash
PROFILE=ai-qa-dbr
P1_JOB_ID=761501966564581
P2_JOB_ID=281692486694630
P3_JOB_ID=21697534238749
INGESTION_JOB_ID=1042416268045266
RECLAIM_JOB_ID=<resolved-after-deployment>
```

For production, use the production values from the table above.

Confirm there are no active P1, P2, or chained-ingestion runs:

```bash
databricks jobs list-runs --job-id "$P1_JOB_ID" --profile "$PROFILE" --limit 5
databricks jobs list-runs --job-id "$P2_JOB_ID" --profile "$PROFILE" --limit 5
databricks jobs list-runs --job-id "$INGESTION_JOB_ID" --profile "$PROFILE" --limit 5
```

Run this read-only query in the environment's SQL warehouse and save the result:

```sql
SELECT metadata_status, chunk_status, COUNT(*) AS docs
FROM <metadata_table>
GROUP BY metadata_status, chunk_status
ORDER BY metadata_status, chunk_status;
```

Before QA processing, confirm the bundle's QA source volume paths are intended.
They currently use the `viud` ingestion catalog. Validate the actual mounted
source paths with the platform owner before proceeding.

## 3. Dry-run and apply the reclaim

Run the reclaim job with its safe default:

```bash
databricks jobs run-now "$RECLAIM_JOB_ID" --profile "$PROFILE"
```

Confirm the reported count equals the preflight `date_filtered` count. Then run
the explicit apply:

```bash
databricks jobs run-now "$RECLAIM_JOB_ID" --profile "$PROFILE" \
  --json '{"job_parameters":{"RECLAIM_DRY_RUN":"false"}}'
```

Verify the migration before starting P1:

```sql
SELECT metadata_status, COUNT(*) AS docs
FROM <metadata_table>
GROUP BY metadata_status
ORDER BY metadata_status;
```

Expected: `date_filtered` is zero and `pending` increased by the same count.

## 4. Run the all-document backfill

Use the standalone jobs so P2 can consume completed P1 batches while P1 is
still running. Leave `FSR_TARGET_PDF_NAMES` and `FSR_V2_P1_MAX_DOCS` empty.
`FSR_V2_P1_SLICE_SIZE=2000` bounds driver memory but does not stop after 2,000;
one P1 run continues through slices until the queue drains.

```bash
databricks jobs run-now "$P1_JOB_ID" --profile "$PROFILE" --no-wait
databricks jobs run-now "$P2_JOB_ID" --profile "$PROFILE" --no-wait
```

If P2 finishes while P1 is still producing completed rows, start P2 again only
after confirming no P2 run is active. Do not use the chained ingestion job for
this backfill because its P2 task waits for the full P1 task to finish.

## 5. Monitor

Queue status:

```sql
SELECT metadata_status, chunk_status, COUNT(*) AS docs
FROM <metadata_table>
GROUP BY metadata_status, chunk_status
ORDER BY metadata_status, chunk_status;
```

Recent run summaries:

```sql
SELECT job_name, start_time, end_time, docs_claimed, docs_succeeded,
       docs_failed, docs_date_filtered, chunks_written, error_summary
FROM <run_log_table>
ORDER BY start_time DESC
LIMIT 20;
```

For runs on the new code, `docs_date_filtered` must be `0`. The column remains
only for compatibility with historical run records.

Stuck-state check:

```sql
SELECT
  SUM(CASE WHEN metadata_status = 'pending' THEN 1 ELSE 0 END) AS metadata_pending,
  SUM(CASE WHEN metadata_status = 'date_filtered' THEN 1 ELSE 0 END) AS legacy_date_filtered,
  SUM(CASE WHEN chunk_status = 'in_progress' THEN 1 ELSE 0 END) AS chunk_in_progress,
  SUM(CASE WHEN metadata_status = 'completed' AND chunk_status = 'pending'
           THEN 1 ELSE 0 END) AS chunk_pending
FROM <metadata_table>;
```

P2 reclaims claims older than its configured stale-claim window. P1 retries
failed rows only while `metadata_retry_count` is below its configured cap.

## 6. Complete and validate

P1 is drained when `pending=0`, `date_filtered=0`, and remaining failed rows
have reached the retry policy or have an understood terminal cause. P2 is
drained when no completed metadata rows remain pending or in progress.

Run P3 after the final P2 run:

```bash
databricks jobs run-now "$P3_JOB_ID" --profile "$PROFILE"
```

Run the full FSR v2 correctness validation and retain its output. Confirm:

- no legacy `date_filtered` rows remain;
- no completed documents are waiting for chunking;
- no stale P2 claims remain;
- P1 run logs show `docs_date_filtered=0`;
- the vector index sync completed successfully.

After QA passes, repeat sections 1-6 for production with production identifiers.

## Runtime estimate

Do not reuse the earlier screened-throughput estimate. With the filter removed,
every reclaimed document receives full parsing, preprocessing, LLM extraction,
metadata writes, chunking, and embedding.

```text
P1 hours ~= (date_filtered + pending + retryable_failed) / completed_docs_per_hour
```

At the previously observed 260-300 completed documents/hour, 30,000 documents
would require roughly 100-116 P1 hours, before retries and service slowdowns.
Measure QA throughput again before scheduling the production window.
