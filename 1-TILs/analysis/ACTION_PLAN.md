# Refactoring Action Plan — nb_sdg_til_metadata.py

**Status:** Phase 2 ✅ COMPLETE | Phase 1 ✅ DECIDED | Phase 3 🟡 FINAL REVIEW  
**Last updated:** 2026-06-25  
**Next:** Final code review and smoke validation  

---

## Summary of Changes (Phase 2 Complete)

**Files modified:**
- `nb_sdg_ai_ser_repo/silver/src/etl/nb_sdg_til_metadata.py` (5 fixes applied, ~400 lines affected)

**Key improvements:**
- ✅ Removed 4 unused imports (tempfile, base64, Path, Optional)
- ✅ Added 3 config helper functions (get_runtime_param, get_runtime_bool, parse_runtime_list)
- ✅ Parameterized all hardcoded config values (8 parameters now configurable via job parameters)
- ✅ Removed emoji icons from logging (3 instances)
- ✅ Removed dangerous FORCE_RESET pattern (2 lines deleted, defer to admin job)
- ✅ Renamed variables for clarity (MAX_PDFS → P1_MAX_PDFS, TARGET_TIL_NUMBERS → P1_TARGET_TIL_NUMBERS, etc.)
- ✅ Updated all references throughout notebook (~300+ instances)
- ✅ Added max_tokens to LLM call (was hardcoded to 4000, now parameterized)
- ✅ Added TODO comment explaining sys.path decision defer

**What's ready:**
- Notebook is now fully parameterized and ready for job deployment
- Can run with defaults or override via Databricks job parameters
- Cleaner, more maintainable code
- All "Phase 2: Quick Wins" feedback items resolved

**What's left for Phase 3:**
- Final code validation for the MERGE path and status transitions
- Optional follow-up: tighten raw-response retention rules if the audit store needs a separate cleanup job
- Confirm MLflow artifact retention meets team expectations

**Watch-list items (not blockers for v1):**
- Future D&A source behavior changes
- Potential move from `til_number` to a composite key if update/revision signals change

**Completed in Phase 3 so far:**
- Delta MERGE/upsert path on `til_number`
- Explicit status transitions in logs
- MLflow run logging for run-level metrics and artifacts
- Selective raw-response capture for failed / low-confidence cases

---

## Phase 1: Decisions and Watch-list ✅ COMPLETE

These are the decisions already made for v1, plus the small watch-list for future source behavior changes:

### ✅ A. LLM Calling Pattern

**Investigation Complete:** [See INVESTIGATION_I1_RESULTS.md](INVESTIGATION_I1_RESULTS.md)

**Findings:**
- DS Team uses: **LiteLLM gateway** (not Databricks serving endpoint)
- Gateway: `https://dev-gateway.apps.gevernova.net`
- Model: `azure-gpt-5-2` (OpenAI GPT-5 via LiteLLM proxy)
- Temperature: 0.0 (strict extraction)
- Response format: Forced JSON via API parameter
- Results: 25 TILs extracted with 92% average confidence

**Key Difference from Current Code:**
- Current: Uses Databricks serving endpoint directly
- DS Team: Uses LiteLLM gateway (external, OpenAI-compatible)
- Current: Manual JSON extraction from response
- DS Team: Forced JSON response format via API

**Decision:** ✅ **Option A (Full LiteLLM Alignment)** — CHOSEN

**Implementation Complete:**
- ✅ Created `pw_sdg_ai_ser_repo/common/til_llm_config.py` (API key management, following FSR pattern)
- ✅ Created `pw_sdg_ai_ser_repo/common/til_llm_client.py` (LiteLLM client with retries)
- ✅ Ready for Phase 3 integration

**Key Features:**
- Uses LiteLLM gateway: `https://dev-gateway.apps.gevernova.net`
- Model: `azure-gpt-5-2` (proven 92% confidence)
- Forced JSON response format (no manual extraction fragility)
- Automatic retry logic (2 attempts for transient failures)
- API key resolution: env var → config file → default (following FSR pattern)
- Temperature: 0.0 (strict extraction)

