# Option A Implementation — Deployment Guide

**Status:** ✅ Ready for Phase 3  
**Date:** 2026-06-24  
**Implemented by:** LLM Assistant  

---

## What Was Implemented

### Files Created

**1. `pw_sdg_ai_ser_repo/common/til_llm_config.py`** (NEW)
- LiteLLM gateway configuration following FSR pattern
- API key resolution: `LITELLM_API_KEY` env var → `~/.litellm_config` file → hardcoded default
- Gateway URL: `https://dev-gateway.apps.gevernova.net` (configurable)
- Model: `azure-gpt-5-2` (configurable)
- Includes: temperature, max_tokens, timeout, retry settings

**2. `pw_sdg_ai_ser_repo/common/til_llm_client.py`** (NEW)
- Main LLM calling client for OpenAI-compatible LiteLLM API
- Functions:
  - `call_llm()` - Call LiteLLM with auto-retry logic
  - `parse_llm_response()` - Parse JSON response
  - `extract_til_profile_via_llm()` - Convenience wrapper with timing
- Features:
  - Forced JSON response format (no fragile manual extraction)
  - Automatic retry (2 attempts) for transient failures
  - 300-second timeout for large documents
  - SSL warning suppression for internal gateway

---

## Deployment Steps

### Step 1: Set Up LiteLLM Authentication

Choose ONE of these methods:

**Option A: Environment Variable (Recommended for Databricks jobs)**
```bash
export LITELLM_API_KEY="your-api-key-here"
export LITELLM_BASE_URL="https://dev-gateway.apps.gevernova.net"  # optional
```

**Option B: Config File (For local development)**
```bash
cat > ~/.litellm_config << 'EOF'
your-api-key-here
EOF
chmod 600 ~/.litellm_config
```

**Option C: Job Parameters (For Databricks jobs)**
In your job configuration, add base parameters:
```json
{
  "LITELLM_API_KEY": "your-api-key-here",
  "LITELLM_BASE_URL": "https://dev-gateway.apps.gevernova.net",
  "TIL_LLM_MODEL": "azure-gpt-5-2"
}
```

### Step 2: Update `nb_sdg_til_metadata.py`

Replace the current `call_llm_for_profile_extraction()` function (lines 195-250).

**Before:**
```python
def call_llm_for_profile_extraction(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 4000,
) -> tuple[dict[str, Any] | None, str | None, float]:
    """Call LLM to extract structured TIL profile."""
    # 50+ lines of Databricks endpoint code
```

**After:**
```python
def call_llm_for_profile_extraction(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 4000,
) -> tuple[dict[str, Any] | None, str | None, float]:
    """Call LLM to extract structured TIL profile (via LiteLLM gateway)."""
    from silver.src.common.til_llm_client import extract_til_profile_via_llm
    return extract_til_profile_via_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
    )
```

**Or simpler:** Replace all calls to `call_llm_for_profile_extraction()` with direct calls to:
```python
from silver.src.common.til_llm_client import extract_til_profile_via_llm

parsed_profile, raw_response, latency = extract_til_profile_via_llm(
    system_prompt=SYSTEM_PROMPT,
    user_prompt=user_prompt,
    model=TIL_LLM_MODEL,
)
```

### Step 3: Test on Sample TILs

**Test TIL 1: TIL 2284**
```python
# In notebook:
til_number = "2284"
pdf_path = "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new/TIL_2284.pdf"

# Extract and verify
# Expected: extraction_confidence ≥ 0.91 (DS team got 0.92)
```

**Test TIL 2: TIL 1937-R2**
```python
til_number = "1937-R2"
pdf_path = "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new/TIL_1937-R2.pdf"

# Expected: extraction_confidence ≥ 0.92
```

### Step 4: Validate Against DS Team Results

Compare your results with DS team's baseline:
```bash
# DS team results location:
ls -la /home/u560060992/dbx/1-TILs/analysis/ds-team-til-profile-results/til_profile_pilot_20260609_110447/
```

---

## Configuration Reference

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LITELLM_API_KEY` | (required) | Bearer token for LiteLLM gateway |
| `LITELLM_BASE_URL` | `https://dev-gateway.apps.gevernova.net` | LiteLLM gateway URL |
| `TIL_LLM_MODEL` | `azure-gpt-5-2` | LLM model name |

### Hardcoded Settings (in `til_llm_config.py`)

| Setting | Value | Purpose |
|---------|-------|---------|
| `TIL_LLM_TEMPERATURE` | 0.0 | Strict extraction, no creativity |
| `TIL_LLM_MAX_TOKENS` | 4000 | Max response size |
| `TIL_LLM_TIMEOUT_SECONDS` | 300 | Request timeout (5 minutes) |
| `TIL_LLM_MAX_RETRIES` | 2 | Retry attempts for transient failures |

