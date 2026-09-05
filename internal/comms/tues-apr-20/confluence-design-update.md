# Scraping + Chunking – Design (Updated)

This document describes the two core processes that together form the FSR (Field Service Report) data pipeline:

1. **Process 1 – Scraping & Metadata Extraction** (Silver)
2. **Process 2 – Chunking & Vector Embedding** (Gold)

Both processes run as Databricks serverless notebooks orchestrated by a single multi-task workflow.

---

## Workflow Structure

The pipeline runs as a Databricks Workflows job with four sequential tasks:

| Task | Notebook | Purpose |
|------|----------|---------|
| 1. DDL | `common/nb_sdg_fsr_ddl` | Create metadata + chunk tables if they don't exist |
| 2. Metadata Extraction | `silver/nb_sdg_fsr_metadata` | Process 1 — PDF discovery, scraping, LLM normalization, enrichment |
| 3. Chunk Ingestion | `gold/nb_sdg_fsr_chunks` | Process 2 — chunking, embedding, Vector Search sync |
| 4. Validate | `validation/nb_sdg_fsr_validate` | Automated P1 + P2 + cross-process quality checks |

All tasks run on **Databricks Serverless** compute. Configuration is centralized in `common/fsr_config`, shared via `%run`.

---

## Process 1 – Scraping & Metadata Extraction

### Purpose

Scan FSR PDF files from Unity Catalog volumes, extract structured metadata fields from each PDF, normalize them using an LLM, enrich with IBAT / Event Vision lookup tables, and write the results to a unified metadata registry table.

### Input

#### Source Volumes

Files are read non-recursively from the following Unity Catalog volume paths:

| # | Volume Path | Catalog |
|---|-------------|---------|
| 1 | `/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports` | viud |
| 2 | `/Volumes/viud/ing_ud_fieldvision/fv_field_service_report` | viud |

#### File Types

- **Accepted:** `.pdf` files at the top level of each volume path
- **Skipped:** `.crdownload`, `.tmp`, `.part`, `.download`, `.DS_Store`, `.json`, `.txt`, `.csv`, `.xlsx`, and any sub-directories

#### Lookup / Enrichment Sources

| Source | Default Location | Purpose |
|--------|------------------|---------|
| IBAT Equipment | `vgpd.prm_std_views.ibat_equipment_mst` | ESN / equipment type enrichment |
| Event Vision SOT | `vgpd.fsr_std_views.eventmgmt_event_vision_sot` | Event / project ID enrichment |

### Unified Metadata Registry (Silver Table)

> **Architecture change:** The separate `fsr_file_registry` table has been removed. Discovery, status tracking, metadata, and chunk status are all unified into a single **metadata registry** table. `pdf_name` (the UUID filename stem) is the primary key.

**Table:** `{catalog}.{schema}.fsr_metadata_registry`

| Column | Type | Description |
|--------|------|-------------|
| `pdf_name` | STRING NOT NULL | **Primary key.** UUID filename stem — join key to `fsr_pdf_ref` |
| `volume_path` | STRING NOT NULL | Full `/Volumes/...` path to the source PDF |
| `title` | STRING | Title extracted from page-1 text |
| `customer` | STRING | Customer / site name |
| `esn` | STRING | Equipment Serial Number (resolved via precedence) |
| `esn_source` | STRING | How ESN was resolved: `llm` / `ibat` / `null` |
| `equipment_sys_id` | STRING | System ID from IBAT |
| `equipment_type` | STRING | Equipment type (e.g. Generator, Gas Turbine) |
| `equipment_code` | STRING | Equipment sub-class / code |
| `event_type` | STRING | Event type (e.g. Call-Out, Inspection) |
| `ev_project_id` | STRING | Event Vision project ID |
| `ev_equipment_event_id` | STRING | Event Vision equipment event ID |
| `ofs_event_id` | STRING | OFS event ID |
| `fsp_project_id` | STRING | FSP project ID |
| `project_id` | STRING | Additional project ID (pipe-separated if multiple) |
| `fsr_number` | STRING | FSR document number |
| `report_issued_date` | STRING | Date the FSR was issued — format: `YYYY-MM-DD` |
| `outage_start_date` | STRING | Outage start date — format: `YYYY-MM-DD` |
| `outage_end_date` | STRING | Outage end date — format: `YYYY-MM-DD` |
| `prepared_by` | STRING | Report author |
| `approved_by` | STRING | Report approver |
| `page_count` | INT | Number of pages in the PDF |
| `file_size_bytes` | LONG | File size in bytes |
| `file_last_modified` | TIMESTAMP | Last modified timestamp from volume listing |
| `metadata_status` | STRING NOT NULL | `pending` / `completed` / `failed` |
| `metadata_error` | STRING | Error message if metadata extraction failed |
| `metadata_retry_count` | INT | Number of extraction retry attempts |
| `metadata_version` | INT | Bumped when enrichment logic changes |
| `chunk_status` | STRING NOT NULL | `pending` / `completed` / `failed` |
| `chunk_error` | STRING | Error message if chunking failed |
| `ingested_at` | TIMESTAMP | When this row was first created |
| `scraped_at` | TIMESTAMP | When metadata scraping completed |
| `updated_at` | TIMESTAMP | Last modification timestamp |

