# FSR Pipeline — Production Readiness Plan

> **Date:** 2026-04-21  
> **Status:** Step 6 complete; Step 7 next

---

## Current State

- Interactive notebooks (tested with 10 PDFs) in `notebooks/` folder
- `code/` folder is empty, ready for production code
- Schema v2 agreed with Pranesh (pdf_name as PK, 3-state statuses)
- Process 1 notebook still uses old schema (document_id, old statuses) — needs update
- Process 2 notebook updated to schema v2
- Validation notebook references old schema

---

## Reference Pattern (from `gp_fdc_repo-dev`)

The Databricks team uses:
```
silver/src/
  ddl/          ← DDL notebooks (CREATE TABLE)
  etl/          ← ETL notebooks (one per job task)
  workflows/
    enabled/    ← workflow YAML files
common/
  enablers/
    functions/  ← shared utility notebooks (%run imports)
databricks.yml  ← bundle config with variables + targets (dev/prod)
```

**Key patterns we adopt:**
- Shared config via `%run` (we already do this with `fsr_config.py`)
- Separate DDL notebook for table creation
- Workflow YAML with `${var.*}` parameterization
- `databricks.yml` with dev/prod targets
- Serverless compute (our case; they use instance pools)

**Patterns we skip:**
- Instance pools / cluster policies (we use Serverless)
- Huge env config files with 200+ schema mappings

---

## Production Code Structure

Named `sdg-pipelines` (not `fsr-processing`) because this layout will expand to
include ER, risk matrix, and other SDG document types — FSR is just the first.

```
implementation/sdg-pipelines/
  common/                              ← shared config + DDL (all doc types)
    fsr_config.py                      ← FSR shared config (schema v2)
    nb_sdg_fsr_ddl.py                  ← DDL: CREATE metadata + chunk tables
  silver/                              ← Process 1: metadata extraction & registration
    nb_sdg_fsr_metadata.py             ← P1: extract, LLM normalize, IBAT/EV enrich
  gold/                                ← Process 2: chunking, embeddings, VS sync
    nb_sdg_fsr_chunks.py               ← P2: chunk, embed, write to Delta + VS
  validation/
    nb_sdg_fsr_validate.py             ← Post-run validation checks
  workflows/
    pw_sdg_fsr_ingestion.yml           ← DBR workflow (DDL → P1 → P2 → validate)
    databricks.yml                     ← Bundle config with dev/prod targets
  design/                              ← Design docs (this folder)
  notebooks/                           ← Archive of interactive dev notebooks
```

When future doc types come (ER, risk matrix), they add:
- `common/er_config.py`, `silver/nb_sdg_er_metadata.py`, `gold/nb_sdg_er_chunks.py`, etc.

Naming follows team convention: `nb_sdg_fsr_*` (subdomain=sdg, domain=fsr).

Bronze data (source PDF volumes in VIUD) is read-only — no bronze notebooks needed.

---

## Step-by-Step Plan

### Step 1: Directory structure + shared files

Create the `sdg-pipelines/` skeleton and populate `common/`:

- **1a** — Create directory skeleton: `common/`, `silver/`, `gold/`, `validation/`, `workflows/`, `design/`, `notebooks/`
- **1b** — Copy `fsr_config.py` into `common/` (already schema v2, no changes)
- **1c** — Create `nb_sdg_fsr_ddl.py` in `common/` (CREATE TABLE IF NOT EXISTS for both tables)
- **1d** — Copy interactive notebooks into `notebooks/` as archive
- **1e** — Copy design docs into `design/`

**Status: ✅ DONE** (all 1a–1e completed)

### Step 2: Convert P1 notebook → `silver/nb_sdg_fsr_metadata.py`

Convert `fsr_metadata_extraction.ipynb` into a production `.py` notebook.
This is the biggest change — the interactive notebook is still on the OLD schema.

Key changes from the interactive notebook:
- `%run ../common/fsr_config` (relative path to common/)
- Remove test overrides (hardcoded API key, `_test` table suffix, `P1_MAX_PDFS = 10`)
- Update to schema v2: `pdf_name` is PK (remove `document_id`), remove `source_volume`
- Status values: `completed`/`failed` (not `ok`/`skipped`)
- Add `scraped_at` timestamp on success
- MERGE keys on `pdf_name` instead of `document_id`
- Structured logging instead of print statements
- No `%pip install` (deps handled by cluster/workflow)

