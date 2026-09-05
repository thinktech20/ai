# Airflow Pipeline Design — FSR Scraping & Chunk Ingestion

**Date:** 2026-04-17
**Status:** Draft — updated with walkthrough findings
**Inputs:**
- Databricks team KT (Vinayaka, Akshay — Apr 15)
- Airflow Pipeline Development walkthrough (Sonam, Akshay, Chaithra — Apr 17)
- Tao's recommendation on pipeline ordering
- Vince's metadata materialization plan
- Sample repos: `GP_AF_FDC-main` (Airflow DAGs), `gp_fdc_repo-dev` (DBR bundle)
- Existing `job_config.json` and pipeline code

---

## Overview

This document describes the Airflow DAG design for the two FSR production pipelines:

1. **FSR metadata extraction** (scraping pipeline)
2. **FSR chunk ingestion** (chunking + Delta + Vector Search pipeline)

These two pipelines currently run independently. The target design wires them together so that metadata extraction runs **first**, and chunk ingestion consumes its output to materialize metadata into chunk rows.

---

## DAG Structure

### DAG Name

```
pw_sdg_fsr_ingestion
```

Follows the confirmed naming convention. Sonam clarified the prefix is `PW` (Power, the business unit) `SDG` (the product). Airflow DAG ID will be `pw.sdg.pw_sdg_fsr_ingestion` (dot-separated domain prefix).

### DAG-Level Settings

| Setting | Value | Rationale |
|---|---|---|
| Schedule | `None` (manual trigger initially) | Until pipeline is validated end-to-end in Dev |
| Max concurrent runs | 1 | Prevents conflicting writes to same Delta tables |
| Default timeout | 7200s (2 hours) per task | Matches existing job config |
| Tags | `['PW', 'SDG', 'Databricks']` | Confirmed by Sonam — matches existing DAG tag convention |
| Retry policy | 1 retry per task, 5 min delay | Allows recovery from transient LLM/network failures |
| Failure notification | Team Slack channel or email (TBD) | — |

### Task Graph

```
[fsr_metadata_extraction] ──→ [fsr_chunk_ingestion] ──→ [fsr_vs_sync_validation]
```

Three tasks in sequence. The chunk ingestion task depends on successful metadata extraction. Validation runs after chunk ingestion succeeds.

### Airflow → Databricks Integration Pattern

**CONFIRMED: Pattern A — single multi-task Databricks job, Airflow triggers it.**

This was explicitly demonstrated by Akshay in the Apr 17 walkthrough and confirmed by reviewing the sample repos:

- **DBR workflow** (in Databricks bundle YAML): defines all notebook tasks with `depends_on` sequencing, parameters, and compute. Created first via DBR UI, then exported as YAML.
- **Airflow YAML**: one entry that calls `common.databricks_connection_module` to trigger the DBR job by name via Jobs API `run-now`.
- **Airflow's role is purely scheduling/triggering** — it does not orchestrate individual tasks. All task sequencing, retries, and monitoring happen in Databricks.

Rationale (confirmed by Sonam): calling notebooks directly from Airflow spins up a separate cluster per notebook, increasing duration and cost. Putting everything in a single DBR workflow keeps it on one cluster.

From sample code (`databricks_connection_module.py`):
1. Airflow retrieves PAT from AWS Secrets Manager (keyed by functional SSO)
2. Looks up job ID by name via Databricks Jobs API
3. Calls `POST /api/2.0/jobs/run-now` with the job ID + optional `job_parameters`
4. Polls `GET /api/2.0/jobs/runs/get` every 30s until TERMINATED
5. Raises exception on failure, returns on SUCCESS

---

## Task 1: FSR Metadata Extraction

### Purpose

Extract structured metadata from FSR PDFs using the 3-stage scraping pipeline:
1. PDF field extraction (pdfplumber — first page)
2. LLM normalization (LiteLLM → 15-field canonical schema)
3. IBAT + Event Vision enrichment

### Compute

**Serverless** — confirmed by Shivam. No instance pools or job clusters needed for the AI workspace. Databricks auto-scales compute.

### DBR Workflow YAML (Databricks Asset Bundle)

This goes in the DBR repo under `silver/src/workflows/enabled/`:

