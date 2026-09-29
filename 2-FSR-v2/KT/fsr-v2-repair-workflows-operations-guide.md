# FSR v2 Document Repair Workflows: Operations Guide

## Purpose

These workflows provide a controlled way to reprocess documents that are already known to FSR v2. They are intended for approved corrections such as section-path, metadata, chunking, or preprocessor-profile fixes.

They are not a replacement for daily ingestion or backfill. New documents must go through normal ingestion first, unless an approved candidate includes a valid source path and is intentionally handled as a missing metadata target.

## Workflow Summary

### 1. `PW_SDG_FSR_V2_Prepare_Repair_Scope`

This job validates the approved candidate table and creates the repair manifest in the scope table.

It:

- normalizes candidate document IDs and resolves them against FSR v2 metadata
- identifies resolved documents, duplicates, missing targets, and missing source paths
- records the repair reason, expected profile, requester, and audit defaults
- creates rows for a unique `REPAIR_RUN_ID` only when dry-run is disabled
- does not update metadata, chunks, embeddings, or the Vector Search index

Always run this job first with `REPAIR_DRY_RUN=true`. Review the counts, then rerun with the same new run ID and `REPAIR_DRY_RUN=false` to create the manifest.

### 2. `PW_SDG_FSR_V2_Document_Repair`

This job processes only documents in the prepared manifest for the supplied run ID. It runs the standard FSR v2 notebooks in repair mode and in this order:

1. **P1 metadata extraction:** reparses the source, applies the deployed preprocessor, replaces metadata, captures rollback data, and sets `chunk_status=pending`.
2. **P2 chunking and embedding:** replaces the complete chunk and embedding set and removes stale chunks only after successful processing.
3. **P3 Vector Search sync:** synchronizes the approved production index with the replacement chunks.

The job records separate P1, P2, and P3 statuses so that partial completion is visible. It also records actual profile selection, processing strategy, before/after fingerprints, counts, run IDs, errors, and rollback availability.

## Production Run Procedure

### Before starting

- Confirm the required code/profile fix is deployed to production.
- Use an approved, governed candidate table; do not paste IDs into job parameters or manually insert scope rows.
- Confirm the candidate table has the required document identifier and source path where applicable.
- Check that none of the documents are in another active repair run. Overlapping repairs must run sequentially or be combined into one approved scope.
- Create a new, unique run ID. Never reuse a completed run ID.
- Confirm production table and Vector Search defaults are correct. Override environment defaults only through an approved change.

### Step 1: Validate the scope

Run `PW_SDG_FSR_V2_Prepare_Repair_Scope` with:

```text
REPAIR_CANDIDATE_TABLE=<approved catalog.schema.table>
REPAIR_RUN_ID=<new unique run ID>
REPAIR_REASON=<approved repair reason>
EXPECTED_PREPROCESSOR_PROFILE=<profile, or blank for an approved mixed-profile scope>
PAGE_FALLBACK_ENABLED=<required when final_master_report is expected>
PAGE_FALLBACK_VERSION=<required when final_master_report is expected>
REQUESTED_BY=<operator or service identity>
REPAIR_DRY_RUN=true
```

Review:

- requested, resolved, duplicate, missing-target, and missing-source counts
- source-path resolution
- expected profile and page-fallback settings
- the exact number of documents that would enter the manifest

Stop if counts or resolved documents differ from the approved request.

### Step 2: Create the manifest

Rerun `PW_SDG_FSR_V2_Prepare_Repair_Scope` with the same parameters and:

```text
REPAIR_DRY_RUN=false
```

Confirm the scope rows exist for the run ID and begin in the expected pending or skipped states. Do not create or modify scope rows manually.

### Step 3: Preview the repair

Run `PW_SDG_FSR_V2_Document_Repair` with:

```text
FSR_V2_REPAIR_RUN_ID=<same run ID>
FSR_V2_REPAIR_DRY_RUN=true
FSR_V2_REPAIR_MAX_DOCS=<approved batch limit, if applicable>
FSR_V2_REPAIR_KILL_SWITCH=false
```

Confirm that only documents in the approved scope are selected. Review the expected P1, P2, and P3 impact before applying changes.

### Step 4: Apply the repair

Rerun `PW_SDG_FSR_V2_Document_Repair` with the same run ID and:

```text
FSR_V2_REPAIR_DRY_RUN=false
```

Use conservative batch limits for broad scopes. The job allows only one concurrent run and queues additional launches. Do not launch another repair for overlapping documents.

Set `FSR_V2_REPAIR_KILL_SWITCH=true` if operations must stop the job from claiming new documents. Already committed document work is not interrupted.

## Completion Checks

A production repair is complete only when:

- every requested document has an explained terminal scope status
- every successful document has `p1_status`, `p2_status`, and `p3_status` completed
- actual profile and processing strategy match expectations
- final-master-report rows contain the required page-fallback configuration and reason
- before/after fingerprints and region/chunk counts are populated and explainable
- rollback artifacts are available for every changed document
- stale chunks are absent and no document has a partial embedding set
- overwrite audit records match the number of completed P1 overwrites
- equipment/ESN metadata is unchanged unless that change was approved
- representative retrieval checks pass after index sync
- unrelated metadata, chunks, and index content were not changed

Failed rows remain visible and retryable. Correct the cause and rerun the same repair run ID; completed rows must not be reprocessed.

## Important Safety Notes

- A missing run ID or empty scope must fail closed.
- Do not use `FSR_TARGET_PDF_NAMES` for bulk repair.
- Do not use these workflows for routine ingestion or date-based backfill.
- Do not run P3 until the production chunk source and index impact have been reviewed and approved.
- Do not delete previous scope runs or rollback artifacts before QA and operations sign-off.
- If rollback is required, enable the kill switch, restore metadata/chunks/embeddings/index references from the captured artifact, validate consistency, and then update rollback status.
