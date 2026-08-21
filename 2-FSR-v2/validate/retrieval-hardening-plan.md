# Retrieval Hardening Plan — FSR v2

Created: 2026-07-25  
Status: **complete** (all items implemented, committed `86f8e06`)

---

## Items

### 1. ✅ [CODE FIX] `r[4]` fragile index in Step 2b — high priority

**File:** `pw_sdg_ai_ser_repo/validation/fsr_v2/retrieval/nb_fsr_v2_retrieval_uc2_current.py`

**Problem:** `r[4] == ""` to identify unattributed chunks relies on column order of the
`_COLS` list staying stable. If anyone adds/reorders columns, this silently returns wrong results.

**Fix:** Replace with named dict lookup:
```python
# Before (fragile):
fallback_results = [r for r in _fb_all if r[4] == ""][:_needed]

# After (safe):
fallback_results = [
    r for r in _fb_all
    if dict(zip(_COLS_2B, r)).get("primary_esn", "") == ""
][:_needed]
```

---

### 2. ✅ [VERIFICATION] `outage_start_date` filter actually excludes old docs

**Location:** New diagnostic section in `nb_verify_retrieval_ucs.py`

**Problem:** We verified the filter is accepted (no BadRequest), but haven't confirmed it
*excludes* docs outside the window. All current dev docs happened to be within 120 months.

**Test:** Run Step 2a for `REQUESTED_ESN` with a recency window set to 1 month before the
doc's `outage_start_date`. Expect 0 results. If any results come back, the filter isn't working.

---

### 3. ✅ [VERIFICATION] Secondary ESN retrieval (chunk-level vs doc-level)

**Location:** New diagnostic section in `nb_verify_retrieval_ucs.py`

**Problem:** We only tested ESNs that appear as doc-level primary. The algorithm is designed
to work for secondary ESNs too (chunk-level `primary_esn` filter, not doc-level). Untested.

**Test:**
1. Query map table for ESNs where `is_primary_esn = false` and `is_active = true`.
2. If any exist, run UC2-current against one and verify chunks come back.
3. Also confirm those chunks actually have `primary_esn` matching the queried ESN at chunk level.

---

### 4. ✅ [VERIFICATION] Multi-doc ESN returns chunks from both docs

**Location:** New diagnostic section in `nb_verify_retrieval_ucs.py`

**Problem:** `298464` has `eligible_docs=2`. Haven't confirmed VS returns chunks from
both documents, not just the more recent/more similar one.

**Test:** Run UC2-current for `298464`, collect `document_id` values from returned chunks,
verify multiple distinct `document_id`s appear (or at least confirm both docs are represented
when queried with a large `NUM_RESULTS`).

---

### 5. ✅ [VERIFICATION] Step 2b fallback fires and filters correctly

**Location:** New diagnostic section in `nb_verify_retrieval_ucs.py`

**Problem:** Step 2b code is fixed but has never actually triggered and returned unattributed
chunks. The `document_id` IN-filter semantics in VS are assumed, not confirmed.

**Test:**
1. Query `fsr_chunks_v2` to find ESNs that have unattributed chunks (`primary_esn = ''`).
2. If any exist, run UC2-current for that ESN with `MIN_RESULTS` set very high (e.g., 999)
   to force Step 2b to trigger.
3. Verify the returned results include chunks with `primary_esn = ''` (unattributed).
4. Verify those chunks' `document_id` values belong to eligible docs from Step 1.

---

## Pipeline hardening (separate from retrieval verification)

### 6. ✅ [PIPELINE] No pipeline hardening needed right now

After reviewing the ingest pipeline code and the issues encountered during dev:
- VS index `create` now triggers sync correctly (`vector_index.py` fix — `826fcdb`)
- DDL `columns_to_sync` now matches `vector_index.py` (`aef869a`)
- `outage_start_date` in DDL, chunking, and VS index — all consistent

No additional pipeline changes needed before verifying retrieval fully.

---

## Implementation order

1. ✅ Fix `r[4]` → dict lookup in `nb_fsr_v2_retrieval_uc2_current.py`
2. ✅ Add diagnostic + verification sections to `nb_verify_retrieval_ucs.py`
   - Section D: Schema diagnostics (unattributed chunk count, secondary ESNs, multi-doc ESNs)
   - Section E: Recency filter gate test
   - Section F: Secondary ESN retrieval test
   - Section G: Multi-doc ESN test  
   - Section H: Step 2b fallback end-to-end test
3. ✅ Sync `2-FSR-v2/validate/` to Databricks
4. ✅ Committed repo change as `86f8e06` on `fsr_v2`

**Next step: run `nb_verify_retrieval_ucs` on Databricks — Section D output will tell you which of E–H are exercisable with the current dev dataset.**