```yaml
resources:
  jobs:
    pw_sdg_fsr_ingestion:
      name: pw_sdg_fsr_ingestion
      tasks:
      - task_key: fsr_metadata_extraction
        notebook_task:
          notebook_path: ${var.filename_param}/silver/src/etl/run_scraping_pipeline
          source: WORKSPACE
          base_parameters:
            FSR_OUTPUT_TABLE: "${var.catalog_name}.gp_services_sdg_poc.fsr_scraped_file_mapping_ref"
            FORCE_RESET: "false"
            FSR_BATCH_SIZE: "4"
            FSR_BATCH_THREADS: "4"
      - task_key: fsr_chunk_ingestion
        notebook_task:
          notebook_path: ${var.filename_param}/silver/src/etl/run_pipeline
          source: WORKSPACE
          base_parameters:
            EMBEDDINGS_TABLE: "${var.catalog_name}.gp_services_sdg_poc.field_service_report"
            FSR_REF_VIEW: "${var.catalog_name}.fsr_std_views.fsr_pdf_ref"
            VS_ENDPOINT_NAME: "pw-ser-sdg-vector-search"
            FORCE_RESET: "false"
        depends_on:
        - task_key: fsr_metadata_extraction
      max_concurrent_runs: 1
      run_as:
        user_name: ${var.jb_run_as}
```

### Airflow DAG YAML

This goes in the Airflow repo under `dags/databricks/<domain>/workflows/`:

```yaml
dag_id: pw.sdg.pw_sdg_fsr_ingestion
tags: ['PW', 'SDG', 'Databricks']
fsso: '<functional_sso_id>'          # ETL FSSO — get from Sonam/Shivam
schedule_interval: null               # Manual trigger initially
tz: 'America/New_York'

tasks:
- method_name: databricks_connection
  task_name: tsk_pw_sdg_fsr_ingestion
  job_module: common.databricks_connection_module
  task_id: 1
  job_name: pw_sdg_fsr_ingestion
```

### Notebook Parameters

| Parameter | Dev Value | Prod Value (TBD) | Notes |
|---|---|---|---|
| `FSR_OUTPUT_TABLE` | `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref` | TBD (canonical VAID target) | File-level metadata output |
| `FORCE_RESET` | `false` | `false` | Incremental by default |
| `FSR_BATCH_SIZE` | `4` | `4` | PDFs per LLM batch |
| `FSR_BATCH_THREADS` | `4` | `4–8` | Concurrent batch workers |
| `FSR_LLM_MODEL` | `gemini-3-flash` | TBD | May change in prod |
| `FSR_LLM_CONCURRENCY` | `3` | `3–6` | Adaptive; starts at this value |
| `FSR_LLM_VERIFY_SSL` | `false` | `true` | Must fix gateway SSL for prod |
| `FSR_LOOKUP_SOURCE` | `auto` | `auto` | Reads IBAT/EV from Databricks tables |

### Inputs

| Source | Path / Table |
|---|---|
| FSR PDFs (FieldVision) | `/Volumes/viud/ing_ud_fieldvision/fv_field_service_report` |
| FSR PDFs (manual/box) | `/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports` |
| IBAT equipment master | `vgpd.prm_std_views.ibat_equipment_mst` |
| Event Vision SOT | `vgpd.fsr_std_views.eventmgmt_event_vision_sot` |

### Output

| Target | Path / Table |
|---|---|
| Metadata table | `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref` |

Schema: 15 STRING columns — `esn`, `equipment_sys_id`, `equipment_type`, `equipment_code`, `event_type`, `ev_project_id`, `ev_equipment_event_id`, `ofs_event_id`, `fsp_project_id`, `xxx_project_id`, `fsr_number`, `report_issued_date`, `outage_start_date`, `outage_end_date`, `pdf_name`.

Primary key: `(pdf_name, esn)`.

### External Dependencies

| Dependency | Detail |
|---|---|
| LLM gateway | `https://dev-gateway.apps.gevernova.net` (LiteLLM) |
| Secret scope | Databricks secret scope (named after functional SSO). Ticket to admin team to create scope; contents: `LITELLM_API_KEY` and any other keys. Role-based access via group membership. |
| IBAT table access | Read on `vgpd.prm_std_views.*` |
| Event Vision access | Read on `vgpd.fsr_std_views.*` |

