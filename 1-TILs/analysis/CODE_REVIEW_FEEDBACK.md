# Code Review: nb_sdg_til_metadata.py

**Date:** 2026-06-24  
**Status:** Pre-implementation feedback  
**Based on:** FSR patterns (nb_sdg_fsr_metadata.py) + Design doc (til-design.md)

---

## Issue-by-Issue Analysis

### 1. sys.path.insert — Why is this needed?

**Current Code:**
```python
sys.path.insert(0, '/Workspace/Repos/githubenterprise.gevernova.net/AIServices_Engineering/uai3071390-genai-services-demand-generation-usecase/backend')
```

**Problem:** Hardcoded path, not Databricks-idiomatic

**FSR Pattern:** Uses `%run ../../../common/fsr_config` instead (Databricks notebook magic)

**Recommendation:**
```python
# Option A (Preferred - if modules are in same repo):
%run ../til_profile_schema
%run ../til_profile_extraction_llm
# Then import without sys.path manipulation
from silver.src.tils.til_profile_schema import normalize_til_profile, ...

# Option B (If modules are truly external):
# Use proper Databricks package installation or wheel deployment
# (defer to ops/packaging strategy)
```

**Decision needed:** Where do `til_profile_schema.py` and `til_profile_extraction_llm.py` live? Should they be in a deployed package or local to the repo?

---

### 2. Remove dead code

**Current code imports:**
```python
from pathlib import Path
import tempfile
import base64
```

**Check:** Are these used?
- `tempfile` — Not used (no temp file creation)
- `base64` — Not used (no base64 encode/decode)
- `Path` — Not used (no path operations)
- `Optional` from typing — Not used in function signatures

**Action:** Remove unused imports.

---

### 3. Hardcoded paths and schema — Configuration Management

**Current:**
```python
TIL_VOLUME_PATHS = [
    "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new",
]
METADATA_TABLE = "vgpd.til_profiles.til_metadata"
```

**Problems:**
- a) Hardcoded, not parameterized
- b) Mismatch: schema is `til_profiles` but table is `til_metadata` — what's the distinction?
- c) Not following FSR pattern

**FSR Pattern:**
```python
%run ../../../common/fsr_config  # Centralized config

# Parameters via job base_parameters / env vars / widgets
PDF_VOLUME_PATHS = parse_runtime_list("FSR_SOURCE_VOLUME_PATHS")  # comma-separated
METADATA_TABLE = get_runtime_param("FSR_METADATA_TABLE", "vgpd.qlt_std_views.fsr_metadata")
```

**Clarification needed:**
1. **Schema naming:** Is `vgpd.til_profiles` the schema? Then what goes in it?
   - `vgpd.til_profiles.til_metadata` (extraction metadata)
   - `vgpd.til_profiles.til_chunks` (chunking results)
   - Or is there a single `vgpd.til_metadata` table?

2. **Volume path:** Is this the only TIL source? Can we make it configurable?

**Recommendation:**
```python
# Create til_config.py (similar to fsr_config.py)
TIL_VOLUME_PATHS = parse_runtime_list("TIL_SOURCE_VOLUME_PATHS") or [
    "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new",
]
TIL_METADATA_TABLE = get_runtime_param("TIL_METADATA_TABLE", "vgpd.til_profiles.til_metadata")
TIL_CHUNKS_TABLE = get_runtime_param("TIL_CHUNKS_TABLE", "vgpd.til_profiles.til_chunks")
```

---

### 4. LLM Model Alignment

**Current:**
```python
LLM_MODEL = dbutils.widgets.get("llm_model", "databricks-gpt-oss-20b")
```

**Question:** What model did DS team use? What does FSR use?

**DS Team:** Need to check their run_til_profile_extraction_pilot.py for `DEFAULT_MODEL` or `model` parameter

**FSR:** Uses LiteLLM gateway (not direct serving endpoint), so they pass `model` as LiteLLM model name