### Processing Steps

#### Step 1 – Volume Scan & Stub Row Registration

1. Read `MAX(ingested_at)` from the metadata registry as a watermark (null on first run → scan all files)
2. Scan volumes via `dbutils.fs.ls`, filtering to `.pdf` files where `modificationTime > watermark`
3. Cap at `FSR_MAX_PDFS` if set (for dev/testing)
4. MERGE stub rows into the metadata registry:
   - **New file** (`pdf_name` not in table) → insert with `metadata_status = 'pending'`, `chunk_status = 'pending'`
   - **Re-uploaded file** (`pdf_name` exists) → reset both statuses to `pending`

#### Step 2 – PDF Field Extraction

1. Query registry: `WHERE metadata_status IN ('pending', 'failed') AND metadata_retry_count < max_retries`
2. Open each PDF with `pdfplumber`, extract title and key:value fields from page 1, record `page_count`
3. On extraction failure: record error, continue to next file

#### Step 3 – LLM Normalization

1. Send extracted fields to LLM in batches (default batch size: 4)
2. Model: `gemini-3-flash` via LiteLLM gateway (`https://dev-gateway.apps.gevernova.net`)
3. LLM normalizes fields to a fixed schema: ESN, dates → `YYYY-MM-DD`, project IDs, event types from allowed list
4. Map LLM response rows back to `pdf_name` via volume path

#### Step 4 – IBAT & Event Vision Enrichment

1. Load IBAT Equipment table: fill missing ESN, equipment_sys_id, equipment_type, equipment_code
2. Load Event Vision SOT table: fill missing event_type, outage dates
3. Track ESN provenance via `esn_source` column (`llm` if from LLM, `ibat` if filled from lookup)
4. Dedup by `pdf_name` after joins (lookups can multiply rows)
5. If enrichment tables are inaccessible, skip gracefully — LLM-only results are kept

#### Step 5 – Write Results

1. MERGE enriched records into the metadata registry: set all metadata columns + `metadata_status = 'completed'`
2. For failures (extraction or LLM errors): set `metadata_status = 'failed'`, increment `metadata_retry_count`, record `metadata_error`

**FORCE_RESET override:** Setting `FORCE_RESET = true` truncates the metadata table and re-scans all files from scratch.

**Retry behavior:** Files with `metadata_status = 'failed'` are automatically retried on the next run (up to `max_retries`).

---

## Process 2 – Chunking & Vector Embedding

### Purpose

Read FSR PDFs that have completed metadata extraction, parse and recursively chunk the full document content, generate vector embeddings, and write chunk rows to a Delta table backed by Databricks Vector Search.

### Input

#### Source Table (Process 1 Output)

Process 2 does **not** scan volumes directly. It reads from the metadata registry and processes only rows where `metadata_status = 'completed'` AND `chunk_status IN ('pending', 'failed')`.

The `volume_path` column is used to locate the physical PDF file. All metadata fields for enrichment are already in the same row.

> **Incremental by design:** Because Process 2 filters on chunk_status, re-running the job automatically picks up any new or previously failed files.

### Processing Steps

1. Query metadata registry for documents ready to chunk
2. For each document, use `volume_path` to open the PDF file via **PyMuPDF**
3. Extract full text from all pages, build a page-offset map for page tracking
4. Recursively split text into chunks using `langchain-text-splitters` (RecursiveCharacterTextSplitter)
   - Chunk size: 4000 chars, Overlap: 200 chars
   - Track `start_page` and `end_page` per chunk using character offset mapping
5. Generate vector embeddings via LiteLLM (`azure-text-embedding-3-large-1`, 3072 dimensions)
   - Batched: 32 chunks per API call
6. MERGE chunk rows to the Delta chunk table
7. Update metadata registry: `chunk_status = 'completed'` on success, `chunk_status = 'failed'` + `chunk_error` on failure
8. Trigger Databricks Vector Search index sync (DELTA_SYNC, TRIGGERED pipeline)

### Output

#### Chunk Delta Table (Gold)

**Table:** `{catalog}.{schema}.fsr_chunks`

