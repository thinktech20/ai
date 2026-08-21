# FSR v2 Retrieval Algorithm

> **Design note:** This algorithm is derived from first-principles analysis of
> the P1/P2/P3 pipeline code and schema — not from the retrieval flow diagram
> shared earlier. That diagram has a critical flaw addressed below.

**Last updated:** 2026-07-25 — reflects production-ready implementation in
`pw_sdg_ai_ser_repo/validation/fsr_v2/retrieval/` (branch `fsr_v2`, commit `f171241`).

---

## Implementation Plan

| Use Case | Algorithm variants | Status |
|---|---|---|
| UC1 — Data Readiness API | One algorithm only — pure SQL on mapping + metadata tables. Not affected by any pipeline issues. | ✅ Implemented |
| UC2 — FSR Retrieval API | **Two variants** until Issue 3 is resolved. See below. | |
| UC2 — current (Issue 3 exists) | Step 1 (SQL pre-gate) + Step 2a (VS primary ESN filter) + optional Step 2b (fallback for unattributed chunks from eligible docs) | ✅ Implemented |
| UC2 — after Issue 3 fixed | Step 1 (SQL pre-gate) + Step 2a only. Same VS query — no code change to retrieval logic, just remove Step 2b. | ✅ Implemented (nb_fsr_v2_retrieval_uc2_future) |

**Issue 3 fix location:** P1 preprocessor (`silver/src/etl/fsr_v2/preprocessor_v2_final.py`) — emit a fallback region for char spans not covered by any specific ESN region, using doc-level `primary_esn` as the default. Once fixed, Step 2b can be deleted from the retrieval code.

---

## Use Cases

1. **Data Readiness API** — `GET /dataservices/api/v1/equipment/{esn}`  
   Return all FSR documents for a given ESN, regardless of whether it is primary or secondary in the doc.

2. **FSR Retrieval API** — `POST /retrieve`  
   Return the most relevant chunks for a given ESN + query text, within the recency window.

---

## Critical flaw in the earlier retrieval flow diagram

The diagram went:  
`doc-level primary_esn → candidate documents → retrieve all chunks`

This is **wrong for v2**, because:

- It uses `primary_esn` from `fsr_metadata_v2` (document-level). In a multi-equipment doc (e.g., GT + Generator), only one ESN is the primary.
- If the user queries the secondary ESN, that doc would be excluded in Step 1 — even though many of its chunks are correctly attributed to that ESN at the chunk level.
- v2's entire purpose is chunk-level ESN attribution via `preprocessor_regions`. The correct filter is `chunk.primary_esn = requested_esn`, not `doc.primary_esn = requested_esn`.

**Correct approach:**  
Filter `primary_esn` at the **chunk level** in the VS index directly. Use the mapping table only for doc eligibility gates (active status, completion status), not for ESN-to-doc resolution.

---

## Schema issues (fixed or flagged)

### Issue 1 — `outage_start_date` was missing from VS index (fixed in DDL + `vector_index.py`)

`outage_start_date` is a doc-level field extracted from the cover page via LLM + Event Vision enrichment. One date per document. Every chunk for that document gets the same value.

It was in `fsr_chunks_v2` as a top-level column but was absent from `columns_to_sync` in the DDL and `vector_index.py`. Both are now fixed.

**Important:** The Databricks VS REST API does **not** support nested range filters like `{"outage_start_date": {"gte": "2016-01-01"}}`. The `VectorSearchClient` Python SDK handled this internally, but direct REST API calls (which we now use to avoid the `databricks-vectorsearch` package dependency) send `filters_json` verbatim. The nested format returns HTTP 200 with `row_count: 0` — silently filtering out all results.

**Workaround in effect:** `outage_start_date` is NOT passed as a VS filter. Instead:
1. Step 1 (SQL gate) already guarantees all `candidate_doc_ids` are within the recency window at the document level.
2. Step 2a over-fetches (`num_results × 3`) then post-filters in Python: `dict(zip(_COLS, r)).get("outage_start_date", "") >= threshold_date`.

This is safe because `outage_start_date` is stored as `YYYY-MM-DD` string, which sorts lexicographically correctly.

**About `outage_start_date`:** It is **doc-level**, not per-region or per-chunk. There is one outage start date per FSR document. The v2 schema copies it to every chunk for filter convenience. This is correct behavior.

