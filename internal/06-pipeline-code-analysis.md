# Pipeline Code Analysis — DS Reference Implementation

Analysis of the DS team's reference pipeline in `reference/examples/databricks_pipeline_sample/`.

---

## Overview

Two reference implementations exist:

| Folder | What it is |
|---|---|
| `fsr_pipeline_dbr_final/` | Ingestion pipeline — PDF → chunk → Delta → VS index |
| `REChain_final/` | RE chain experiment — uses FSR retrieval as a step in an agentic chain |

Both are production-quality Python modules (not notebooks), deployable as Databricks workspace files via `deploy.py`.

---

## Ingestion Pipeline (`fsr_pipeline_dbr_final/`)

### Key architectural fact: VS auto-embeds

> **[DECIDED — from code]** The ingestion pipeline does **not** call LiteLLM to generate embeddings. Databricks Vector Search generates embeddings from `chunk_text` automatically during index sync. Only the query-time path calls LiteLLM.

This means:
- Delta table stores raw text in `chunk_text`; no embedding vectors written by the pipeline
- VS index config specifies the embedding model to use (configured on the VS side)
- After writing to Delta, a VS sync is triggered; VS calls the embedding model at that point

### Delta Table Schema (`main.gp_services_sdg_poc.field_service_report`)

From `delta_store.py`:

| Column | Type | Notes |
|---|---|---|
| `chunk_id` | STRING NOT NULL | `{pdf_name}_{chunk_index}` or `{pdf_name}_{chunk_index}__{esn}` (multi-ESN) |
| `pdf_name` | STRING NOT NULL | Normalized stem (no path, no `.pdf`) |
| `page_number` | INT | start page |
| `generator_serial` | STRING | Primary ESN |
| `report_date` | DATE | From ref view (preferred) or doc metadata |
| `chunk_text` | STRING NOT NULL | Raw chunk text |
| `metadata` | STRING | JSON blob — see below |
| `created_at` | TIMESTAMP | Ingest timestamp |
| `uploaded_at` | TIMESTAMP | Same as created_at |

### Metadata JSON blob

The `metadata` column stores a JSON string (schema_version=1) with these keys:

```json
{
  "schema_version": 1,
  "chunk_index": 0,
  "chunk_count": 42,
  "chunk_size": 4000,
  "token_count": null,
  "start_page": 5,
  "end_page": 7,
  "section_1": "Background",
  "section_2": "Inspection Findings",
  "section_3": null,
  "section_4": null,
  "section_5": null,
  "document_extension": ".pdf",
  "chunk_esns": ["297837"],
  "esn_labels": ["297837"]
}
```

### Multi-ESN row duplication

When a PDF document is tagged with multiple ESNs (e.g. it covers two generators):
- **One Delta row is written per ESN**, not one per chunk
- `chunk_id` pattern: `{pdf_name}_{chunk_index}__{esn}` (double underscore + ESN suffix)
- This ensures `generator_serial = 'ESN_X'` equality filters surface the chunk for every tagged unit
- ESN qualification: count ≥ 5 AND fraction ≥ 10% of all ESN mentions in the document

### ESN Extraction (`esn_identifier.py`)

3-phase approach:
1. **One LLM call per document** (not per chunk) using `azure-gpt-4o`
2. Sends start/middle/end windows of document text (max 3000 chars each, 9000 total)
3. LLM returns `{"ESN": count}` JSON — counts explicit mentions across document
4. Filter: keep ESNs where count ≥ `MIN_ESN_COUNT=5` AND fraction ≥ `MIN_ESN_FRACTION=10%`
5. **Every chunk in the document receives the same ESN label set** (document-level, not chunk-level)
6. Fallback: if no ESN found, uses `generator_serial` from the ref view (`fsr_pdf_ref`)
7. ESN format: 4–12 alphanumeric chars, uppercase normalized

### Chunking (`recursive_chunking_v3.py`)

Full implementation of V3 Hierarchical Recursive Chunking:

1. **TOC detection**: identifies table-of-contents pages by dot-leaders, underscore-leaders, numbered entries; skips front-matter pages
2. **Boilerplate filtering**: removes positional headers/footers (top 4% / bottom 8% of page height) and lines appearing on ≥20% of pages
3. **Header classification** (two-pass):
   - Pass 1: TOC match (exact or prefix) + section numbering depth
   - Pass 2: font-size relative to body font (mode) + bold flags
   - Contextual sibling detection: once first header found, scan for matching signature
4. **Section hierarchy**: tracks up to 5 levels (`section_1` through `section_5`); deeper resets when parent changes
5. **Semantic chunking**: groups body text by section path, then applies `RecursiveCharacterTextSplitter(separators=["\n\n", "\n", ". ", " ", ""])`
6. Page range tracking: each chunk records `start_page` / `end_page` from source lines

Config used in production: `chunk_size=4000, chunk_overlap=200, max_depth=5`

### Ingestion Pipeline Steps (`pipeline.py`)

```
Step 0: Locate PDFs across 3 Volume paths
Step 1: Chunk PDFs → Delta
  - ProcessPoolExecutor for parallel PDF chunking (CPU-bound)
  - Serialized Delta writes via threading write queue
  - Cache-first: skip PDFs already in EMBEDDINGS_TABLE (pdf_name match)
  - Batch load ref view lookup (fsr_pdf_ref) before parallel processing
Step 2: Load from Delta (verify)
Step 3: Vector Search sync (wake endpoint early in step 0)
Step 4: Smoke test queries
```

### Deployment Pattern (`deploy.py`)

Notebook/module pattern — **not a REST service**, not a Databricks App:
- Uploads `run_pipeline.py` + all `src/*.py` + cert + config files as Databricks workspace files
- Runs as a Databricks notebook/job triggered manually or on schedule
- Runtime env vars: `FORCE_RESET`, `MAX_PDFS`, `VS_ENDPOINT_OVERRIDE`, `SECRET_SCOPE_OVERRIDE`
- Authentication: `dbutils.secrets.get('fsr-pipeline', 'LITELLM_API_KEY')` when on Databricks; env var fallback for local dev

---

## Query Pipeline (`REChain_final/REChainExperiment/fsr.py`)

This is the RE chain experiment's FSR retrieval client. Closest to the `query_fsr` tool spec.

### `query_fsr()` Function

```python
def query_fsr(serial_number, query, k=10, query_type="HYBRID") -> List[Dict]
```

**Step 1 — Embed query** (on-the-fly LiteLLM):
```python
query_vector = get_query_vector(query)  # LiteLLM REST call, lru_cache(512)
```

**Step 2 — HYBRID VS query**:
- POST to `/api/2.0/vector-search/indexes/{VS_INDEX_NAME}/query`
- Body: `{query_text, query_vector, columns, num_results, query_type, filters_json}`
- Filter: `{"generator_serial": serial_number}` — equality match on ESN

**Step 3 — Parallel metadata lookups** (`ThreadPoolExecutor(max_workers=3)`):
- `_chunk_rows_by_id(chunk_ids)` — `SELECT * FROM {FSR_CHUNK_TABLE} WHERE chunk_id IN (...)`
- `_pdf_ref_rows(pdf_names)` — `SELECT * FROM {FSR_PDF_REF_VIEW} WHERE s3_filename IN (...) OR PDF_name IN (...)`
- `_scraped_mapping_rows(pdf_names)` — `SELECT * FROM {FSR_SCRAPED_MAPPING_VIEW} WHERE LOWER(pdf_name) LIKE '%/{name}.pdf'`

**Step 4 — Sequential (needs pdf_ref results)**:
- `_fsr_report_rows(pdf_ref_rows)` — ROW_NUMBER() OVER dedup by status: Completed→Started→Not Started→Hold, then by date DESC

**Step 5 — Assemble results**:
- `_choose_pdf_ref()`: prefers `(pdf_name, ESN)` exact match, falls back to file-only match, then first row
- `_build_results()`: flat dict per VS result row with all enrichment fields inlined

### Result Shape (REChain fsr.py)

Flat dict per result — slightly different from `query_fsr_with_metadata.py` which uses nested `{rank, chunk, fsr_report, pdf_ref, scraped_mapping}`:

