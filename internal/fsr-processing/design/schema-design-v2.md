# FSR Pipeline — Schema Design v2

> **Date:** 2026-04-20  
> **Status:** Agreed with Pranesh (pending Abhijit review on chunk table)  
> **Supersedes:** Unified schema proposal v1 (internal/comms/tues-apr-20/unified-metadata-schema-proposal.md)

---

## Changes from v1 (Pranesh review, Apr 20)

| # | Change | Rationale |
|---|--------|-----------|
| 1 | **`document_id` removed** — `pdf_name` (UUID) is the primary key and MERGE key | Pranesh confirmed pdf_name is the FieldVision UUID and is unique across files. Eliminates the synthetic hash. |
| 2 | **`source_volume` removed** from both metadata and chunk tables | Redundant with `volume_path` which already identifies which volume the file came from. |
| 3 | **Status values simplified** to 3 states: `pending` / `completed` / `failed` | Applies to both `metadata_status` and `chunk_status`. `ok` → `completed`. `skipped` and `processing` dropped. Processing state is tracked in Airflow/Databricks logs only, not in the table. |
| 4 | **`scraped_at` added** — TIMESTAMP for when metadata scraping completed | Distinct from `ingested_at` (row creation) and `updated_at` (last modification). |
| 5 | **`prepared_by` kept** but flagged for verification | Not confirmed for removal — unclear what it maps to in the PDFs. Test output didn't populate it. Needs further checking. |
| 6 | **`customer` added** back to DDL | Was in Pranesh's original schema; now explicitly included as nullable. |

---

## Metadata Registry Table

**Table:** `biz_metadata_field_service_report`  
**Primary key:** `pdf_name`

| Column | Type | Description |
|--------|------|-------------|
| `pdf_name` | STRING NOT NULL | UUID filename — primary key, join key to fsr_pdf_ref |
| `volume_path` | STRING NOT NULL | Full /Volumes/... path to the source PDF |
| `title` | STRING | Title extracted from page-1 text |
| `customer` | STRING | Customer / site name (nullable) |
| `esn` | STRING | Equipment Serial Number (resolved via precedence) |
| `esn_source` | STRING | How ESN was resolved: sot / llm / regex / null |
| `equipment_sys_id` | STRING | System ID from IBAT |
| `equipment_type` | STRING | Equipment type |
| `equipment_code` | STRING | Equipment sub-class / code |
| `event_type` | STRING | Event type |
| `ev_project_id` | STRING | Event Vision project ID |
| `ev_equipment_event_id` | STRING | Event Vision equipment event ID |
| `ofs_event_id` | STRING | OFS event ID |
| `fsp_project_id` | STRING | FSP project ID |
| `xxx_project_id` | STRING | XXX project ID |
| `fsr_number` | STRING | FSR document number |
| `report_issued_date` | STRING | YYYY-MM-DD normalized |
| `outage_start_date` | STRING | YYYY-MM-DD normalized |
| `outage_end_date` | STRING | YYYY-MM-DD normalized |
| `prepared_by` | STRING | Report author (nullable — needs verification) |
| `approved_by` | STRING | Report approver (nullable) |
| `page_count` | INT | Number of pages in the PDF |
| `file_size_bytes` | LONG | File size in bytes |
| `file_last_modified` | TIMESTAMP | Last modified timestamp from volume listing |
| `metadata_status` | STRING NOT NULL | pending / completed / failed |
| `metadata_error` | STRING | Error message if metadata_status = failed |
| `metadata_retry_count` | INT | Number of extraction retry attempts |
| `metadata_version` | INT | Bump when enrichment logic changes |
| `chunk_status` | STRING NOT NULL | pending / completed / failed |
| `chunk_error` | STRING | Error message if chunk_status = failed |
| `ingested_at` | TIMESTAMP | When this row was first created |
| `scraped_at` | TIMESTAMP | When metadata scraping completed |
| `updated_at` | TIMESTAMP | Last modification timestamp |

**Total: 32 columns**

---

## Chunk Table

**Table:** `biz_chunk_field_service_report`  
**Primary key:** `chunk_id`  
**Foreign key:** `pdf_name` → metadata registry

| Column | Type | Description |
|--------|------|-------------|
| `chunk_id` | STRING NOT NULL | Hash of pdf_name + chunk_index |
| `pdf_name` | STRING NOT NULL | FK to metadata registry (UUID filename) |
| `chunk_index` | INT NOT NULL | 0-based chunk position within document |
| `chunk_text` | STRING NOT NULL | Chunk content |
| `embedding` | ARRAY\<DOUBLE\> | Pre-computed embedding vector (3072-dim) |
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

**Total: 16 columns**

> **Note:** Abhijit suggested chunk table should only have chunk_text + embedding as top-level columns, with all metadata in a metadata column. Pranesh to finalize with Abhijit — this may change the chunk table structure. See open question #3 below.

---

## Open Design Questions

### 1. Same PDF in two volumes

If the same UUID exists in two different volumes, `pdf_name` as PK means only one row in the metadata table. Options:

- **Accept it:** If the PDF content is identical, one row is correct. The `volume_path` just records whichever was ingested first.
- **Composite key:** Use `(pdf_name, volume_path)` if both copies need separate tracking. This ripples into the chunk table FK.
- **Recommendation:** Confirm with Pranesh whether this scenario actually occurs. If not, park it.

### 2. `prepared_by` — keep or drop?

Neither our test output nor Pranesh's original schema had clear data for this field. It was discussed but no decision was made. Need to:

- Check if the LLM normalization prompt extracts it
- Check if any downstream consumer (app, reporting) uses it
- If unused, remove to simplify schema

### 3. Chunk table structure — flat columns vs metadata column

Abhijit told Pranesh the vector store should have just `chunk_text` + `embedding`, with everything else as a single metadata column (JSON or struct). Our current design materializes metadata as top-level columns.

Trade-offs:

| Approach | Pros | Cons |
|----------|------|------|
| **Top-level columns** (current) | SQL filter pushdown, simpler queries, VS metadata filter support | More columns to maintain, schema changes need DDL migration |
| **Metadata column** (Abhijit) | Flexible schema, cleaner vector table | No pushdown, harder to filter in VS, need to parse JSON |

**Pending:** Pranesh to confirm with Abhijit. If VS filtering on metadata is needed (it is for the app), top-level columns are better.

### 4. `approved_by` — same question as `prepared_by`

Pranesh explicitly discussed removing `prepared_by` (unclear), but didn't mention `approved_by`. Likely same situation — needs verification.

### 5. Dead-letter / skip logic

With only 3 statuses (no `skipped`), what happens after max retries? Options:

- Keep retrying forever (metadata_retry_count just for observability)
- Add `skipped` back as a terminal state for dead-lettered rows
- Use a threshold check in code: if `metadata_retry_count >= N`, skip in the SELECT

Current implementation uses the threshold check approach — no schema change needed.

### 6. `document_summary` (deferred to v2)

Both sides agreed this is not needed for v1. Can be added as nullable column without schema break. Would be generated in P1 (LLM call on full text) and materialized into chunks in P2.