### Runtime Estimate

- ~15–30 min for 100 PDFs (depends on LLM concurrency and network)
- Timeout: 7200s (2 hours)
- Max retries: 1

### Error Behavior

- LLM failures: 4 auto-retries with exponential backoff per batch
- Adaptive concurrency: reduces workers if error rate > 40%
- Lookup failures: falls back to Stage 2 output (enrichment skipped, not fatal)
- Individual PDF failures: logged and skipped, pipeline continues

---

## Task 2: FSR Chunk Ingestion

### Purpose

Chunk FSR PDFs into retrieval-ready rows, write to Delta, and sync to Vector Search:
1. Scan PDF volumes, deduplicate against existing Delta rows
2. Chunk each PDF (PyMuPDF + recursive semantic splitting)
3. Identify ESNs per document (LLM-assisted)
4. Enrich from ref view + scraping metadata output (integration TBD)
5. Write chunk rows to Delta table
6. Trigger incremental Vector Search sync

### Airflow Integration

Task 2 is sequenced via `depends_on: fsr_metadata_extraction` in the DBR workflow YAML (shown above). No separate Airflow entry needed — Airflow triggers the whole multi-task job.

### Notebook Parameters

| Parameter | Dev Value | Prod Value (TBD) | Notes |
|---|---|---|---|
| `EMBEDDINGS_TABLE` | `main.gp_services_sdg_poc.field_service_report` | TBD | Chunk Delta table |
| `FSR_REF_VIEW` | `vgpd.fsr_std_views.fsr_pdf_ref` | same | Enrichment lookup |
| `VS_ENDPOINT_NAME` | `pw-ser-sdg-vector-search` | TBD | Vector Search endpoint |
| `VS_INDEX_NAME` | `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm` | TBD | VS index |
| `FORCE_RESET` | `False` | `False` | Incremental |
| `PDF_PROCESS_WORKERS` | `auto` | `auto` | `min(8, cpu_count - 1)` |

### Inputs

| Source | Path / Table |
|---|---|
| FSR PDFs | Same volumes as Task 1 |
| PDF ref view | `vgpd.fsr_std_views.fsr_pdf_ref` |
| Scraping metadata | `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref` (integration TBD) |
| LLM gateway | Same as Task 1 |

### Outputs

| Target | Detail |
|---|---|
| Chunk Delta table | `main.gp_services_sdg_poc.field_service_report` |
| Vector Search index | `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm` |

Chunk schema: `chunk_id` (STRING), `pdf_name` (STRING), `page_number` (INT), `chunk_text` (STRING), `metadata` (STRING/JSON), plus materialized metadata columns (post-integration).

### External Dependencies

| Dependency | Detail |
|---|---|
| LLM gateway | ESN identification + query-time embeddings |
| Secret scope | Same Databricks secret scope as Task 1 |
| Databricks VS endpoint | `pw-ser-sdg-vector-search` |
| GE Enterprise Root CA | Required for corporate SSL |

### Runtime Estimate

- ~1–2 hours for 100 PDFs (including VS sync wait)
- Timeout: 7200s (2 hours)
- Max retries: 1

### Error Behavior

- Per-PDF failures logged and skipped
- LLM retries: 5 attempts with exponential backoff
- VS sync retries: 6 attempts, 20s between retries
- Writer thread: fatal flag on write failure stops processing

---

## Task 3: VS Sync Validation (Optional / Lightweight)

### Purpose

Confirm that the Vector Search index is queryable after sync. Runs a small set of known-good queries and logs retrieval scores.

### Airflow Integration

If included, this becomes a third task in the DBR workflow YAML with `depends_on: fsr_chunk_ingestion`. No separate Airflow entry — same single-job trigger.

This task is optional. It can be excluded from the initial DAG and added once the pipeline is stable.

### Behavior

- 5 canned queries (e.g., "borescope inspection findings")
- Queries VS index in HYBRID and ANN modes
- Logs top-1 scores and snippet previews
- Fails only if VS endpoint is unreachable

### Runtime Estimate

- ~2 min

---

