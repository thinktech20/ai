# Unified Metadata Table Schema — Proposal

**Date:** 2026-04-20  
**Table:** `biz_metadata_field_service_report`  
**Context:** Consolidates Pranesh's metadata table + file registry into a single table, with additions from Madhurima's implementation testing.

---

## Column-Level Schema

| # | Column | Type | Pranesh | Madhurima | Status | Reason for Change |
|---|--------|------|---------|-----------|--------|-------------------|
| 1 | `document_id` | STRING NOT NULL | — | Added | **NEW** | Deterministic MERGE key (`SHA-256(volume_path)[:16]`). Enables upsert for re-uploaded files and crash recovery instead of append-only writes. |
| 2 | `volume_path` | STRING NOT NULL | ✓ | ✓ | **Unchanged** | — |
| 3 | `pdf_name` | STRING | ✓ | ✓ | **Unchanged** | — |
| 4 | `title` | STRING | ✓ | ✓ | **Unchanged** | — |
| 5 | `customer` | STRING | ✓ | ✓ | **Unchanged** | Nullable — populated when extractable, null otherwise. |
| 6 | `esn` | STRING | ✓ | ✓ | **Unchanged** | — |
| 7 | `esn_source` | STRING | — | Added | **NEW** | Tracks how ESN was resolved: `sot` / `llm` / `regex` / `null`. Useful for debugging ESN quality and establishing field precedence. |
| 8 | `equipment_sys_id` | STRING | ✓ | ✓ | **Unchanged** | — |
| 9 | `equipment_type` | STRING | ✓ | ✓ | **Unchanged** | — |
| 10 | `equipment_code` | STRING | ✓ | ✓ | **Unchanged** | — |
| 11 | `event_type` | STRING | ✓ | ✓ | **Unchanged** | — |
| 12 | `ev_project_id` | STRING | ✓ | ✓ | **Unchanged** | — |
| 13 | `ev_equipment_event_id` | STRING | ✓ | ✓ | **Unchanged** | — |
| 14 | `ofs_event_id` | STRING | ✓ | ✓ | **Unchanged** | — |
| 15 | `fsp_project_id` | STRING | ✓ | ✓ | **Unchanged** | — |
| 16 | `xxx_project_id` | STRING | ✓ | ✓ | **Unchanged** | — |
| 17 | `fsr_number` | STRING | ✓ | ✓ | **Unchanged** | — |
| 18 | `report_issued_date` | STRING | ✓ | ✓ | **Unchanged** | — |
| 19 | `outage_start_date` | STRING | ✓ | ✓ | **Unchanged** | — |
| 20 | `outage_end_date` | STRING | ✓ | ✓ | **Unchanged** | — |
| 21 | `prepared_by` | STRING | ✓ | ✓ | **Unchanged** | Nullable — also passed into chunk metadata by Process 2. |
| 22 | `approved_by` | STRING | ✓ | ✓ | **Unchanged** | Nullable — same as `prepared_by`. |
| 23 | `page_count` | INT | — | Added | **NEW** | Captured during PDF extraction at no extra cost. Helps Process 2 estimate chunk counts and filter unusually large/small files. |
| 24 | `source_volume` | STRING | — | Added | **NEW** | Records which volume a file came from. Useful for monitoring and debugging across 17K+ files in multiple volumes. |
| 25 | `file_size_bytes` | LONG | — | Added | **NEW** | Enables filtering empty/corrupt files and capacity monitoring. Available from `dbutils.fs.ls` at discovery time. |
| 26 | `file_last_modified` | TIMESTAMP | In file registry | Absorbed | **Moved here** | Originally in the file registry table as `last_modified`. Consolidated into one table to avoid maintaining two tables with overlapping status tracking. Powers watermark-based incremental detection. |
| 27 | `metadata_status` | STRING NOT NULL | — | Added | **Evolved from `processed`** | Separates Process 1 (metadata) and Process 2 (chunking) status into independent columns. This way each process can track and retry its own work without ambiguity. Values: `pending` / `ok` / `failed` / `skipped`. |
| 28 | `metadata_error` | STRING | — | Added | **Evolved from `error` + `error_reason`** | Dedicated error field for metadata extraction failures. Splitting by phase makes it clear which step failed and what needs retrying. |
| 29 | `metadata_retry_count` | INT | — | Added | **NEW** | Tracks how many times extraction was attempted. Enables dead-letter logic: after N failures, mark as `skipped` so the pipeline doesn't retry indefinitely. |
| 30 | `metadata_version` | INT | — | Added | **NEW** | Version stamp for the enrichment logic that produced the row. Supports re-processing when enrichment logic changes (e.g. new IBAT fields, updated LLM prompt). |
| 31 | `chunk_status` | STRING NOT NULL | — | Added | **Evolved from `processed`** | Process 2 reads `chunk_status = pending` to find its work, independent of whether metadata extraction succeeded or failed. Values: `pending` / `processing` / `completed` / `failed`. |
| 32 | `chunk_error` | STRING | — | Added | **Evolved from `error` + `error_reason`** | Dedicated error field for chunking/embedding failures. Same rationale as `metadata_error` — phase-specific tracking. |
| 33 | `ingested_at` | TIMESTAMP | was `ingestion_timestamp` | Renamed | **Renamed** | Shorter name, consistent with `updated_at`. Same purpose: when the row was first created. Also serves as watermark source for incremental detection. |
| 34 | `updated_at` | TIMESTAMP | was `scraped_at` in registry | Absorbed | **Moved here** | Originally `scraped_at` in the file registry. Tracks when the row was last modified by either process. Consolidated into one table per ADR-007. |

---

## Columns Consolidated or Deferred

| Original Column | What Happened | Reasoning |
|---|---|---|
| `processed` | Split → `metadata_status` + `chunk_status` | Since Process 1 and Process 2 run as separate jobs, each needs its own status column to track and retry independently. |
| `error` + `error_reason` | Split → `metadata_error` + `chunk_error` | One error field per phase avoids ambiguity about which step failed. Two fields (`error` + `error_reason`) consolidated to one per phase since a single message is sufficient. |
| `ingestion_timestamp` | Renamed → `ingested_at` | Shorter, pairs naturally with `updated_at`. No functional change. |
| `fsr_file_registry` table | Absorbed into this table | one table instead of two avoids duplicated status tracking and extra I/O. The registry columns (`last_modified`, `scraped_at`, `discovered_at`) map to `file_last_modified`, `updated_at`, `ingested_at`. |
| `document_summary` | Deferred to v2 | Both sides agree this is not needed for v1. Can be added later as a nullable column without a schema break. |

---

## Summary

- **18 columns unchanged** — all core metadata fields carry over as-is
- **2 columns absorbed** from file registry into this table 
- **4 columns evolved** — better granularity for two-process status tracking
- **7 columns new** — operational: merge key, provenance, retry, versioning, file stats
- **1 column deferred** — `document_summary` (both agree not v1)
- **Net: 34 columns in 1 table** vs 24 + 7 across 2 tables previously
