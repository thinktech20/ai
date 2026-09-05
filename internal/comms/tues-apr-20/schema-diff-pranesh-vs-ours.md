# Schema Diff — Pranesh's Table vs Our Metadata Registry

**Date:** 2026-04-20  
**Pranesh's table:** `biz_metadata_field_service_report` (created in POC schema, no records yet)  
**Our table:** `fsr_metadata_registry` (tested as `_test` suffix, 10 records validated)

---

## Column-Level Diff

| Column | Pranesh | Ours | Notes |
|---|---|---|---|
| `document_id` | — | Added (PK) | SHA-256 of volume_path (16 hex chars). Needed for deterministic MERGE key (ADR-007) |
| `title` | yes | yes | Same |
| `customer` | yes | Removed | Not reliably extracted, not needed for retrieval |
| `esn` | yes | yes | Same |
| `esn_source` | — | Added | Tracks how ESN was resolved: `llm` / `ibat` / `sot` / `null` |
| `equipment_sys_id` | yes | yes | Same |
| `equipment_type` | yes | yes | Same |
| `equipment_code` | yes | yes | Same |
| `event_type` | yes | yes | Same |
| `ev_project_id` | yes | yes | Same |
| `ev_equipment_event_id` | yes | yes | Same |
| `ofs_event_id` | yes | yes | Same |
| `fsp_project_id` | yes | yes | Same |
| `project_id` / `xxx_project_id` | `project_id` | `xxx_project_id` | Renamed to match DS-team LLM prompt field name |
| `fsr_number` | yes | yes | Same |
| `report_issued_date` | yes | yes | Same |
| `outage_start_date` | yes | yes | Same |
| `outage_end_date` | yes | yes | Same |
| `prepared_by` | yes | Removed | Not needed for retrieval pipeline |
| `approved_by` | yes | Removed | Not needed for retrieval pipeline |
| `document_summary` | yes (LLM) | Removed | Expensive per-doc LLM call, not needed for metadata registry |
| `pdf_name` | yes | yes | Same — bare filename / GUID stem |
| `volume_path` | yes | yes | Same — full `/Volumes/...` path |
| `processed` | yes (null/completed/failed) | Removed | Replaced by split status columns below |
| `metadata_status` | — | Added | `pending` / `ok` / `failed` / `skipped` |
| `chunk_status` | — | Added | `pending` / `processing` / `completed` / `failed` |
| `error` | yes | Removed | Replaced by phase-specific error columns |
| `error_reason` | yes | Removed | Replaced by phase-specific error columns |
| `metadata_error` | — | Added | Error message if metadata extraction failed |
| `chunk_error` | — | Added | Error message if chunking failed |
| `metadata_retry_count` | — | Added | Enables retry logic + dead-letter after N failures |
| `metadata_version` | — | Added | Bump when enrichment logic changes |
| `page_count` | — | Added | Useful for doc-type heuristics + chunk estimation |
| `source_volume` | — | Added | Track which volume the file came from |
| `file_size_bytes` | — | Added | Useful for monitoring/filtering |
| `file_last_modified` | — | Added | Watermark source — `modificationTime` from `dbutils.fs.ls` |
| `ingestion_timestamp` | yes (single) | Split into `ingested_at` + `updated_at` | Stub rows need creation time separate from last-update time |

---

## Architectural Differences

### 1. No separate file registry (ADR-007)

Pranesh proposed a separate `fsr_file_registry` table to track discovered files before scraping. We chose **stub rows in the same metadata table** instead.

- No duplicated status tracking across two tables
- No extra I/O hop (write to registry → read back → write to metadata)
- Single source of truth for "which files exist and what's their state"
- One less table to manage (schema, permissions, monitoring)

See: `internal/adr/ADR-007-file-registry-stub-rows.md`

### 2. Two-phase status tracking

Pranesh used a single `processed` column (null/completed/failed). We split into `metadata_status` and `chunk_status` because:

- Process 1 (metadata) and Process 2 (chunking) run as separate workflow tasks
- A file can succeed at metadata extraction but fail at chunking
- Process 2 reads `chunk_status = pending` to find its work — independent of metadata status

### 3. MERGE not append

Pranesh's design appends rows. Ours uses `MERGE INTO ... ON document_id` because:

- Re-uploaded files (same path, new content) get their metadata reset
- Failed files stay in the table and get retried on next run
- Crash recovery: stub rows persist even if extraction fails mid-batch
- `document_id = SHA-256(volume_path)` is the deterministic merge key

### 4. Leaner schema

Removed `customer`, `prepared_by`, `approved_by`, `document_summary`:
- `customer` is not reliably present on page 1
- `prepared_by` / `approved_by` are not used by the retrieval pipeline
- `document_summary` would require a separate LLM call per document — expensive and not needed for metadata registry (summaries can be generated at query time if needed)

### 5. Richer operational columns

Added `metadata_retry_count`, `metadata_version`, `file_size_bytes`, `file_last_modified`, `source_volume` for production ops: retry logic, version tracking, monitoring, and watermark support.

---

## References

- ADR-007: `internal/adr/ADR-007-file-registry-stub-rows.md`
- Tao review: `internal/comms/tues-apr-20/tao-review-findings.md`
- Our DDL: `implementation/fsr-processing/code/fsr_config.py` → `METADATA_TABLE_DDL_COLS`
- Pranesh's design: `internal/comms/tues-apr-20/scraping+chunking-design-pranesh.pdf`