## Pipeline Sequencing Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Airflow DAG: specs_ai_fsr_ingestion              │
│                                                                      │
│  ┌─────────────────────┐     ┌─────────────────────┐     ┌────────┐ │
│  │  Task 1             │     │  Task 2             │     │ Task 3 │ │
│  │  fsr_metadata_      │────▶│  fsr_chunk_         │────▶│ fsr_vs │ │
│  │  extraction         │     │  ingestion          │     │ _sync_ │ │
│  │                     │     │                     │     │ valid. │ │
│  │  Stages:            │     │  Steps:             │     │        │ │
│  │  1. PDF extraction  │     │  0. Locate PDFs     │     │ Smoke  │ │
│  │  2. LLM normalize   │     │  1. Chunk + ESN ID  │     │ test   │ │
│  │  3. IBAT+EV enrich  │     │  2. Enrich from ref │     │ queries│ │
│  │  4. Write metadata  │     │  3. Write Delta     │     │        │ │
│  │                     │     │  4. VS sync         │     │        │ │
│  └─────────────────────┘     └─────────────────────┘     └────────┘ │
│                                                                      │
│  Shared resources:                                                   │
│  • PDF Volumes: /Volumes/viud/...                                    │
│  • LLM Gateway: dev-gateway.apps.gevernova.net                       │
│  • Secret scope: Databricks secret scope (functional SSO)            │
│  • Compute: Serverless (confirmed by Shivam)                         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Environment Mapping

| Concern | Dev | Prod (TBD) |
|---|---|---|
| Databricks workspace | `gevernova-ai-dev-dbr.cloud.databricks.com` | AI Prod workspace |
| Catalog | `main.gp_services_sdg_poc` | Canonical VAID/VAIQ targets (`vgpd`→`vgpp` per `databricks.yml` variables) |
| LLM gateway | `dev-gateway.apps.gevernova.net` | Prod gateway |
| Secret scope | Databricks secret scope (functional SSO) | Same pattern, prod scope |
| Compute | Serverless (confirmed) | Serverless |
| VS endpoint | `pw-ser-sdg-vector-search` | TBD |
| Airflow instance | Separate MWAA instance for AI jobs (Shivam creating) | Same, prod config |
| Airflow DAG tag | `pw.sdg.pw_sdg_fsr_ingestion` | Same, different env config |
| Schedule | Manual trigger | TBD — daily, weekly, or event-driven |

---

## Schedule Options (For Discussion)

| Option | Trigger | Pros | Cons |
|---|---|---|---|
| **Manual only** | On-demand | Simple, safe for early phase | No automation |
| **Weekly batch** | Cron (e.g., Sunday 2 AM) | Catches new PDFs regularly | May be too infrequent |
| **Daily incremental** | Cron (e.g., daily 1 AM) | Fresh metadata, low lag | LLM cost if volume is low |
| **Event-driven** | Volume file watcher / webhook | Processes new PDFs immediately | Requires event infrastructure |

**Recommendation:** Start with **manual trigger** in Dev. Move to **weekly batch** as the first production schedule. Consider daily or event-driven only if business need requires fresher data.

---

## Integration Gap: Wiring Scraping → Chunking

### Current State

The two pipelines are **disconnected**. The chunk pipeline does not read `fsr_scraped_file_mapping_ref`. It enriches only from `fsr_pdf_ref`.

### Target State (Per Vince's Materialization Plan)

After Task 1 completes:
1. Task 2 reads the metadata table produced by Task 1
2. For each PDF being chunked, Task 2 looks up the file-level metadata row
3. Selected metadata fields are written directly into each chunk row:
   - `title`, `customer_name`, `esn`, `equipment_type`, `event_type`
   - `ev_project_id`, `ev_equipment_event_id`, `fsp_project_id`
   - `outage_start_date`, `outage_end_date`, `fsr_number`
4. This reduces query-time joins and makes chunk rows self-describing

### Work Required

| Item | Owner | Status |
|---|---|---|
| Extend chunk table schema with materialized metadata columns | App team | Not started |
| Add metadata lookup step in chunk pipeline (read scraping output) | App team | Not started |
| Define field precedence rules (scraping vs. ref view vs. chunk-level) | App team + DS | Not started |
| Backfill existing chunk rows if schema changes retroactively | App team | Not started |

