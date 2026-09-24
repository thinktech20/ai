# TIL Pipeline Process 1 - Implementation Summary

**Date:** 2026-06-24  
**Architecture:** Option C (Hybrid) - Full-document extraction + LLM structured normalization  
**Parser:** ai_parse_document (Databricks native, replaces Foundation API)  
**Status:** ✅ Implementation Complete, Ready for Testing

---

## What Was Delivered

### 1. Core Components (Python Modules)

#### `til_profile_schema.py`
- **normalize_til_profile()** — Ensures 40+ fields present with proper defaults
- **validate_mandatory_fields()** — Checks required fields are populated
- **get_til_profile_json_schema()** — JSON schema for documentation

#### `til_profile_extraction_llm.py`
- **SYSTEM_PROMPT** — Expert engineer role with DS team's extraction constraints
- **USER_PROMPT_TEMPLATE** — Comprehensive 40-field extraction schema
- **build_user_prompt()** — Populates prompt with extracted text + tables
- **extract_json_from_llm_response()** — Robust JSON parsing (handles markdown fences)
- **clean_text()** — Text normalization

#### `nb_sdg_til_metadata.py` (Process 1 Notebook)
- **PDF Discovery** — Lists TILs from Databricks volumes
- **Text Extraction** — ai_parse_document → VARIANT → JSON → text + tables
- **LLM Extraction** — Calls Databricks Foundation Model endpoint
- **Schema Normalization** — Applies defaults, validates mandatory fields
- **Delta Storage** — Writes results to `vgpd.til_profiles.til_metadata`
- **Quality Metrics** — Tracks confidence, latency, success rate

### 2. Documentation

#### `P1_IMPLEMENTATION_GUIDE.md`
- Component overview and usage examples
- Running instructions (test, specific TILs, full corpus)
- Output schema (40+ structured fields)
- Integration points (P2, app layer, vector index)
- Error handling and troubleshooting

#### Architecture Decision Documents (from previous phase)
- `ARCHITECTURE_DECISION_ANALYSIS.md` — Why Option C
- `TIL_PIPELINE_COMPLETION_PLAN.md` — Full project plan

---

## Key Design Decisions

### Parser: ai_parse_document Instead of Foundation
| Aspect | ai_parse_document | Foundation |
|--------|---------|-----------|
| **Accessibility** | ✅ Databricks native | ❌ External service (not accessible from dbx) |
| **Cost** | ✅ Included in Databricks | ❌ Paid API calls |
| **Type Handling** | ⚠️ VARIANT (requires JSON cast) | ✅ Native JSON |
| **Quality** | ⚠️ Adequate for structured docs | ✅ Better for complex layouts |

**Mitigation:** Explicit VARIANT type handling via `to_json()` + `cast(... AS STRING)` (proven in analysis notebooks)

### LLM: Databricks Foundation Model Endpoint
- **Advantage:** Native integration, managed authentication
- **Configuration:** Via API token + workspace URL
- **Temperature:** 0.0 (strict extraction, no creativity)
- **Max tokens:** 4000 (detailed responses with snippets)

