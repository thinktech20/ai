## TIL Databricks Workflows

Workflow definitions for TIL pipeline jobs (Process 1 and Process 2).

**Files:**

### `pw_sdg_til_ddl.yml`
- **Purpose:** Create all TIL pipeline tables (idempotent, safe for reruns)
- **Tables created:** til_metadata, til_elements, til_chunks, til_validation_results, til_evaluation_results, til_pipeline_run_audit
- **Run frequency:** One-time setup, or when schema changes are needed
- **Parameters:** `environment` (dev/staging/prod)

### `pw_sdg_til_metadata.yml`
- **Purpose:** Process 1 (P1) — TIL PDF ingestion, parsing, and profile normalization
- **Steps:**
  1. Discover TIL PDFs from volume
  2. Parse with selected method (foundation, pdfplumber, databricks_ai)
  3. Normalize with LLM → ProfileJSON
  4. Store in `til_metadata`
  5. Track run in `til_pipeline_run_audit`
- **Run frequency:** As needed (backfill, incremental, evaluation subsets)
- **Key parameters:**
  - `PARSER_METHOD`: Which parser to use (foundation [HTTP], pdfplumber [local], databricks_ai [DBR native])
  - `TIL_SOURCE_VOLUME_PATHS`: Where to find PDFs
  - `TIL_P1_MAX_PDFS`: Limit for testing
  - `TIL_P1_TARGET_PDF_NAMES`: Specific PDFs to ingest — comma-separated file names or distinctive substrings (case-insensitive). Empty = all. Substrings matching >1 file fail strict and are written as `pdf_not_found` audit rows.
  - `TIL_BATCH_SIZE`: Batch claim size

**Future workflows:**
- `pw_sdg_til_chunks.yml` — Process 2 (P2) Chunking + Embedding
- `pw_sdg_til_validation.yml` — Quality checks before deployment

**Deployment:**
Use Databricks CLI or UI to deploy:
```bash
databricks jobs create --json-file pw_sdg_til_ddl.yml
databricks jobs create --json-file pw_sdg_til_metadata.yml
```