Break this into sub-tasks to keep each change small:

- **2a** — Create skeleton: imports, config run, logging setup, banner ✅
- **2b** — Watermark scan + volume listing logic ✅
- **2c** — MERGE stub rows (schema v2: pdf_name PK, no document_id/source_volume) ✅
- **2d** — PDF extraction (pdfplumber, page-1 fields) ✅
- **2e** — LLM normalization (batched, with retries) ✅
- **2f** — IBAT + Event Vision enrichment ✅
- **2g** — Final MERGE results + failure handling ✅

**Status: ✅ DONE** (all 2a–2g completed)

### Step 3: Convert P2 notebook → `gold/nb_sdg_fsr_chunks.py`

Convert `fsr_chunk_ingestion.ipynb`. Already mostly on schema v2.

- **3a** — Create skeleton: imports, config, logging ✅
- **3b** — Query pending docs + PyMuPDF text extraction ✅
- **3c** — Recursive chunking with page tracking ✅
- **3d** — Embedding generation (batched LiteLLM calls) ✅
- **3e** — MERGE chunks to Delta + update metadata chunk_status ✅
- **3f** — Vector Search index sync ✅

**Status: ✅ DONE** (all 3a–3f completed)

### Step 4: Convert validation → `validation/nb_sdg_fsr_validate.py`

Convert `fsr_validation.ipynb`:

- **4a** — Process 1 checks (update to schema v2: pdf_name PK, completed/failed statuses) ✅
- **4b** — Process 2 checks (chunk table, embeddings) ✅
- **4c** — Cross-process consistency checks + summary ✅

**Status: ✅ DONE** (all 4a–4c completed)

### Step 5: Create DBR workflow YAML

**Status: ✅ DONE** — `workflows/databricks.yml` + `workflows/pw_sdg_fsr_ingestion.yml` created.

Multi-task workflow with dependency chain:

```
DDL (create tables) → Process 1 (metadata) → Process 2 (chunks + VS sync) → Validate
```

- DDL runs first (idempotent, fast)
- P1 depends on DDL
- P2 depends on P1
- Validate depends on P2
- All tasks share serverless compute
- Runtime params passed via `base_parameters` (table names, volumes, LLM config)

Create `databricks.yml` with:
- `dev` target: AI Dev workspace, POC schema, test volumes
- `prod` target: Production workspace, vaid schema, production volumes

### Step 5b: Export workflow YAML from Databricks UI

If bundle deploy is blocked (network policy), use the UI as fallback:
1. Create the workflow manually in Databricks UI (Jobs → Create Job)
2. Add the 4 tasks with dependencies (DDL → P1 → P2 → Validate)
3. Export the generated JSON/YAML via Jobs API: `GET /api/2.1/jobs/get?job_id=<id>`
4. Save the exported definition into `workflows/` for version control
5. This gives us the canonical YAML that Airflow can trigger via `run-now`

Databricks UI also lets you generate workflow YAML directly from the job definition page — use "View JSON" or the API export to capture the exact config.

### Step 6: Test run — 10 files, measure timing

**Status: ✅ COMPLETE**

Completed in AI Dev with the standard 10-file cap. Keep the timing notes with the run record so we can reuse them in Confluence and in sizing discussions.

What to retain from Step 6:
- Workflow run URL / job run ID
- Wall-clock time for each task: DDL, P1, P2, Validate
- Total PDFs processed, total chunk rows written, total docs marked `completed`
- Simple scale estimate for 17,000 PDFs

### Step 7: Validate against existing production data

Use this step once we have the specific PDFs to test. This is a focused correctness check, not another broad timing run.

**Goal**
- Start from the old-logic baseline the dev team is using now
- Pick 2 PDF UUIDs from that baseline and capture 2 representative chunks per PDF
- Verify the existing vector store and existing Vector Search index before creating any new test objects
- Run the new pipeline for the same PDFs in isolated test targets
- Compare old baseline vs new pipeline output at chunk, metadata, and searchability level