**Recommendation:**
1. Check DS team's prompt what LLM model they specified
2. Check if we need to use LiteLLM (like FSR) instead of Databricks serving endpoint directly
3. Align on: do we call Foundation Model serving endpoint? Or LiteLLM gateway?

**Decision Blocker:** Need alignment with how FSR calls LLM.

---

### 5. Check for hardcoded parameters

**Identified hardcoded values:**
- `LLM_TEMPERATURE = 0.0` — OK (extraction should be strict), but make configurable
- `MAX_CHARS_PER_PDF = 40000` — Question in #7
- `METADATA_TABLE` — Addressed in #3
- `TIL_VOLUME_PATHS` — Addressed in #3
- `temperature=0.0` in LLM call — OK, consistent
- `max_tokens=4000` in LLM call — Consider making configurable

**Recommendation:** Add widget parameters for tuning:
```python
LLM_TEMPERATURE = float(dbutils.widgets.get("llm_temperature", "0.0"))
LLM_MAX_TOKENS = int(dbutils.widgets.get("llm_max_tokens", "4000"))
MAX_CHARS_PER_PDF = int(dbutils.widgets.get("max_chars_per_pdf", "40000"))
```

---

### 6. FORCE_RESET pattern — Security concern

**Current:**
```python
FORCE_RESET = dbutils.widgets.get("force_reset", "false").lower() == "true"

if FORCE_RESET:
    if JB_ENV == "prod":
        raise ValueError("FORCE_RESET is not allowed when jb_env=prod")
    spark.sql(f"TRUNCATE TABLE {METADATA_TABLE}")
```

**User's concern:** Dangerous pattern, too easy to accidentally trigger.

**FSR's approach:** They have guard rails (check `jb_env != "prod"`) but still allow it

**Better approach:** Don't build it into Process 1 notebook. Create a separate admin utility:

**Option A (Recommended):**
```python
# nb_sdg_til_admin_reset.py (separate notebook, requires explicit approval)
# - Only runs in dev/staging environments
# - Logs who ran it and when
# - Clears metadata table + chunk table
# - Cannot be called from production

# Process 1 stays simple: no FORCE_RESET flag
if existing_docs:
    log.info(f"Skipping {len(existing_docs)} already-extracted TILs")
```

**Option B (If FORCE_RESET needed):**
```python
FORCE_RESET = get_runtime_bool("TIL_FORCE_RESET", default=False)
if FORCE_RESET:
    if JB_ENV == "prod":
        raise ValueError("FORCE_RESET not allowed in production")
    log.warning("FORCE_RESET: truncating metadata table — all extraction state lost")
    spark.sql(f"TRUNCATE TABLE {TIL_METADATA_TABLE}")
```

**Recommendation:** Skip FORCE_RESET for now. We can add an admin reset job later.

---

### 7. Why MAX_CHARS_PER_PDF?

**Current:**
```python
MAX_CHARS_PER_PDF = 40000  # Limit text passed to LLM
```

**Rationale:**
- LLM context window is finite (typically 4K-8K tokens)
- 40KB ≈ ~8K-10K tokens (rough: 5 chars per token)
- Prevents truncation of user prompt + safety margin
- Matches DS team's approach (check their value)

**Question:** Is 40KB the right threshold?
- If `max_tokens=4000` in LLM call, and input is ~10K tokens, leaves only ~-6K for output (BAD)
- Should actually be: `input_max_chars = (context_window_tokens - reserved_output_tokens) * 5`

**Recommendation:**
```python
# Better approach:
LLM_CONTEXT_WINDOW_TOKENS = 4096  # or 8192 for larger models
LLM_RESERVED_OUTPUT_TOKENS = 4000  # max_tokens parameter
LLM_RESERVED_SYSTEM_TOKENS = 500   # system prompt overhead
MAX_CHARS_PER_PDF = (LLM_CONTEXT_WINDOW_TOKENS - LLM_RESERVED_OUTPUT_TOKENS - LLM_RESERVED_SYSTEM_TOKENS) * 5
# = (4096 - 4000 - 500) * 5 = -2040 (INVALID)

# Actually: This suggests we need a bigger context window, or smaller output max_tokens
# Decision: What context window does our LLM have?
```

