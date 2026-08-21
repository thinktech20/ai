# FSR v2 Dev Ingest Agent Design

## Goal

Provide a small agent interface for dev-only targeted FSR v2 ingest that runs end-to-end on Databricks and reports per-document results without manual intervention.

This agent should:

- accept one or more document file names from Databricks volumes
- support only two reset modes: `drop` and `no-drop`
- run on dev only for the first version
- support three dev table/index profiles: `ms_test`, `ds_test`, and `dev`
- continue processing the full batch even if one document fails
- stop after the batch and report partial state clearly
- perform lightweight validation and return step-by-step logs plus a per-doc status table
- persist run-level and failure-level telemetry to FSR v2 Delta audit tables

## Simplified Natural Language Interface

Use one command shape only:

`Ingest and validate these docs <file_names> in dev using <ms_test|ds_test|dev> with <drop|no-drop>`

Examples:

- `Ingest and validate these docs 12345, 67890 in dev using ms_test with drop`
- `Ingest and validate these docs abc_report.pdf, xyz_report in dev using ds_test with no-drop`
- `Ingest and validate these docs sample_1.pdf in dev using dev with no-drop`

Interpretation:

- `file_names`: the same input expected by P1 metadata ingest, which is passed through `FSR_TARGET_PDF_NAMES`
- `using ms_test|ds_test|dev`: choose which dev table/index set to run against
- `drop`: drop and recreate the dev metadata table, chunk table, document-equipment map table, and vector index before ingest
- `no-drop`: keep shared dev tables and index in place, but for each requested doc delete its existing rows and index entries before reprocessing

If `using` is omitted, default to `using ms_test` for first-rollout safety.

## Scope

In scope for v1:

- dev workspace only
- targeted ingest for one or more file names from configured volume paths
- existing FSR v2 tables and index
- existing FSR v2 run-log and DQ-log tables
- profile-based routing between ms_test, ds_test, and standard dev tables/index
- per-doc best-effort processing
- lightweight validation and reporting

Out of scope for v1:

- qa and prod execution
- automatic remediation beyond stop-and-report
- approval workflows for destructive actions
- full validation suite in `2-FSR-v2/validate` or `pw_sdg_ai_ser_repo/validation/fsr_v2`

## Source Of Truth

Use the `fsr_v2` branch in `pw_sdg_ai_ser_repo` as source of truth.

Primary implementation surfaces already present:

- `pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest.py`
- `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py`
- `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_v2_chunks.py`
- `pw_sdg_ai_ser_repo/vs/src/etl/nb_sdg_fsr_v2_index.py`
- `pw_sdg_ai_ser_repo/ddls/fsr_v2/nb_sdg_fsr_v2_ddl.py`

Audit logging surfaces now implemented:

- `pw_sdg_ai_ser_repo/common/fsr_v2/config.py`
- `pw_sdg_ai_ser_repo/ddls/fsr_v2/nb_sdg_fsr_v2_ddl.py`
- `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py`
- `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_v2_chunks.py`
- `pw_sdg_ai_ser_repo/workflows/fsr_v2/pw_sdg_fsr_v2_p1_metadata.yml`
- `pw_sdg_ai_ser_repo/workflows/fsr_v2/pw_sdg_fsr_v2_p2_chunking.yml`
- `pw_sdg_ai_ser_repo/databricks.yaml`

Important current contract confirmed from code:

- targeted documents are passed as `FSR_TARGET_PDF_NAMES`
- target names are normalized by stripping quotes, removing optional `.pdf`, and lowercasing
- input resolution probes the configured dev volumes for both `<name>` and `<name>.pdf`
- v2 audit table params are `RUN_LOG_TABLE_V2` and `DQ_LOG_TABLE_V2`
- P1 writes one run summary row to `RUN_LOG_TABLE_V2` and doc-level failures to `DQ_LOG_TABLE_V2`
- P2 writes one run summary row to `RUN_LOG_TABLE_V2`

## Dev Table Profile Selection

The agent must resolve one of three table/index profiles from NL:

- `ms_test` profile:
  - use personal validation objects (tables/index names with `ms_test_` prefix) in the same dev workspace
  - intended for first-pass verification after major code changes

- `dev` profile:
  - use standard FSR v2 dev objects from bundle variables in `databricks.yaml`
  - examples: `fsr_metadata_table_v2`, `fsr_chunk_table_v2`, `fsr_doc_equipment_map_table_v2`, `fsr_vs_index_v2`, `fsr_run_log_table_v2`, `fsr_dq_log_table_v2`

