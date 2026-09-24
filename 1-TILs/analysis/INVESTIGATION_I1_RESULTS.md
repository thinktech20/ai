# Phase 1.A Investigation Results — LLM Calling Pattern

**Status:** ✅ Complete  
**Date:** 2026-06-24  
**Source:** DS team code + execution results  

---

## Summary

**The DS team uses LiteLLM gateway with OpenAI-compatible API, NOT Databricks native serving endpoint.**

This is a critical finding: their pattern is significantly different from what was initially coded.

---

## What DS Team Uses

### Infrastructure
- **LLM Gateway:** LiteLLM (external service, OpenAI-compatible)
- **Gateway URL:** `https://dev-gateway.apps.gevernova.net` (or env var `LITELLM_BASE_URL`)
- **Authentication:** Bearer token from `LITELLM_API_KEY` environment variable or `litellm_token.txt`

### Model & Configuration
- **Model:** `azure-gpt-5-2` (OpenAI GPT-5 via LiteLLM proxy)
- **Temperature:** 0.0 (strict extraction, no creativity)
- **Response Format:** JSON object (enforced via `response_format: {"type": "json_object"}`)
- **Timeout:** 300 seconds
- **Retries:** 2 attempts with exponential backoff for retriable status codes

### Code Pattern
```python
# From: code_assets/runtime/llm.py
from code_assets.runtime.llm import call_llm, parse_llm_response

# Call the LLM
raw_response = call_llm(
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    model=model or LLM_MODEL_NAME,  # Defaults to "azure-gpt-5-2"
    temperature=0.0,
)

# Parse response
parsed_profile, raw_response = parse_llm_response(raw_response) if raw_response else None, raw_response
```

### HTTP Request Details
- **Endpoint:** `POST {LITELLM_HOST}/v1/chat/completions`
- **Headers:**
  ```json
  {
    "Authorization": "Bearer {LITELLM_TOKEN}",
    "Content-Type": "application/json"
  }
  ```
- **Payload:**
  ```json
  {
    "model": "azure-gpt-5-2",
    "messages": [
      {"role": "system", "content": "...system_prompt..."},
      {"role": "user", "content": "...user_prompt..."}
    ],
    "temperature": 0.0,
    "response_format": {"type": "json_object"}
  }
  ```

---

## DS Team Results (Validation Data)

**Run:** `til_profile_pilot_20260609_110447` (25 TILs extracted)

| TIL | Status | Method | Confidence |
|-----|--------|--------|-----------|
| TIL 2284 | completed | foundation | 0.92 |
| TIL 1937-R2 | completed | foundation | 0.93 |
| TIL 2342-R1 | completed | foundation | 0.93 |
| ... (22 more) | ... | ... | 0.91-0.93 |

**Average Confidence:** ~92% across 25 TILs  
**Method Used:** `foundation` (the LiteLLM call)  
**Alternative Methods Available:** `pdfplumber` (fast text extraction fallback)

---

## Extraction Pattern (Three-Step Process)

### Step 1: PDF Parsing
- Use Foundation API (external service): `/pdf/extract/` endpoint
- Extract text + tables + metadata from PDF
- Returns structured JSON with `elements[]` array

### Step 2: Text + Table Preparation
- Extract all `elements` where `type` in [text, table, images]
- Build markdown-formatted user prompt with extracted content
- Truncate to 40,000 characters max

### Step 3: LLM Normalization
- Call LiteLLM with system prompt + formatted document text
- System prompt: `til_profile_extraction_pilot_v2026-06-02a.txt` (150+ lines)
- LLM returns JSON with 40+ structured fields
- Parse JSON and normalize schema (handle nulls, defaults, etc.)

---

## Comparison: Current vs. DS Team

### Current (nb_sdg_til_metadata.py)
```
Infrastructure:  Databricks Foundation Model serving endpoint
Model:           databricks-gpt-oss-20b (default, configurable)
Auth:            dbutils.notebook.entry_point.getContext().apiToken()
Response Format: Direct JSON parsing from choices[0].message.content
Temperature:     0.0 ✓
Max Tokens:      4000 ✓
```