**Phase 3 Next Steps:**
1. Update `nb_sdg_til_metadata.py` to use `extract_til_profile_via_llm()` from `common.til_llm_client`
2. Remove manual Databricks endpoint code (lines 206-240)
3. Test on 2-3 TILs (validate extraction_confidence ≥ 0.91)

---

### B. Table Schema Clarification

**Decision:** ✅ New schema/tables with FSR-consistent naming

**DS pilot output naming observed (file-level):**
- Per-TIL folder contains `extracted_document.json`, `foundation_raw_extraction.json`, `profile_response.json`
- This helps with naming style but does not define Delta schema/table names

**Chosen table naming (Process 1):**
```
vgpd.til_profiles (schema)
  └─ til_metadata (table)
```

**Chosen column pattern for `til_metadata`:**
- `til_number` (STRING)
- `til_profile` (JSON payload; store as STRING in Delta, parse as needed)
- `extraction_confidence` (DOUBLE)
- `metadata_status` (STRING)
- `llm_model` (STRING)
- `processed_at` (TIMESTAMP)

**Notes:**
- `til_profile` is the canonical structured profile column (JSON format), aligned with your proposal.
- Keep naming consistent with FSR convention (`*_metadata` for Process 1 output).

**Status:** Ready for Phase 3 implementation updates in the notebook.

---

### C. TIL Unique Key Strategy

**Working decision (v1):**

- Business key for Process 1 table: `til_number`
- Merge behavior: latest-state table (upsert, not append-only history)
- `source_file_path` is lineage metadata, not part of merge key
- `llm_model` is audit metadata, not part of merge key

**Interim MERGE rule:**
- `ON tgt.til_number = src.til_number`
- `WHEN MATCHED THEN UPDATE` (replace profile/status/metadata fields)
- `WHEN NOT MATCHED THEN INSERT`

**Source behavior watch-list (future only):**
1. Can the same `til_number` reappear in future volume drops?
2. Is ingestion one-time or incremental/recurring?
3. What is the authoritative signal for newer updates if repeats occur?

**Adjustment later if the source contract changes:**
- If recurrence with version signal is confirmed, move to composite key (for example `til_number + revision/version`).
- If latest-only remains the source contract, keep `til_number` as key.

**Status:** Implemented in v1 using `til_number` key and documented as an assumption.

---

### D. Status Tracking Pattern

**Decision:** ✅ Use FSR status tracking pattern

**Chosen metadata status flow:**
- `PENDING` → `PROCESSING` → `COMPLETED` | `FAILED`

**Why this stays consistent with FSR:**
- Supports controlled retries for failed records
- Improves run-level and record-level observability
- Enables safe reprocessing rules instead of blind appends

**Implementation intent (Process 1 / til_metadata):**
- Persist `metadata_status` on every row
- Set `COMPLETED` for successful profile extraction
- Set `FAILED` when extraction or LLM call fails
- Keep `error_message` for failed rows

**MERGE interaction:**
- Continue latest-state upsert by `til_number`
- On matched rows, update profile/status/metadata columns
- Failed records remain queryable for targeted retry

**Status:** Decision finalized; ready for full MERGE + retry implementation.

---

### E. Raw LLM Response Storage

**Decision:** ✅ Hybrid policy (table + selective raw retention + MLflow)

**Policy for Process 1 (`til_metadata`):**
- Do **not** store full raw LLM response for every row in the main Delta table.
- Store parsed output (`til_profile`) + operational metadata (`metadata_status`, `extraction_confidence`, `llm_model`, `processed_at`, `error_message`).

**When to keep raw response:**
- Keep full raw response only for:
  - `FAILED` extractions
  - low-confidence extractions (threshold to be configured)
- Store raw payloads in a separate controlled audit location with retention policy (for example 7-30 days).

**Pros of this approach:**
- Keeps main table lean and query-friendly
- Preserves debugging capability where it matters most
- Reduces storage and governance overhead