### Storage: Delta Table (Append Mode)
- Allows incremental processing (don't reprocess already-extracted)
- Schema evolution supported
- Time-series audit trail (timestamps)
- Easy integration with subsequent processes

---

## Output Schema (40+ Fields)

### Identifiers & Metadata
```
til_number         — TIL ID (e.g., "TIL 2284")
revision          — Revision number (or null)
title             — Human-readable title
publish_date      — YYYY-MM-DD format
reason_for_revision — Why this revision
```

### Classification (Mandatory)
```
compliance_category_code    — M | C | A | S (mandatory)
compliance_category_text    — Full category description
recurring_indicator_if_found — One-time or repeating?
coarse_outage_type          — HGP, MI, etc.
```

### Operational Content (Mandatory)
```
scope_of_work                    — Array of work items
service_recommendation_line_items — Array of recommendations
completion_criteria_text         — How to know when done
maintenance_trigger_text         — What triggers this TIL
recommended_interval_or_trigger  — When to perform
```

### Configuration Applicability (7 Text Fields)
```
frame_or_model_applicability_text           — Frame types (6F, 7F, 9F, etc.)
combustion_or_fuel_configuration_text       — Fuel/combustion config
hardware_or_part_configuration_text         — Hardware specifics
serial_or_unit_applicability_text           — Serial number requirements
exclusions_or_non_applicable_conditions_text — Non-applicable rules
required_prior_modifications_text           — Prerequisites
prerequisite_outage_or_inspection_context_text — Context needed
```

### Usage Counters (Critical for Scheduling)
```
usage_counters_to_check_or_consider  — Array (e.g., ["factored_fired_hours", "starts"])
usage_counter_requirements_text      — Detailed interval logic (e.g., "ECRT = ...")
```

### SBOM & Parts (Critical for Supply Chain)
```
sbom_dependency_flag  — Boolean (true if MLI, parts, or config validation needed)
sbom_trigger_reason   — Why SBOM flag set
parts_referenced      — Array of {part_number, context, inspection_types, source_location}
mli_numbers          — Array of {mli_number, context}
reference_documents  — Array of {document_number, type, context}
```

### Risk & Severity
```
severity_signals           — Array (e.g., ["Compliance A", "Equipment damage risk"])
failure_consequences       — Array (e.g., ["Rim section liberation", "Collateral damage"])
risk_summary               — Summary text
safety_or_damage_language_found — Boolean
```

### Quality Signals
```
configuration_dependent     — Boolean (does applicability depend on config?)
configuration_variables    — Array of variables (e.g., ["Frame type", "ECRT hours"])
configuration_summary      — Summary of config rules
extraction_confidence      — 0.0-1.0 (from LLM)
missing_information_flags  — Array of gaps identified by LLM
source_snippets            — Array of {field, verbatim_evidence}
```

---

## Data Flow

```
TIL PDF (Databricks Volume)
    ↓
ai_parse_document(content, version='2.0')
    → Returns VARIANT with {metadata, document.{pages, elements}}
    ↓
Extract Text + Tables
    ├─ to_json(parsed_content) — VARIANT → JSON string
    ├─ Parse JSON → extract elements[]
    ├─ Collect type=text → text_parts[]
    ├─ Collect type=table → tables[]
    └─ Result: full_text (~40KB), tables (~1-5)
    ↓
Build LLM Prompt
    ├─ System prompt (constraints, rules)
    ├─ User prompt (40-field extraction schema)
    └─ User input (json.dumps(tables) + full_text)
    ↓
LLM Extraction
    ├─ Call Databricks Foundation Model endpoint
    ├─ Temperature 0.0 (strict)
    ├─ Max tokens 4000
    └─ Response: raw text (possibly with ```json fences)
    ↓
Parse JSON Response
    ├─ Strip markdown fences (if present)
    ├─ Extract JSON object
    └─ Result: parsed_profile dict
    ↓
Normalize Schema
    ├─ Apply defaults (null for scalars, [] for lists)
    ├─ Normalize nested objects (parts_referenced, mli_numbers, etc.)
    └─ Result: normalized_profile (all 40 fields present)
    ↓
Validate Mandatory Fields
    ├─ Check: til_number, title, compliance_code, scope_of_work, recommendations, confidence
    ├─ Log warnings if missing
    └─ Continue even if validation fails (store with quality flag = "review")
    ↓
Write to Delta Table
    ├─ Table: vgpd.til_profiles.til_metadata
    ├─ Columns: til_number, parsed_profile (JSON string), confidence, latency_s, error_message, timestamp
    └─ Mode: append (incremental)
    ↓
Generate Summary
    ├─ Success rate: X/Y completed
    ├─ Avg confidence: 0.92
    ├─ Avg latency: 45.2s per PDF
    └─ Display results table
```

---

## How to Test

### Step 1: Quick Validation (2-3 PDFs)

Edit the notebook to target specific TILs:
```python
TARGET_TIL_NUMBERS = ["TIL 2284", "TIL 1937-R2", "TIL 2069"]
```

Run:
```bash
databricks workspace run \
  --notebook-path /Workspace/Repos/githubenterprise.gevernova.net/.../silver/src/etl/nb_sdg_til_metadata \
  --parameters="max_pdfs=3,llm_model=databricks-gpt-oss-20b"
```

Expected output:
```
[1/3] Processing TIL 2284...
  ✅ Success (confidence: 0.92, latency: 47.3s)
[2/3] Processing TIL 1937-R2...
  ✅ Success (confidence: 0.91, latency: 43.1s)
[3/3] Processing TIL 2069...
  ✅ Success (confidence: 0.92, latency: 45.8s)

=== Process 1 Complete ===
  Total processed: 3
  Successful: 3/3 (100%)
  Avg confidence: 0.92
  Avg latency: 45.4s
```

### Step 2: Compare with DS Team Results

DS team extracted 25 TILs. Compute field-level agreement:
```sql
-- Our extraction
SELECT til_number, 
       JSON_EXTRACT_SCALAR(parsed_profile, '$.til_number') as til_num,
       JSON_EXTRACT_SCALAR(parsed_profile, '$.extraction_confidence') as our_confidence