**Action:** Verify with LLM model specs. For now, keep `40000` but document the reasoning.

---

### 8. TARGET_TIL_NUMBERS — Comma-separated?

**Current:**
```python
TARGET_TIL_NUMBERS = []  # Set to ["TIL 2284", "TIL 1937-R2"] to limit to specific TILs
```

**Question:** How does user pass this?

**FSR Pattern:**
```python
TARGET_PDF_NAMES = parse_runtime_list("FSR_TARGET_PDF_NAMES")
# User passes: "FSR_TARGET_PDF_NAMES=fsr-001,fsr-002,fsr-003"
# Or via env var: FSR_TARGET_PDF_NAMES="fsr-001;fsr-002"
# Returns: ["fsr-001", "fsr-002", "fsr-003"]
```

**Recommendation:**
```python
TARGET_TIL_NUMBERS = parse_runtime_list("TIL_TARGET_TIL_NUMBERS")
# User: dbutils.widgets.setVal("TIL_TARGET_TIL_NUMBERS", "TIL 2284,TIL 1937-R2")
# Or: --parameters TIL_TARGET_TIL_NUMBERS="TIL 2284,TIL 1937-R2"
```

**Don't hard-code in notebook.** Use the runtime parameter pattern.

---

### 9. API token retrieval — Why is this needed?

**Current:**
```python
api_token = dbutils.notebook.entry_point.get_dbutils().notebook.getContext().apiToken().get()
workspace_url = spark.conf.get("spark.databricks.workspaceUrl")
endpoint_url = f"https://{workspace_url}/serving-endpoints/{model}/invocations"
```

**Question:** Are we calling Databricks Foundation Model serving endpoint directly?

**Compare:**
- **FSR:** Uses LiteLLM gateway (external service), passes `LITELLM_API_KEY`
- **DS Team:** Need to check (likely LiteLLM or Foundation HTTP endpoint)

**Alternatives:**
1. **Databricks Native Serving Endpoint** (current approach)
   - Pro: No external gateway, uses Databricks auth
   - Con: Requires serving endpoint deployment

2. **LiteLLM Gateway** (FSR pattern)
   - Pro: Tested, handles model routing, works with DS team code
   - Con: External dependency, different auth model

**Recommendation:** Align with FSR/DS team. Check what they use. If using LiteLLM:
```python
# Instead of direct endpoint call:
from code_assets.runtime.llm import call_llm, parse_llm_response

parsed_profile, raw_response = call_llm(
    system_prompt=SYSTEM_PROMPT,
    user_prompt=user_prompt,
    model=LLM_MODEL,
    temperature=0.0,
)
```

**Decision needed:** Which LLM calling pattern do we use?

---

### 10. Unused variables — Clean up

**Current:**
```python
parsed_profile, raw_response, llm_latency = call_llm_for_profile_extraction(...)

extraction_confidence = parsed_profile.get("extraction_confidence", 0.0) if parsed_profile else 0.0
```

**Issues:**
- `raw_response` is captured but never used
- `llm_latency` is captured but never used (latency is computed again in `return` dict)

**Recommendation:**
```python
# Keep raw_response if we want to store LLM response for debugging:
parsed_profile, raw_response, llm_latency = call_llm_for_profile_extraction(...)

# Store raw_response in output for audit trail:
return {
    ...,
    "raw_llm_response": raw_response[:500] if raw_response else None,  # First 500 chars for debugging
    "latency_s": llm_latency,  # Use this, not recalculated
}

# OR discard if not needed:
parsed_profile, _, _ = call_llm_for_profile_extraction(...)
```

**Decision:** Do we need to store raw LLM response for audit/debugging?

---

