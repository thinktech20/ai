# FSR Databricks Pipeline Guide

This document describes the pipeline execution path in `fsr_pipeline_dbr_final`. The package is designed for Databricks workspace notebooks plus workspace files, not for a standalone local run.

---

## 1) Entry points

Primary notebook:
- `run_pipeline.py`

Deployment helper:
- `deploy.py`

Main orchestration module:
- `src/pipeline.py`

`deploy.py` uploads:
- `run_pipeline.py` as a Databricks notebook
- `run_evaluation.py` as a Databricks notebook
- all non-private `src/*.py` modules as workspace files
- `GE_Enterprise_Root_CA_2_1.crt`
- the Heat Map and citations workbooks used by evaluation

---

## 2) Runtime model

The Databricks package does not create local embedding pickles or a local FAISS index. Instead, it writes chunk rows into a Delta table and relies on Databricks Vector Search Delta Sync to embed `chunk_text` and keep the search index current.

Core storage objects from `src/config.py`:

- PDF volume candidates:
  - `/Volumes/vgpd/fsr_std_views/fsr_std_vol/FSR_After_2016/FSR_Databricks/`
  - `/Volumes/viud/ing_ud_fieldvision/fv_field_service_report`
  - `/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report`
- Delta table:
  - `main.gp_services_sdg_poc.field_service_report`
- Vector Search index:
  - `main.gp_services_sdg_poc.vs_field_service_report`
- Vector Search endpoint:
  - `pw-ser-sdg-vector-search`
- ref-view enrichment source:
  - `vgpd.fsr_std_views.fsr_pdf_ref`

---

## 3) Notebook flow

`run_pipeline.py` resolves the deployed `src/` path dynamically inside the Databricks workspace, then exposes a small set of runtime controls:

- `FORCE_RESET`
  - truncates the Delta chunk table before processing
- `MAX_PDFS`
  - optional cap for smoke runs
- `VS_ENDPOINT_OVERRIDE`
  - overrides `VS_ENDPOINT_NAME`
- `SECRET_SCOPE_OVERRIDE`
  - overrides the secret scope used by `src/config.py`
- `RUN_EVALUATION`
  - optionally calls `evaluate_retrieval.evaluate_all()` after the pipeline completes
- `EVAL_MAX_K`
  - max k passed to the evaluation notebook code path

Execution then calls `pipeline.main(force_reset=FORCE_RESET, max_pdfs=MAX_PDFS)`.

---

## 4) Pipeline stages

`src/pipeline.py` runs four operational stages.

### Step 0 - Locate PDF volumes

- Uses `utils.collect_pdfs_from_volumes(PDF_VOLUME_PATHS)`.
- Merges PDFs from every configured Unity Catalog volume that is both reachable and non-empty.
- Skips duplicate PDF stems when the same document appears in more than one volume.
- Fails fast if no PDFs are found in any configured volume.

### Step 1 - Chunk PDFs to Delta

- Enumerates the merged PDF list returned from the active configured volumes.
- Skips documents already present in the Delta table via `delta_store.chunk_table_doc_ids()`.
- Processes remaining PDFs in a 10-thread pool.
- For each PDF:
  - `pdf_processor.process_single_pdf()` extracts and chunks text.
  - `esn_identifier.identify_esns()` tags chunks with ESNs using LiteLLM.
  - `delta_store.save_chunks_to_delta()` appends rows to the Delta table.

Important behavior:

- ESN identification is treated as a hard dependency for the pipeline path. If the LiteLLM ESN stage fails in a hard way, the thread pool is aborted instead of silently degrading.
- Delta writes are serialized with a lock even though chunking and ESN inference run in parallel.
- `load_ref_view_lookup()` enriches chunks with ESN/report-date data from `vgpd.fsr_std_views.fsr_pdf_ref`.
- Multi-ESN chunks are duplicated one row per ESN so equality filters on `generator_serial` can surface the chunk for every tagged unit.

### Step 2 - Load documents from Delta

- `document_loader.load_all_chunks_from_delta()` reads `pdf_name`, `page_number`, and `chunk_text` from the Delta table.
- This is the single source of truth for the cleaned Databricks pipeline.

### Step 3 - Vector Search index sync

- `_sync_vs_index()` triggers or waits for Delta Sync so the search index reflects the current Delta table state.
- No local embedding array is built in this package.

### Step 4 - Retrieval smoke test

- `_test_retrieval(num_results=5)` performs a small validation query against the Vector Search index.
- This is a sanity check, not the ground-truth evaluation harness.

---

## 5) Supporting modules

- `src/config.py`
  - environment detection, secret loading, volume/table/index names, chunking config
- `src/delta_store.py`
  - Delta append, ref-view enrichment, MERGE-based metadata repair
- `src/document_loader.py`
  - reads chunk text back from the Delta table for inspection
- `src/esn_identifier.py`
  - 3-phase ESN extraction pipeline driven by LiteLLM
- `src/pdf_processor.py`
  - PDF parsing and recursive chunk generation
- `src/recursive_chunking_v3.py`
  - hierarchical chunker implementation
- `src/utils.py`
  - logging, metadata cleaning, PDF volume validation

---

## 6) Operational notes

- `FORCE_RESET=True` truncates the Delta table before processing. Use it only when you want to rebuild the table from scratch.
- The default secret scope is `fsr-pipeline`. `src/config.py` resolves `LITELLM_BASE_URL` and `LITELLM_API_KEY` from that scope first, then falls back to environment variables.
- `GE_Enterprise_Root_CA_2_1.crt` is uploaded alongside the notebooks and used to build a combined CA bundle when direct HTTPS calls are required.
- The pipeline assumes the Delta table and Vector Search index already exist. Table/index provisioning is not done in this package.

---

## 7) Outputs and validation surface

Primary persistent output:

- Delta rows in `main.gp_services_sdg_poc.field_service_report`

Derived searchable output:

- Vector Search index `main.gp_services_sdg_poc.vs_field_service_report`

Notebook-visible validation:

- PDF volume discovery logs
- per-PDF chunk and save logs
- document inspection samples after Delta load
- Vector Search smoke-test output
- optional handoff into the evaluation notebook code path

---