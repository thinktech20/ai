# FSR v2 Generic Repair Workflow Design

Updated: 2026-09-24
Status: Implemented in repository; Databricks dev validation pending

## Decision Summary

The current document-repair workflow should not have a separate repair P1 notebook. It should use the same three-stage FSR v2 pipeline as normal ingestion:

1. P1 metadata extraction and enrichment
2. P2 chunking and embedding
3. P3 vector-index synchronization

The difference is the input and write contract:

- normal mode discovers new documents from the source volumes
- repair mode reads an approved document scope from a Delta repair-scope table
- repair mode resolves existing metadata rows or approved source PDFs
- repair mode updates existing metadata rows and may insert a missing target only when the source PDF is resolved in the approved scope
- P2 and P3 process only the same repair scope
- the job remains generic; the repair reason and expected profile are data in the scope table, not issue-specific pipeline code

This design supports the UUID section-path correction, the `final_master_report` correction, and future pipeline fixes without creating a new parser, enrichment path, chunker, or embedding implementation.

## Why P2 and P3 Are Required

A metadata-only overwrite is insufficient for both current issues.

The UUID fix changes section boundaries and section labels. The final-master-report fix changes region attribution and may change region metadata. Existing chunks would otherwise retain stale boundaries and stale metadata.

P2 must therefore:

- read the repaired `preprocessor_regions` from `fsr_metadata_v2`
- create the replacement chunk and embedding set
- delete stale chunks only for documents whose replacement set completed successfully
- leave prior chunks in place for failed documents

P3 must then synchronize the updated chunk table with the vector index. The repair flow is therefore P1 -> P2 -> P3, matching `pw_sdg_fsr_v2_ingestion.yml`.

## Workflow Shape

The repair job should be a parameterized copy of the regular ingestion workflow's orchestration shape, with the same notebook paths:

```text
repair_scope_preflight
        |
        v
regular P1 metadata notebook
        |
        v
regular P2 chunk notebook
        |
        v
regular P3 vector-index notebook
        |
        v
repair scope finalization / summary
```

The P1, P2, and P3 tasks should call the same notebooks used by the regular ingestion job:

- `silver/src/etl/nb_sdg_fsr_v2_metadata`
- `gold/src/etl/nb_sdg_fsr_v2_chunks`
- `vs/src/etl/nb_sdg_fsr_v2_index`

Before the repair pipeline is started, production operators run the separate
scope-preparation job:

- job: `PW_SDG_FSR_V2_Prepare_Repair_Scope`
- schema bootstrap: `ddls/fsr_v2/nb_sdg_fsr_v2_repair_scope_ddl`
- population/preflight: `validation/fsr_v2/nb_sdg_fsr_v2_prepare_repair_scope`

That job accepts a candidate table and writes only the repair manifest. It does
not write metadata, chunks, embeddings, or the vector index. The repair
pipeline consumes the resulting `run_id`; there is no manual table editing in
production.

There should be no `nb_sdg_fsr_v2_repair.py` execution path. If a small repair-specific preflight or finalization notebook is useful, it must only validate and update scope state. It must not parse PDFs, run preprocessing, enrich metadata, chunk documents, create embeddings, or synchronize the index.

## Runtime Modes

Use one explicit mode parameter rather than multiple unrelated parameter names:

```text
FSR_V2_RUN_MODE=incremental | targeted | repair
```

The existing normal ingestion job continues to use `incremental` or `targeted` behavior. The repair job always sets:

```text
FSR_V2_RUN_MODE=repair
FSR_V2_REPAIR_SCOPE_TABLE=<catalog.schema.fsr_v2_repair_scope>
FSR_V2_REPAIR_RUN_ID=<short immutable run id>
FSR_V2_REPAIR_DRY_RUN=true|false
FSR_V2_REPAIR_MAX_DOCS=<optional bounded cap>
FSR_V2_REPAIR_KILL_SWITCH=false|true
```

The scope table and run ID must be required together. `FSR_V2_RUN_MODE=repair` without both values must fail before any pipeline task can write. A repair run must never fall back to volume discovery or an unscoped queue drain.

Do not maintain separate aliases such as `REPAIR_RUN_ID`, `FSR_V2_REPAIR_RUN_ID`, `FSR_V2_OVERWRITE_RUN_ID`, and `FSR_V2_REPAIR_SCOPE_TABLE`. One canonical parameter contract prevents P1 and P2 from receiving different scopes.

## Repair Scope Contract