This integration is tracked in [03-vince-metadata-materialization-plan.md](../implementation/fsr-processing/design/03-vince-metadata-materialization-plan.md).

---

## Airflow YAML Template (Reference Only)

> The actual YAML formats are now documented above under "DBR Workflow YAML" and "Airflow DAG YAML" sections. The template below is superseded but kept for historical reference.

<details>
<summary>Old template (pre-walkthrough)</summary>

```yaml
# specs_ai_fsr_ingestion.yml
dag_id: specs_ai_fsr_ingestion
schedule: null
tags:
  - sdg
  - fsr-ingestion
max_concurrent_runs: 1

tasks:
  - task_name: fsr_metadata_extraction
    task_key: fsr_metadata_extraction
    notebook_path: /Repos/sdg-ai/notebooks/fsr_scraping/run_scraping_pipeline
    base_parameters:
      FSR_OUTPUT_TABLE: "main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref"
      FORCE_RESET: "false"
      FSR_BATCH_SIZE: "4"
      FSR_BATCH_THREADS: "4"
      FSR_LLM_MODEL: "gemini-3-flash"
      FSR_LLM_CONCURRENCY: "3"
      FSR_LOOKUP_SOURCE: "auto"
    timeout_seconds: 7200
    max_retries: 1

  - task_name: fsr_chunk_ingestion
    task_key: fsr_chunk_ingestion
    notebook_path: /Repos/sdg-ai/notebooks/fsr_pipeline/run_pipeline
    depends_on:
      - fsr_metadata_extraction
    base_parameters:
      EMBEDDINGS_TABLE: "main.gp_services_sdg_poc.field_service_report"
      FSR_REF_VIEW: "vgpd.fsr_std_views.fsr_pdf_ref"
      VS_ENDPOINT_NAME: "pw-ser-sdg-vector-search"
      FORCE_RESET: "false"
    timeout_seconds: 7200
    max_retries: 1

  - task_name: fsr_vs_sync_validation
    task_key: fsr_vs_sync_validation
    notebook_path: /Repos/sdg-ai/notebooks/fsr_pipeline/run_evaluation
    depends_on:
      - fsr_chunk_ingestion
    timeout_seconds: 600
    max_retries: 0
```

</details>

---

## Open Questions

### Design Decisions (Adopted)

These are the architectural decisions we are following. Not open for discussion — they reflect standard best practices.

| # | Decision | Rationale |
|---|---|---|
| D1 | Thin notebook wrappers with shared logic in Python modules | Keeps notebooks testable, diff-friendly, and avoids code duplication across notebooks |
| D2 | Notebook changes and Airflow YAML changes ship in the same PR | Prevents drift between DAG config and the notebook it points to |
| D3 | All notebooks strip output before commit | Avoids bloated diffs, accidental data leaks, and merge conflicts |
| D4 | Structured logging with run ID, task key, and timestamp in every notebook | Required for production debugging and audit trail |
| D5 | `FORCE_RESET=true` is a parameterized variant of the same DAG, not a separate DAG | Reduces DAG sprawl; reset is a runtime flag, not a structural difference |
| D6 | Evaluation notebooks are excluded from the production Airflow DAG | They are development/QA tools, not operational workloads |
| D7 | `run_reenrich.py` is an ad hoc maintenance notebook, not a scheduled job | Re-enrichment is a backfill operation triggered by metadata changes, not a recurring need |
| D8 | Branch model follows `feature_<story>` / `bugfix_<ticket>` → `dev` → `main` with squash-before-review | Matches the Databricks team's established process from KT |
| D9 | Use job clusters for Prod, existing all-purpose cluster for Dev | Job clusters give isolation and cost control in Prod; all-purpose is faster for Dev iteration |
| D10 | Dev uses current POC tables (`main.gp_services_sdg_poc.*`); Prod targets canonical VAID/VAIQ objects | Avoids blocking Dev work on catalog promotion; Prod cutover is a separate migration step |
| D11 | DAG naming: `pw_sdg_<purpose>`, task naming: `fsr_<step>`, notebook naming: `run_<purpose>` | Confirmed by Sonam — prefix is PW (Power business unit) + SDG (product) |
| D12 | Validation task (Task 3) is excluded from the initial DAG, added once pipeline is stable | Reduces initial complexity; smoke test can run manually during validation phase |
| D13 | Serverless compute for all AI workspace jobs | Confirmed by Shivam — no instance pools or job clusters needed |
| D14 | Pattern A confirmed — single multi-task DBR job, Airflow triggers once | Akshay demonstrated: all orchestration in DBR workflow, Airflow calls `run-now` on the job |
| D15 | Git structure follows bronze/silver/gold convention with `src/ddl`, `src/etl`, `src/workflows` | Matches `gp_fdc_repo-dev` sample; silver for SOT (scrape+chunk), gold for consumption (vector) |
| D16 | Development approach: build DBR workflow via UI first, export YAML for deployment | Akshay walked through: create in UI → test → export as YAML → commit to repo |