**Inputs needed before starting**
- Existing baseline CSV export: `internal/comms/wed-apr-21/validation/field_service_report_gt_litellm.csv`
- 2 target `pdf_name` values chosen from that CSV
- 2 representative chunk rows per selected PDF
- Expected ESN for each PDF, if known
- Any expected title / event type / report date values we can use as spot checks

**Baseline objects to inspect first**
- Baseline CSV snapshot: `internal/comms/wed-apr-21/validation/field_service_report_gt_litellm.csv`
- Baseline chunk table in Databricks if still available: `main.gp_services_sdg_poc.field_service_report_gt_litellm`
- Baseline Vector Search index: `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm`
- Baseline Vector Search endpoint: `pw-ser-sdg-vector-search`
- If the baseline Delta table no longer exists, treat the CSV export as the frozen source of truth for the old logic comparison

**Important current limitation**
- The production notebooks currently support `FSR_MAX_PDFS`, but they do **not** yet support a runtime allowlist such as `FSR_TARGET_PDF_NAMES`
- Because of that, Step 7 should be run as an **interactive targeted test**, not as a normal scheduled workflow run
- For this step, use a temporary local filter in the notebook session so only the requested PDFs are processed. Do not commit that temporary filter to source control

**How to run Step 7**

1. Establish the old-logic baseline from the CSV
  - Open `field_service_report_gt_litellm.csv`
  - Group by `pdf_name` and count rows so we know which PDFs have enough chunk coverage for comparison
  - Pick 2 `pdf_name` values that each have multiple chunk rows and readable chunk text
  - For each selected PDF, save 2 representative chunk rows with these fields:
    - `chunk_id`
    - `pdf_name`
    - `page_number`
    - `chunk_text`
    - `generator_serial`
    - `report_date`
    - `metadata`
  - Prefer one short chunk and one larger chunk if possible, so we compare both boundary behavior and content quality

2. Check the existing baseline vector store and index before creating anything new
  - Confirm the baseline Vector Search endpoint `pw-ser-sdg-vector-search` is `ONLINE`
  - Confirm the baseline index `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm` exists
  - Confirm which source table the baseline index is reading from
  - Confirm the index is queryable for the selected PDFs using a phrase copied from one of the saved baseline chunks
  - If the baseline Delta table exists, compare the saved CSV chunk rows against the live table rows to make sure the CSV is still representative
  - Record baseline facts before any new run:
    - endpoint state
    - index name
    - source table name
    - selected `pdf_name` values
    - selected `chunk_id` values
    - whether baseline search returns the expected chunks

3. Reset to isolated test targets
  - Metadata table: `main.gp_services_sdg_poc.fsr_metadata_registry_test`
  - Chunk table: `main.gp_services_sdg_poc.fsr_chunks_test`
  - VS index: `main.gp_services_sdg_poc.vs_fsr_chunks_test`
  - VS endpoint: `pw-ser-sdg-vector-search_test`
  - Use `FORCE_RESET=true` if you want a clean targeted run

4. Load the target PDF list
  - Build the test list directly from the 2 `pdf_name` values selected from the baseline CSV
  - For FieldVision files, use the filename stem (UUID without `.pdf`)
  - For manual files, use the filename stem exactly as the pipeline derives it
  - We are validating the exact same PDFs across old and new logic, so do not substitute other examples

5. Run Process 1 interactively with a temporary PDF filter
  - Open the production notebook for P1
  - After the volume scan builds `new_files`, temporarily filter that list to the requested PDF stems only
  - Example logic for the interactive session:

```python
TARGET_PDF_NAMES = {
   "pdf_name_1",
   "pdf_name_2",
}

new_files = [
   nf for nf in new_files
   if Path(nf["path"]).stem in TARGET_PDF_NAMES
]
```

  - Keep `FSR_MAX_PDFS` empty or set it to a value >= the size of the target list
  - Continue the notebook through metadata extraction and final MERGE

6. Validate Process 1 output for the target PDFs
  - Confirm one row per target PDF in the metadata table
  - Confirm `metadata_status = 'completed'`
  - Confirm `pdf_name`, `volume_path`, `title`, `esn`, `customer`, `report_issued_date`, `event_type`, `page_count`, and `scraped_at` are populated when expected
  - Confirm failures, if any, are explicit in `metadata_error`

