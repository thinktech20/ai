# Operationalization Plan

Updated: 2026-09-22
Issue: Section path / UUID chunking

## Goal

Provide a controlled way to reprocess a large document scope without passing thousands of document IDs as job parameters, while preserving auditability and preventing accidental whole-table overwrites. The same workflow supports both the UUID section-path fix and the `final_master_report` profile fix.

This is a repair/reprocessing workflow for documents already present in
`fsr_metadata_v2`. It does not discover, parse, or ingest new source documents.
New documents must complete the normal ingestion path first; they can then be
included in a later repair scope if needed.

The operational flow is:

1. Load the target document IDs into a Delta scope table.
2. Start a run using only a short `run_id` parameter.
3. Process the scope in bounded P1 batches.
4. Overwrite each target document's metadata and reset its `chunk_status` to `pending`.
5. Let the existing P2 queue claim only those documents in batches, re-chunk, re-embed, and replace stale chunks.
6. Update scope status and write one audit record per document.

## Why a scope table is needed

Passing thousands of IDs through `FSR_TARGET_PDF_NAMES` is limited by job parameter and widget size. A Delta scope table removes that limit and gives operations a durable record of what was requested, what completed, what failed, and which run made the change.

## Compatibility with daily ingestion and backfill

The repair workflow is deliberately separate from normal daily ingestion and backfill:

- normal P1 continues to discover new documents and retry only `pending`/`failed` rows
- normal P2 continues to drain the regular `chunk_status` queue because repair scope parameters are empty
- existing backfill workflows are unchanged and do not read the repair scope table
- only the manual repair workflow sets `FSR_V2_REPAIR_SCOPE_TABLE` and `FSR_V2_REPAIR_RUN_ID`
- P2 applies the scope filter only when both repair parameters are non-empty
- scope-table status changes are keyed by `(run_id, document_id)`, so concurrent or later daily runs do not claim repair rows accidentally

The repair workflow must not be used as a replacement for daily ingestion or the existing date-filtered backfill process.

## Proposed scope table

Suggested table: `fsr_v2_repair_scope`

| Column | Purpose |
| --- | --- |
| `run_id` | Groups one operational reprocessing request |
| `document_id` | Normalized document identifier |
| `reason` | Why the document is being reprocessed, such as `preprocessor_boundary_fix` |
| `expected_preprocessor_profile` | Profile expected to produce the replacement output, such as `uuid_section_path` or `final_master_report` |
| `actual_preprocessor_profile` | Profile actually selected for this document |
| `actual_preprocessor_strategy` | ToC/attribution strategy actually used for this document |
| `preprocessor_version` | Deployed preprocessor/profile version used for this document |
| `detection_method` | How the profile was selected, such as `behavioral` or `known_document_inventory` |
| `detection_signals` | Persisted routing signals and confidence evidence for this document |
| `detection_confidence` | Numeric or categorical confidence from profile routing |
| `page_fallback_enabled` | Whether final-master-report page fallback is enabled for this run |
| `page_fallback_version` | Version and threshold configuration used by page fallback, initially `generator_evidence_count > 7` |
| `requested_by` | Operator or service identity |
| `requested_at` | Scope creation timestamp |
| `p1_status` | P1 state: `pending`, `in_progress`, `completed`, `failed`, or `skipped` |
| `p2_status` | P2 state: `pending`, `in_progress`, `completed`, `failed`, or `skipped` |
| `attempt_count` | Number of processing attempts |
| `error_message` | Last failure detail |
| `started_at` | Claim timestamp |
| `completed_at` | Successful completion timestamp |
| `p1_run_id` | P1 run that overwrote metadata |
| `p2_run_id` | P2 run that replaced chunks |
| `before_fingerprint` | Required hash of prior region/chunk state |
| `after_fingerprint` | Required hash of resulting region/chunk state |
| `before_region_count` | Number of regions before replacement |
| `after_region_count` | Number of regions after replacement |
| `before_chunk_count` | Number of chunks before replacement |
| `after_chunk_count` | Number of chunks after replacement |
| `rollback_status` | `not_needed`, `available`, `requested`, `completed`, or `failed` |
| `rollback_artifact_uri` | Location of the captured pre-repair metadata/chunk/embedding snapshot |
| `rollback_snapshot_version` | Immutable snapshot or Delta version used for restoration |