**Cons / controls required:**
- Need retention/cleanup job for audit payload store
- Need access controls for raw text payloads

**MLflow role (recommended):**
- Use MLflow for run-level experiment tracking:
  - model name, prompt version, parameters
  - aggregate metrics (success rate, avg confidence, latency)
  - small representative samples as artifacts
- Do not use MLflow as the long-term store for all per-document raw responses.

**Status:** Decision finalized; implementation can proceed with selective raw-response capture and MLflow run tracking.

---

## Phase 2: Immediate Fixes ✅ COMPLETE

All quick wins implemented. Changes made to `nb_sdg_til_metadata.py`:

### ✅ Fix 1: Remove unused imports
**Status:** Done  
**Removed:** `tempfile`, `base64`, `Path`, `Optional` from imports  
**Lines affected:** ~20-32  

### ✅ Fix 2: Remove emoji icons
**Status:** Done  
**Replaced:** `❌ Failed` → `Failed to extract`  
**Replaced:** `✅ Success` → `Extracted` / `Wrote`  
**Lines affected:** ~371, ~373, ~420  

### ✅ Fix 3: Make parameters configurable
**Status:** Done  
**Changes applied:**
```python
# Added helper functions (lines 59-88):
- get_runtime_param(name, default) — Read from env var → widget → default
- get_runtime_bool(name, default) — Parse boolean params
- parse_runtime_list(name) — Parse comma/newline-separated lists

# Parameterized all config values (lines 90-120):
- TIL_SOURCE_VOLUME_PATHS (was: TIL_VOLUME_PATHS, hardcoded)
- TIL_METADATA_TABLE (was: METADATA_TABLE, hardcoded)
- LLM_MODEL (now uses get_runtime_param)
- LLM_TEMPERATURE (now parameterized, floated)
- LLM_MAX_TOKENS (now parameterized)
- MAX_CHARS_PER_PDF (now parameterized)
- P1_MAX_PDFS (was: MAX_PDFS, renamed and parameterized)
- P1_TARGET_TIL_NUMBERS (was: TARGET_TIL_NUMBERS, renamed and parameterized)

# All references updated throughout notebook (300+ lines affected)
```

**Job Parameters (now accepted):**
```
TIL_SOURCE_VOLUME_PATHS=<paths>
TIL_METADATA_TABLE=<table>
TIL_LLM_MODEL=<model>
TIL_LLM_TEMPERATURE=<0.0-1.0>
TIL_LLM_MAX_TOKENS=<int>
TIL_MAX_CHARS_PER_PDF=<int>
TIL_P1_MAX_PDFS=<int>
TIL_P1_TARGET_TIL_NUMBERS=<comma-separated>
```

### ✅ Fix 4: Remove FORCE_RESET
**Status:** Done  
**Removed:** 
- Line 81: `FORCE_RESET = dbutils.widgets.get(...)`
- Line 90: `log.info(f"  Force reset      : {FORCE_RESET}")`
- All FORCE_RESET logic removed
**Reason:** Too risky; defer to separate admin job if needed later  

### ✅ Fix 5: sys.path decision
**Status:** Deferred (TODO comment added)  
**Added:** Inline TODO comment explaining pending architectural decision:
```python
# TODO: Decide on module import strategy
# Option A: Use %run notebook magic (Databricks-idiomatic)
# Option B: Deploy as wheel package
# For now, using sys.path; will refactor after architectural decision
```
**Note:** Will address after Phase 1 investigation completes  

---

## Phase 3: Major Refactoring (Blocked on Phase 1)

These depend on investigation outcomes:

### Refactor 1: LLM Calling Pattern
**Issue:** #4, #9  
**Blocker:** Phase 1.A (LLM pattern decision)  
**Changes:**
- Replace direct `requests.post(...)` with utility function
- Use FSR/DS team pattern
- Update auth logic
- Remove `raw_response` unused variable (or store if needed)