### Implementation Questions (Need External Input)

Questions answered by the Apr 17 walkthrough are marked CLOSED. Remaining open items still need external input.

**Airflow & YAML**

1. ~~Can the Databricks team share a sample YAML from an existing production DAG so we can validate the exact schema?~~
   **CLOSED (Apr 17):** Sample repos shared — `GP_AF_FDC-main` (Airflow) and `gp_fdc_repo-dev` (DBR bundle). Exact YAML formats documented above.

2. ~~How are notebook widget parameters passed from the Airflow YAML `base_parameters` into the notebook runtime?~~
   **CLOSED (Apr 17):** Two layers: (a) DBR workflow YAML `base_parameters` on each `notebook_task` — these become widget params in the notebook, (b) `databricks.yml` variables with dev/prod targets for env-specific values (e.g., `${var.catalog_name}`). Airflow does NOT pass parameters — it just triggers the job by name.

3. ~~Does Airflow submit the entire DAG as a single multi-task Databricks job (Pattern A), or does it orchestrate each task as a separate notebook run (Pattern B)?~~
   **CLOSED (Apr 17):** Pattern A confirmed. Airflow uses `databricks_connection_module` which calls `POST /api/2.0/jobs/run-now` for the named job. All task orchestration is in Databricks.

4. How are failure alerts routed — Airflow-level config, YAML field, or separate alerting setup?
   **Partially answered:** DBR workflow YAML has `email_notifications.on_success` / `on_failure`. Airflow UI shows DAG run status. Full alerting setup TBD.

**Hosting & Deployment**

5. ~~How does Airflow authenticate to Databricks — service principal, PAT, or OAuth? Is this already configured for the AI workspaces?~~
   **CLOSED (Apr 17):** Functional SSO → AWS Secrets Manager → PAT. The `databricks_connection_module` retrieves `databricks_access_token` from the secret keyed by functional SSO ID. Akshay confirmed this is the standard pattern. Setup for AI workspace needs Sonam/Shivam to provide the FSSO ID.

6. ~~Do production notebook runs execute under a service principal, or a shared user account?~~
   **CLOSED (Apr 17):** Functional SSO user. DBR workflow YAML specifies `run_as.user_name: ${var.jb_run_as}` (e.g., `Service.PMOFUNCTIONALSSO@ge.com`). Two types of FSSOs: ETL FSSO (for write/processing — ours), and consumption FSSO (for read). Chaithra to provide the specific FSSO for our project.

7. How are Python dependencies installed on job clusters? (Init script, cluster-scoped library, `%pip install` in notebook, or a shared `requirements.txt`?)
   **Partially answered:** Serverless compute — need to verify if `%pip install` works on serverless or if dependencies must be pre-packaged. Still open.

8. Is the GE Enterprise Root CA cert pre-installed on AI workspace clusters, or does it need an init script / cluster config?
   **OPEN** — not discussed in walkthrough.

9. ~~Are notebooks deployed to the workspace via Databricks Repos (Git sync), or does CI/CD push artifacts separately?~~
   **CLOSED (Apr 17):** CI/CD uses Databricks Asset Bundles. When CI/CD runs, it deploys to the CICD user folder (`/Users/<cicd-user-uuid>/.bundle/<bundle-name>/files/...`). The notebook paths in the workflow YAML use `${var.filename_param}` which resolves to this path.