### DS Team
```
Infrastructure:  LiteLLM gateway (external, OpenAI-compatible)
Model:           azure-gpt-5-2 (OpenAI GPT-5 via proxy)
Auth:            Bearer token from env var or file
Response Format: Forced JSON via response_format parameter ✓✓
Temperature:     0.0 ✓
Retry Logic:     Built-in with exponential backoff ✓✓
```

---

## Key Decision Points

### 1. LiteLLM vs. Databricks Serving Endpoint

**LiteLLM Advantages:**
- ✅ Proven by DS team (25 TILs, 92% confidence)
- ✅ OpenAI-compatible API (portable, well-documented)
- ✅ Built-in retries and error handling
- ✅ Supports multiple models seamlessly
- ✅ Better response format enforcement

**Databricks Serving Endpoint Advantages:**
- ✅ Native to Databricks workspace (no external dependency)
- ✅ No API key management needed
- ✅ Direct workspace authentication

### 2. Model Choice

**Current:** `databricks-gpt-oss-20b` (Databricks open-source)
**DS Team:** `azure-gpt-5-2` (OpenAI's GPT-5 via Azure)

**Recommendation:** Use DS team's model for consistency:
- Already proven on same TILs (92% confidence)
- Better performance expected
- Maintains reproducibility

### 3. Response Format Enforcement

**Current:** Manual JSON extraction from response text
**DS Team:** Response format enforced via API parameter

**Recommendation:** DS team pattern is superior (guarantees valid JSON)

---

## System Prompt Details

**Source:** `code_assets/experiments/step6/prompts/til_profile_extraction_pilot_v2026-06-02a.txt`

**Length:** ~150 lines of detailed extraction instructions

**Key Rules:**
- "Use only the supplied metadata, text, and tables"
- "Do not infer facts that are not stated"
- "Preserve technical terminology exactly as it appears"
- "Search entire document for part references, not only dedicated sections"
- "For tables without text labels, the information may still appear in extracted text"

**Output Schema:** 40+ structured fields including:
- `til_number`, `revision`, `title`, `publish_date`
- `compliance_category_code`, `scope_of_work`, `service_recommendation_line_items`
- `parts_referenced`, `mli_numbers`, `reference_documents`
- `configuration_variables`, `severity_signals`, `failure_consequences`
- `extraction_confidence` (float 0.0-1.0)
- And 20+ more...

---

## Implementation Recommendation

### Option A: Full Alignment with DS Team (Recommended)
1. Replace Databricks serving endpoint with LiteLLM gateway
2. Update model to `azure-gpt-5-2`
3. Update auth from `dbutils` to environment variable/file-based
4. Reuse DS team's util function: `code_assets.runtime.llm.call_llm()`
5. Reuse DS team's prompt: `til_profile_extraction_pilot_v2026-06-02a.txt`

**Pros:** Proven 92% confidence, code reuse, consistency with DS team
**Cons:** External dependency (LiteLLM gateway availability)

### Option B: Adapt DS Team's Approach to Databricks Endpoint
1. Keep Databricks serving endpoint
2. Adopt response format enforcement pattern
3. Adopt retry logic pattern
4. Update system prompt to match DS team's
5. Update model to best-available Databricks model

**Pros:** No external dependency, native to workspace
**Cons:** Unknown confidence score, untested pattern

### Option C: Hybrid (Current + DS Team Utilities)
1. Keep current infrastructure
2. Import `call_llm` util from DS team
3. Use DS team's system prompt
4. Add response format enforcement
5. Add retry logic

**Pros:** Balanced approach, incremental risk
**Cons:** Not fully tested with current infra

---

## What Was Built vs. What Should Be

### Current (nb_sdg_til_metadata.py)
```python
def call_llm_for_profile_extraction(
    system_prompt, user_prompt, model, temperature=0.0, max_tokens=4000
):
    api_token = dbutils.notebook.entry_point.getContext().apiToken().get()
    workspace_url = spark.conf.get("spark.databricks.workspaceUrl")
    endpoint_url = f"https://{workspace_url}/serving-endpoints/{model}/invocations"
    
    payload = {
        "messages": [...],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    response = requests.post(endpoint_url, headers=headers, json=payload)
    raw_text = response.json()["choices"][0]["message"]["content"]
    parsed_profile = extract_json_from_llm_response(raw_text)
    return parsed_profile, raw_text, latency
```

### Should Be (Following DS Team)
```python
from code_assets.runtime.llm import call_llm, parse_llm_response

raw_response = call_llm(
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    model="azure-gpt-5-2",  # Or env var
    temperature=0.0
)

parsed_profile, _ = parse_llm_response(raw_response) if raw_response else (None, None)
```

---

## Next Steps

### Immediate (Phase 3 Implementation)
- [ ] **Decision:** Choose Option A, B, or C
- [ ] **Update:** Refactor `call_llm_for_profile_extraction()` accordingly
- [ ] **Copy:** Get system prompt from DS team or reuse existing
- [ ] **Test:** Run on 2-3 TILs with both current and DS team pattern
- [ ] **Compare:** Validate extraction_confidence scores

### Deferred (Post-Phase 1)
- [ ] Integration test with full 25 TIL dataset
- [ ] Performance comparison (LiteLLM vs. Databricks)
- [ ] Error handling for external gateway (LiteLLM)
- [ ] Fallback strategy if LiteLLM unavailable

---

## Files Referenced

| File | Purpose |
|------|---------|
| `code_assets/runtime/llm.py` | LLM calling utility (call_llm, parse_llm_response) |
| `code_assets/runtime/config.py` | Configuration (LITELLM_HOST, LLM_MODEL_NAME, etc.) |
| `code_assets/experiments/step6/run_til_profile_extraction_pilot.py` | DS team's main extraction script |
| `code_assets/experiments/step6/prompts/til_profile_extraction_pilot_v2026-06-02a.txt` | System prompt for LLM |
| `code_assets/runtime/retry.py` | Retry logic for resilience |

---

## ✅ Decision: Option A (Full LiteLLM Alignment)

**Implementation Status:** Ready for Phase 3

**Files Created:**
1. **`pw_sdg_ai_ser_repo/common/til_llm_config.py`** (NEW)
   - LiteLLM gateway configuration (following FSR pattern)
   - API key resolution: env var → config file → default
   - Model, timeout, retry settings
   - Lazy-loaded config with validation

2. **`pw_sdg_ai_ser_repo/common/til_llm_client.py`** (NEW)
   - `call_llm()` function (OpenAI-compatible API wrapper)
   - `parse_llm_response()` function (JSON parsing)
   - `extract_til_profile_via_llm()` convenience function
   - Automatic retries (2 attempts) for retriable status codes
   - SSL warning suppression for internal gateway

**Key Improvements Over Original:**
- ✅ Uses LiteLLM gateway (proven by DS team, 92% confidence)
- ✅ Follows FSR pattern for API key management (env → file → default)
- ✅ Forced JSON response format (no manual extraction fragility)
- ✅ Built-in retry logic (handles transient failures)
- ✅ Timeout: 300 seconds (5 minutes for large documents)
- ✅ Temperature: 0.0 (strict extraction, no creativity)
- ✅ Model: `azure-gpt-5-2` (OpenAI GPT-5 via LiteLLM proxy)

**How to Deploy:**
1. Set `LITELLM_API_KEY` environment variable or create `~/.litellm_config`
2. Set `LITELLM_BASE_URL` (default: `https://dev-gateway.apps.gevernova.net`)
3. Set `TIL_LLM_MODEL` (default: `azure-gpt-5-2`)
4. Import and use: `from common.til_llm_client import extract_til_profile_via_llm`

**Phase 3 Implementation Roadmap:**
1. Update `nb_sdg_til_metadata.py` to use `extract_til_profile_via_llm()` instead of direct Databricks endpoint
2. Remove manual API token extraction code
3. Remove Databricks workspace URL detection code
4. Test on 2-3 TILs to validate extraction_confidence scores
5. Run full 25-TIL validation against DS team results