### Refactor 2: Delta MERGE Logic
**Issue:** #13  
**Blocker:** Phase 1.C (unique key strategy)  
**Changes:**
```python
# Instead of:
output_df.write.mode("append").option("mergeSchema", "true").saveAsTable(...)

# Do:
merge_sql = f"""
MERGE INTO {TIL_METADATA_TABLE} AS tgt
USING (SELECT ...) AS src
ON tgt.til_number = src.til_number
WHEN MATCHED THEN UPDATE SET ...
WHEN NOT MATCHED THEN INSERT ...
"""
spark.sql(merge_sql)
```

### Refactor 3: Add Status Tracking
**Issue:** #14  
**Blocker:** Phase 1.D (status pattern decision)  
**Changes:**
- Add `metadata_status` and `chunk_status` columns to schema
- Compute status from extraction result
- Update MERGE logic to handle status

---

## Timeline Proposal

**✅ Phase 2 Complete** (Today, ~30 min):
- ✅ Removed unused imports
- ✅ Made all parameters configurable  
- ✅ Removed emoji icons from logging
- ✅ Removed FORCE_RESET pattern
- ✅ Added TODO for sys.path decision

**Next: Phase 1 Investigation** (30-45 min):
- 📝 Investigate LLM calling pattern (DS team vs FSR)
- 📝 Clarify table schema (vgpd.til_profiles schema structure)
- 📝 Define unique key strategy for MERGE logic
- 📝 Decide status tracking pattern (metadata_status, chunk_status)
- 📝 Decide raw LLM response storage

**Then: Phase 3 Refactoring** (1-2 hours, depends on Phase 1 outcomes):
- 🔧 Implement LLM calling pattern alignment
- 🔧 Implement Delta MERGE logic with proper WHEN clauses
- 🔧 Add status tracking fields to schema
- 🔧 Update notebook to use MERGE instead of APPEND
- 🔧 Test on 2-3 sample PDFs

**Final: Validation & Deployment** (Next iteration):
- 🧪 Run on 5-10 TILs, compare with DS team results
- 🧪 Validate extraction_confidence scores
- 🧪 Refine LLM prompt if needed
- 🧪 Design Process 2 (chunking)

---

## Investigation Checklist

Use this to track Phase 1 research:

```
Phase 1.A: LLM Calling Pattern
- [ ] Found DS team's model choice (grep notebooks/)
- [ ] Confirmed FSR uses LiteLLM (already confirmed in code)
- [ ] Decision: use [LiteLLM | Databricks serving] like [FSR | DS team]

Phase 1.B: Table Schema
- [ ] Confirmed: vgpd.til_profiles is a [schema | table]
- [ ] Will there be: vgpd.til_profiles.til_chunks?
- [ ] Table names finalized: til_metadata, til_chunks

Phase 1.C: TIL Unique Key
- [ ] Confirmed: til_number uniqueness and any revisions
- [ ] MERGE ON clause defined: til_number [only | + revision]
- [ ] Re-extraction policy decided: [overwrite | keep history]

Phase 1.D: Status Tracking
- [ ] Decision: adopt [metadata_status like FSR | simpler model]
- [ ] If yes: defined states (PENDING, COMPLETED, FAILED, etc.)

Phase 1.E: Raw LLM Response
- [ ] Decision: store [first 500 chars | discard | full]
```

---

## Questions for You

**Before we proceed, please clarify:**

1. **LLM:** What model did DS team use? Do they have existing util functions for calling it?

2. **Schema:** Confirm the full schema path and table structure. Is it:
   - `vgpd.til_profiles.til_metadata` (what you want)
   - `vgpd.til_metadata` (simpler)
   - Something else?

3. **Unique key:** Can a TIL be re-extracted? (e.g., with new LLM version?)

4. **Status:** Should we track metadata_status + chunk_status like FSR, or keep it simpler?

5. **sys.path:** Where should the utility modules live? In this repo under `backend/`? Or elsewhere?

Once you clarify these, we can implement Phase 2 (quick fixes) immediately and Phase 3 (major refactoring) without further blocking.

