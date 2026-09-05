# FSR Pipeline – Design Document (Draft)

> **Status:** Draft v0.1 · April 17 2026  
> **Author:** Pranesh

---

## Overview

This document describes the two core processes that together form the FSR (Field Service Report) data pipeline:

1. **Process 1 – Scraping & Metadata Extraction** 
2. **Process 2 – Chunking & Vector Embedding** 

Both processes run on Databricks and operate on the same set of PDF source volumes.

---

## Process 1 – Scraping & Metadata Extraction

### Purpose
Scan FSR PDF files from Unity Catalog volumes, extract structured metadata fields from each PDF, normalise them using an LLM, enrich with IBAT / Event Vision lookup tables, and write the results to a table.

### Input

#### Source Volumes
Files are read non-recursively from the following Unity Catalog volume paths:

| # | Volume Path | Catalog |
|---|-------------|---------|
| 1 | `/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports` | `viud` |
| 2 | `/Volumes/viud/ing_ud_fieldvision/fv_field_service_report` | `viud` |

> **Volume paths are configurable** (Tao review, Apr 2026)  
> Volume paths are parameterized at runtime (via job `base_parameters`), not hard-coded. Additional paths may be added without code changes — e.g. `/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/UAT_Files/` for UAT documents or ad-hoc uploads.

#### File Types
- **Accepted:** `.pdf` files at the top level of each volume path
- **Skipped:** `.crdownload`, `.tmp`, `.part`, `.download`, `.DS_Store`, `.json`, `.txt`, `.csv`, `.xlsx`, and any sub-directories

#### Lookup / Enrichment Sources
| Source | Default Location | Purpose |
|--------|-----------------|---------|
| IBAT Equipment | `vgpd.prm_std_views.ibat_equipment_mst` | ESN / equipment type enrichment |
| Event Vision SOT | `vgpd.fsr_std_views.eventmgmt_event_vision_sot` | Event / project ID enrichment |

### New File Detection (Watermark-based Incremental Logic)

With ~20,000 files on the volumes, scanning and diffing the full file list on every run is too expensive. Instead, Process 1 will use a **watermark** derived from the output table itself.

**How it works:**

1. **Read the watermark** — At the start of each run, query `MAX(ingestion_timestamp)` from the output table. This is the point-in-time of the last successful scrape run.
2. **Scan only new files** — Call the dbutils.fs.ls /Databricks Files API with a filter: only return files whose `last_modified` timestamp is **greater than** the watermark. 
3. **Process new files only** — Only the filtered files are passed through extraction, LLM normalisation, and enrichment steps.
4. **Write & stamp** — Append new rows to the output table, each stamped with `ingestion_timestamp = current_timestamp()`. This automatically advances the watermark for the next run.

```
watermark = MAX(ingestion_timestamp) from output table
new files  = volume files where last_modified > watermark
```

**Result:** Each Airflow-triggered run only touches files that are genuinely new since the last run.

> **Fallback: path-based diff** (Tao review, Apr 2026)  
> The Files API / `dbutils.fs.ls` may not expose `last_modified` timestamps for all volume types. If timestamps are unavailable or unreliable, Process 1 falls back to a **path-based diff**: collect the set of `volume_path` values already in the metadata registry and only process PDFs whose full path is not yet present. This is slightly more expensive (requires reading the existing path set) but does not depend on file-system timestamps. 

> **First run / empty table:** When the output table is empty, `MAX(ingestion_timestamp)` returns `null`. In this case Process 1 falls back to processing all files on the volume (full bootstrap).

> **`FORCE_RESET` override:** Setting `FORCE_RESET = true` bypasses the watermark, truncates the output table, and reprocesses every file from scratch. Use only when a full re-scrape is explicitly needed (e.g. after a schema change or LLM prompt update).

### Processing Steps (high-level)
1. Read `MAX(ingested_at)` from the metadata table as the watermark (null = first run)
2. Call `dbutils.fs.ls` for each volume, filtering to files with `modificationTime > watermark` (epoch ms)
3. **MERGE stub rows** into the metadata table for every candidate file — set `metadata_status = pending`, `chunk_status = pending`. Matched rows (re-uploads) get `metadata_status` reset to `pending`. *(See [ADR-007](../../adr/ADR-007-file-registry-stub-rows.md) — stub rows replace a separate file registry table.)*
4. Select all rows where `metadata_status IN (pending, failed)` — this picks up both newly discovered files *and* files that failed on a previous run
5. Extract key-value fields and title from page 1 of each PDF
6. Send extracted text to LLM for field normalisation (model: `gemini-3-flash` by default)
7. Enrich normalised records with IBAT and Event Vision lookups
8. **On success:** update the row — populate all metadata fields, set `metadata_status = ok`, `ingested_at = current_timestamp()`
9. **On failure:** update the row — set `metadata_status = failed`, populate `metadata_error`, increment `metadata_retry_count`. The row will be retried on the next run (step 4). Dead-letter after N retries (`metadata_retry_count >= max_retries` → `metadata_status = skipped`).