| Column | Type | Description |
|--------|------|-------------|
| `chunk_id` | STRING NOT NULL | **Primary key.** `md5(pdf_name + "_" + chunk_index)` |
| `pdf_name` | STRING NOT NULL | FK to metadata registry (UUID filename) |
| `chunk_index` | INT NOT NULL | 0-based chunk position within document |
| `chunk_text` | STRING NOT NULL | Chunk content |
| `embedding` | ARRAY\<DOUBLE\> | Pre-computed embedding vector (3072 dimensions) |
| `title` | STRING | Materialized from metadata registry |
| `esn` | STRING | Materialized from metadata registry |
| `equipment_type` | STRING | Materialized from metadata registry |
| `event_type` | STRING | Materialized from metadata registry |
| `report_issued_date` | STRING | Materialized from metadata registry |
| `page_count` | INT | Materialized from metadata registry |
| `chunk_count` | INT | Total chunks in this document |
| `start_page` | INT | First page this chunk spans |
| `end_page` | INT | Last page this chunk spans |
| `chunk_size` | INT | Character length of chunk_text |
| `ingested_at` | TIMESTAMP | When this chunk row was written |

> **Schema change:** Metadata is now **materialized as first-class columns** on the chunk table, not serialized into a JSON blob. This enables direct column filtering in Vector Search without JSON parsing.

#### Vector Search Index

**Index:** `{catalog}.{schema}.vs_fsr_chunks`

- **Endpoint:** `pw-ser-sdg-vector-search`
- **Type:** DELTA_SYNC (triggered pipeline)
- **Source table:** chunk table above
- **Embedding column:** `embedding`
- **Primary key:** `chunk_id`

---

## Key Differences from Previous Design

| Area | Previous Design | Current Implementation |
|------|----------------|----------------------|
| **File registry** | Separate `fsr_file_registry` table with volume_path PK | Eliminated — unified into metadata registry table with `pdf_name` PK |
| **Primary key** | `volume_path` (file registry) / none clear (metadata) | `pdf_name` (UUID filename stem) across both tables |
| **Discovery** | Watermark on `MAX(discovered_at)` from registry | Watermark on `MAX(ingested_at)` from metadata table |
| **Status columns** | `scraped` + `processed` / `error` / `error_reason` | `metadata_status` + `metadata_error` + `metadata_retry_count` + `chunk_status` + `chunk_error` |
| **Retry tracking** | No retry count | `metadata_retry_count` with configurable max (default 3) |
| **Metadata table** | Flat output: title through ingestion_timestamp | Extended: adds `page_count`, `file_size_bytes`, `file_last_modified`, `esn_source`, `metadata_version`, audit timestamps |
| **Chunk schema** | `chunk_id`, `chunk_text`, `embedding`, `metadata` (JSON blob) | 16 materialized columns — no JSON; includes `start_page`, `end_page`, `chunk_size`, `chunk_count` |
| **Embedding type** | `ARRAY<FLOAT>` | `ARRAY<DOUBLE>` |
| **PDF extraction** | pdfplumber (P1 + P2) | pdfplumber (P1 page-1 only), PyMuPDF (P2 full text) |
| **Page tracking** | `page_number` in metadata JSON | `start_page` / `end_page` per chunk via character offset mapping |
| **DDL** | No explicit DDL step | Separate DDL notebook runs first in workflow |
| **Validation** | None | Dedicated validation notebook with 23 automated checks |
| **Compute** | Not specified | Databricks Serverless |

---

## Configuration

All parameters are configurable via job parameters (widgets) or environment variables. Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FSR_METADATA_TABLE` | `main.gp_services_sdg_poc.fsr_metadata_registry` | Metadata registry table |
| `FSR_CHUNK_TABLE` | `main.gp_services_sdg_poc.fsr_chunks` | Chunk table |
| `FSR_VS_INDEX` | `main.gp_services_sdg_poc.vs_fsr_chunks` | Vector Search index |
| `FSR_LLM_MODEL` | `gemini-3-flash` | LLM model for normalization |
| `FSR_EMBEDDING_MODEL` | `azure-text-embedding-3-large-1` | Embedding model |
| `FSR_EMBEDDING_DIMENSION` | `3072` | Embedding vector dimension |
| `FSR_BATCH_SIZE` | `4` | PDFs per LLM batch |
| `FSR_MAX_PDFS` | (unlimited) | Cap for dev/testing |
| `FORCE_RESET` | `false` | Truncate and re-process everything |
| `LITELLM_API_KEY` | (secret scope / job param) | LLM gateway API key |

---

## Open Items / To Be Confirmed

- [ ] Production table naming: `vaid.ai_sot_field_service_report.*` vs current POC schema
- [ ] `prepared_by` / `approved_by` extraction accuracy — not yet validated
- [ ] LLM-generated document summary in metadata
