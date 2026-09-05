# Airflow Setup Tracker

> **Purpose:** Track the parallel workstream for helping the Airflow team validate the Databricks pipeline integration, starting with creating and sharing the Vector Search index setup they need for test workflow development.
> **Primary outcome:** Create the required Vector Search index setup, confirm the dependent objects/settings, and capture what must be handed to the Airflow team.
> **Related docs:** `implementation/design/production-readiness-plan.md`, `implementation/design/fsr-pipeline-design.md`, `implementation/backfill-tracker.md`

---

## Current State (Apr 24, 2026)

| Item | Status |
|------|--------|
| **Workstream** | Airflow setup / Databricks integration support |
| **Primary task** | Create a Vector Search index for Airflow team testing |
| **Goal** | Share the created index details and any required configuration with the Airflow team |
| **Status** | Airflow-shared workflow YAML reviewed; test object names mostly aligned but workflow still needs a few fixes before run approval |
| **Dependency context** | Airflow team is building an automated test workflow and needs the Databricks-side setup in place |

## Operating Notes

- This tracker is separate from the backfill tracker and should be used for Airflow-facing setup work only.
- Use this file as the source of truth across chat sessions for the Airflow setup workstream.
- Before making changes, confirm whether the request is for a new isolated test index, reuse of an existing index, or a reproducible creation flow the Airflow team can call.
- Prefer isolated test objects for Airflow validation. Do not point Airflow testing at shared live production-style objects unless explicitly approved.

## Known Anchors

- Baseline Vector Search endpoint noted in implementation docs: `pw-ser-sdg-vector-search`
- Baseline historical Vector Search index referenced in design notes: `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm`
- Current canonical DEV chunk table used by the pipeline: `vaid.ai_std_con_field_service_report.vec_field_service_report`
- Current canonical DEV Vector Search index used by the pipeline/backfill: `vaid.ai_std_con_field_service_report.vs_vec_field_service_report`
- Requested isolated Airflow test endpoint: `pw-ser-sdg-vector-search_af_test`
- Requested isolated Airflow test index: `vaid.ai_std_con_field_service_report.vs_vec_field_service_report_chunks_af_test`

## Dependencies / Blockers

| Item | Status | Notes |
|------|--------|-------|
| Airflow/MWAA access | Blocked / external coordination noted | Existing implementation note says Chetra/Sonam coordination is needed |
| Databricks-side Vector Search object creation | Pending | This is the immediate task for this tracker |
| Exact Airflow handoff format | In progress | Airflow team shared a draft Databricks workflow YAML for review |
| Airflow workflow YAML readiness | Needs fixes before approval | Missing explicit test VS endpoint, VS index value looks wrong, API key unresolved, and no DDL/setup task |

## Questions To Resolve

1. Which source Delta table should the test index point to?
2. Does the Airflow team need only the final object names, or also the step-by-step creation procedure and validation checks?
3. Should validation include a simple query or sync check after index creation?

Resolved so far:

- The Airflow team needs a brand-new dedicated test Vector Search setup.
- Chosen isolated objects:
	- endpoint: `pw-ser-sdg-vector-search_af_test`
	- index: `vaid.ai_std_con_field_service_report.vs_vec_field_service_report_chunks_af_test`
- Updated decision: do **not** point the Airflow test index at the existing DEV chunk table used by backfill.
- Isolation note: the Airflow test setup should use a separate test Delta table so the endpoint/index creation is both object-isolated and data-isolated from backfill operations.

## Proposed Work Plan

1. Confirm the exact target objects for the Airflow test path.
2. Verify whether an appropriate Vector Search endpoint already exists and should be reused.
3. Create or document creation of the required Vector Search index.
4. Validate the index status and sync behavior.
5. Hand the Airflow team the object names, expected dependencies, and validation instructions.
6. Record final handoff details here.

## Working Notes

- Apr 23, 2026: Created this tracker to separate Airflow setup work from backfill debugging.
- Immediate focus: create the Vector Search index setup needed for the Airflow team’s automated test workflow.
- Apr 23, 2026: Requested Airflow test objects captured:
	- `pw-ser-sdg-vector-search_af_test`
	- `vaid.ai_std_con_field_service_report.vs_vec_field_service_report_chunks_af_test`
	- do not use the existing DEV chunk table as the source table
	- next step: create a separate empty test chunk table for the Airflow test index
- Apr 23, 2026: Confirmed the isolated test source table already exists:
	- initial assumed name was wrong
	- next step: create only the test endpoint and test index against that existing isolated table
