# Monday Architect Meeting — Discussion Notes

> Date: April 21, 2026
> Topic: Metadata-first FSR pipeline architecture
> Reference diagram: `architecture-assets/fsr-processing/metadata-first-end-to-end-flow.drawio`

---

## 1. Watermark Reliability

`last_modified` from `dbutils.fs.ls` may not be reliable for incremental detection. File copies into volumes can preserve the original timestamp, meaning a newly added file could look "old" and get skipped.

**Ask**: Do we need a diff-based fallback (e.g., compare file list against registered `volume_path` values in the metadata table) in addition to the timestamp watermark? Or is timestamp good enough for the source volumes we're targeting?

---

## 2. Extraction Gaps

The current scraping code does not yet extract: `customer`, `prepared_by`, `approved_by`, `page_count`.

These fields appear in the recommended metadata schema. Extraction sources would be a mix of page-1 text, file attributes, LLM extraction, and possibly IBAT/EV enrichment.

**Ask**: Which of these are must-haves for the first production iteration vs. can be backfilled later? `customer` seems high-value for retrieval filtering. `page_count` is low-effort (file attribute). `prepared_by` / `approved_by` may be lower priority.

---

## 3. Separate Metadata Tables per Document Type

Proposal: instead of a single metadata table with a `document_type` column, use one table per document type:
- `biz_metadata_field_service_report`
- `biz_metadata_engineering_report`
- etc.

The table name *is* the type. This removes the need for a `document_type` column and simplifies downstream queries.

**Tradeoff**: Classification is still needed at discovery time to route files to the right table. A misclassified document would need to be deleted from one table and re-inserted into another.

**Ask**: Is the team aligned on separate tables? The data catalog already uses `biz_metadata_field_service_report` under `vaid.ai_sot_field_service_report` — does that pattern hold for other doc types?

---

## 4. Batch Strategy and Checkpointing

### Process 1 — Metadata Writes

Process 1 extracts metadata per document. For steady-state this is fine row-by-row, but for bootstrap (~20K files), writing one row at a time is expensive.

Recommendation:
- Micro-batch writes (e.g., every N documents) via MERGE/append
- Don't hold all results in memory until the end — flush periodically

**Ask**: Row-by-row acceptable for incremental runs? What batch size for bootstrap?

### Process 2 — Chunk Writes

Process 2 loops over documents selected from the metadata table. For steady-state (a few new PDFs), this is fine. For bootstrap (~20K files), we need guardrails.

Recommendation:
- Micro-batch writes (e.g., 50 docs at a time) to the chunk table
- Batch status updates via MERGE, not row-by-row
- Checkpoint after each micro-batch so a crash doesn't lose all progress

**Ask**: What batch size and concurrency should we target for bootstrap? The POC full-corpus run took 20+ hours. Do we parallelize within a single notebook, or split into multiple jobs?

---

## 5. Embedding Model and Vector Search Mode

The current POC uses Delta Sync with auto-embed (`databricks-gte-large-en`), but queries are embedded with `azure-text-embedding-3-large-1`. These are different models — retrieval quality suffers from the mismatch.

Production must use pre-computed embeddings with `azure-text-embedding-3-large-1` (3072-dim) stored in the chunk Delta table. Vector Search should sync on that stored column, not auto-embed.

Delta Sync is Databricks-managed — we write to the chunk table and VS auto-syncs. Only the index creation (one-time provisioning) is our responsibility.

**Ask**: Confirm we're using Delta Sync with a stored embedding column (not Direct Vector Access, not auto-embed). This is a breaking change from the current POC setup.

---

## 6. Chunking Strategy

Current recursive chunking strategy is kept as-is for this iteration. Not proposing changes to the algorithm now.

**Ask**: Agree to revisit chunking quality once the pipeline is operational and we can evaluate retrieval results end-to-end? Changing chunking mid-build adds risk without data to guide the decision.

---

## 7. Table Naming Convention