### API Endpoint

- **URL:** `{LITELLM_BASE_URL}/v1/chat/completions`
- **Method:** POST
- **Response Format:** Forced JSON via `response_format: {"type": "json_object"}`

---

## Troubleshooting

### Issue: API Key Not Found
```
ValueError: LiteLLM API key not found. Set LITELLM_API_KEY or create ~/.litellm_config
```

**Solution:**
1. Set environment variable: `export LITELLM_API_KEY="..."`
2. Or create config file: `cat > ~/.litellm_config << 'EOF' ... EOF`
3. Or add to job parameters

### Issue: Connection Refused
```
ConnectionError: Failed to connect to https://dev-gateway.apps.gevernova.net
```

**Solution:**
1. Verify gateway URL: `echo $LITELLM_BASE_URL`
2. Check network connectivity: `curl -I https://dev-gateway.apps.gevernova.net`
3. Verify you're on correct network (VPN if required)

### Issue: 401 Unauthorized
```
HTTP 401: Unauthorized
```

**Solution:**
1. Verify API key is correct: `echo $LITELLM_API_KEY | head -c 20`
2. Check if key is base64-encoded (shouldn't be for bearer tokens)
3. Get fresh API key from gateway admin

### Issue: Low extraction_confidence
```
extraction_confidence: 0.65 (expected ≥ 0.91)
```

**Possible causes:**
1. Different LLM model than DS team's `azure-gpt-5-2`
2. Different system/user prompt format
3. Temperature setting > 0.0
4. Document preprocessing differences (text extraction, table parsing)

**Solution:**
1. Verify model: `echo $TIL_LLM_MODEL` (should be `azure-gpt-5-2`)
2. Verify temperature: hardcoded to 0.0 in config
3. Compare document text with DS team's extraction
4. Check if tables are extracted correctly

---

## API Key Management (FSR Pattern Details)

The implementation follows FSR's security pattern:

1. **Priority 1: Environment Variable**
   - Read: `os.getenv("LITELLM_API_KEY")`
   - Use case: Databricks job parameters, CI/CD secrets

2. **Priority 2: Config File**
   - Read: `~/.litellm_config` (home directory)
   - Also checked: `/etc/litellm_config`, `/Workspace/config/litellm_config`
   - Use case: Local development, shared admin configs

3. **Priority 3: Hardcoded Default**
   - Not applicable for API key (security risk)
   - Would fall back to error if not found

4. **Base64 Decoding**
   - Automatically detects and decodes if accidentally stored encoded
   - Skips if already looks like token/URL

---

## What Changed vs. Original Code

| Aspect | Original | New |
|--------|----------|-----|
| **Infrastructure** | Databricks serving endpoint | LiteLLM gateway |
| **Model** | databricks-gpt-oss-20b | azure-gpt-5-2 |
| **Auth** | `dbutils.notebook.entry_point.getContext().apiToken()` | Environment variable (FSR pattern) |
| **Response Parsing** | Manual JSON extraction from response text | Forced JSON via API parameter |
| **Retry Logic** | None | 2 automatic retries |
| **Timeout** | 60 seconds | 300 seconds |
| **Error Handling** | Basic logging | Comprehensive with retry tracking |
| **Proven Results** | Unknown | 92% avg confidence (25 TILs) |

---

## Next Steps After Deployment

### Phase 1: Validation (1-2 hours)
- [ ] Test on TIL 2284 (target: extraction_confidence ≥ 0.91)
- [ ] Test on TIL 1937-R2 (target: extraction_confidence ≥ 0.92)
- [ ] Compare with DS team baseline results

### Phase 1.B-E: Continue Investigation (Remaining Phase 1)
- [ ] I2: Shared utility functions (OPTIONAL - already mostly done)
- [ ] I3: Table schema clarification (vgpd.til_profiles structure)
- [ ] I4: TIL unique key strategy (for Delta MERGE)
- [ ] I5: Status tracking pattern (metadata_status field)

### Phase 3: Complete Refactoring
- [ ] Update Delta MERGE logic (once I4 is decided)
- [ ] Add status tracking (once I5 is decided)
- [ ] Run full 25-TIL validation
- [ ] Deploy to production

---

## Questions?

Refer to:
1. **Full Decision Document:** [INVESTIGATION_I1_RESULTS.md](INVESTIGATION_I1_RESULTS.md)
2. **Action Plan:** [ACTION_PLAN.md](ACTION_PLAN.md)
3. **DS Team Reference:** `/home/u560060992/dbx/SDG_Scoping_Feedback_Loop/code_assets/runtime/llm.py`