Manifest uniqueness: `(run_id, requested_document_id)`; resolved documents must
also be unique by `(run_id, document_id)`. `document_id` may be null for a
candidate recorded as `missing_target`.

The P1 and P2 statuses must remain separate because metadata replacement and
chunk replacement are asynchronous operations. A document is operationally
complete only when both statuses are `completed`.

Scope rows must be created through the production job
`PW_SDG_FSR_V2_Prepare_Repair_Scope`, not by manually running an `INSERT`.
The job receives the candidate table and repair configuration as parameters:

```text
REPAIR_SCOPE_TABLE=<catalog.schema.fsr_v2_repair_scope>
REPAIR_CANDIDATE_TABLE=<catalog.schema.approved_repair_candidates>
REPAIR_RUN_ID=<new-unique-run-id>
REPAIR_REASON=<repair-reason>
EXPECTED_PREPROCESSOR_PROFILE=<optional-profile>
PAGE_FALLBACK_ENABLED=<true|false when required>
PAGE_FALLBACK_VERSION=<version when final_master_report is expected>
REQUESTED_BY=<optional-operator-or-service-identity>
REPAIR_DRY_RUN=true|false
METADATA_TABLE_V2=<catalog.schema.fsr_metadata_v2>
```

For example, an approved run may pass
`REPAIR_REASON=preprocessor_section_boundary_fix` and
`EXPECTED_PREPROCESSOR_PROFILE=uuid_section_path`; a final-master-report run
passes its own reason, profile, and page-fallback configuration. The candidate
table is an input to the job and must be produced by a governed upstream job
or query. It is not a manually pasted list of IDs.

The preparation job normalizes candidates, resolves them against
`fsr_metadata_v2`, records source-resolved missing targets as `missing_target`,
records candidates without a source as `missing_source`, and inserts the
resulting manifest rows. It assigns `requested_at`, initial statuses, and other
audit defaults at runtime. It defaults to dry-run and only writes scope rows
when `REPAIR_DRY_RUN=false`.

The candidate source can be an issue-specific document list, validation query,
or known family inventory. It is not the source of truth for the stored key.
For already-ingested documents, resolve every candidate against
`fsr_metadata_v2` and store the canonical `m.document_id` in the scope table.
Do not copy the full metadata row into the scope table. Candidates that do not
resolve to an existing metadata row but include a source path are recorded as
`missing_target` and may enter the regular P1 flow for insertion. Candidates
without a source path are recorded as `missing_source` with P1/P2/P3 skipped;
normal ingestion or backfill may create them later.

Review resolved, unresolved, and duplicate counts for the `run_id` before
triggering the repair job. The scope table is the repair manifest; the metadata
table remains the source of truth for the current document state.

Before loading a scope, check for documents already present in another active
repair run. Overlapping scopes must either be combined into one run after both
fixes are deployed or be processed sequentially with an explicit dependency;
two concurrent overwrites of the same document are not allowed.

## Required implementation changes

> Implementation note: the execution design in
> [repair-workflow-design.md](repair-workflow-design.md) supersedes the older
> separate-repair-P1 wording below. Production uses
> `PW_SDG_FSR_V2_Prepare_Repair_Scope` followed by the regular FSRv2 P1, P2,
> and P3 notebooks in repair mode. The old `nb_sdg_fsr_v2_repair.py` path is
> not part of the implemented workflow.

### 1. Scope creation utility

Create a small SQL/notebook utility that accepts a source file or query and writes normalized document IDs to the scope table. It must:

- normalize casing and remove a `.pdf` suffix
- resolve candidate IDs to the canonical `document_id` in `fsr_metadata_v2`
- report unresolved candidates instead of silently inserting them
- reject empty or duplicate IDs
- require a non-empty `run_id` and reason
- require an expected profile; require page-fallback configuration when the
	expected profile is `final_master_report`
