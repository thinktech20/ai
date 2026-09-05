# FSR Pipeline — Production Readiness Plan

> **Date:** 2026-04-22  
> **Status:** Steps 1–6 complete; Step 8 scaling code shipped (Phases 1–2 + P2 hardening); P1 hardening + config tuning + scale test remain

---

## Current State

- Interactive notebooks (tested with 10 PDFs) in `notebooks/` folder
- `code/` folder is empty, ready for production code
- Schema v3 implemented: `document_id` (UUID stem) is PK, `pdf_name` is derived from `fsr_pdf_ref`
- All production notebooks updated to schema v3 identity model (Apr 21)
- Process 1 derives `pdf_name` via `fsr_pdf_ref.PDF_name` join, with `volume_path` fallback
- Process 2 materializes `document_id` as FK and `pdf_name` as nullable field on chunk rows
- Validation notebook checks 12 materialized fields, `pdf_name` derivation coverage, and `document_id` normalization

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
    fsr_config.py                      ← FSR shared config (schema v3)
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
  design/                              ← Design docs copied only when needed for packaging
  notebooks/                           ← Archive of interactive dev notebooks
```

This canonical design folder now lives at `implementation/design/` so we can
check in `sdg-pipelines/` without pulling along internal-only planning content.

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
- Update to schema v3: `document_id` is PK, `pdf_name` derived from `fsr_pdf_ref`
- Status values: `completed`/`failed` (not `ok`/`skipped`)
- Add `scraped_at` timestamp on success
- MERGE keys on `document_id` instead of `pdf_name`
- Structured logging instead of print statements
- No `%pip install` (deps handled by cluster/workflow)

Break this into sub-tasks to keep each change small:

- **2a** — Create skeleton: imports, config run, logging setup, banner ✅
- **2b** — Watermark scan + volume listing logic ✅
- **2c** — MERGE stub rows (schema v3: document_id PK, pdf_name derived) ✅
- **2d** — PDF extraction (pdfplumber, page-1 fields) ✅
- **2e** — LLM normalization (batched, with retries) ✅
- **2f** — IBAT + Event Vision enrichment ✅
- **2g** — pdf_name derivation from fsr_pdf_ref + volume_path fallback ✅
- **2h** — Final MERGE results + failure handling ✅

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

- **4a** — Process 1 checks (update to schema v3: document_id PK, completed/failed statuses) ✅
- **4b** — Process 2 checks (chunk table, embeddings) ✅
- **4c** — Cross-process consistency checks (12-field materialized comparison, pdf_name coverage, document_id normalization) + summary ✅

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
SELECT document_id, pdf_name, metadata_status, chunk_status, esn, title, event_type,
     report_issued_date, page_count, scraped_at
FROM main.gp_services_sdg_poc.fsr_metadata_registry_test
WHERE document_id IN ('doc_id_1', 'doc_id_2');
```

Chunk counts + embedding size:

```sql
SELECT document_id, pdf_name,
     COUNT(*) AS chunk_rows,
     MIN(size(embedding)) AS min_embedding_dim,
     MAX(size(embedding)) AS max_embedding_dim,
     MIN(start_page) AS min_page,
     MAX(end_page) AS max_page
FROM main.gp_services_sdg_poc.fsr_chunks_test
WHERE document_id IN ('doc_id_1', 'doc_id_2')
GROUP BY document_id, pdf_name;
```

Chunk samples:

```sql
SELECT document_id, pdf_name, chunk_index, start_page, end_page, substring(chunk_text, 1, 300) AS chunk_preview
FROM main.gp_services_sdg_poc.fsr_chunks_test
WHERE document_id IN ('doc_id_1', 'doc_id_2')
ORDER BY document_id, chunk_index;
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

### Step 8: Scale to Full Corpus — 17.8K Files

> **Date added:** 2026-04-21  
> **Status:** Phase 1 + Phase 2 + P2 failure hardening **✅ DONE** (shipped in code). P1 hardening (gaps 1–2), config tuning, and scale testing **remaining**.  
> **Context:** Test run processed 7 docs (avg ~115 MB each) in ~7 min producing 1,125 chunks. Extrapolating serially to 17.8K files would take ~12+ days. This step covers the plan to get that down to under a day.

#### 8.1 Current Bottleneck Analysis

The pipeline has 4 workflow tasks: `DDL → P1 (metadata) → P2 (chunks) → Validate`.

P2 (chunk ingestion) is the bottleneck. Within P2:

| Step | Current behavior | Time share | Bottleneck? |
|------|-----------------|:----------:|:-----------:|
| PDF text extraction (PyMuPDF) | Sequential for-loop over docs | ~10% | No |
| Embedding generation (LiteLLM) | ~~Serial batches of 32, one API call at a time~~ → **Concurrent** (8 workers via ThreadPoolExecutor) | **~85%** | **Addressed by Phase 1** |
| Delta MERGE + status update | Single Spark SQL statement | ~5% | No |

~~The embedding loop sends 32 texts to LiteLLM, waits for response, then sends the next 32. All network latency is serial.~~  
**Updated:** Embedding now runs 8 concurrent workers via `ThreadPoolExecutor` + `safe_embed_batch`. Serial bottleneck is resolved.

#### 8.2 Failure Handling Audit

Current failure hooks in the pipeline code:

**P1 — Metadata Extraction (`nb_sdg_fsr_metadata.py`):**
| Scenario | Current handling | Adequate? |
|----------|-----------------|:---------:|
| PDF open failure | Caught per-doc, saved in `failures` dict, marked `metadata_status=failed` with error message | ✅ |
| LLM call failure | 3 retries with exponential backoff; batch-level failure marks all docs in batch as `failed` | ⚠️ See gap 1 |
| LLM returns no match for a doc | Detected, marked as `llm_failures` with message | ✅ |
| LLM returns malformed JSON | Caught by `json.loads`, entire batch marked failed | ⚠️ See gap 2 |
| IBAT/EV enrichment table not accessible | Caught, logged, continues without enrichment | ✅ |
| IBAT join multiplies rows | Handled by `dropDuplicates(["document_id"])` | ✅ |
| pdf_name derivation fails | Falls back to volume_path stem | ✅ |
| Status updates after failure | `metadata_status=failed`, `metadata_error` populated, `scraped_at` set | ✅ |
| Re-processing failed docs | Picks up `FAILED` docs up to `P1_MAX_RETRIES` per run | ✅ |

**P2 — Chunk Ingestion (`nb_sdg_fsr_chunks.py`):**
| Scenario | Current handling | Adequate? |
|----------|-----------------|:---------:|
| PDF text extraction fails | Caught per-doc, added to `doc_errors`, marked `chunk_status=failed` | ✅ |
| Empty text after extraction | Caught, added to `doc_errors` | ✅ |
| Embedding API fails | 3 retries with backoff per batch; `safe_embed_batch` catches failure, returns None per ref | ✅ Fixed (gap 3) |
| Embedding dimension mismatch | Logged as warning but continues | ✅ |
| Missing embedding for a chunk | Per-doc coverage check: >10% missing → doc marked failed | ✅ Fixed (gap 4) |
| MERGE to Delta | Standard Spark SQL, idempotent on `chunk_id` | ✅ |
| VS endpoint not online | Detected, sync skipped with warning | ✅ |
| VS index doesn't exist | Auto-created with correct schema | ✅ |
| VS sync fails | 3 retries with 20s backoff; warns and continues | ✅ |
| Status tracking | Success → `chunk_status=completed`; failures → `chunk_status=failed` + error | ✅ |

**Identified gaps to fix before scaling:**

| # | Gap | Impact at scale | Fix | Status |
|---|-----|----------------|-----|:------:|
| 1 | LLM batch failure marks all docs in batch as failed, even if only one caused the issue | At P1_BATCH_SIZE=4 this is minor; at larger batches, a single bad doc wastes the whole batch | Add per-doc fallback: on batch failure, retry each doc individually | ⬚ Open |
| 2 | Malformed LLM JSON response fails entire batch | Same batch-blast-radius issue | Parse response defensively; extract what we can, mark remainder as failed | ⬚ Open |
| 3 | Embedding failure kills the entire P2 run (exception propagates) | A single bad batch (e.g., text too long) stops all remaining docs | Wrap per-batch in try/except; skip failed batch, mark affected docs as failed | ✅ Done |
| 4 | Missing embedding for a chunk → chunk silently dropped | A doc could appear "completed" but have missing chunks | Log a warning; if >10% of a doc's chunks have no embedding, mark doc as failed instead of completed | ✅ Done |
| 5 | No `in_progress` state → concurrent runs grab same docs | Wasted compute when running parallel jobs | Add claim-based locking (see 8.3 Phase 2) | ✅ Done |
| 6 | No per-run progress tracking | If a run crashes mid-batch, we only know from the job failure log | Add a progress counter log every N docs; consider writing a `_run_log` temp table | ✅ Done |

#### 8.3 Scaling Plan — Three Phases

##### Phase 1: Concurrent Embedding Calls (code change, high impact) — ✅ DONE

Parallelize embedding API calls within a single run using `ThreadPoolExecutor`.

**File:** `gold/src/etl/nb_sdg_fsr_chunks.py`  
**New config param:** `FSR_P2_EMBED_CONCURRENCY` (default 8)  
**Also:** Wrap each embedding batch in try/except so one failed batch doesn't kill the run.

```python
# Current (serial):
for i in range(0, len(all_chunk_texts), EMBED_BATCH_SIZE):
    vectors = embed_batch(batch_texts)
    ...