10. ~~Where is Airflow hosted, and is there confirmed network connectivity from Airflow to both AI Dev and Prod Databricks workspaces?~~
    **CLOSED (Apr 17):** AWS MWAA (Managed Workflows for Apache Airflow). Shivam is creating a separate MWAA instance for AI jobs. Access via IAM role tied to a DL. Connectivity confirmed — same pattern as existing FDC Airflow→Databricks integration.

**Compute & Access**

11. Are there runtime restrictions or a pre-approved library list for the AI workspaces? (We need `pdfplumber`, `litellm`, `PyMuPDF`, `databricks-vectorsearch`.)
    **OPEN** — not discussed in walkthrough.

12. ~~Is the `fsr-pipeline` secret scope already provisioned in both AI Dev and Prod workspaces?~~
    **CLOSED (Apr 17):** No, not yet. The process is: raise a ticket with admin team → they create the scope (named after functional SSO) → we provide the list of secrets → they add them. Sonam to ask Shivam to set this up. Role/group membership determines access to the scope.

**Data Targets**

13. What are the confirmed production table names for: metadata table, chunk table, and Vector Search index?
    **OPEN** — not discussed in walkthrough. Dev uses `main.gp_services_sdg_poc.*`.

14. ~~Is there an approved migration path from `main.gp_services_sdg_poc.*` to the canonical production objects?~~
    **Partially answered:** `databricks.yml` variables handle dev/prod catalog switching (`vgpd` vs `vgpp`). The migration path is: define table names as parameterized variables, prod values set in targets. Exact prod schema names still TBD.

### Ownership, Milestones & Timeline

15. ~~Which GitHub repo is the official source of truth for these notebooks, and what does `/Repos/<path>` resolve to?~~
    **CLOSED (Apr 17):** Existing `GPFSR` repo (Sonam mentioned it at start). DS team + Aaron to confirm final git structure. Notebook path resolves via `${var.filename_param}` → `/Users/<cicd-user>/.bundle/FDC/files/<layer>/src/etl/<notebook>`.

16. ~~Are we creating a new folder inside the existing AI Databricks repo, or standing up a separate repo?~~
    **CLOSED (Apr 17):** Use existing `GPFSR` repo. DS team needs to provide the folder structure they need, then folders will be created. Will follow bronze/silver/gold convention.

17. Who owns production support: Databricks team, app team, or shared?
    **OPEN** — not discussed in walkthrough.

18. ~~Who owns the Airflow YAML file in the repo?~~
    **CLOSED (Apr 17):** The team creating the DAG owns the YAML. Airflow YAML lives in a separate repo (`GP_AF_FDC` pattern). Changes go through the same PR flow. Code owners = GE leads approve PRs to QA/STG; Pranesh/Abhijit for production approvals. Operations team also approves for production.

19. Are Dev and Prod Databricks workspaces fully ready, or is additional setup still pending?
    **Partially answered:** Dev workspace is accessible. Airflow instance for AI is being created by Shivam. Secret scope not yet provisioned. LLM gateway intermittent issues resolved.

20. What is the target schedule for the first production run?
    **OPEN** — not discussed.

21. When should the scraping → chunking integration (metadata materialization) be wired in?
    **OPEN** — tracked in Vince's materialization plan.

---

## Next Steps (Updated Apr 17)

1. ~~Get Databricks team to share a sample YAML / DAG template~~ — DONE (repos shared)
2. ~~Confirm notebook repo path and Git repo for deployment~~ — DONE (GPFSR repo, bronze/silver/gold structure)
3. Resolve LLM gateway + secret scope access blockers (in progress — Sonam coordinating with Shivam)
4. Run both pipelines manually end-to-end in Dev
5. **NEW: Create DBR workflow via UI** — Step 1 per Sonam's suggestion: add notebooks to DBR workflow, add schedule for UAT
6. **NEW: Parameterize code** — add widget params, use `databricks.yml` variables for env-specific values
7. **NEW: Provide git structure to DS team/Aaron** — they need our folder layout to create the structure
8. Wire the YAML into the Airflow setup once MWAA instance is ready
9. Run DAG-triggered execution in Dev
7. Begin scraping → chunking metadata integration work

---