The AWS data engineering doc (`reference/aws-dev-team/data_engineering_and_ingestion.pdf`) defines these names:

| Table | Proposed Name | Catalog / Schema |
|---|---|---|
| Metadata (FSR) | `biz_metadata_field_service_report` | `vaid.ai_sot_field_service_report` |
| Chunks + embeddings | `vec_field_service_report` | `vaid.ai_std_con_field_service_report` |
| Vector Search index | `vs_field_service_report` | `vaid.ai_std_con_field_service_report` |

However, the Databricks team's GP repo uses a different convention — suffixes like `_sot`, `_ref`, `_stg`, `_mst` (e.g., `ibat_equipment_mst`, `fc_timesheet_detail_stg_iu`). The `biz_` / `vec_` / `ocr_` prefixes don't appear in any Databricks team reference code.

The AWS doc is not yet confirmed as the final standard. We may need to align to the Databricks team's naming convention instead.

**Ask**: Which naming standard applies to the AI catalogs (`vaid`/`vaiq`/`vaip`)? Are the `biz_`/`vec_` prefixes confirmed, or should we follow the Databricks team's suffix pattern? Are the production tables created yet?

---

## 8. Retry Strategy for Failed Metadata Extraction

Process 1 extraction can fail for individual documents (LLM timeout, malformed PDF, enrichment source unavailable). These failures shouldn't block the rest of the batch.

Recommendation:
- Write the metadata row anyway with a `metadata_status = failed` and `metadata_error` populated
- A subsequent run picks up failed rows for retry (similar to how Process 2 retries `chunk_status = failed`)
- Set a max retry count to avoid infinite loops on permanently broken documents
- Optionally: dead-letter queue pattern — after N retries, mark as `skipped` and surface in an operational dashboard

**Ask**: Should we add `metadata_status` alongside `chunk_status`? Or is a single combined status sufficient? Do we want a separate retry job or just let the next scheduled run pick up failures?

---

## 9. ESN Precedence

ESN should be resolved once in Process 1 and carried forward to chunks. No re-resolution in Process 2 or the query layer.

Precedence:
1. SOT reference (e.g., `fsr_pdf_ref`)
2. LLM extraction (normalized)
3. Regex / heuristic fallback
4. `null`

Record the winning source in `esn_source`. This removes the current ambiguity where the chunk pipeline, query service, and scraping pipeline each resolve ESN differently.

**Ask**: Is this precedence order correct? Any cases where LLM should outrank SOT?

---

## 10. Status Model

Replace the draft's `processed` flag with explicit `chunk_status`:

| Value | Meaning |
|---|---|
| `pending` | Registered, not yet chunked |
| `processing` | Chunking in flight |
| `completed` | Chunks + embeddings written |
| `failed` | Chunking failed — see `chunk_error_code` |

This makes in-flight rows visible, supports retries, and avoids overloading `null`.

---

## Quick Reference: What's Already Aligned

These items from Pranesh's design are directionally correct and don't need debate:

- Two-process separation (metadata → chunking)
- Watermark-based incremental ingestion
- Process 2 reads metadata table, not the volume directly
- Selected metadata materialized onto chunk rows
- Upsert (not append) for re-uploaded files

---

## 11. How the Consumer App Accesses Metadata

The consumer (query service / app layer) gets metadata through two layers:

### Layer 1 — Materialized on chunk rows (instant)

Process 2 copies high-value fields from the Silver metadata table directly onto each Gold chunk row as **top-level Delta columns**. When Vector Search returns results, these fields come back immediately — no extra lookup needed.

Fields materialized onto chunks: `generator_serial`, `title`, `customer_name`, `equipment_type`, `event_type`, `report_issued_date`, `document_id`, plus other Phase 1 fields from Vince's list.

### Layer 2 — Secondary join at query time (full depth)

For the complete response shape (per Query FSR Spec Steps 5-6), the query service does secondary SQL joins after Vector Search returns chunk_ids:

1. Join Gold Delta table by `chunk_id` — full chunk row hydration
2. Join Silver metadata table by `document_id` — all 15+ scraped fields
3. Join `fsr_pdf_ref` by filename — SOT event/ESN data
4. Join `fsr_field_vision_psot` by event_id — outage type, status, dates

### Why both layers?

- Materializing everything onto chunks would bloat the Gold table and make metadata corrections hard (you'd need to reprocess chunks just to fix a title)
- Joining everything at query time would be slow for fields needed during search (Vector Search can only filter on columns in the index)
- So: **filter-critical fields on the chunk, full depth via join**

The Silver table stays as the single source of truth for document-level metadata. If metadata gets corrected, you update Silver — the query-time join picks it up automatically for the enrichment fields, and a targeted re-materialization can refresh the chunk-level fields without re-chunking.

---

## 12. Top-Level Columns, Not Raw JSON

Metadata on chunk rows must be stored as **top-level Delta columns** (e.g., `title STRING`, `customer_name STRING`, `generator_serial STRING`), not as a single raw JSON blob.

### Why this matters

1. **Vector Search filtering** — Databricks Vector Search can only filter on top-level columns in the index. A JSON blob cannot be used as a native filter (you can't do `WHERE metadata.esn = '270T658'` through VS).
2. **Delta SQL performance** — Top-level columns enable predicate pushdown and stats-based skipping. Querying inside a JSON string column requires full scan + parsing.
3. **Schema enforcement** — Top-level columns enforce type and presence at write time. A JSON blob silently accepts missing or misspelled fields.
4. **Downstream simplicity** — The query service and app layer can read columns directly without JSON extraction logic.

A catch-all `metadata` JSON column can still exist for less-used or evolving fields, but the retrieval-critical ones must be promoted to top-level columns.

---

## Changes from Pranesh's Design (Draft v0.1, April 17)

| # | Area | Pranesh's Design | Our Recommendation | Type |
|---|---|---|---|---|
| 1 | Primary key | No stable PK — relies on `pdf_name` / `volume_path` | Add `document_id` (deterministic hash of `volume_path`) | New |
| 2 | Status model | `processed` (null / yes / failed) | `chunk_status` (pending / processing / completed / failed) | Replaced |
| 3 | ESN resolution | `esn` column, no precedence defined | Explicit precedence (SOT → LLM → regex → null) + `esn_source` | Enhanced |
| 4 | Document type | No `document_type` column or routing | Separate tables per doc type — table name is the type | New |
| 5 | Chunk metadata | All metadata in a JSON `metadata` column | Promote high-value fields to top-level columns on chunk rows | Changed |
| 6 | Embedding approach | Correctly specifies `azure-text-embedding-3-large-1` | Same model, but explicitly store embeddings in Delta (no auto-embed on VS side) | Clarified |
| 7 | VS index name | `vs_vec_field_service_report` | `vs_field_service_report` | Renamed |
| 8 | Re-materialization | Not addressed | `metadata_version` — bump when enrichment logic changes, refresh chunk metadata without re-chunking | New |
| 9 | P1 failure handling | Not addressed | `metadata_status` + retry/dead-letter strategy for extraction failures | New |
| 10 | Date types | STRING (YYYY-MM-DD) | DATE type with normalization | Changed |
| 11 | Upsert vs append | Listed as open item | Recommend upsert on `volume_path`, resets `chunk_status = pending` | Decided |
| 12 | Batch/write strategy | Not addressed (P1 or P2) | Micro-batch writes, MERGE for status updates, checkpointing | New |
| 13 | Error columns | `error` + `error_reason` | `chunk_error_code` + `chunk_error_reason` (more specific) | Renamed |
| 14 | `page_count` | Not in schema | Added — low-effort, useful for classification/debugging | New |
| 15 | Catalog paths | `vaid/vaiq/vaip` placeholder | Specific: `vaid.ai_sot_field_service_report`, `vaid.ai_std_con_field_service_report` | Resolved |