```python
{
  "chunk_id": "...",
  "pdf_name": "...",
  "page_number": 5,
  "chunk_text": "...",
  "generator_serial": "297837",
  "score": 0.82,
  "start_page": 5,
  "end_page": 7,
  "section_1": "Background",
  "section_2": "Inspection Findings",
  "section_3": None, "section_4": None, "section_5": None,
  "start_date": "2023-04-01", "end_date": "2023-04-15",
  "report_name": "FSR-297837-2023.pdf",
  "event_type": "...", "outage_type": "...", "technology_type": "...",
  "report_unit_status": "Completed",
  "metadata": {...},       # parsed JSON dict
  "pdf_ref": {...},        # selected fsr_pdf_ref row
  "fsr_report": {...},     # selected fsr_field_vision row
  "scraped_mapping": {...} # selected fsr_scraped_file_mapping row
}
```

The `query_fsr_with_metadata.py` version adds `rank` + `rerank_score` and wraps sub-objects differently — that is the **canonical tool spec implementation**.

---

## Embedding Architecture Summary

| Stage | Who embeds | Model | When |
|---|---|---|---|
| Ingestion → Delta | Nobody | — | Text stored as-is in `chunk_text` |
| Delta → VS index sync | Databricks VS | `azure-text-embedding-3-large-1` (configured on VS) | During index sync |
| Query time | LiteLLM proxy | `azure-text-embedding-3-large-1` | Per request (cached by `lru_cache(512)`) |

**Impact on ADR-002**: On-the-fly LiteLLM is the correct approach for query embedding. The ingestion pipeline intentionally delegates embedding to VS — this is simpler and avoids managing embedding vectors manually.

---

## Key Implementation Patterns to Reuse

| Pattern | File | Notes |
|---|---|---|
| Corporate cert bundle | `pipeline.py` | Combines system certs + GE Enterprise Root CA before any HTTPS call |
| Secret scope auth | `config.py` | `dbutils.secrets.get('fsr-pipeline', key)` with env var fallback |
| LiteLLM URL fallback | `vector_embeddings.py` | Tries configured path, then `/v1/embeddings`, then `/embeddings` |
| ESN extraction | `esn_identifier.py` | One doc-level LLM call; `azure-gpt-4o`; start/middle/end window |
| PDF key normalization | `fsr.py` | `_normalize_pdf_key()` — strips path, `.pdf` suffix, handles backslash |
| SQL quote safety | `fsr.py` | `_sql_quote()` + `_sql_string_list()` — no ORM, raw SQL with manual quoting |
| HYBRID VS POST | `fsr.py` | Body: `{query_text, query_vector, columns, num_results, query_type, filters_json}` |
| Parallel SQL lookups | `fsr.py` | `ThreadPoolExecutor(max_workers=3)` for chunk hydration + 2 metadata views |
| Status-priority dedup | `fsr.py` | `ROW_NUMBER() OVER (... ORDER BY CASE report_unit_status WHEN 'COMPLETED' THEN 1 ...)` |
| chunk_id format | `delta_store.py` | `{pdf_name}_{chunk_index}` or `{pdf_name}_{chunk_index}__{esn}` for multi-ESN |
| Delta retry | `delta_store.py` | Catches `ConcurrentAppendException`, retries up to 5x with linear backoff |

---

## ADR Updates from Code Review

| ADR | Finding |
|---|---|
| ADR-001 (hosting) | Code uses workspace-file + notebook-job pattern for ingestion; REST service (query) is a separate Python module called from the RE chain — confirms FastAPI as a clean separation |
| ADR-002 (embedding) | **Ingestion delegates to VS auto-embed; query uses on-the-fly LiteLLM.** Option A (on-the-fly) is correct for query service. LiteLLM connectivity is the only remaining question. |
| ADR-003 (reranking) | REChain `fsr.py` does NOT rerank — basic HYBRID only. `query_fsr_with_metadata.py` does add reranking. Reranking is the key gap. |
| ADR-004 (trigger) | Pipeline is currently manual/job-triggered. Autoloader path not implemented. |
| ADR-006 (structure) | Code is pure Python modules — no notebook dependency in the query path. FastAPI wrapper is the right pattern. Pipeline submodules (`embed.py`, `search.py`, `hydrate.py`, `enrich.py`) map directly to what's in `fsr.py`. |