- show the requested count before execution
- support dry-run validation
- never delete prior scope runs

### 2. Separate repair P1 scope-table mode

Use a separate repair notebook and workflow rather than adding overwrite behavior
to the normal P1 ingestion notebook. The initial implementation is:

- `ddls/fsr_v2/nb_sdg_fsr_v2_repair_scope_ddl.py`
- `validation/fsr_v2/nb_sdg_fsr_v2_repair.py`
- `workflows/fsr_v2/repairs/pw_sdg_fsr_v2_document_repair.yml`

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
- select the deployed profile using the configured family detector and persist
	the selected profile, version, detection method, signals, and confidence
- persist the actual profile and ToC/attribution strategy per document; the
	actual profile may differ from the expected profile and may vary within one
	`run_id`
- persist final-master-report page-fallback version, enabled state, threshold,
	and per-span fallback reason when that profile is selected
- update `fsr_metadata_v2` as it does today
- reset `chunk_status='pending'` for successful P1 overwrites
- record `p1_run_id`, status, timestamps, and errors back to the scope table

The normal P1 ingestion notebook remains unchanged. Scope-table repair mode is the only path for this controlled overwrite operation.

### 3. P2 scope correlation

P2 continues to use `fsr_metadata_v2.chunk_status` as its work queue, with a
mandatory scope filter whenever repair mode is enabled. No second chunking
implementation is needed.

For operational visibility, require the run/scope filter in repair mode and add
a post-claim join so the P2 run can report:

- how many scope documents entered P2
- how many completed
- how many failed or exhausted retries
- the P2 run ID associated with each completed scope row

Repair-mode P2 must not claim unrelated documents that happen to have
`chunk_status = 'pending'`. It may claim only documents in the requested
`(run_id, document_id)` scope, and it must update the matching scope row only
after the complete chunk and embedding set succeeds.

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

The audit detail should include the overwrite run ID, P1/P2 run IDs when available, reason, preprocessor profile/version, detection method/signals, and before/after fingerprints. Fingerprints and region/chunk counts are required for these repairs rather than optional.

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
- Record the deployed code commit and profile version in every scope row. Both
	fixes must be deployed before a combined scope is processed.
- Do not delete old chunks until the replacement document has a complete embedding set.
- Capture a restorable snapshot or equivalent rollback artifact for metadata,
	chunks, embeddings, and index references before replacement.

## Rollout sequence

### Phase 0: Design and dry run

1. Create the scope table in the target environment.
2. Load a small test scope, such as 5-20 documents.
3. Validate ID normalization and source-volume resolution.
4. Run in dry-run mode and review counts.

### Phase 1: Smoke overwrite

1. Select a few already-completed documents, including the uploaded UUID sample, one Generator/sub-report case, and one `final_master_report` case.
2. Run P1 scope mode.
3. Confirm metadata rows changed and `chunk_status` became `pending`.
4. Run P2 for the resulting queue.
5. Confirm new chunks exist, stale chunks are removed, and audit rows are present.
6. Compare before/after region counts, section paths, and chunk counts.
7. Confirm profile/version provenance and verify rollback artifacts are restorable.

### Phase 2: Targeted regression scope

1. Add all cited regression documents.
	Include the final-master-report validation corpus: Components as section 2
	and 3, unlabeled Components and Appendix content, equipment-leading labels,
	`UNCATEGORIZED`, Generator-in-ToC, repeated Generator body evidence, and
	Gas/Steam-Turbine fallback cases.
2. Process in bounded batches.
3. Review failures and unexpected chunk-count changes.
4. Validate retrieval for representative queries.
5. Pause if metadata drift appears outside intended section-boundary changes.
6. Do not process overlapping active scopes concurrently; combine overlapping
	documents into one run when both fixes are included.

### Post-merge dev verification corpus

After the repair code is merged and deployed to the dev bundle, use a new
candidate table and new `run_id` for this exact ten-document verification
scope. Do not reuse the smoke-test run ID.

### Dev deployment verified 2026-09-24

ICD created both expected jobs in the dev workspace using
`dev-dbr-profile`:

- `PW_SDG_FSR_V2_Prepare_Repair_Scope` — job ID `661313870227575`
- `PW_SDG_FSR_V2_Document_Repair` — job ID `58807500594750`

The scope-preparation job contains the expected DDL bootstrap followed by
scope population task. The document-repair job contains the regular FSRv2
metadata, chunking, and vector-index notebooks in dependency order, with the
canonical `FSR_V2_REPAIR_*` parameters. The completed Xujin run is recorded
below.

```text
42944a96-6210-4f8a-ba54-fa1d5cd2a29b_605015096-47162-152296-Final_Master_Report
768c7c3f-b8f2-4603-8f4a-f5c5a4e0976f_605001793-17435-297129-Final_Master_Report
00f23784-d121-4595-b61d-49d223253a05_605011513-188120-198090-Final_Master_Report
153595df-646d-410b-8ee5-371fa057c1f4_212369717-36105-SY0048243-Final_Master_Report
d72f404c-7d35-49e9-a341-40266e687652_605010863-54129-875064-Final_Master_Report
93c2180b-f866-4521-b090-b88442c6dcf1_204006084-2510-297422-Final_Master_Report
9ecb1354-1f3a-4634-8a74-12943aff45a9_605003354-23849-298081-Final_Master_Report.pdf
8ff5a231-c213-4441-b4ed-e39ed1988c8d_605030072-50465-298364-Final_Master_Report.pdf
af693a98-1e5c-499d-aa10-cccc54885c64
796f4d53-a8ad-42e1-af4d-53a8add2e1a4
017bd409-e1e7-4080-bbd4-09e1e7e08008
```

Run sequence after deployment:

1. Confirm the two repair jobs are present in dev and the merged notebooks are deployed.
2. Run `PW_SDG_FSR_V2_Prepare_Repair_Scope` with `REPAIR_DRY_RUN=true` and review resolved, missing, duplicate, and source-path counts.
3. Run the same preparation job with a new `run_id` and `REPAIR_DRY_RUN=false`.
4. Run `PW_SDG_FSR_V2_Document_Repair` with the new `run_id`, first in dry-run mode and then apply mode.
5. Verify P1/P2/P3 scope statuses, metadata profile/strategy, before/after fingerprints, rollback artifacts, stale-chunk replacement, and DQ warnings.
6. For final-master-report documents, verify Components/Appendix attribution, page-fallback settings/reasons, and representative retrieval results.
7. Do not run P3 against the real dev index unless the scope uses the approved dev chunk source and the index-sync impact has been reviewed.

### Xujin Dev end-to-end run completed 2026-09-24

The ten-document Xujin corpus was executed through the deployed Dev jobs with
run ID `xujin-dev-apply-20260924`:

- preparation dry run: `132732281081245` - succeeded
- preparation apply: `654189125001659` - succeeded
- document repair dry run: `747069254649341` - succeeded
- document repair apply: `691758332012210` - succeeded

Final scope result:

- 10/10 documents: `p1_status=completed`, `p2_status=completed`, `p3_status=completed`
- 10/10 documents: `rollback_status=available`
- all three repair tasks succeeded: metadata, chunking, and vector-index sync
- actual profiles: 8 `final_master_report`, 2 `shared`
- actual strategies: 8 `components_labels_and_appendix_fallback`, 2 `shared_section_preprocessor`
- replacement chunks written: 361
- overwrite audit rows: 10 with `check_name=p1_target_overwrite`
- rollback snapshots: 1 metadata snapshot and 4 chunk snapshot groups recorded for the run

The run used the real Dev repair scope table and real Dev FSRv2 metadata/chunk
tables. The source-resolved missing metadata targets were inserted through the
regular P1 MERGE, then chunked and synchronized through the regular P2/P3 path.

### Phase 3: Controlled broader rollout

1. Load the approved document population into a new scope run.
2. Process with conservative concurrency and retry caps.
3. Monitor P1/P2 success rates, audit counts, chunk deltas, and embedding failures.
4. Keep the old output available for before/after comparison until QA sign-off.
5. Promote only after the scope run has no unexplained failures.