# New (concurrent + fault-tolerant):
from concurrent.futures import ThreadPoolExecutor, as_completed

P2_EMBED_CONCURRENCY = int(get_runtime_param("FSR_P2_EMBED_CONCURRENCY", "8"))

def safe_embed_batch(batch_idx, texts, refs):
    """Embed a batch, return results or error."""
    try:
        vectors = embed_batch(texts)
        return [(ref, vec) for ref, vec in zip(refs, vectors)]
    except Exception as e:
        log.error(f"Batch {batch_idx} failed: {e}")
        return [(ref, None) for ref in refs]  # mark as failed

batches = [
    (i // EMBED_BATCH_SIZE, all_chunk_texts[i:i+EMBED_BATCH_SIZE],
     all_chunk_refs[i:i+EMBED_BATCH_SIZE])
    for i in range(0, len(all_chunk_texts), EMBED_BATCH_SIZE)
]

with ThreadPoolExecutor(max_workers=P2_EMBED_CONCURRENCY) as pool:
    futures = {
        pool.submit(safe_embed_batch, idx, texts, refs): idx
        for idx, texts, refs in batches
    }
    for future in as_completed(futures):
        for ref, vec in future.result():
            if vec is not None:
                all_embeddings[ref] = vec
            else:
                embed_failures.add(ref[0])  # track doc_id
```

**Expected impact:** 4–8x speedup on embedding step (currently ~85% of runtime).  
**Risk:** LiteLLM rate limiting. Start at 8 concurrent workers, monitor for 429 responses.

##### Phase 2: Claim-Based Locking for Parallel Job Runs (code change) — ✅ DONE

Add `chunk_status = 'in_progress'` so multiple concurrent job runs don't process the same files.

**File:** `gold/src/etl/nb_sdg_fsr_chunks.py`

```python
# Step 1: Claim a batch atomically
spark.sql(f"""
    UPDATE {METADATA_TABLE}
    SET chunk_status = 'in_progress',
        chunked_at = current_timestamp()
    WHERE document_id IN (
        SELECT document_id FROM {METADATA_TABLE}
        WHERE metadata_status = 'completed'
          AND chunk_status IN ('pending', 'failed')
        LIMIT {P2_BATCH_SIZE}
    )
""")

