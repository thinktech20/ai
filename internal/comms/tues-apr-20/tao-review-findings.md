# Tao's Review of Pranesh's Metadata Design Doc — Findings

**Date:** 2026-04-20

Tao reviewed Pranesh's design doc and flagged 6 items. All are valid. Here's the gap analysis against our implementation.

---

## 1. Watermark relies on `last_modified` — may not work

- Files API may not expose file timestamps for all volume types.
- **Alternative:** compare `volume_path` against already-processed paths in the metadata registry.
- **Our implementation:** `fsr_config.py` stores `file_last_modified` in the schema, but no fallback is coded yet.
- **Action:** Added fallback note to design doc. Implementation should try timestamp first, fall back to path-diff.

## 2. Volume paths should be configurable

- Example: UAT docs may land in `/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/UAT_Files/`.
- **Our implementation:** Already parameterized — `PDF_VOLUME_PATHS` in `fsr_config.py` uses `get_runtime_param`. UAT path is in comments.
- **Action:** Added configurability note to design doc. No code change needed.

## 3. `volume_path` vs `pdf_name` — are they the same column?

- Vince's `scraped_meta_normalized_updated.json` only has `pdf_name` (which contains the full path).
- **Our implementation:** Already separated — `volume_path` = full `/Volumes/...` path, `pdf_name` = bare filename or UUID stem.
- **Action:** Expanded both column descriptions in the design doc schema.

## 4. `s3_filename` missing from schema

- `s3_filename` is the UUID identifier for FieldVision PDFs, used by download endpoint (`/fsr/pdf/{uuid}`) and as join key to `fsr_pdf_ref`.
- **Our implementation:** Our `pdf_name` IS `s3_filename` for FieldVision PDFs. The join is documented in data catalog (`pdf_name = fsr_pdf_ref.s3_filename`).
- **Action:** Added explicit note to `pdf_name` description in design doc.

## 5. Re-uploaded files — upsert vs append

- Append creates orphan chunks in the vector index from the old version.
- **Our implementation:** `document_id = SHA-256(volume_path)` is a natural MERGE key. Upsert with `chunk_status = pending` reset is the correct approach.
- **Action:** Resolved the open item in design doc — MERGE by `document_id`, reset chunk status.

## 6. Equipment type filter should be configurable

- Current use case (Generator Risk Assessment) assumes Generator-only, but the pipeline ingests all equipment types.
- **Our implementation:** Not addressed. Current queries filter by `generator_serial` only, no `equipment_type` pre-filter.
- **Action:** Added as new open item in design doc. Recommend: ingest all types, let query layer filter via materialized `equipment_type` on chunk rows. Keeps pipeline reusable for future use cases.

---

## Side note: `chunk_status` states

Pranesh proposed 3 states: `null` / `yes` / `failed`.  
Our implementation has 4: `pending` / `processing` / `completed` / `failed`.  
The extra `processing` state marks in-flight rows so crash recovery can distinguish "never attempted" from "died mid-run." Open question: simplify to 3, or keep 4?

---

## Vince's Architecture Simplification Notes (via Tao)

Vince walked through a major simplification of the FSR data architecture with Business (Jon and others). Three key points raised:

### 1. Metadata tags don't affect vectorization — no re-chunking needed

> Adding new metadata (e.g., CPM, Event Vision ID) later won't require re-chunking or re-embedding.

**Our design covers this.** Embeddings are generated only from `chunk_text`. Metadata fields (`esn`, `equipment_type`, `event_type`, etc.) are materialized as separate columns in the chunk table, orthogonal to the vector. Adding a new metadata field = schema evolution + backfill, no re-vectorization.

### 2. Document summary per chunk (at ingest or on-the-fly)

**Deferred to v2 in our design.** No `document_summary` column exists yet, but the architecture supports it cleanly: generate summary in P1 (LLM call on full text) → store in `fsr_metadata_registry` → materialize into `fsr_chunks` in P2. No re-chunking or re-embedding needed.

### 3. Separate non-vector lookup table for metadata-only queries

**Already covered.** Our two-table design provides exactly this:

| Table | Purpose | Has vectors? |
|-------|---------|-------------|
| `fsr_metadata_registry` | Document-level metadata, statuses, enrichment | No |
| `fsr_chunks` | Chunk text + embeddings + materialized metadata | Yes |

Metadata-only queries (e.g., "what ESN does this PDF have?") hit `fsr_metadata_registry` without touching vectors.