### Phase 4: Rollback if required

1. Stop new P1/P2 claims for the affected `run_id` using the repair kill switch.
2. Identify affected documents from scope rows and confirm their
	`before_fingerprint` values.
3. Restore metadata, chunks, embeddings, and index references from the captured
	pre-repair snapshot or rollback artifact.
4. Mark the scope rows with `rollback_status=completed` only after restoration
	and consistency checks succeed.
5. Record the rollback reason, operator, code/profile version, and validation
	results in the audit log.

## Dev-to-QA validation cycle

Use the same approved document list and a new environment-specific scope table/run ID in each environment. The scope `reason` identifies the repair type, for example `preprocessor_section_boundary_fix`, `esn_metadata_repair`, or `chunk_metadata_repair`:

1. **Dev dry run:** create the dev scope rows with `p1_status=pending`, `p2_status=pending`; run the repair job with `REPAIR_DRY_RUN=true` and verify candidate counts.
2. **Dev apply:** run the same scope with `REPAIR_DRY_RUN=false`; confirm P1 scope rows complete, metadata `chunk_status` becomes pending, and P2 completes only those rows.
3. **Dev checks:** compare region counts, section paths, chunk counts, primary ESN/equipment metadata, stale-chunk cleanup, and retrieval samples.
4. **QA dry run:** copy only the approved scope IDs into the QA scope table under a new run ID; review counts before writes.
5. **QA apply and checks:** repeat the apply and validation sequence; stop if QA shows unexplained metadata or retrieval drift.
6. **Promotion decision:** retain the scope and audit rows from both environments; do not reuse a completed `run_id`.

### Dev smoke test completed 2026-09-24

The first three-document smoke test was executed in the dev sandbox using the
`dev-dbr-profile` and user-owned `ms_test_*` metadata, chunk, equipment-map, and
DQ tables. The deployed repair jobs were not used because the current
`fsr_v2` branch is not deployed to the dev bundle; bundle deployment is
currently blocked by existing Databricks job permissions. The sandbox ran the
same notebooks referenced by the two new jobs.

Test documents:

- `5b688732-39f2-48d2-a887-3239f258d28b`
- `fcb1511e-596a-4a56-b151-1e596afa569c`
- `35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270T483-Final_Master_Report.pdf`

Test scope and candidate objects:

- candidate table: `vaid.ai_sot_field_service_report.ms_test_fsr_repair_candidates_20260924`
- scope table: `vaid.ai_sot_field_service_report.ms_test_fsr_v2_repair_scope_20260924`
- rollback table: `vaid.ai_sot_field_service_report.ms_test_fsr_v2_repair_rollback_20260924`
- apply run ID: `repair-smoke-apply-20260924`

Results:

- scope preparation dry run succeeded: run `366815487130806`
- scope preparation apply succeeded: run `120446913866720`
- regular P1 repair succeeded after correcting the P1 claim-ID correlation: run `431102360897622`
- all three P1 scope rows completed
- three metadata snapshots and `279` chunk snapshot rows were captured
- three `p1_target_overwrite` DQ warnings were written
- regular P2 repair succeeded: run `755630577236348`
- all three P2 scope rows completed and metadata `chunk_status` returned to `completed`
- replacement chunk counts were `162`, `110`, and `6`
- P3 repair dry-run guard succeeded: run `234127829810543`

Actual P3 synchronization remains pending until a user-owned dev Vector Search
index is provisioned for the `ms_test_fsr_chunks_v2` source. The real dev index
must not be used for this smoke test because it is not isolated from the test
chunk table.

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
- profile/version and routing signals are present for every completed document
- actual profile and ToC/attribution strategy are present for every completed
	document, including mixed strategies within one `run_id`
- page-fallback configuration and reason are present for every completed
	final-master-report document
- rollback artifacts exist and are restorable for every completed document

## Open implementation decision

The scope-table repair implementation is now staged for validation. Before any broad run, validate the workflow in dev with a 5-20 document scope containing both fix types, then repeat the same run pattern in QA. Do not work around parameter-size limits by splitting an untracked ID list across many manually launched jobs.