7. Run Process 2 interactively for the same target PDFs
  - Open the production chunking notebook
  - It reads pending/completed metadata rows from the test metadata table
  - Use the same test table / index parameters as Step 7 setup
  - If needed, temporarily cap the docs list to the known target `pdf_name` values before chunking begins
  - Run through chunking, embedding generation, Delta MERGE, and VS sync trigger

8. Validate the new Delta chunk table first
  - This is the source of truth for vectorized content before index sync
  - For each target PDF, confirm:
    - At least one chunk row exists
    - `chunk_status = 'completed'` in metadata
    - `chunk_count` in metadata matches the number of rows in the chunk table
    - `chunk_text` is non-empty and page ranges look reasonable
    - `embedding` is populated and has dimension `3072`
    - Materialized metadata in chunk rows matches the metadata table for `pdf_name`, `title`, `esn`, `equipment_type`, `event_type`, and `report_issued_date`

9. Validate the new Vector Search endpoint + index sync
  - Confirm the endpoint state is `ONLINE`
  - Confirm the index exists with type `DELTA_SYNC`
  - Confirm the index source table is the Step 7 chunk test table
  - Confirm the embedding column is `embedding` with dimension `3072`
  - Trigger sync if Process 2 did not already do it in this run
  - Wait for the sync pipeline to finish before judging results
  - Capture the last successful sync time / status in the test notes

10. Validate the new searchable index, not just the table
  - Run at least one query in the Vector Search UI or API using a known phrase from each PDF
  - Confirm the returned chunks come from the expected `pdf_name`
  - Confirm the returned metadata includes the expected ESN and file-level fields
  - If the index returns no rows but the chunk table is populated, treat that as a sync/index problem, not a chunking problem

11. Compare old baseline vs new pipeline output
  - For each selected PDF, compare the 2 saved old baseline chunks against the corresponding new chunk output
  - Compare chunk text fidelity, start/end page range, ESN resolution, and chunk size behavior
  - Compare metadata completeness between old and new logic
  - Compare whether the new pipeline produces more useful chunk boundaries or better ESN assignment than the old logic
  - Compare baseline search results from `vs_field_service_report_gt_litellm` against new test search results from `vs_fsr_chunks_test`
  - Exact chunk boundaries do not need to be byte-identical, but the new output should be at least as usable and ideally better aligned to the document structure

12. Record outcomes
  - For each target PDF, record: `pdf_name`, old baseline chunk count, new chunk count, expected ESN, actual ESN, metadata result, VS sync result, queryability result, and any mismatch notes
  - Record whether the baseline table/index existed live, or whether the comparison used CSV + index only
  - Save screenshots or exported rows if we need to review differences with Pranesh later

**Exact baseline-selection queries for the 100-row CSV sample**

Find candidate PDFs with multiple chunk rows:

```sql
SELECT pdf_name, COUNT(*) AS chunk_rows
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm
GROUP BY pdf_name
HAVING COUNT(*) >= 2
ORDER BY chunk_rows DESC, pdf_name
LIMIT 20;
```

If the live baseline table is not available, do the same grouping from the CSV and pick 2 `pdf_name` values manually.

Fetch 2 baseline chunks for a selected PDF:

```sql
SELECT chunk_id, pdf_name, page_number, generator_serial, report_date,
     substring(chunk_text, 1, 500) AS chunk_preview, metadata
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm
WHERE pdf_name = 'pdf_name_1'
ORDER BY page_number, chunk_id
LIMIT 2;
```

Check baseline index queryability:

```sql
-- Use a phrase copied from one saved baseline chunk and test it in the
-- Vector Search UI or API against:
-- main.gp_services_sdg_poc.vs_field_service_report_gt_litellm
```

**Recommended SQL checks for Step 7**

Metadata table:

```sql
SELECT pdf_name, metadata_status, chunk_status, esn, title, event_type,
     report_issued_date, page_count, scraped_at
FROM main.gp_services_sdg_poc.fsr_metadata_registry_test
WHERE pdf_name IN ('pdf_name_1', 'pdf_name_2');
```