The repair scope is the manifest and audit state for one requested operation. It
must retain both the operator-supplied candidate and the resolved metadata key:

- `requested_document_id` is the normalized candidate supplied by the operator
- `document_id` is the canonical key resolved from `fsr_metadata_v2` and may be null before a source-resolved missing target is inserted
- `source_volume_path`, `source_file_size_bytes`, and `source_file_last_modified` provide the source needed to insert a missing target

Use `(run_id, requested_document_id)` as the manifest uniqueness key. Resolved
rows must also be unique by `(run_id, document_id)`. This allows unresolved
candidates to be recorded without pretending that they are valid metadata rows.

### Required request fields

- `run_id`
- `requested_document_id`
- canonical `document_id`, when resolution succeeds
- `reason`
- `requested_by`
- `requested_at`
- `expected_preprocessor_profile`, optional for a generic non-profile repair but required when the repair is profile-specific
- `page_fallback_enabled` and `page_fallback_version` when the expected profile is `final_master_report`
- `dry_run_approved` or an equivalent operator approval marker

### Processing fields

- `p1_status`: `pending`, `in_progress`, `completed`, `failed`, `skipped`
- `p2_status`: `pending`, `in_progress`, `completed`, `failed`, `skipped`
- `p3_status`: `pending`, `in_progress`, `completed`, `failed`, `skipped`
- `resolution_status`: `pending`, `resolved`, `missing_target`, `missing_source`, `duplicate`, `invalid`
- `skip_reason`
- `attempt_count`
- `p1_run_id`, `p2_run_id`, `p3_run_id`
- `started_at`, `completed_at`, `error_message`
- `kill_switch_requested_at`

### Provenance fields

- `actual_preprocessor_profile`
- `actual_preprocessor_strategy`
- `preprocessor_version`
- `parser_version`
- `detection_method`
- `detection_signals`
- `detection_confidence`
- `page_fallback_enabled`
- `page_fallback_version`
- `fallback_reason`
- deployed code commit
- chunking parameters
- embedding model and dimension

### Before/after and rollback fields

- `before_fingerprint`
- `after_fingerprint`
- `before_region_count`
- `after_region_count`
- `before_chunk_count`
- `after_chunk_count`
- `rollback_status`
- `rollback_artifact_uri`
- `rollback_snapshot_version`

The scope table should have uniqueness constraints or equivalent validation for
`(run_id, requested_document_id)` and, for resolved rows,
`(run_id, document_id)`. It must not delete or overwrite prior runs.

## Scope Creation and Preflight

Scope creation is separate from pipeline execution.

In production, scope creation is implemented by
`PW_SDG_FSR_V2_Prepare_Repair_Scope`. The job first runs the idempotent scope
DDL notebook, then validates and optionally inserts the manifest. It defaults
to `REPAIR_DRY_RUN=true`; an apply run requires an explicit new `run_id`, a
candidate table, and a reason.

1. Accept a source query, file, or validated document list.
2. Normalize IDs using the same canonical document-ID rule as FSR input handling: trim, remove a trailing `.pdf`, normalize casing, and preserve the UUID-prefix contract where applicable.
3. Resolve each candidate against `fsr_metadata_v2`; for a missing target, require source path and file metadata in the candidate table so regular P1 can process and insert it.
4. Report empty, duplicate, unresolved, and already-active IDs before inserting scope rows.
5. Insert existing targets as `resolution_status=resolved`; insert source-resolved missing targets as `resolution_status=missing_target` with P1/P2/P3 pending; record candidates without a target or source as `missing_source` with all stages skipped.
6. Reject duplicate resolved document IDs and overlap with another active repair run unless the operator explicitly closes or sequences the prior run.
7. Show resolved, missing-target, duplicate, and invalid counts and representative IDs for operator approval.
8. Insert `pending` scope rows only for resolved existing targets. The missing-target rows remain as a terminal manifest record and are never sent to P1.

The preflight task must verify:

- the run ID is new and non-empty
- the scope table exists
- the selected scope is non-empty
- every `resolution_status=resolved` scope document exists in `fsr_metadata_v2`
- every `resolution_status=missing_target` scope document has a resolvable source volume path
- no document is already claimed by another active repair run
- the deployed code and profile versions are the intended versions
- repair mode is not configured to discover new documents

A missing or empty scope fails closed. It must not be interpreted as "process all pending documents." A candidate absent from `fsr_metadata_v2` is eligible for repair insertion only when its source PDF is resolved; otherwise it is recorded as `missing_source`, skipped, and remains available for normal ingestion or backfill.