### Issue 2 — `active_esns` changed from pipe-delimited string to `ARRAY<STRING>` (fixed in code)

**Origin:** P2 — `gold/src/etl/fsr_v2/chunking.py`, `_build_active_esns()`. Previously written as a pipe-delimited string (e.g. `"155360|316X914"`), which could not be used as a VS filter.

**Fix applied:**
- `_build_active_esns()` now returns `list[str]` instead of a joined string.
- `fsr_chunks_v2` DDL changed from `STRING` to `ARRAY<STRING>` in `common/fsr_v2/config.py`.
- Spark schema in `chunking.py` updated from `StringType()` to `ArrayType(StringType())`.
- `active_esns` is already in `columns_to_sync` in `vector_index.py` — no change needed there.

**After next index recreate**, VS-native array-contains filtering is possible:
```python
filters={"active_esns": {"contains": requested_esn}}
```
This enables "any ESN in doc" filtering at the VS layer without a SQL pre-step if needed.

**Note:** The existing table `fsr_chunks_v2` will need an `ALTER TABLE` to change the column type, or a full drop-and-recreate via the DDL notebook. Existing data must be re-chunked (P2 re-run) to populate the array format.

### Issue 3 — Chunks with no region attribution have `primary_esn = ""` (data pipeline issue, not retrieval)

**Origin:** P1 preprocessor — does not emit regions covering every character span in the document. Intro/header/footer/transition sections between equipment areas produce no region. P2 then has nothing to attribute for chunks landing in those gaps and explicitly sets `primary_esn = ""`.

**Impact on retrieval:** VS filter `primary_esn = requested_esn` correctly skips those chunks — returning content with unknown ESN attribution would hurt precision. The retrieval layer behaves correctly. The gap is a recall issue: some content relevant to the queried ESN may not be returned if it falls in an unattributed span.

**Fix location:** P1 preprocessor (`silver/src/etl/fsr_v2/preprocessor_v2_final.py`). The preprocessor should emit a fallback region for spans not attributed to any specific ESN, using the doc-level `primary_esn` as the default. This would eliminate mapping misses for boundary chunks without affecting precision for multi-equipment sections.

**Prior art in `ds-guru`:** The `ds-guru` app (`/home/u560060992/dbx/ds-guru/`) has a working FSR preprocessor (`FSR_PREPROCESSOR.md`) that solves this exact problem via character-offset regions with a catch-all fallback region. That implementation should be referenced when fixing P1.

---

## Algorithm: UC1 — Data Readiness API

**Input:** `requested_esn` (string)  
**Output:** List of documents with metadata, ordered by recency  
**Data path:** SQL/Delta only — no vector search needed  

```sql
SELECT
    m.document_id,
    m.pdf_name,
    m.primary_esn,
    m.primary_equip_type,
    d.esn                    AS matched_esn,
    d.equip_type             AS matched_equip_type,
    d.is_primary_esn,
    m.report_issued_date,
    m.outage_start_date,
    m.outage_end_date,
    m.outage_type,
    m.customer,
    m.event_type,
    m.ev_project_id,
    m.ev_equipment_event_id,
    m.ofs_event_id,
    m.fsp_project_id,
    m.fsr_number,
    m.technology_type
FROM fsr_document_equipment_map_v2  d
INNER JOIN fsr_metadata_v2          m  ON d.document_id = m.document_id
WHERE UPPER(d.esn)        = UPPER('{requested_esn}')
  AND d.is_active         = true
  AND m.metadata_status   = 'completed'
  AND m.chunk_status      = 'completed'
  AND m.outage_start_date >= DATE_FORMAT(ADD_MONTHS(CURRENT_DATE(), -120), 'yyyy-MM-dd')
ORDER BY m.report_issued_date DESC
```

**Why this is correct:**
- `fsr_document_equipment_map_v2.esn` covers all ESNs in a doc (primary and secondary). Both are queryable — satisfies the use case requirement.
- `is_active = true` excludes ESNs marked inactive for this outage.
- `metadata_status = 'completed'` and `chunk_status = 'completed'` ensure only fully processed documents are returned.
- `outage_start_date >= 120 months` is the recency window, applied on `fsr_metadata_v2` where it is stored as `YYYY-MM-DD` string.

---