- `ds_test` profile:
  - use DS-team test objects (tables/index names with `ds_test_` prefix) in the same dev workspace
  - these should be provided to the orchestrator as explicit runtime overrides for:
    - `METADATA_TABLE_V2`
    - `CHUNK_TABLE_V2`
    - `DOC_EQUIPMENT_MAP_TABLE_V2`
    - `VS_INDEX_V2`
    - `RUN_LOG_TABLE_V2`
    - `DQ_LOG_TABLE_V2`

Profile resolution rule:

- if user says `using ms_test`, route to ms_test objects
- if user says `using ds_test`, route to the DS test objects
- if user says `using dev`, route to standard dev objects
- if `using` is omitted, default to `ms_test`

## Why Databricks Execution, Not Local VS Code Execution

The agent should use VS Code only as the control plane.

Actual ingest must run inside Databricks because:

- the source files live in Databricks volumes
- Spark, Unity Catalog, and vector search are native there
- notebook failures and status are easier to capture in one execution context
- local Databricks Connect will add file-access mismatches for volume-backed input

## Proposed Architecture

Use a two-layer model.

### 1. User-facing agent

The VS Code agent parses the natural language request and triggers a Databricks-side orchestrator with structured parameters.

Input parameters:

- `env=dev`
- `file_names=[...]`
- `mode=drop|no-drop`

Internal agent decision (not a notebook parameter):

- resolve profile from NL intent: `ms_test`, `ds_test`, or `dev`
- map resolved profile to concrete table/index values
- pass only concrete Databricks parameters (`METADATA_TABLE_V2`, `CHUNK_TABLE_V2`, `DOC_EQUIPMENT_MAP_TABLE_V2`, `VS_INDEX_V2`, `RUN_LOG_TABLE_V2`, `DQ_LOG_TABLE_V2`)

Output back to the user:

- overall batch result
- per-doc status table
- step-by-step logs
- clear failure summary with stage and error text

### 2. Databricks orchestrator notebook

Implement or evolve a single dev orchestrator notebook that performs:

1. environment preflight
2. optional global reset for `drop`
3. per-doc cleanup for `no-drop`
4. per-doc P1 ingest
5. queue-driven P2 chunking using the existing `pending` behavior
6. batch P3 vector index sync or create+sync
7. lightweight validation
8. structured summary output
9. run-level and failure-level audit writes to v2 Delta log tables

The existing `nb_fsr_v2_dev_ingest.py` is the right starting point. It should be evolved into the agent backend rather than replaced, but it must still remain independently runnable as a Databricks notebook without the VS Code agent wrapper.

Important: do not add a `TABLE_PROFILE` widget/parameter to the notebook. Profile resolution belongs to the agent NLP layer.

## Execution Flow

### Mode: `drop`

1. Drop profile-selected chunk, map, metadata, run-log, and DQ-log tables.
2. Delete the dev vector index.
3. Recreate tables and index definition through the existing DDL notebook.
4. Process requested docs.
5. Trigger vector index sync.
6. Validate and report.
7. Persist run summary and failure diagnostics in v2 audit tables.

### Mode: `no-drop`

1. Keep the selected profile tables and index, including audit tables.
2. For each requested doc:
   delete matching rows from metadata, chunk, and map tables
   ensure stale vectors are removed by running index sync after table cleanup and again after reinsertion, or by relying on Delta Sync after the final batch sync
3. Process requested docs.
4. Trigger vector index sync.
5. Validate and report.
6. Append run summary and failures to audit tables (append-only behavior).

## Per-Document Processing Strategy

Process documents with per-doc P1 targeting, then let P2 use its existing queue-driven behavior.

Reason:

- current P1 already supports targeted input through `FSR_TARGET_PDF_NAMES`
- current P2 already drains eligible docs from metadata status queues based on `chunk_status`
- reusing the current P2 behavior keeps the first version simpler and closer to production behavior
- the orchestrator can still report per-doc results after P2 completes

Recommended v1 behavior:

1. resolve the requested file name in Databricks volumes
2. cleanup existing rows for that doc if running in `no-drop`
3. run P1 with only that doc in `FSR_TARGET_PDF_NAMES`
4. verify P1 result from metadata table
5. after all requested docs have been staged into metadata, run P2 once using its normal `pending` queue behavior
6. run P3 sync once for the batch
7. verify chunk, map, and index outputs per doc
8. mark each doc as `passed` or `failed`

This means doc isolation is strongest in P1 and cleanup, while P2 and P3 stay batch-oriented.

## Error Capture Without Manual Intervention

This was a key concern. The agent can capture Databricks-side failures without asking the user to inspect notebook cells manually.

Recommended pattern:

