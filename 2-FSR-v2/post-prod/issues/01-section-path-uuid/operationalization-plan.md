# Operationalization Plan

Updated: 2026-09-17
Issue: Section path / UUID chunking

## Goal

Provide a controlled way to reprocess a large document scope without passing thousands of document IDs as job parameters, while preserving auditability and preventing accidental whole-table overwrites.

The operational flow is:

1. Load the target document IDs into a Delta scope table.
2. Start a run using only a short `run_id` parameter.
3. Process the scope in bounded P1 batches.
4. Overwrite each target document's metadata and reset its `chunk_status` to `pending`.
5. Let the existing P2 queue claim those documents in batches, re-chunk, re-embed, and replace stale chunks.
6. Update scope status and write one audit record per document.

## Why a scope table is needed

Passing thousands of IDs through `FSR_TARGET_PDF_NAMES` is limited by job parameter and widget size. A Delta scope table removes that limit and gives operations a durable record of what was requested, what completed, what failed, and which run made the change.

## Proposed scope table

Suggested table: `fsr_v2_overwrite_scope`

| Column | Purpose |
| --- | --- |
| `run_id` | Groups one operational reprocessing request |
| `document_id` | Normalized document identifier |
| `reason` | Why the document is being reprocessed, such as `preprocessor_boundary_fix` |
| `requested_by` | Operator or service identity |
| `requested_at` | Scope creation timestamp |
| `status` | `pending`, `in_progress`, `completed`, `failed`, or `skipped` |
| `attempt_count` | Number of processing attempts |
| `error_message` | Last failure detail |
| `started_at` | Claim timestamp |
| `completed_at` | Successful completion timestamp |
| `p1_run_id` | P1 run that overwrote metadata |
| `p2_run_id` | P2 run that replaced chunks |
| `before_fingerprint` | Optional hash of prior region/chunk state |
| `after_fingerprint` | Optional hash of resulting region/chunk state |

Primary key or uniqueness constraint: `(run_id, document_id)`.

## Required implementation changes

### 1. Scope creation utility

Create a small SQL/notebook utility that accepts a source file or query and writes normalized document IDs to the scope table. It must:

- normalize casing and remove a `.pdf` suffix
- reject empty or duplicate IDs
- require a non-empty `run_id` and reason
- show the requested count before execution
- support dry-run validation
- never delete prior scope runs

### 2. Separate repair P1 scope-table mode

Use a separate repair notebook and workflow rather than adding overwrite behavior
to the normal P1 ingestion notebook. The initial implementation is:

- `validation/fsr_v2/nb_sdg_fsr_v2_scope_ddl.py`
- `validation/fsr_v2/nb_sdg_fsr_v2_repair.py`
- `workflows/fsr_v2/repairs/pw_sdg_fsr_v2_section_repair.yml`

Parameters include:

```text
FSR_V2_OVERWRITE_TARGETS=true
FSR_V2_OVERWRITE_RUN_ID=<run_id>
FSR_V2_OVERWRITE_SCOPE_TABLE=<catalog.schema.fsr_v2_overwrite_scope>
```

Behavior:

- require all three values together
- reject `FSR_V2_OVERWRITE_TARGETS=true` without a scope table and run ID
- select only `pending` or retryable `failed` scope rows for the run
- join scope rows to `fsr_metadata_v2` and source-volume resolution
- claim a bounded batch atomically or with a compare-and-set status update
- re-run the existing parse, preprocessor, and enrichment flow from the separate repair notebook
- update `fsr_metadata_v2` as it does today
- reset `chunk_status='pending'` for successful P1 overwrites
- record `p1_run_id`, status, timestamps, and errors back to the scope table

The normal P1 ingestion notebook remains unchanged. Scope-table repair mode is the only path for this controlled overwrite operation.

### 3. P2 scope correlation

P2 continues to use `fsr_metadata_v2.chunk_status` as its work queue, with an optional scope filter implemented in the existing chunking engine. No second chunking implementation is needed.

For operational visibility, add an optional run/scope filter or a post-claim join so the P2 run can report:

- how many scope documents entered P2
- how many completed
- how many failed or exhausted retries
- the P2 run ID associated with each completed scope row

After successful chunking, update the corresponding scope rows with `p2_run_id`, status, and completion time.

### 4. Stale chunk replacement

The existing P2 merge uses document-scoped `WHEN NOT MATCHED BY SOURCE ... THEN DELETE`. Preserve this behavior and validate it before rollout:

- successful documents receive the new chunk set
- stale chunks for those documents are deleted
- failed documents retain the previous chunk set rather than being marked complete with a partial set
- unrelated documents are not touched

### 5. Audit and impact logging

Use the existing DQ log for a first operational version and write one warning per successfully overwritten document:

```text
check_name = p1_target_overwrite
failure_category = target_document_overwritten
```

The audit detail should include the overwrite run ID, P1/P2 run IDs when available, reason, and before/after fingerprints if implemented.

A dedicated audit table is recommended later if operators need long-term reporting beyond the DQ log. It should not be required for the first controlled run.

## Safety controls

- Scope-table mode must require an explicit run ID.
- A missing or empty scope must fail closed.
- No full-table overwrite mode should exist.
- Limit concurrent P1/P2 runs for the same scope.
- Use bounded batches and retry caps.
- Keep failed scope rows retryable without reprocessing completed rows.
- Require a dry run and count review before enabling writes.
- Support a kill switch that stops claiming new scope rows without interrupting already committed documents.
- Log source code version, preprocessor version, parser version, chunking parameters, and embedding model.
- Do not delete old chunks until the replacement document has a complete embedding set.

## Rollout sequence

### Phase 0: Design and dry run

1. Create the scope table in the target environment.
2. Load a small test scope, such as 5-20 documents.
3. Validate ID normalization and source-volume resolution.
4. Run in dry-run mode and review counts.

### Phase 1: Smoke overwrite

1. Select a few already-completed documents, including the uploaded sample and one Generator/sub-report case.
2. Run P1 scope mode.
3. Confirm metadata rows changed and `chunk_status` became `pending`.
4. Run P2 for the resulting queue.
5. Confirm new chunks exist, stale chunks are removed, and audit rows are present.
6. Compare before/after region counts, section paths, and chunk counts.

### Phase 2: Targeted regression scope

1. Add all cited Xujin regression documents.
2. Process in bounded batches.
3. Review failures and unexpected chunk-count changes.
4. Validate retrieval for representative queries.
5. Pause if metadata drift appears outside intended section-boundary changes.

### Phase 3: Controlled broader rollout

1. Load the approved document population into a new scope run.
2. Process with conservative concurrency and retry caps.
3. Monitor P1/P2 success rates, audit counts, chunk deltas, and embedding failures.
4. Keep the old output available for before/after comparison until QA sign-off.
5. Promote only after the scope run has no unexplained failures.

## Acceptance checks

A run is successful only when:

- every requested document has a terminal scope status
- every successful P1 document has a successful P2 result
- no successful document has a partial embedding set
- stale chunks are absent for successfully replaced documents
- failed documents are not falsely marked complete
- overwrite audit rows equal the number of completed-document overwrites
- primary ESN/equipment metadata is stable unless the change is explicitly expected
- section boundary and chunk-count changes are explainable
- retrieval smoke tests pass

## Open implementation decision

The scope-table repair implementation is now staged for validation. Before any broad run, validate the workflow in dev with a 5-20 document scope, then repeat the same run pattern in QA. Do not work around parameter-size limits by splitting an untracked ID list across many manually launched jobs.