FROM vgpd.til_profiles.til_metadata
WHERE til_number IN ('TIL 2284', 'TIL 1937-R2', 'TIL 2069')
```

Compare with DS team's `profile_response.json` files:
- Check til_number, title, compliance_category_code match
- Check scope_of_work array lengths similar
- Check extraction_confidence within 0.05 (92% ± 5%)
- Identify any missing mandatory fields

### Step 3: Scale to Full Corpus

Remove TARGET_TIL_NUMBERS filter, run full:
```bash
databricks workspace run \
  --notebook-path /Workspace/Repos/.../silver/src/etl/nb_sdg_til_metadata \
  --parameters="llm_model=databricks-gpt-oss-20b"
```

---

## Integration Points

### ↓ Downstream: Process 2 (Chunking)
- **Input:** parsed_profile fields from Delta table
- **Uses:** scope_of_work, service_recommendation_line_items (for section boundaries)
- **For:** Semantic chunking + table-aware splits

### ↓ Downstream: App Layer (Applicability Logic)
- **Input:** Structured profile fields
- **Uses:** compliance_category_code, usage_counters, sbom_dependency_flag, configuration_variables
- **For:** Filtering, scheduling, SBOM validation

### ↓ Downstream: Vector Index
- **Input:** Title, scope_of_work, recommendations (for retrieval)
- **Uses:** Full markdown or reconstructed text from profile fields
- **For:** Semantic search, evidence retrieval

---

## Known Limitations & Mitigation

| Issue | Severity | Mitigation |
|-------|----------|-----------|
| **VARIANT type complexity** | ⚠️ Medium | Explicit JSON casting (proven pattern from 2.2 notebook) |
| **LLM hallucination** | ⚠️ Medium | "Do not infer" prompt rule + validation checks |
| **External API failures** | ⚠️ Medium | Retry logic, error logging, manual review queue |
| **PDF quality variations** | ⚠️ Medium | Extraction confidence scores flag low-quality results |
| **Cost (LLM calls)** | ⚠️ Low | Monitor per-PDF cost, consider batching if needed |

---

## Next Steps (Immediate)

### 1. Test on 2-3 PDFs (Today/Tomorrow)
- Run notebook with TARGET_TIL_NUMBERS set
- Inspect results in Delta table
- Check extraction_confidence scores (expect 0.90-0.93)
- Check latency (expect 40-50s per PDF)

### 2. Validate Against DS Team (This Week)
- Compare our extracted profiles with DS team's results
- Calculate field-level agreement for:
  - til_number, title, compliance_category_code (exact match)
  - scope_of_work, recommendations (array length + content similarity)
  - parts_referenced, mli_numbers (count match)
- Document any systematic differences
- Iterate on prompt if needed

### 3. Scale to Full Corpus (Next Week)
- Run on all ~25 TILs in DS team's top-25 list
- Monitor success rate, avg confidence, total latency
- Identify and fix any systematic failures
- Store baseline metrics for comparison

### 4. Design & Implement Process 2 (Chunking)
- Decide on chunking strategy (section-based? semantic? hybrid?)
- Implement chunker module (contract: parsed_profile → chunks[])
- Test on 2-3 PDFs
- Measure chunk quality (coverage, semantic coherence)

---

## File Locations

**Implementation Files:**
- `/home/u560060992/dbx/pw_sdg_ai_ser_repo/silver/src/tils/til_profile_schema.py` — Schema normalization
- `/home/u560060992/dbx/pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction_llm.py` — LLM extraction
- `/home/u560060992/dbx/pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_til_metadata.py` — Process 1 notebook

**Documentation Files:**
- `/home/u560060992/dbx/1-TILs/analysis/P1_IMPLEMENTATION_GUIDE.md` — Complete guide
- `/home/u560060992/dbx/1-TILs/analysis/ARCHITECTURE_DECISION_ANALYSIS.md` — Architecture decision (Option C)
- `/home/u560060992/dbx/1-TILs/analysis/TIL_PIPELINE_COMPLETION_PLAN.md` — Full project plan

**Reference (DS Team):**
- `/home/u560060992/dbx/SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/` — DS team code
- `/home/u560060992/dbx/1-TILs/analysis/ds-team-til-profile-results/til_profile_pilot_20260609_110447/` — DS team results (25 TILs)

---

## Summary

✅ **Process 1 (TIL Metadata Extraction)** is now ready to test and validate.

**What we built:**
- Full-document PDF parsing with ai_parse_document (Databricks native)
- LLM-based structured field extraction (40 fields, DS team's prompt pattern)
- Schema normalization + validation
- Delta table storage for incremental processing

**What to do next:**
- Test on 2-3 PDFs (confirm 90%+ confidence, 40-50s latency)
- Validate against DS team results (field-level agreement)
- Scale to full corpus
- Design Process 2 (chunking)

