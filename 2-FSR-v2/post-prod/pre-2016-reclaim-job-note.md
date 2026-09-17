# Pre-2016 Reclaim Job Note

Updated: 2026-09-15
Date first noted: 2026-09-15

## Summary

`PW_SDG_FSR_V2_Reclaim_Date_Filtered` is the manual Databricks job created to process pre-2016 documents that were previously marked `date_filtered` under the retired `FSR_V2_MIN_DOC_YEAR=2016` rule.

## What the job does

- Runs as a one-time repair job.
- Defaults to `RECLAIM_DRY_RUN=true`.
- With `RECLAIM_DRY_RUN=false`, changes metadata rows from `date_filtered` to `pending`.
- Clears `metadata_error` and updates `updated_at`.
- Does not change completed rows, chunk rows, equipment-map rows, or parsed documents.

## Why it exists

The `2016` lower-bound filter was used during the earlier backfill. Later runbook notes say that filter has been retired and all FSR documents should now be processed. This reclaim job is the controlled path for returning the previously filtered pre-2016 rows to P1.

## Deployment status

The workflow file exists in the repo, but the runbook says the reclaim job ID is created only after deployment. Based on the current notes, treat this as pending deployment until QA and prod bundle deployment is confirmed.

## Current counts from backfill notes

- QA `date_filtered (pre-2016)`: `25,292`
- Prod `P1 date-filtered`: `22,608`

## Next checks

1. Confirm whether the bundle containing this job has been deployed to QA.
2. Resolve the created job ID in QA and run the dry run.
3. Validate QA processing before deploying and applying in prod.

## Sources

- `pw_sdg_ai_ser_repo/workflows/fsr_v2/repairs/pw_sdg_fsr_v2_reclaim_date_filtered.yml`
- `ai-arch/2-FSR-v2/backfill/qa-process-all-docs-runbook.md`
- `ai-arch/2-FSR-v2/backfill/qa-backfill-tracker.md`
- `ai-arch/2-FSR-v2/backfill/prod-backfill-tracker.md`