### Output

#### Output Table
`vaid/vaiq/vaip.ai_sot_field_service_report.biz_metadata_field_service_report` 

#### Schema

| Column | Type | Description |
|--------|------|-------------|
| `title` | STRING | Report title extracted from the PDF |
| `customer` | STRING | Customer / site name |
| `esn` | STRING | Equipment Serial Number |
| `equipment_sys_id` | STRING | System ID from IBAT |
| `equipment_type` | STRING | Equipment type (e.g. Generator, Gas Turbine) |
| `equipment_code` | STRING | Equipment sub-class / code (lookup – reliability TBC) |
| `event_type` | STRING | Event type (e.g. Call-Out, Inspection) |
| `ev_project_id` | STRING | Event Vision project ID (lookup) |
| `ev_equipment_event_id` | STRING | Event Vision equipment event ID (lookup) |
| `ofs_event_id` | STRING | OFS event ID (lookup – validate with SMEs) |
| `fsp_project_id` | STRING | FSP project ID |
| `xxx_project_id` | STRING | Additional project ID field (pipe-separated if multiple) |
| `fsr_number` | STRING | FSR document number (lookup) |
| `report_issued_date` | STRING | Date the FSR was issued — **format: YYYY-MM-DD** |
| `outage_start_date` | STRING | Outage start date — **format: YYYY-MM-DD** |
| `outage_end_date` | STRING | Outage end date — **format: YYYY-MM-DD** |
| `prepared_by` | STRING | Name of the person who prepared the report |
| `approved_by` | STRING | Name of the person who approved the report |
| `pdf_name` | STRING | Bare filename or UUID stem (e.g. `00576c50-5466-41a7-af6d-070c903e5cbd`). For FieldVision PDFs this is the `s3_filename` GUID used by the download endpoint (`/fsr/pdf/{uuid}`) and as the join key to `fsr_pdf_ref.s3_filename`. For manual/Box uploads this is the human-readable filename without extension. |
| `volume_path` | STRING | Full volume path to the source PDF file (e.g. `/Volumes/viud/ing_ud_fieldvision/.../00576c50-...pdf`). Used by Process 2 to locate the physical file. Distinct from `pdf_name` — `volume_path` is always the full path, `pdf_name` is the bare identifier. |
| `processed` | STRING | Chunking status: `null`/empty = not yet processed, `yes` = chunked successfully, `failed` = chunking failed |
| `error` | STRING | Short error type / code if chunking failed, otherwise null |
| `error_reason` | STRING | Full error message / stack trace if chunking failed, otherwise null |
| `ingestion_timestamp` | TIMESTAMP | When this row was written by Process 1 — used as the watermark for incremental detection on the next run |

> **Date format:** All date columns must be normalised to `YYYY-MM-DD` (ISO 8601) during the LLM normalisation step, regardless of how they appear in the source PDF.

---

## Process 2 – Chunking & Vector Embedding

### Purpose
Read FSR PDFs from the same volumes, parse and recursively chunk the full document content, generate vector embeddings, and write chunk rows to a Delta table backed by Databricks Vector Search.

### Input

#### Source Table (Process 1 Output)
Process 2 does **not** scan volumes directly. It reads from the Process 1 output table and processes only rows where `processed` is `null`, empty, or `no`.

| Table | Purpose |
|-------|---------|
| `vaid/vaiq/vaip.ai_sot_field_service_report.biz_metadata_field_service_report` | Provides both the `volume_path` to locate each PDF and all metadata fields for enrichment |

The `volume_path` column on each row is used to load the physical PDF file from the volume. No separate volume scan or enrichment table is required — all metadata is already available in the source table row.

> **Incremental by design:** Because Process 2 filters on `processed` status, re-running the job automatically picks up any new or previously failed files without any additional configuration.

