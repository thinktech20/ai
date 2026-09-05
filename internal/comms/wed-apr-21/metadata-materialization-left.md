# Metadata Materialization — What's Left

Date: 2026-04-21

This note captures the remaining work after the two-PDF validation against the old `gt_litellm` baseline.

It also includes the Apr 21 follow-up from today's discussion on `document_id` vs `pdf_name` and the new PDF-name lookup references shared under `internal/comms/wed-apr-21/pdf_name_extraction`.

## What is already working

- Metadata extraction and chunking complete successfully for the tested PDFs.
- Chunk rows are no longer duplicated across multiple ESN variants for the same PDF.
- The chunk table now materializes some important top-level fields:
  - `title`
  - `esn`
  - `equipment_type`
  - `event_type`
  - `report_issued_date`
  - `page_count`
- The test Vector Search index can be recreated, synced, and queried end to end with a query embedding.

## What is still left for Vince's materialization plan

### 1. Correct document identity before widening materialization — ✅ DONE

Implemented Apr 21. All production notebooks updated:

- `document_id` (UUID stem, lowercased) is now the PK and MERGE key in metadata + chunk tables
- `pdf_name` is a nullable derived field populated from `fsr_pdf_ref.PDF_name` (with volume_path fallback)
- DDL, stub rows, MERGE logic, chunk FK, validation SQL all updated
- Schema header bumped to v3 across all notebooks

### 2. Define how `pdf_name` is derived from reference tables — RESOLVED

**Decision (data-backed, Apr 21):**

- **Winning source:** `vgpp.fsr_std_views.fsr_pdf_ref.PDF_name`
- **Winning join key:** normalized `document_id` = normalized `fsr_pdf_ref.s3_filename`
- **ESN must not be used as the primary join key** for pdf_name derivation

Evidence from validation queries run against production data:

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Total distinct document IDs in fsr_pdf_ref | 15,133 | Large enough to be authoritative |
| Document IDs with a non-null PDF_name | 15,133 (100%) | Full coverage — no gaps |
| UUIDs mapping to >1 distinct PDF_name | 0 | Zero conflicts — clean 1:1 mapping |
| ESNs mapping to >1 distinct PDF_name | 3,459 | ESN-only join is far too ambiguous |
| Duplicate rows (same UUID, different ESN) | 2,486 | Expected — one PDF can cover multiple ESNs |

`fsr_field_vision_field_services_report_psot` does not carry a filename column at all. It is a business/report-level table reached through `(esn, event_id)` after the file has already been identified. It should not be a source for `pdf_name`.

**Implementation rule:**

- store the raw UUID as `document_id` (PK, MERGE key)
- derive `pdf_name` by joining `document_id` to `fsr_pdf_ref.s3_filename` and reading `fsr_pdf_ref.PDF_name`
- for manual / non-FieldVision files not in `fsr_pdf_ref`, use the basename from `volume_path` as fallback
- `pdf_name` should be nullable but will be populated for all FieldVision files

**Open (minor):** the PSOT enrichment bridge is not yet confirmed. `ev_ofs_event_id -> psot.event_id` returned 0 matches. `ev_equipment_event_id -> psot.event_id` is the next candidate to test. This does not block the `pdf_name` fix.

### 3. Expand chunk-level materialized metadata — ✅ ALREADY DONE

The following fields were already materialized as top-level chunk columns before this pass:

- `equipment_sys_id`
- `outage_start_date`
- `outage_end_date`
- `ev_equipment_event_id`
- `fsp_project_id`
- `report_issued_date`

Still deferred (per step 4):

- `customer`
- `ev_project_id` (not in chunk DDL — metadata-only for now)
- `fsr_number` (not in chunk DDL — metadata-only for now)
- `document_summary` (not yet implemented)

### 4. Decide which fields stay metadata-only vs chunk-level

Some fields exist in the metadata table but are not yet promoted to chunk rows. We need a clear decision for each field:

- materialize to chunk rows for retrieval and filtering
- keep only in the canonical metadata table
- defer until there is stronger evidence that the field is needed

### 5. Resolve field precedence rules before widening materialization

Before promoting more fields to chunk rows, define the winning source per field when PDF extraction, LLM normalization, IBAT, Event Vision, and reference-table lookups disagree.

Priority examples to settle explicitly:

- `pdf_name`
- `event_type`
- `report_issued_date`
- `equipment_sys_id`
- `ev_project_id`
- `ev_equipment_event_id`
- `fsp_project_id`
- `outage_start_date`
- `outage_end_date`

### 6. Handle currently null-but-important metadata

In the two tested PDFs, these fields were still null or inconsistently populated:

- `customer`
- `ev_project_id`
- `fsr_number`
- `prepared_by`
- `approved_by`

This needs a decision between:

- improve extraction/enrichment logic
- accept as nullable in v1
- backfill later from another source

### 7. Decide whether `prepared_by` and `approved_by` are still required

These fields exist in the metadata table schema but were not populated in the tested PDFs and are not materialized to chunk rows.

Need a clear decision:

- required for first production iteration
- keep in schema but do not prioritize
- remove from the active materialization scope

### 8. Align naming and keys with the agreed schema before more backfills — ✅ DONE

All of the following are now aligned to the schema v3 identity model:

- metadata table DDL (`document_id` PK, `pdf_name` nullable derived)
- chunk table DDL (`document_id` FK, `pdf_name` nullable materialized)
- lookup/backfill logic for `document_id` -> `pdf_name` via `fsr_pdf_ref`
- merge/update logic (all MERGE ON `document_id`)
- validation SQL (uniqueness, cross-process joins, materialized field checks)
- chunk `chunk_id` hash uses `document_id + chunk_index`

Still needed before production:
- workflow reset/rebuild steps (re-create tables with new DDL)
- confirm Pranesh Confluence schema doc is updated

### 9. Keep production manual validation isolated

If we test future metadata-materialization changes in production, the manual workflow must continue using isolated test objects only.

Do not point manual validation at:

- `main.gp_services_sdg_poc.field_service_report_gt_litellm`
- `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm`
- any other shared UAT-backed object

## Recommended next implementation slice — ✅ DONE (Apr 21)

All 5 items implemented in code:

1. ✅ Reintroduce `document_id` into the metadata and chunk schema, and move the current UUID value there.
2. ✅ Keep `pdf_name` as a separate derived field, with lookup logic sourced from `fsr_pdf_ref` (join on `s3_filename`). Fallback to `volume_path` basename.
3. ✅ `equipment_sys_id`, `outage_start_date`, `outage_end_date`, `ev_equipment_event_id`, and `fsp_project_id` were already on chunk rows — confirmed, no changes needed.
4. ⏳ `customer`, `prepared_by`, `approved_by`, and `document_summary` remain explicit follow-up decisions.
5. ✅ Validation queries expanded: 12-field materialized-value comparison, `pdf_name` derivation coverage check, `document_id` normalization check.

Files changed:
- `common/fsr_config.py` — DDL definitions
- `silver/nb_sdg_fsr_metadata.py` — identity model, pdf_name derivation, MERGE logic
- `gold/nb_sdg_fsr_chunks.py` — FK, chunk_id hash, materialized fields
- `validation/nb_sdg_fsr_validate.py` — expanded cross-process checks
- `common/nb_sdg_fsr_ddl.py` — no changes needed (uses DDL vars from config)

## Validation standard for the next pass

For at least 2 known PDFs, verify:

- metadata row contains the expected `document_id`, derived `pdf_name`, and field values
- chunk rows carry the same promoted values as top-level columns
- Vector Search results return the promoted metadata fields in the payload
- no regression to the old duplicated-chunk behavior
- manual / fallback cases still get a usable `pdf_name` even when reference lookup is missing