# Step 2: Read only claimed rows
pending_df = spark.sql(f"""
    SELECT ... FROM {METADATA_TABLE}
    WHERE chunk_status = 'in_progress'
""")
```

**Also add stale-claim recovery** (at the start of each run):
```python
spark.sql(f"""
    UPDATE {METADATA_TABLE}
    SET chunk_status = 'pending'
    WHERE chunk_status = 'in_progress'
      AND chunked_at < current_timestamp() - INTERVAL 30 MINUTES
""")
```

On success → `chunk_status = 'completed'`. On failure → `chunk_status = 'failed'`.

**File:** `Common/fsr_config.py`  
- Add `in_progress` to `ChunkStatus` enum.

**Expected impact:** Reduces overlap risk for parallel job runs (5–10 concurrent).  
**Risk:** Low — Delta table transactions are ACID.

##### Phase 3: Increase Batch Sizes (config only) — ⬚ Params exist, values not yet bumped

| Parameter | Current default | Proposed | Rationale | Status |
|-----------|:-------:|:--------:|-----------|:------:|
| `FSR_P2_BATCH_SIZE` | 50 | 500 | Fewer job runs needed once gateway limits are under control | ⬚ Not bumped |
| `EMBED_BATCH_SIZE` | 32 | 128 | Fewer API calls, more efficient | ⬚ Not bumped |
| `FSR_P2_EMBED_CONCURRENCY` | 8 | 8 | Concurrent embedding workers | ✅ Exists |

All three are runtime params — bump via job `base_parameters` without code changes.

**Risk:** Monitor memory on larger batches. 500 docs × ~161 chunks × 3072-dim float vectors ≈ 1.5 GB in memory. Should fit on serverless, but test with 200 first.

#### 8.4 Failure Hardening Changes (alongside scaling)

These changes should ship together with Phase 1 since they share the same file:

| Change | File | Description | Status |
|--------|------|-------------|:------:|
| Per-batch embedding fault tolerance | `nb_sdg_fsr_chunks.py` | Wrap each batch in try/except, skip failed batches, mark affected docs as failed | ✅ Done |
| Missing-embedding threshold check | `nb_sdg_fsr_chunks.py` | After embedding loop, check each doc. If >10% of chunks have no embedding, mark doc as `failed` instead of `completed` | ✅ Done |
| Per-doc LLM fallback (P1) | `nb_sdg_fsr_metadata.py` | On batch LLM failure, retry each doc individually before marking all as failed | ⬚ Open |
| Configurable `EMBED_BATCH_SIZE` | `fsr_config.py` | Move from hardcoded `32` to `get_runtime_param("FSR_EMBED_BATCH_SIZE", "32")` | ✅ Done |
| Add `in_progress` chunk status | `fsr_config.py` | New status value for claim-based locking | ✅ Done |
| Progress logging | `nb_sdg_fsr_chunks.py` | Log every 100 docs processed (not just every embedding batch) | ✅ Done |
| Audit run log | `nb_sdg_fsr_chunks.py` + `fsr_config.py` | `fsr_run_log` table with per-batch timing/counts | ✅ Done |

#### 8.5 Projected Timeline

| Scenario | Parallel runs | Docs/run | Est. time/run | Total wall-clock |
|----------|:------------:|:--------:|:--------------:|:----------------:|
| Current (serial, batch=50) | 1 | 50 | ~50 min | ~12 days |
| Phase 1 only (concurrent embed) | 1 | 50 | ~10 min | ~2.5 days |
| Phase 1 + 3 (bigger batches) | 1 | 500 | ~80 min | ~2.4 days |
| **Phase 1 + 2 + 3 (5 parallel)** | **5** | **500** | **~80 min** | **~12 hours** |
| Phase 1 + 2 + 3 (10 parallel) | 10 | 500 | ~80 min | ~6 hours |

#### 8.6 Implementation Sequence

1. ✅ **Implement Phase 1 + P2 failure hardening** in `nb_sdg_fsr_chunks.py` (concurrent embedding + per-batch fault tolerance + coverage threshold + progress logging + audit log)
2. ✅ **Implement Phase 2** (claim-based locking + stale claim recovery + batch drain loop) in same file + `fsr_config.py`
3. ⬚ **P1 hardening (gaps 1–2):** per-doc LLM fallback + defensive JSON parsing in `nb_sdg_fsr_metadata.py`
4. ⬚ **Test with 100-doc batch** to validate timing + error handling
5. ⬚ **Bump config** (Phase 3) and launch parallel runs
6. ⬚ **Monitor** LiteLLM rate limits, cluster memory, and `chunk_status=failed` count
7. ⬚ **Full 17.8K corpus** should complete in under a day

#### 8.7 Rollback Plan

All changes are backward-compatible:
- If concurrent embedding causes issues, set `FSR_P2_EMBED_CONCURRENCY=1` (reverts to serial)
- If claim-based locking has issues, run jobs sequentially (only one at a time) — `in_progress` rows auto-recover after 30 min
- If batch size is too large, reduce via runtime params without code changes

---

### Step 9: Update Confluence design page

- Update Pranesh's Confluence page with:
  - Schema v2 (metadata + chunk table DDL)
  - Updated process flow diagram (metadata-first-end-to-end-flow)
  - Open design questions from `schema-design-v2.md`
  - Timing results from Step 6
  - Correctness findings from Step 7, including vector store and Vector Search sync validation
- Confluence page URL: TBD (Madhurima to share)

### Step 9b: Large File Handling & Document Summary

> **Date added:** 2026-04-21  
> **Status:** Not started — to discuss with Vince

#### Large File Chunking Impact

Larger files produce proportionally more chunks. The pipeline won't break on large files (PyMuPDF reads page-by-page, no memory issue), but time scales linearly with chunk count.

| File size | Est. pages | Est. chunks | Embedding time vs avg |
|-----------|:----------:|:-----------:|:---------------------:|
| ~50 MB (avg) | ~100 | ~50 | 1x |
| ~115 MB (test run avg) | ~300 | ~161 | 3x |
| 500 MB | ~1000 | ~600–800 | 12–16x |
| 1 GB | ~2000 | ~1200–1600 | 24–32x |

Current strategy: `RecursiveCharacterTextSplitter`, `chunk_size=4000`, `overlap=200`. Joins all pages into one string, then splits. No size-based special handling.

**37 large files (>500 MB) ≈ equivalent work of ~160 average files** — not a concern in a 17.8K corpus.

File size distribution from Pranesh's analysis:

| Category | Count | % |
|----------|------:|-----:|
| > 1 GB | 4 | 0.02 |
| 500 MB – 1 GB | 33 | 0.18 |
| 100 MB – 500 MB | 1,691 | 9.47 |
| 50 MB – 100 MB | 2,220 | 12.43 |
| 20 MB – 50 MB | 3,935 | 22.03 |
| 10 MB – 20 MB | 2,438 | 13.65 |
| 5 MB – 10 MB | 1,861 | 10.42 |
| < 5 MB | 5,681 | 31.80 |

#### Document Summary — Post-Processing Approach

**Current state:** `document_summary` column exists in metadata schema but is always `NULL`. No summarization code exists in the pipeline.

**Recommendation: Implement as a separate post-processing step**, not inline with P1 or P2.

**Why post-processing:**
- **Decoupled risk** — summary LLM failure shouldn't block metadata extraction or chunking (the critical path for vector search)
- **Already have chunks** — once P2 runs, summarization can read chunk texts from Delta instead of re-reading PDFs
- **Backfill-friendly** — can run for all 17.8K files after the main pipeline finishes
- **Independent retry** — if summary fails for some docs, re-run only the summary step

**Strategy by file size:**

| Size | Pages | Approach | LLM calls/doc |
|------|:-----:|----------|:-------------:|
| < 100 MB | < ~500 | Single-pass: concatenate first N chunks (up to context window), send to LLM | 1 |
| 100 MB – 500 MB | 500–1000 | Map-reduce: summarize every 10 chunks → summarize the summaries | ~15–20 |
| > 500 MB | 1000+ | Map-reduce (same as above, just more chunks) | ~30–50 |

~16K files (< 100 MB) use single-pass = 16K LLM calls.  
~1,800 files (> 100 MB) use map-reduce = ~30K LLM calls.  
**Total: ~46K LLM calls** — manageable, and can be parallelized.

**Implementation plan:**

| Item | Detail |
|------|--------|
| New notebook | `gold/src/etl/nb_sdg_fsr_doc_summary.py` (~150 lines) |
| Reads from | Chunk table — `SELECT pdf_name, chunk_text FROM chunks GROUP BY pdf_name` |
| Writes to | Metadata table — `UPDATE SET document_summary = ... WHERE document_summary IS NULL` |
| Workflow placement | Optional task after P2, before validate (or as a standalone job) |
| New config params | `FSR_SUMMARY_BATCH_SIZE`, `FSR_SUMMARY_MAX_CHUNKS_PER_DOC`, `FSR_SUMMARY_MODEL` |
| Effort estimate | ~1 day dev, ~0.5 day testing |
| Can be deferred | Yes — summary is not needed for vector search to work. Can backfill later. |

**Summary prompt template (draft):**
```
You are summarizing a Field Service Report (FSR) for a power generation asset.
Given the following text chunks from the report, provide a concise summary 
in 3–5 sentences covering: equipment inspected, key findings, 
actions taken, and overall condition assessment.
```

#### Decision needed from Vince
- Confirm post-processing approach is acceptable (vs inline with P1)
- Priority: should summary ship with the initial 17.8K run, or backfill after?
- Whether current chunk strategy (4000 chars, 200 overlap) is acceptable for large files, or if we should consider adaptive chunking

---

### Step 10: Close the remaining metadata materialization scope — partially done

The schema v3 identity correction (Apr 21) resolved the biggest blocker. Updated status:

Already materialized on chunk rows:
- `title`, `esn`, `equipment_type`, `event_type`, `report_issued_date`, `page_count`
- `equipment_sys_id`, `outage_start_date`, `outage_end_date`, `ev_equipment_event_id`, `fsp_project_id`
- `pdf_name` (derived from `fsr_pdf_ref`, nullable)

Still deferred:
- `customer`, `prepared_by`, `approved_by` — pending extraction quality decision
- `ev_project_id`, `fsr_number` — metadata-only for now, not promoted to chunk rows
- `document_summary` — not yet implemented
- Source-precedence rules per field when multiple enrichment sources disagree

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
- In production, any manual workflow used for targeted PDF validation must point only to isolated test objects.
- Do not point a production manual workflow at shared live tables, shared live Vector Search indexes, or UAT-backed objects.
- Drop `_test` tables when done; don't leave test artifacts long-term
- Production code uses runtime params for table names — same code works for test and prod by changing params

---

## Dependencies / Blockers

| Item | Status | Owner |
|------|--------|-------|
| Schema v3 finalized | ✅ Done (document_id PK, pdf_name derived) | Vince |
| Confluence page URL | Pending — Madhurima to share | Madhurima |
| Airflow/MWAA access | Blocked — Chetra/Sonam coordination | Pranesh/Madhurima |
| Secret scope access | PERMISSION_DENIED — using direct API key | Needs admin ticket |
| Databricks CLI bundle deploy | Blocked by network policy | Needs DBR team help |
| P1 notebook update to schema v3 | ✅ Done | Vince |