## Algorithm: UC2 — FSR Retrieval API

**Input:** `requested_esn` (string), `query_text` (string), `num_results` (int, default 5)  
**Output:** Ranked list of relevant chunks with metadata  

### Step 1 — Eligibility pre-gate (SQL/Delta) — same regardless of Issue 3

Check whether any eligible documents exist for this ESN before hitting VS. This is a cheap gate — not for ESN-to-chunk resolution. Also fetches candidate doc IDs needed for the Issue 3 fallback in Step 2b.

```sql
SELECT DISTINCT d.document_id
FROM fsr_document_equipment_map_v2  d
INNER JOIN fsr_metadata_v2          m  ON d.document_id = m.document_id
WHERE UPPER(d.esn)        = UPPER('{requested_esn}')
  AND d.is_active         = true
  AND m.chunk_status      = 'completed'
  AND m.outage_start_date >= DATE_FORMAT(ADD_MONTHS(CURRENT_DATE(), -120), 'yyyy-MM-dd')
```

If result is empty: return empty result immediately without calling VS.

**After Step 1:** embed `query_text` via LiteLLM to get `query_vector` (3072-dim, model `azure-text-embedding-3-large-1`).

---

### When Issue 3 exists (current state — preprocessor has coverage gaps)

Some chunks near section boundaries, headers, or intro/transition text have `primary_esn = ""` because the P1 preprocessor did not emit a region covering their char offset. These chunks are invisible to the `primary_esn` filter.

**Step 2a — Primary VS search (high precision)**

Uses the Databricks VS REST API directly (`POST /api/2.0/vector-search/indexes/{index}/query`).
No `databricks-vectorsearch` package dependency — uses `requests` + Databricks token from `dbutils`.

> **Note:** VS REST API does not support nested range filters (`{"gte": val}`).
> `outage_start_date` is post-filtered in Python after fetching.

```python
# Embed query first
query_vector = litellm_embed(query_text)  # 3072-dim

# VS query — ESN equality filter only, over-fetch for date post-filter
raw = vs_rest_query(
    index=VS_INDEX,
    query_vector=query_vector,
    columns=["chunk_id", "document_id", "pdf_name", "chunk_text",
             "primary_esn", "primary_equip_type", "outage_start_date", "metadata"],
    filters={"primary_esn": requested_esn},
    num_results=num_results * 3,          # over-fetch for post-filter headroom
)

# Post-filter by date in Python (string comparison works for YYYY-MM-DD)
results = [
    r for r in raw
    if dict(zip(COLS, r)).get("outage_start_date", "") >= threshold_date
][:num_results]
```

**Step 2b — Fallback VS search for unattributed chunks (optional, improves recall)**

Only run if `len(results) < min_results` (threshold: 3).

> **Note:** VS REST API rejects `{"primary_esn": ""}` (empty string filter) with HTTP 400.
> Workaround: filter by `document_id IN candidate_doc_ids`, over-fetch, then
> post-filter in Python for `primary_esn == ""`.

```python
candidate_doc_ids = [row.document_id for row in step1_result]
needed = num_results - len(results)

# VS query — eligible docs filter, no primary_esn filter
fb_raw = vs_rest_query(
    index=VS_INDEX,
    query_vector=query_vector,
    columns=COLS,
    filters={"document_id": candidate_doc_ids},  # IN semantics for list values
    num_results=min(needed * 5, 50),
)

# Post-filter: date recency + unattributed chunks only
fb_dated = [
    r for r in fb_raw
    if dict(zip(COLS, r)).get("outage_start_date", "") >= threshold_date
]
fallback = [
    r for r in fb_dated
    if dict(zip(COLS, r)).get("primary_esn", "") == ""
][:needed]

# Merge, keeping Step 2a results ranked first
results = _merge_dedup(results, fallback, num_results)
```

**Tradeoff:** Step 2b lowers precision (unattributed chunks may be generic intro text, not equipment-specific). Use only as a low-confidence supplement when primary results are sparse.

---

### When Issue 3 is fixed (preprocessor emits full-coverage fallback regions)

The P1 preprocessor assigns doc-level `primary_esn` as the fallback for any char span not covered by a specific region. Every chunk will have a non-empty `primary_esn`. Step 2b is no longer needed.

**Step 2 — Single VS search**