### 11. Check FSR's pdf_bytes reading

**Current:**
```python
pdf_bytes = dbutils.fs.get_file_stream(volume_path).read()
```

**FSR's approach:** Yes, same pattern. This is correct.

**Verification:** Confirmed. ✅ No change needed.

---

### 12. Remove emoji icons

**Current:**
```python
log.info(f"  ✅ Success (confidence: {result['extraction_confidence']:.2f}, latency: {result['latency_s']:.1f}s)")
log.warning(f"  ❌ Failed: {result['error']}")
```

**FSR Pattern:** No emojis, plain logging

**Recommendation:**
```python
if result["error"]:
    log.warning(f"Failed to extract {til_number}: {result['error']}")
else:
    log.info(f"Extracted {til_number} (confidence: {result['extraction_confidence']:.2f}, latency: {result['latency_s']:.1f}s)")
```

**Action:** Remove all emojis from logging.

---

### 13. Delta MERGE strategy — Keys and WHEN clauses

**Current:**
```python
output_df.write \
    .format("delta") \
    .mode("append") \
    .option("mergeSchema", "true") \
    .saveAsTable(METADATA_TABLE, path=None)
```

**Problem:** This uses APPEND mode, not MERGE. No conflict resolution.

**FSR Pattern:** Uses explicit MERGE with WHEN MATCHED/WHEN NOT MATCHED:
```sql
MERGE INTO target AS tgt
USING source AS src
ON tgt.document_id = src.document_id
WHEN MATCHED AND tgt.metadata_status NOT IN ('COMPLETED', 'FAILED') THEN 
    UPDATE SET metadata_status = src.metadata_status, ...
WHEN NOT MATCHED THEN 
    INSERT (document_id, metadata_status, ...) 
    VALUES (src.document_id, src.metadata_status, ...)
```

**Critical questions:**
1. **Primary Key:** What uniquely identifies a TIL profile?
   - `til_number` (e.g., "TIL 2284" or "TIL 1937-R2")?
   - Or auto-generated `extraction_id` (UUID)?
   - What about revisions? Do we keep all revisions or only latest?

2. **Update semantics:** Should we overwrite an extraction if:
   - `extraction_confidence` improves?
   - We have a new LLM version?
   - Or keep first successful extraction?

3. **Status tracking:** Should we track `metadata_status` (PENDING → COMPLETED/FAILED) like FSR?

**Recommendation:**
```python
# Design question first: What is the unique key for TILs?
# Assuming: til_number is unique, but we might re-extract

MERGE_SQL = f"""
MERGE INTO {TIL_METADATA_TABLE} AS tgt
USING (
    SELECT * FROM src_temp
) AS src
ON tgt.til_number = src.til_number
WHEN MATCHED THEN 
    UPDATE SET 
        parsed_profile = src.parsed_profile,
        extraction_confidence = src.extraction_confidence,
        extraction_method = src.extraction_method,
        error_message = src.error_message,
        extraction_timestamp = src.extraction_timestamp,
        metadata_status = CASE 
            WHEN src.error_message IS NULL THEN 'COMPLETED'
            ELSE 'FAILED'
        END
WHEN NOT MATCHED THEN 
    INSERT (
        til_number, parsed_profile, extraction_confidence, extraction_method, 
        error_message, extraction_timestamp, metadata_status
    )
    VALUES (
        src.til_number, src.parsed_profile, src.extraction_confidence, src.extraction_method,
        src.error_message, src.extraction_timestamp,
        CASE WHEN src.error_message IS NULL THEN 'COMPLETED' ELSE 'FAILED' END
    )
"""
```

**Decision needed:**
- What is the unique key for TIL profiles? (til_number? until_number + revision?)
- Should we track metadata_status like FSR does?
- Should we allow re-extraction or is first extraction final?

---

### 14. Metadata Status & Chunk Status (from FSR)