- Apr 23, 2026: First endpoint/index creation attempt blocked before creation step:
	- Databricks returned `TABLE_OR_VIEW_NOT_FOUND` for `vaid.ai_std_con_field_service_report.vec_field_service_report_chunks_af_test`
	- Current hypothesis: table name, catalog/schema, or object visibility does not match what the notebook session can resolve
	- Next step: verify the exact visible object name from Databricks before retrying endpoint/index creation
- Apr 23, 2026: Confirmed this is not just SQL string formatting:
	- `spark.table("vaid.ai_std_con_field_service_report.vec_field_service_report_chunks_af_test").count()` fails with the same `TABLE_OR_VIEW_NOT_FOUND`
	- conclusion: the object name is not visible exactly as written from the current Databricks session
- Apr 23, 2026: Resolved the table-name mismatch via `SHOW TABLES IN vaid.ai_std_con_field_service_report`
	- actual visible test source table: `vaid.ai_std_con_field_service_report.vec_field_service_report_af_test`
	- `vec_field_service_report_chunks_af_test` does not exist in the schema
	- next step: create the Airflow test endpoint/index against `vec_field_service_report_af_test`
- Apr 24, 2026: Reviewed Airflow team shared workflow YAML: `implementation/pw_sdg_fsr_dbr_workflow_test_chk.yml`
	- good: required job params are present for `FSR_METADATA_TABLE` and `FSR_CHUNK_TABLE`
	- good: task order is `metadata_extraction -> chunk_ingestion -> validate`
	- issue: workflow does not include the DDL/setup notebook task, so first run can fail if the `_af_test` tables are not already created
	- issue: `FSR_VS_ENDPOINT` is not passed, so Databricks code will fall back to the default shared endpoint instead of the isolated Airflow test endpoint
	- issue: `FSR_VS_INDEX` value in the shared YAML looks like a placeholder and does not match the agreed target index name
	- issue: `LITELLM_API_KEY` is still `TBD`; acceptable only if Databricks secret scope already provides the real key at runtime
	- issue: `FSR_MAX_PDFS` is blank in the shared YAML, so the run is not capped to a small test batch
	- recommended fixes to send back:
		- add DDL/setup task first, unless `_af_test` tables are already guaranteed to exist
		- set `FSR_VS_ENDPOINT = pw-ser-sdg-vector-search_af_test`
		- set `FSR_VS_INDEX = vaid.ai_std_con_field_service_report.vs_vec_field_service_report_chunks_af_test`
		- resolve `LITELLM_API_KEY` via secret scope or runtime secret injection instead of leaving `TBD`
		- set `FSR_MAX_PDFS = 2` if the test is intended to stay small

## Airflow YAML Review

Reviewed file: `implementation/pw_sdg_fsr_dbr_workflow_test_chk.yml`

Current assessment: not yet approved as-is.

Passes:

- supplies the two fail-fast required pipeline params:
	- `FSR_METADATA_TABLE = vaid.ai_sot_field_service_report.biz_metadata_field_service_report_af_test`
	- `FSR_CHUNK_TABLE = vaid.ai_std_con_field_service_report.vec_field_service_report_af_test`
- includes test run log and DQ log tables
- includes a VS index parameter slot
- uses the expected three notebook flow: metadata, chunks, validate

Open issues:

- missing `FSR_VS_ENDPOINT`; current pipeline code would use default `pw-ser-sdg-vector-search`
- `FSR_VS_INDEX` currently shared as `vaid.ai_std_con_field_service_report.FSR_VS_INDEX_airflow_test`, which should be replaced with `vaid.ai_std_con_field_service_report.vs_vec_field_service_report_chunks_af_test`
- `LITELLM_API_KEY` is unresolved in the YAML (`TBD`)
- `FSR_MAX_PDFS` is blank, so the test run is effectively uncapped from the Process 1 side
- no DDL/setup task included ahead of metadata extraction

Approval condition for the shared YAML:

- okay to proceed only after the above items are confirmed or corrected

## Handoff Template

Use this section once the setup is ready.

| Item | Value |
|------|-------|
| Vector Search endpoint | `pw-ser-sdg-vector-search_af_test` |
| Vector Search index | `vaid.ai_std_con_field_service_report.vs_vec_field_service_report_chunks_af_test` |
| Source Delta table | `vaid.ai_std_con_field_service_report.vec_field_service_report_af_test` |
| Environment | DEV |
| Validation status | TBD |
| Notes for Airflow team | Shared workflow YAML reviewed Apr 24; do not approve unchanged until VS endpoint, VS index, key resolution, and DDL/setup expectations are clarified |

## Resume Instructions

> Give this to a new chat session:
>
> "I'm working on Airflow enablement for the FSR Databricks pipeline. Read `implementation/airflow-setup-tracker.md` first. The immediate goal is to create and share the Vector Search index setup the Airflow team needs for test workflow development. Then continue from the tracker."