```python
# Same REST API approach, same COLS list
raw = vs_rest_query(
    index=VS_INDEX,
    query_vector=query_vector,
    columns=COLS,
    filters={"primary_esn": requested_esn},
    num_results=num_results * 3,
)
results = [
    r for r in raw
    if dict(zip(COLS, r)).get("outage_start_date", "") >= threshold_date
][:num_results]
```

Previously-unattributed boundary chunks (intro/transition text) are now returned if their fallback region matches `requested_esn`. No change to the query logic — the improvement is entirely from better P1 data quality.

---

### Step 3 — Post-processing (optional but recommended)

For each returned chunk, surface the following fields from the `metadata` JSON for LLM context:

- `metadata.doc.customer`
- `metadata.doc.event_type`
- `metadata.doc.outage_type`
- `metadata.doc.technology_type`
- `metadata.doc.inactive_esns` — useful to show which ESNs were not active this outage
- `metadata.region.primary_esn` — confirm chunk-level attribution matches requested ESN
- `metadata.region.primary_equip_type` — equipment type for this chunk
- `metadata.section.section_title` — section heading for the chunk, useful for LLM grounding

---

## Field Reference

| Field | Table / Source | Meaning |
|---|---|---|
| `esn` | `fsr_document_equipment_map_v2` | Any ESN in the document (primary or secondary). Covers all ESNs regardless of which is primary. |
| `is_active` | `fsr_document_equipment_map_v2` | False when the ESN appears in `inactive_esns` for this outage. Derived in P1 from preprocessor output. |
| `is_primary_esn` | `fsr_document_equipment_map_v2` | True when this ESN is the cover-page/doc-level primary. Not used in retrieval filtering — chunk-level `primary_esn` is the correct gate. |
| `document_id` | All three tables | UUID stem of the source PDF. FK across metadata, chunks, and map tables. |
| `metadata_status` | `fsr_metadata_v2` | P1 status. Only `'completed'` rows have reliable metadata. |
| `chunk_status` | `fsr_metadata_v2` | P2 status. Only `'completed'` rows have chunks ready in VS index. |
| `outage_start_date` | `fsr_metadata_v2`, `fsr_chunks_v2`, `fsr_vs_index_v2` (after fix) | **Doc-level.** One date per document, extracted from cover page via LLM + Event Vision enrichment. Copied to every chunk for filter convenience. Used for 120-month recency window. Stored as `YYYY-MM-DD` string in metadata; as `DATE` in chunks. |
| `report_issued_date` | `fsr_metadata_v2` | Date the FSR was issued. Used for ordering in UC1. |
| `primary_esn` | `fsr_chunks_v2`, `fsr_vs_index_v2` | **Chunk-level.** ESN attributed to this specific chunk via preprocessor region overlap (max-overlap or start-char). Varies per chunk within a multi-equipment document. This is the key filter for chunk relevance in UC2. Empty string if chunk had no matching region (mapping miss). |
| `primary_equip_type` | `fsr_chunks_v2`, `fsr_vs_index_v2` | Equipment type attributed to this chunk (same region logic as `primary_esn`). |
| `active_esns` | `fsr_chunks_v2`, `fsr_vs_index_v2` | **Doc-level, repeated on every chunk.** `ARRAY<STRING>` of normalized active ESNs for the document (e.g. `["155360", "316X914"]`). Supports VS array-contains filtering. Not a chunk-level precision filter — same value on all chunks in the document. Use for "does this ESN appear anywhere in the doc" queries. |
| `chunk_text` | `fsr_vs_index_v2` | Text content of the chunk returned in results. |
| `chunk_embedding` | `fsr_chunks_v2` | Pre-computed 3072-dim embedding vector. Used by VS for similarity scoring. Not returned to the caller. |
| `metadata` (JSON) | `fsr_vs_index_v2` | Contextual fields per chunk. Key sub-fields: `doc.*` (title, customer, event_type, project IDs, outage dates, inactive_esns), `region.*` (chunk-level primary_esn and primary_equip_type), `section.*` (section_title), `chunk_context.chunk_start_char`. |
| `inactive_esns` | `fsr_metadata_v2` | JSON array of ESNs not applicable for this outage. Used to populate `is_active = false` in the map table. Also in `metadata.doc.inactive_esns` per chunk for downstream context. |