- run a parent orchestrator notebook on Databricks
- inside the notebook, call child notebooks with `dbutils.notebook.run(...)`
- wrap each child call in `try/except`
- on failure, capture:
  - stage name
  - exception text
  - document name being processed
  - any table state already written
- store per-doc execution results in memory for response formatting
- persist canonical telemetry in v2 Delta audit tables:
  - `RUN_LOG_TABLE_V2` for run-level summary
  - `DQ_LOG_TABLE_V2` for document-level failures and validation findings
- return a final structured JSON summary from the orchestrator notebook

This avoids the weak pattern of relying on a human to inspect a failed Databricks notebook run. The VS Code agent only needs the final structured result payload.

## Lightweight Validation For v1

Do not run the full existing verification notebooks. Run only quick sanity checks.

Per doc, validate:

- metadata row exists for the document
- metadata status is `completed`
- key metadata fields are present: `document_id`, `pdf_name`, `primary_esn` if derivable, `preprocessor_regions`
- chunk rows exist and count is greater than zero
- chunk status is `completed`
- document-equipment map rows exist when ESNs were emitted
- vector index state is healthy after sync
- vector index contains rows for the document if queryable by `document_id`

If a validation step fails, mark the document failed and include which validation failed.

## Reporting Contract

The agent should return two outputs.

### 1. Per-doc status table

Suggested columns:

- `requested_file_name`
- `resolved_document_id`
- `cleanup_status`
- `metadata_status`
- `chunk_status`
- `map_status`
- `index_status`
- `validation_status`
- `final_status`
- `error_stage`
- `error_message`

### 2. Step-by-step logs

Suggested log sections:

- request received
- environment and parameter resolution
- reset or cleanup actions taken
- P1 start and end
- P2 start and end
- P3 sync start and end
- validation checks
- batch summary

Additionally, the run should leave durable audit artifacts in Delta:

- one P1 row and one P2 row in `RUN_LOG_TABLE_V2` per orchestrated run
- one or more doc-level rows in `DQ_LOG_TABLE_V2` when failures or WARN findings occur

## Audit Table Contract (v2)

Use these tables as system-of-record for operational telemetry:

- `RUN_LOG_TABLE_V2`
  - columns: `run_id`, `job_name`, `start_time`, `end_time`, `duration_seconds`, `docs_claimed`, `docs_succeeded`, `docs_failed`, `chunks_written`, `error_summary`, `created_at`
  - write mode: append
  - current writers: P1 metadata notebook and P2 chunking notebook

- `DQ_LOG_TABLE_V2`
  - columns: `dq_id`, `run_id`, `document_id`, `pdf_name`, `check_name`, `severity`, `failure_category`, `detail`, `created_at`
  - write mode: append
  - current writer: P1 metadata notebook for document-level failures

Agent behavior with these tables:

- read the latest run rows for the orchestrated `run_id` to produce summary
- read DQ rows for the same `run_id` to populate per-doc failure details
- do not treat audit-table write failures as hard pipeline failures in v1; report them as non-blocking warnings

When NL intent resolves to `ds_test`, reads and writes must use ds_test audit tables, not the standard dev audit tables.

## Recommended Implementation Path

Phase 1 should reuse and extend what already exists.

1. Start from `pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest.py`.
2. Add strict `drop` and `no-drop` semantics.
3. Add agent-side table-profile routing (`dev` vs `ds_test`) and wire runtime table/index overrides.
4. Add doc-level cleanup in `no-drop` mode.
5. Keep the notebook independently runnable in Databricks with widgets and defaults.
6. Pass `RUN_LOG_TABLE_V2` and `DQ_LOG_TABLE_V2` through DDL, P1, and P2 calls.
7. Add structured per-doc result collection.
8. Add lightweight validation queries.
9. Return machine-readable summary from the notebook.
10. Let the VS Code agent call only this orchestrator entry point.

## Open Implementation Notes

- `drop` mode is destructive and should remain dev-only for now.
- `no-drop` mode still performs destructive cleanup for the targeted docs only.
- P2 does not need to be restricted per doc in v1; current `pending` queue behavior is acceptable.
- P3 should use the existing v2 vector index notebook or an existing sync utility, not a new custom sync path unless current code proves insufficient.
- v2 audit-table schema exists; keep any future validation writer aligned to `DQ_LOG_TABLE_V2_DDL_COLS`.

## Recommendation

Build the first version as a Databricks orchestrator notebook plus a thin VS Code agent wrapper.

That gives:

- correct access to Databricks volumes
- direct access to Spark tables and vector search
- automatic capture of notebook-stage failures
- a clean path to later extend the same interface to qa and prod with stricter safety rules