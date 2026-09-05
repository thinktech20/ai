# Chunk Integrity Fix — Partial Ingestion Prevention

**Date:** 2026-04-24
**File:** `gold/src/etl/nb_sdg_fsr_chunks.py`
**Status:** Fixed (pending review)

---

## Finding

5 documents with `chunk_status = failed` had **643 partial chunk rows** persisted in the chunk Delta table. Because the Vector Search index is a Delta Sync index backed by the same table, those incomplete rows were visible to the frontend search.

| document_id | pdf_name | chunks stored | expected | missing % |
|---|---|---|---|---|
| `a5b2ff90-...` | FSP-270859_C-10334131 | 395 | unknown | embed failure |
| `4b06401b-...` | EV-174741_PMX-EG0-007404_EVP-549261 | 124 | 149 | 20% |
| `ae0512f9-...` | A-1693796_EV-111798_EVP-515754 | 50 | 66 | 24% |
| `6a2840b8-...` | EV-110307_C-10364786 | 46 | 61 | 36% |
| `ab02ac80-...` | A-1840852_EV-159332_C-10377918_EVP-538490 | 28 | 38 | 26% |

## Impact

- Frontend search returns results from partially ingested documents.
- Users see content from an FSR but miss 20-36% of that document's findings/recommendations.
- No signal in the search response that the result came from a partial document.

## Root Cause

In `process_one_batch`, the success/failure determination (`all_failed_ids`, `success_doc_ids`) was computed **after** chunk rows had already been assembled and merged into the Delta table. The flow was:

```
chunk → embed → assemble ALL rows → MERGE into table → then decide which docs failed
```

The per-doc embedding coverage check correctly identified docs with too many missing embeddings and added them to `embed_failures`, but the rows that *did* succeed for those same docs were already in the `chunk_rows` list and got written.

## Resolution

### Immediate (live data)

Deleted the 643 orphaned rows from the chunk table:

```sql
DELETE FROM <CHUNK_TABLE>
WHERE document_id IN (
  SELECT document_id FROM <METADATA_TABLE>
  WHERE chunk_status = 'failed'
);
```

The 5 documents retain `chunk_status = failed` in the metadata table, so the next P2 run will re-claim and reprocess them.

### Code fix

Moved the success/failure determination **before** row assembly. The flow is now:

```
chunk → embed → coverage check → determine success/fail → assemble rows for SUCCESS ONLY → MERGE
```

Three changes in `process_one_batch`:

1. `all_failed_ids` and `success_doc_ids` are computed immediately after the per-doc embedding coverage check, before any row assembly.
2. The assembly loop iterates `success_doc_ids` instead of all `doc_chunks`. Failed docs never enter the row list.
3. Removed the duplicate derivation of both variables from the status-update section below — they reference the same sets computed earlier.

Added observability: when failed docs are excluded, a log line reports how many docs and chunks were skipped.

No change to successful-document behavior — MERGE, status update, and audit log work identically.

## Validation

Run the summary query from the integrity check notebook against the chunk and metadata tables. The `failed_docs_with_chunks` count should be 0.

## TODO

- [ ] Build a lightweight test/validation app that can be run independently to verify chunk completeness, embedding integrity, and VS index alignment before sharing data with consuming teams.
