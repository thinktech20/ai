# TIL Process 1 Implementation Guide

## Overview

Process 1 (TIL Metadata Extraction) extracts structured TIL profiles from PDF documents using:
1. **Parser:** Databricks native `ai_parse_document` (replaces Foundation API)
2. **LLM:** Databricks Foundation Model serving endpoint for field extraction
3. **Schema:** 40+ structured fields with normalization and validation
4. **Architecture:** Full-document extraction + structured LLM normalization (Option C - Hybrid)

## Components Created

### 1. `til_profile_schema.py`
**Purpose:** Schema definition, normalization, validation

**Functions:**
- `normalize_til_profile(profile)` — Ensures all 40+ fields present with proper defaults
- `validate_mandatory_fields(profile)` — Checks required fields are populated
- `get_til_profile_json_schema()` — Returns JSON schema for docs

**Usage:**
```python
from silver.src.tils.til_profile_schema import normalize_til_profile

parsed_profile = normalize_til_profile(llm_output)
is_valid, missing = validate_mandatory_fields(parsed_profile)
```

### 2. `til_profile_extraction_llm.py`
**Purpose:** LLM prompt templates and JSON parsing

**Key Components:**
- `SYSTEM_PROMPT` — Expert engineer role with extraction constraints
- `USER_PROMPT_TEMPLATE` — Populated with extracted text + tables
- `build_user_prompt(pdf_text, tables)` — Constructs final prompt
- `extract_json_from_llm_response(raw_response)` — Robust JSON parsing (handles markdown fences)
- `clean_text(value)` — Text normalization

**DS Team Prompt Features:**
- Do not infer (strict extraction rules)
- Search entire document for parts/MLI (not just dedicated sections)
- Capture configuration-dependent rules (7 text fields)
- SBOM-aware (parts, MLI numbers, config variables)
- Safety/damage language detection
- Usage counter requirements (critical for scheduling)
- Source snippets for explainability
- Extraction confidence score

**Usage:**
```python
from silver.src.tils.til_profile_extraction_llm import (
    SYSTEM_PROMPT,
    build_user_prompt,
    extract_json_from_llm_response,
)

user_prompt = build_user_prompt(pdf_text, tables)
parsed_profile = extract_json_from_llm_response(llm_response)
```

### 3. `nb_sdg_til_metadata.py` (Process 1 Notebook)
**Purpose:** Main orchestration for TIL metadata extraction

**Key Sections:**

**Discovery:**
- Lists TIL PDFs from Databricks volumes
- Uses `discover_tils()` utility from `til_profile_extraction.py`
- Filters by TARGET_TIL_NUMBERS if specified
- Can limit to MAX_PDFS for testing

**Text Extraction:**
- Calls `ai_parse_document(content, version='2.0')` for each PDF
- Returns VARIANT type with nested JSON structure
- Extracts text + labeled tables
- Handles VARIANT type by casting to JSON string, then parsing

**LLM Extraction:**
- Builds user prompt with extracted text + tables
- Calls Databricks Foundation Model serving endpoint (via API)
- Uses system + user prompts for structured field extraction
- Temperature = 0.0 (strict, no creativity)
- Max tokens = 4000 (for detailed responses)

**Schema Normalization:**
- Applies `normalize_til_profile()` to LLM output
- Ensures all fields present with proper defaults
- Validates mandatory fields

**Storage:**
- Writes results to Delta table: `vgpd.til_profiles.til_metadata`
- Schema: til_number, parsed_profile (JSON string), extraction_confidence, latency_s, error_message, timestamp
- Append mode (allows incremental processing)

**Quality Signals:**
- Extracts extraction_confidence from LLM response
- Tracks latency per PDF
- Records error messages for failed extractions
- Generates summary statistics (success rate, avg confidence, avg latency)

## Parameters

Set via Databricks widgets:

```python
llm_model = "databricks-gpt-oss-20b"  # Default Databricks model
max_pdfs = None                        # Limit for testing (None = unlimited)
force_reset = "false"                  # Reprocess already-extracted PDFs
```

## Running the Notebook

### Option 1: Quick Test (5 PDFs)
```bash
databricks workspace run \
  --notebook-path /Workspace/Repos/..../silver/src/etl/nb_sdg_til_metadata \
  --parameters="max_pdfs=5,llm_model=databricks-gpt-oss-20b"
```

### Option 2: Specific TILs (Testing)
Edit notebook to set:
```python
TARGET_TIL_NUMBERS = ["TIL 2284", "TIL 1937-R2", "TIL 2069"]
```

### Option 3: Full Corpus
```bash
databricks workspace run \
  --notebook-path /Workspace/Repos/..../silver/src/etl/nb_sdg_til_metadata \
  --parameters="llm_model=databricks-gpt-oss-20b"
```

## Data Flow

```
PDF (bytes)
  ↓
ai_parse_document(v2.0)
  → VARIANT with {metadata, document.{pages[], elements[]}}
  ↓
Extract Text + Tables (from VARIANT)
  → text_content: "TIL 2284...", tables: [{type, content, confidence}]
  ↓
Build User Prompt (text + tables)
  ↓
LLM Extraction (System + User Prompt)
  → raw_response: "```json\n{...}\n```"
  ↓
Parse JSON (strip markdown fences)
  → parsed_profile: {til_number, revision, ..., extraction_confidence}
  ↓
Normalize Schema
  → Add defaults, ensure all fields present
  ↓
Validate (check mandatory fields)
  ↓
Write to Delta Table
  → {til_number, parsed_profile (JSON string), confidence, latency, error, timestamp}
```

