# Schema Recommendation: `document_id` + Derived `pdf_name`

Date: 2026-04-21
Status: Proposed (pending Pranesh Confluence schema update alignment)

---

## Summary

Reintroduce `document_id` as the primary key and MERGE key. Add `pdf_name` as a derived, human-readable field populated from `fsr_pdf_ref.PDF_name`.

This reverses the Apr 20 decision to remove `document_id` and use `pdf_name` (UUID) as PK.

---

## Evidence

All numbers from validation queries run against `vgpp.fsr_std_views.fsr_pdf_ref` on Apr 21.

- 15,133 distinct document UUIDs in `fsr_pdf_ref`
- 100% have a non-null `PDF_name` value
- 0 UUIDs map to more than one distinct `PDF_name` (zero conflicts)
- 3,459 ESNs map to more than one distinct `PDF_name` (ESN is not safe as a join key)
- 2,486 duplicate rows exist because one UUID can appear with multiple ESNs (expected)

---

## Metadata Registry Table Changes

**Table:** `biz_metadata_field_service_report`
**Primary key:** `document_id` (was `pdf_name`)

| Column | Type | Change | Description |
|--------|------|--------|-------------|
| `document_id` | STRING NOT NULL | **ADD — new PK** | Normalized UUID stem from volume path. Matches `fsr_pdf_ref.s3_filename` (lowercased, `.pdf` stripped). |
| `pdf_name` | STRING | **CHANGE — no longer PK** | Human-readable filename derived from `fsr_pdf_ref.PDF_name`. Nullable for files not in fsr_pdf_ref. Fallback: basename from `volume_path`. |

All other columns unchanged.

### Derivation logic for `pdf_name`

```sql
-- During metadata extraction or as a post-enrichment step:
SELECT
    meta.document_id,
    COALESCE(
        ref.PDF_name,
        regexp_extract(meta.volume_path, '([^/]+)\\.pdf$', 1)
    ) AS pdf_name
FROM metadata_registry meta
LEFT JOIN vgpp.fsr_std_views.fsr_pdf_ref ref
    ON lower(regexp_replace(trim(ref.s3_filename), '\\.(pdf|PDF)$', ''))
     = meta.document_id
```

### How `document_id` is computed

Same as the current `pdf_name` value — the bare UUID stem extracted from the volume path:

```python
document_id = Path(volume_path).stem.lower()
# e.g. "/Volumes/.../8e13978c-6568-4785-9397-8c6568c785d5.pdf"
#   -> "8e13978c-6568-4785-9397-8c6568c785d5"
```

---

## Chunk Table Changes

**Table:** `biz_chunk_field_service_report`
**Primary key:** `chunk_id` (unchanged)
**Foreign key:** `document_id` → metadata registry (was `pdf_name`)

| Column | Type | Change | Description |
|--------|------|--------|-------------|
| `chunk_id` | STRING NOT NULL | **UPDATE hash input** | Hash of `document_id` + `chunk_index` (was `pdf_name` + `chunk_index`) |
| `document_id` | STRING NOT NULL | **RENAME from `pdf_name`** | FK to metadata registry |
| `pdf_name` | STRING | **ADD as materialized field** | Human-readable name, copied from metadata registry at chunk time |

All other columns unchanged.

---

## MERGE Key Changes

| Location | Old | New |
|----------|-----|-----|
| Metadata stub MERGE | `ON tgt.pdf_name = src.pdf_name` | `ON tgt.document_id = src.document_id` |
| Metadata enrichment MERGE | `ON tgt.pdf_name = src.pdf_name` | `ON tgt.document_id = src.document_id` |
| Chunk MERGE | `ON tgt.chunk_id = src.chunk_id` | unchanged (chunk_id is still PK) |
| Chunk FK | `pdf_name` references metadata | `document_id` references metadata |

---

## What This Does NOT Change

- Volume scan logic (still uses `dbutils.fs.ls`)
- Watermark logic (still uses `MAX(ingested_at)`)
- LLM normalization (still operates on extracted text)
- IBAT / Event Vision enrichment (still joins by ESN)
- Chunking algorithm (still RecursiveCharacterTextSplitter)
- Embedding model (still `azure-text-embedding-3-large-1`)
- Vector Search index setup (still DELTA_SYNC)

---

## Migration Path for Existing Test Data

If `fsr_metadata_registry_test` or `fsr_chunks_test` exist with the old schema:

1. Rename `pdf_name` column to `document_id` (it already contains the UUID)
2. Add `pdf_name` column, populate via the derivation join above
3. Update chunk table FK references

Or simpler: drop test tables and recreate. They only have 10 rows.

---

## Open Item

The PSOT enrichment bridge (`fsr_pdf_ref -> psot`) is not yet confirmed:
- `ev_ofs_event_id -> psot.event_id` returned 0 matches
- `ev_equipment_event_id -> psot.event_id` is the next candidate

This does not block the `document_id` / `pdf_name` schema change.