## P1 Design: Regular Metadata Notebook in Repair Mode

The regular metadata notebook remains the owner of parsing, preprocessing, LLM normalization, enrichment, metadata MERGE, retry behavior, DQ logging, equipment-map updates, and run logging.

Only its input-selection and write-policy behavior needs a repair-mode extension.

### Input selection

In `repair` mode, the regular P1 notebook must:

- select `resolution_status=resolved` or source-resolved `missing_target` rows with `pending` or retryable `failed` P1 status for the supplied run ID
- left join scope rows to `fsr_metadata_v2`, using scope source fields when the metadata row is missing
- resolve or verify the source PDF path using the regular source-volume resolution rules
- process a bounded batch or slice at a time
- claim scope rows with a compare-and-set update from `pending` or retryable `failed` to `in_progress`
- stop claiming new rows when `FSR_V2_REPAIR_KILL_SWITCH=true`

It must not scan all source volumes for new documents in repair mode.

### Scoped write policy

The regular enrichment/metadata write path remains the normal MERGE path. Repair
mode constrains the input scope and validates the source; it does not remove the
normal `WHEN NOT MATCHED THEN INSERT` branch.

In repair mode:

- an existing target row is updated by the matching `document_id`
- a missing target with a resolved source PDF is inserted by the normal MERGE
- a missing target without a resolved source is skipped as `missing_source` and is not passed to P1
- `metadata_status` becomes `completed` only after the normal P1 stages succeed
- `chunk_status` is reset to `pending` after a successful metadata update
- the existing metadata row's stable identity and source path are preserved unless the repair contract explicitly allows a source-path correction
- metadata retry and failure behavior remains the regular P1 behavior
- equipment-map replacement remains the regular P1 behavior
- normal DQ and run-log writes remain enabled

This is the key distinction: repair mode changes the input set and scopes the
normal MERGE; it does not create a second metadata-processing implementation or
permit out-of-scope inserts.

### P1 completion

After each successful update, P1 records:

- `p1_status=completed`
- `p1_run_id`
- actual profile and strategy from the processor output
- profile detection signals and confidence
- parser, preprocessor, and prompt versions
- before/after metadata fingerprints and region counts
- `p2_status=pending`

After a processing failure on a resolved or source-resolved missing target, P1
records the error and leaves the row retryable according to the regular retry
policy. It must not mark P2 ready for a partial metadata update. A missing
target with no source path follows a different path: its scope row is terminal
`missing_source`/`skipped`, the metadata table is untouched, and normal
ingestion or backfill may later create the metadata row.

The DQ log receives one warning per successful repair:

```text
check_name = p1_target_overwrite
failure_category = target_document_overwritten
```

The detail includes the repair run ID, reason, P1 run ID, profile provenance, and before/after fingerprints.

## P2 Design: Regular Chunk Notebook in Repair Mode

The regular P2 notebook remains the owner of claiming metadata rows, loading parsed documents, chunking, embedding, chunk MERGE, retry handling, and stale-chunk deletion.

When repair mode is enabled, P2 must require both the scope table and run ID and add a mandatory scope predicate to every claim query:

```sql
EXISTS (
  SELECT 1
  FROM <scope_table> s
  WHERE s.run_id = <repair_run_id>
    AND s.document_id = m.document_id
    AND s.p1_status = 'completed'
    AND s.p2_status IN ('pending', 'failed')
)
```

P2 must fail closed if repair mode is enabled but either scope parameter is missing. It must never fall back to the normal unscoped queue.

For successful documents, the existing document-scoped replacement behavior remains required:

- write the complete new chunk and embedding set
- delete stale chunks for that document only
- update `chunk_status=completed`
- reset the chunk retry count
- update `p2_status=completed`, `p2_run_id`, and completion time
- retain the before/after chunk counts and fingerprints

For failed documents:

- retain the previous complete chunk set
- mark the metadata and scope row failed/retryable
- do not delete old chunks
- do not mark P2 completed

P2 must report claimed, succeeded, failed, retry-exhausted, and skipped scope counts. The P2 run ID must be written to the corresponding scope rows.

## P3 Design: Regular Vector Index Synchronization

P3 is part of repair because P2 replaces embeddings and chunk rows. The repair job must call the same index notebook as normal ingestion after P2 completes.

P3 must be restricted to the repair run's changed documents when the index implementation supports a document filter. If the index is a Delta-sync index that automatically observes the changed chunk table, the task should still record the index-sync run and validate that the affected documents are visible.