Chunk counts + embedding size:

```sql
SELECT pdf_name,
     COUNT(*) AS chunk_rows,
     MIN(size(embedding)) AS min_embedding_dim,
     MAX(size(embedding)) AS max_embedding_dim,
     MIN(start_page) AS min_page,
     MAX(end_page) AS max_page
FROM main.gp_services_sdg_poc.fsr_chunks_test
WHERE pdf_name IN ('pdf_name_1', 'pdf_name_2')
GROUP BY pdf_name;
```

Chunk samples:

```sql
SELECT pdf_name, chunk_index, start_page, end_page, substring(chunk_text, 1, 300) AS chunk_preview
FROM main.gp_services_sdg_poc.fsr_chunks_test
WHERE pdf_name IN ('pdf_name_1', 'pdf_name_2')
ORDER BY pdf_name, chunk_index;
```

Baseline vs new chunk-count comparison:

```sql
SELECT pdf_name, COUNT(*) AS baseline_chunk_rows
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm
WHERE pdf_name IN ('pdf_name_1', 'pdf_name_2')
GROUP BY pdf_name;

SELECT pdf_name, COUNT(*) AS new_chunk_rows
FROM main.gp_services_sdg_poc.fsr_chunks_test
WHERE pdf_name IN ('pdf_name_1', 'pdf_name_2')
GROUP BY pdf_name;
```

**Pass criteria for Step 7**
- Existing baseline endpoint/index can be inspected and queried before the new test starts
- Two PDFs are selected from the old baseline, with two saved chunk examples per PDF
- All target PDFs finish Process 1 with `metadata_status = completed`
- All target PDFs finish Process 2 with `chunk_status = completed`
- Chunk rows exist for every target PDF and embeddings are consistently 3072-dimensional
- Vector Search endpoint is online and the test index sync completes successfully
- Search queries against the test index return the expected target PDFs
- ESN and key metadata align with the current reference data closely enough to support retrieval parity review
- The new output is at least as good as the old baseline for the selected PDFs, and any regressions are explicitly documented

### Step 8: Update Confluence design page

- Update Pranesh's Confluence page with:
  - Schema v2 (metadata + chunk table DDL)
  - Updated process flow diagram (metadata-first-end-to-end-flow)
  - Open design questions from `schema-design-v2.md`
  - Timing results from Step 6
  - Correctness findings from Step 7, including vector store and Vector Search sync validation
- Confluence page URL: TBD (Madhurima to share)

---

## Test Safety Rules

All testing MUST use isolated test tables — never touch production data.

| What | Test target | Production target |
|------|-------------|-------------------|
| Metadata table | `main.gp_services_sdg_poc.fsr_metadata_registry_test` | `vaid.*.biz_metadata_field_service_report` |
| Chunk table | `main.gp_services_sdg_poc.fsr_chunks_test` | `vaid.*.biz_chunk_field_service_report` |
| VS index | `main.gp_services_sdg_poc.vs_fsr_chunks_test` | TBD |

- Pranesh shared an empty table in `aitd`/`ai_con` schema — can recreate with our schema v2 DDL for testing
- All test runs use `_test` suffix on table names (overridden via runtime params, not in config defaults)
- Cap processing to 10 PDFs during dev (`FSR_MAX_PDFS=10`)
- Source volumes are READ-ONLY — never write to PDF volumes
- Drop `_test` tables when done; don't leave test artifacts long-term
- Production code uses runtime params for table names — same code works for test and prod by changing params

---

## Dependencies / Blockers

| Item | Status | Owner |
|------|--------|-------|
| Schema v2 finalized | Agreed (pending Abhijit review on chunk table) | Pranesh |
| Confluence page URL | Pending — Madhurima to share | Madhurima |
| Airflow/MWAA access | Blocked — Chetra/Sonam coordination | Pranesh/Madhurima |
| Secret scope access | PERMISSION_DENIED — using direct API key | Needs admin ticket |
| Databricks CLI bundle deploy | Blocked by network policy | Needs DBR team help |
| P1 notebook update to schema v2 | Not done yet | Step 1 |