## Output Schema (40+ Fields)

### Required Fields (checked by validation)
- `til_number` — TIL identifier (e.g., "TIL 2284")
- `title` — Human-readable title
- `compliance_category_code` — M | C | A | S
- `scope_of_work` — Array of work items
- `service_recommendation_line_items` — Array of recommendations
- `extraction_confidence` — 0.0-1.0 confidence score

### Configuration Applicability (7 text fields)
- `frame_or_model_applicability_text` — Frame types (6F, 7F, 9F, etc.)
- `combustion_or_fuel_configuration_text` — Fuel/combustion config
- `hardware_or_part_configuration_text` — Hardware specifics
- `serial_or_unit_applicability_text` — Serial number requirements
- `exclusions_or_non_applicable_conditions_text` — Non-applicable rules
- `required_prior_modifications_text` — Prerequisites
- `prerequisite_outage_or_inspection_context_text` — Context

### Critical Fields (for scheduling + SBOM)
- `usage_counters_to_check_or_consider` — Array (e.g., ["factored_fired_hours", "starts"])
- `usage_counter_requirements_text` — Detailed interval logic
- `parts_referenced` — Array of {part_number, context, inspection_types, source_location}
- `mli_numbers` — Array of {mli_number, context}
- `sbom_dependency_flag` — Boolean
- `reference_documents` — Array of {document_number, type, context}

### Risk + Consequences
- `severity_signals` — Array (safety/damage language)
- `failure_consequences` — Array
- `safety_or_damage_language_found` — Boolean
- `risk_summary` — Summary text

### Quality Signals
- `extraction_confidence` — 0.0-1.0 (from LLM)
- `missing_information_flags` — Array of gaps identified
- `source_snippets` — Array of {field, verbatim_evidence}

## Integration with Downstream Processes

### Process 1 → Process 2 (Chunking)
- P1 produces: `parsed_profile` (JSON) + `extracted_text_length`
- P2 reads: Extract `scope_of_work` + `service_recommendation_line_items` for section boundaries
- P2 uses: Full markdown or re-extracted document text for semantic chunking

### Process 1 → App Layer (Applicability Logic)
- App reads: `parsed_profile` JSON fields
- Uses: `frame_or_model_applicability_text`, `usage_counter_requirements_text`, `sbom_dependency_flag`
- For filtering: `compliance_category_code`, `parts_referenced`, `mli_numbers`

### Process 1 → Vector Index
- Store: `parsed_profile.title`, `parsed_profile.scope_of_work`, `parsed_profile.service_recommendation_line_items`
- For retrieval: Full semantic markdown (if available) or reconstructed text from profile fields

## Key Differences from DS Team's Implementation

| Aspect | DS Team | Our Implementation |
|--------|---------|-------------------|
| **Parser** | Foundation API (external service) | ai_parse_document (Databricks native) |
| **PDF Access** | Local workspace + Databricks volume + SQL fallback | Databricks volume only (via dbutils.fs) |
| **LLM Gateway** | LiteLLM external gateway | Databricks Foundation Model serving endpoint |
| **Schema** | 40+ fields (same) | 40+ fields (same) |
| **Prompt** | v2026-06-02a template (same) | Adapted from template (same rules) |
| **Output Format** | profile_response.json per TIL | Delta table (normalized schema) |

## Error Handling

**VARIANT Parsing Failures:**
- If `to_json(parsed_content)` fails → error logged, continue to next PDF
- If JSON is malformed → catch in `extract_text_and_tables_from_parsed_doc()`, return empty text

**LLM Failures:**
- If LLM endpoint unreachable → return `None, "connection error", latency`
- If JSON parse fails → `extract_json_from_llm_response()` returns `None`
- Error message stored in Delta for debugging

**File Access Failures:**
- If PDF not found in volume → catch exception, store error
- If FS.get_file_stream fails → error message recorded

## Validation Checks (Post-Extraction)

```python
# In notebook
is_valid, missing = validate_mandatory_fields(parsed_profile)
if not is_valid:
    log.warning(f"  ⚠️ Missing mandatory fields: {missing}")
    # Still store to Delta with quality flag = "review"
```

## Next Steps

1. **Test on 2-3 PDFs:**
   ```python
   TARGET_TIL_NUMBERS = ["TIL 2284", "TIL 1937-R2"]
   ```
   Run notebook, inspect results in Delta table

2. **Validate Against DS Team:**
   - Extract same 5 PDFs with our P1
   - Compare field-level accuracy with DS team results
   - Iterate on prompt if needed

3. **Scale to Full Corpus:**
   - Remove TARGET filter
   - Set MAX_PDFS to test batch size
   - Monitor cost + latency + error rates

4. **Implement Process 2:**
   - Use `parsed_profile` fields for section-based chunking
   - Implement semantic chunking strategy
   - Test on chunked output

## Troubleshooting

### Issue: VARIANT type "UNRESOLVED_COLUMN"
**Fix:** Ensure `to_json(parsed_content)` is called before selecting

### Issue: LLM returns empty response
**Fix:** Check model endpoint is accessible, firewall rules, API token

### Issue: JSON parse fails
**Fix:** Check `extract_json_from_llm_response()` handles markdown fences

### Issue: Low extraction confidence
**Fix:** Review LLM prompt, adjust temperature if needed, check PDF quality