P3 completion should update `p3_status` and record the index run identifier. A P3 failure must not be reported as a fully completed repair, even when P1 and P2 succeeded.

## Dry Run and Apply Behavior

The workflow should support two explicit execution modes:

### Dry run

- preflight resolves and validates the scope
- P1 performs parsing/profile detection validation without metadata writes
- P2 and P3 do not claim or write anything
- the job reports candidate counts, unresolved IDs, expected profiles, and representative before-state counts
- no scope row is marked completed

### Apply

- preflight repeats the validation immediately before writes
- P1, P2, and P3 run in order
- all writes are limited to the approved `(run_id, document_id)` scope
- failed rows remain retryable
- completed rows are not reprocessed by a later retry of the same run

A dry-run result must not be converted into an apply run by changing a parameter on a partially processed run. Use a new run ID for apply after operator approval.

## Concurrency and Daily Ingestion

The repair workflow must not concurrently overwrite a document that normal P1 or another repair run is processing.

Required controls:

- one active repair run per document
- job-level concurrency limit for the repair job
- scope claim compare-and-set updates
- a preflight overlap check against active scope rows
- a normal-ingestion guard that does not claim a document with an active repair lock
- a repair lock released only after P3 completion or explicit terminal failure
- kill switch stops new claims but allows the current document/batch to finish

The normal daily pipeline remains unscoped and continues processing new documents. It must not see repair scope rows as new ingestion input.

## Rollback

Before the first successful P1 update for a document, capture a restorable snapshot or equivalent Delta version for:

- the metadata row
- all existing chunks
- embeddings
- index references or the information needed to resynchronize the index

Do not delete old chunks before P2 has produced a complete replacement embedding set. Mark `rollback_status=available` only after the snapshot is verified. If rollback is required, stop new claims, restore the metadata and chunk state, resynchronize P3, validate counts/fingerprints, and then mark the scope row rolled back.

## Generic Repair Semantics

The job must not contain branches such as `if uuid_issue` or `if final_master_issue`.

Issue-specific behavior belongs in the deployed shared FSRv2 processor and is selected by the normal family detector. The scope table records why a document was selected and what profile was expected, while the actual profile selected by P1 is persisted for audit.

Examples of generic scope reasons:

- `preprocessor_section_boundary_fix`
- `final_master_report_profile_fix`
- `metadata_enrichment_correction`
- `chunk_metadata_correction`
- `embedding_model_rebuild`

A single run may contain mixed document families. Expected profile is a validation hint; actual profile and strategy are per-document outputs from the regular pipeline.

## Acceptance Criteria

A repair run is successful only when:

- every requested document has terminal P1, P2, and P3 statuses
- no metadata inserts occurred outside the approved repair scope
- every successful P1 update has a corresponding overwrite DQ warning
- every successful P1 document has `chunk_status=pending` before P2 claims it
- P2 claims only documents in the supplied scope
- stale chunks are deleted only for documents with a complete replacement set
- failed documents retain their prior complete chunk set
- P3 synchronization is confirmed for all successful P2 documents
- UUID samples preserve intended Generator/Turbine and ESN behavior while correcting section paths and granularity
- final-master samples correctly apply Components/Appendix attribution and configured fallback behavior
- actual profile, strategy, version, signals, confidence, and fallback reason are present
- before/after region and chunk counts and fingerprints are explainable
- rollback artifacts are restorable
- retrieval smoke tests pass for representative queries

## Implementation Sequence After Design Approval

1. Replace the current repair workflow design with this shared-pipeline model; do not extend `nb_sdg_fsr_v2_repair.py`.
2. Add the repair scope input mode to the regular P1 notebook/input layer.
3. Add the scoped normal-MERGE policy to the regular metadata write path.
4. Add mandatory fail-closed scope propagation and status correlation to regular P2.
5. Add repair-scope propagation and validation to regular P3.
6. Use `PW_SDG_FSR_V2_Prepare_Repair_Scope` for scope creation/preflight and keep the scope schema migration in `ddls/fsr_v2/nb_sdg_fsr_v2_repair_scope_ddl`.
7. Add focused unit tests for scope selection, scoped inserts/updates, failed-row retention, scope isolation, and retry behavior.
8. Run a 5-20 document dry run, then a small apply run containing both UUID and final-master examples.
9. Repeat the same approved document list under a new QA run ID.

No production implementation should proceed until this design is approved.