### Processing Steps (high-level)
1. Read all rows from the Process 1 metadata table where `processed` is `null`, empty, or `no`
2. For each row, use `volume_path` to load the PDF file from the Unity Catalog volume
3. Extract full text from the PDF using `PyMuPDF`
4. Recursively split text into chunks (`langchain-text-splitters`, recursive strategy)
5. Denormalise metadata from the source row onto every chunk (no additional lookup needed)
6. Generate vector embeddings via LiteLLM (`azure-text-embedding-3-large-1`)
7. Write chunk rows to the Delta chunk table
8. Sync Delta table to Databricks Vector Search index
9. **On success:** update the source row — set `processed = 'yes'`, clear `error` and `error_reason`
10. **On failure:** update the source row — set `processed = 'failed'`, populate `error` and `error_reason`; the row will be retried on the next run

### Output

#### Output Delta Table
`vaid/vaiq/vaip.ai_std_con_field_service_report.vec_field_service_report`  

#### Output Vector Search Index
`vaid/vaiq/vaip.ai_std_con_field_service_report.vs_vec_field_service_report`  

#### Chunk Row Schema


| Column | Type | Description |
|--------|------|-------------|
| `chunk_id` | STRING | **Primary key.** Unique identifier per chunk — generated as `md5(pdf_name + chunk_index)` |
| `chunk_text` | STRING | Plain text content of the chunk |
| `embedding` | ARRAY\<FLOAT\> | Dense vector — generated by the configured embedding model (`azure-text-embedding-3-large-1`) |
| `metadata` | STRING (JSON) | All contextual fields serialised as a JSON object — see metadata fields below |

#### `metadata` JSON Fields

All fields below are written into the `metadata` column as a single JSON object at chunking time, sourced directly from the Process 1 output table row:

| Field | Description |
|-------|-------------|
| `pdf_name` | Source PDF file name / identifier |
| `page_number` | Page number within the PDF where this chunk originates |
| `title` | Report title |
| `customer` | Customer / site name |
| `esn` | Equipment Serial Number |
| `equipment_sys_id` | System ID from IBAT |
| `equipment_type` | Equipment type (e.g. Generator, Gas Turbine) |
| `equipment_code` | Equipment sub-class / code |
| `event_type` | Event type (e.g. Call-Out, Inspection) |
| `ev_project_id` | Event Vision project ID |
| `ev_equipment_event_id` | Event Vision equipment event ID |
| `ofs_event_id` | OFS event ID |
| `fsp_project_id` | FSP project ID |
| `xxx_project_id` | Additional project ID (pipe-separated if multiple) |
| `fsr_number` | FSR document number |
| `report_issued_date` | Date the FSR was issued (`YYYY-MM-DD`) |
| `outage_start_date` | Outage start date (`YYYY-MM-DD`) |
| `outage_end_date` | Outage end date (`YYYY-MM-DD`) |
| `prepared_by` | Name of the person who prepared the report |
| `approved_by` | Name of the person who approved the report |


---


## Open Items / To Be Confirmed

- [ ] Confirm final values for `processed` status flags (`yes` / `failed` / null — or use an enum/boolean?)
- [ ] Decide whether `processed` is updated row-by-row during a run or in a batch at the end
- [ ] Confirm volume paths for UAT / PROD environments
- [ ] Define retry limit — should rows that have failed N times be excluded from future runs?
- [x] **Re-uploaded files — resolved (Tao review, Apr 2026):** Process 1 uses **MERGE (upsert) by `document_id`** (deterministic SHA-256 of `volume_path`). When a file is re-uploaded at the same path, the existing row is updated in place and `chunk_status` is reset to `pending`, which triggers Process 2 to re-chunk. This avoids orphan chunks in the vector index from the old version. Append mode is not used because it would leave stale chunk rows pointing to an outdated document version.
- [ ] **LLM-generated document summary in `metadata`:** Evaluate adding a `document_summary` field inside the `metadata` JSON column of the chunk table. The summary would be generated once per document (not per chunk) by an LLM during Process 2, describing the overall FSR content (e.g. "FSR report on ESN 338X424 covering a 12-month outage — combustion inspection findings and bearing replacement"). Key decisions needed: which LLM/prompt to use, which page(s) to summarise from, and whether the summary is stored on all chunks of a document or only the first chunk.
- [ ] **Equipment type filter — configurable pre-filter (Tao review, Apr 2026):** Current use case (Risk Assessment for Generator) assumes Generator-only FSRs, but the metadata table ingests all equipment types from the volumes. Decide: (a) should Process 1 filter to Generator equipment type only (via IBAT `equipment_type`) at ingestion time, or (b) should the table store all equipment types and let the query/app layer apply the filter? If (b), ensure `equipment_type` is materialized in chunk rows so Vector Search pre-filters can be applied at query time. Recommend (b) for flexibility — the same pipeline can serve future use cases (e.g. Gas Turbine risk assessments) without re-ingestion.