**FSR Pattern:** Two-stage workflow
```
metadata_status: PENDING → COMPLETED | FAILED
chunk_status:    PENDING → COMPLETED | FAILED
```

**Design question:** Should TIL pipeline follow this?

**Recommendation:** Yes, add to schema:
```python
# In til_config.py:
@dataclass
class MetadataStatus:
    PENDING = "pending"      # Discovered, not yet processed
    COMPLETED = "completed"  # Extraction succeeded
    FAILED = "failed"        # Extraction failed

@dataclass  
class ChunkStatus:
    PENDING = "pending"      # Not yet chunked
    COMPLETED = "completed"  # Chunking succeeded
    FAILED = "failed"        # Chunking failed

# In notebook:
output_rows.append({
    ...,
    "metadata_status": "completed" if result["error"] is None else "failed",
    "chunk_status": "pending",  # Will be updated by P2
})
```

---

### 15. Design Deviation — til-design.md

**Question:** Are we deviating from the design doc? What are the reasons?

**To assess:** Need to compare:
1. **Extraction module:** Design says "replaceable parser" — we're using ai_parse_document (✓ correct)
2. **LLM normalization:** Design says do this in Silver — we are (✓ correct)
3. **Silver outputs:** Design says extract metadata + lineage + quality signals — we do (✓ correct)
4. **Storage:** Design implies Delta table with lineage — we use Delta (✓ correct but need MERGE)
5. **Validation gates:** Design says mandatory fields + schema checks — we normalize but don't validate (✗ gap)

**Gaps vs. design:**
- No explicit validation gate (should fail/flag if mandatory fields missing)
- No lineage metadata (parser version, prompt version, model version)
- No quality status field (pass/review/fail like FSR)
- No MERGE strategy (just append)

**Recommendation:** Add to output schema:
```python
{
    "til_number": "TIL 2284",
    "parsed_profile": {...},
    "extraction_confidence": 0.92,
    
    # Quality & Lineage
    "metadata_status": "completed",      # PENDING → COMPLETED | FAILED
    "chunk_status": "pending",           # PENDING (for P2 to fill)
    "extraction_method": "ai_parse_document",
    "extraction_version": "v1",          # For replay/lineage
    "llm_model": "databricks-gpt-oss-20b",
    "llm_prompt_version": "2026-06-02",  # DS team template version
    
    "extraction_timestamp": "2026-06-24T...",
    "error_message": None,
}
```

---

## Summary of Required Decisions

| Item | Decision | Impact |
|------|----------|--------|
| **Config pattern** | Use til_config.py (like FSR) | Centralized, parameterized |
| **LLM calling** | FSR/DS team pattern? (LiteLLM vs. serving endpoint) | Affects auth, model availability |
| **Schema naming** | What is `vgpd.til_profiles`? Single table or schema? | Table naming, schema organization |
| **Unique key** | til_number or til_number+revision? | MERGE logic, upsert semantics |
| **Status tracking** | Add metadata_status/chunk_status like FSR? | Audit, re-extraction control |
| **FORCE_RESET** | Skip for now, separate admin job later? | Security, simplicity |
| **Max tokens math** | Verify LLM context window | Prevent LLM truncation errors |

---

## Revised Implementation Checklist

- [ ] Create `til_config.py` (follow FSR pattern)
- [ ] Remove sys.path.insert, use %run instead
- [ ] Remove dead imports (tempfile, base64, Path, Optional)
- [ ] Parameterize all hardcoded values (via widgets)
- [ ] Clarify: LLM calling pattern (align with FSR/DS team)
- [ ] Remove emojis from logging
- [ ] Implement MERGE logic with proper WHEN clauses
- [ ] Add metadata_status, chunk_status fields
- [ ] Add lineage fields (extraction_version, prompt_version)
- [ ] Add validation gate (flag if mandatory fields missing)
- [ ] Remove FORCE_RESET flag (defer to admin utility)
- [ ] Document unique key strategy for TILs
- [ ] Test on 2-3 PDFs before scaling

