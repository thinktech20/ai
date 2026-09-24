# TIL Pipeline Architecture Decision: Option A vs B vs C

**Based on DS Team's Approach & Our Analysis Results**

---

## Executive Summary

The DS team has successfully extracted **25 TILs** using a **full-document, structured field extraction approach** (Option C hybrid). Their results show:
- **Extraction confidence:** 91-93% across all TILs
- **Parser used:** Foundation API (with pdfplumber fallback)
- **Output schema:** ~40 structured fields + markdown rendering
- **Methodology:** Extract document text → pass to LLM → generate structured JSON profile

**Recommendation:** **Adopt Option C (Hybrid)** — combine full-document extraction with structured LLM field normalization, following the DS team's proven pattern.

---

## DS Team's Actual Approach (Detailed Reverse-Engineering)

### Architecture
```
PDF → Foundation Parser (or pdfplumber fallback) 
  → Full document text + labeled tables
  → User prompt with extracted text + tables
  → LLM (with 40-field prompt template)
  → Structured JSON profile (parsed_profile)
  → normalize_profile_schema() 
  → profile_response.json
  → Markdown rendering for human review
```

### Parser Selection
- **Primary:** Foundation API (`TIL_FOUNDATION_URL`)
- **Fallback:** pdfplumber (Python library)
- **Why:** Foundation was built for heavy extraction quality; pdfplumber is lightweight fallback
- **Cost:** Foundation is paid service; pdfplumber is free

### LLM Extraction Approach

**System Prompt Key Points:**
- Expert engineer mindset: "extracting structured TIL profiles for outage scoping"
- **Critical:** "Do not infer facts not stated" (no hallucination)
- Prefer metadata from PowerNow/database for compliance, dates, coarse outage type
- Use document text/tables for detailed engineering content
- **SBOM-aware:** Detect part numbers, MLI references, configuration dependencies
- **Safety-aware:** Flag safety or damage language found

**Extraction Rules (from v2026-06-02a prompt):**
1. til_number, revision, title, publish_date, reason_for_revision, purpose
2. Compliance category code + text (M/C/A/S)
3. Scope of work, service recommendations (structured lists)
4. Maintenance trigger, completion criteria, recommended interval
5. **Configuration applicability** (5 text fields for frame, fuel, hardware, serial, exclusions)
6. **Parts referenced** (part_number OR null + context + inspection types + source_location)
7. **MLI numbers** (must-find structured list with context)
8. **Reference documents** (other TILs, GEK, GEH manuals)
9. **Severity signals, failure consequences, risk summary**
10. **Usage counters** (operating hours, starts, etc.) — explicitly required for interval calculation
11. **Tables summary** (operationally relevant tables only, filter out legend tables)
12. **Source snippets** (verbatim evidence for each extracted field)

### Output Schema (40+ Fields)
```json
{
  "requested_til": "string",
  "model": "string or null",
  "parsed_profile": {
    "til_number": "TIL 2284",
    "revision": "null or string",
    "title": "F-CLASS BALANCE WEIGHT GROOVE ENTRY SLOT RECOMMENDATIONS",
    "publish_date": "2021-05-05",
    "compliance_category_code": "S (M|C|A|S)",
    "compliance_category_text": "Safety - Failure to comply...",
    
    # Scope & Recommendations
    "scope_of_work": ["item1", "item2"],
    "service_recommendation_line_items": ["item1", "item2"],
    "completion_criteria_text": "string",
    "maintenance_trigger_text": "string",
    "recommended_interval_or_trigger": ["item1", "item2"],
    
    # Configuration Applicability (5 text fields)
    "frame_or_model_applicability_text": "6F, 7F, and 9F Heavy Duty Gas Turbines",
    "combustion_or_fuel_configuration_text": "null or string",
    "hardware_or_part_configuration_text": "Compressor aft shaft (CAS)...",
    "serial_or_unit_applicability_text": "null or string",
    "exclusions_or_non_applicable_conditions_text": "Fillet >0.060\"...",
    "required_prior_modifications_text": "null or string",
    "prerequisite_outage_or_inspection_context_text": "null or string",
    
    # Configuration Analysis
    "configuration_dependent": true,
    "configuration_variables": ["Frame type (6F/7F/9F)", "ECRT hours"],
    "configuration_summary": "Applicable to 6F, 7F, 9F...",
    
    # Risk & Consequences
    "severity_signals": ["Category S - Safety", "Critical fillet size"],
    "failure_consequences": ["Sharp corners initiate fatigue cracks", "..."],
    "risk_summary": "Inadequate fillet geometry...",
    "safety_or_damage_language_found": true,
    
    # Parts & References
    "parts_referenced": [
      {
        "part_number": "null or 227C5762",
        "context": "Compressor aft shaft...",
        "required_inspection_types": ["FPI", "MPI"],
        "source_location": "Table 1, page 3"
      }
    ],
    "mli_numbers": [
      { "mli_number": "MLI-1648", "context": "Approved procedure..." }
    ],
    "reference_documents": [
      { "document_number": "TIL-1937", "document_type": "TIL", "context": "..." }
    ],
    
    # Usage Counters (CRITICAL for interval calculation)
    "usage_counters_to_check_or_consider": [
      "equivalent_cold_rotor_turning_time",
      "fired_starts",
      "forced_cool_downs"
    ],
    "usage_counter_requirements_text": "ECRT = TTG - ((SFS-SFC)*X)...",
    
    # SBOM Flag
    "sbom_dependency_flag": true,
    "sbom_trigger_reason": "MLI references + configuration variables",
    
    # Tables & Evidence
    "tables_found_summary": [
      {
        "table_label": "Inspection Intervals",
        "table_description": "...",
        "useful_for_downstream": true,
        "reason": "Required for applicability logic"
      }
    ],
    "source_snippets": [
      { "field": "usage_counter_requirements_text", "snippet": "ECRT must be calculated..." }
    ],
    
    # Quality
    "extraction_confidence": 0.92,
    "missing_information_flags": [
      "No specific serial number applicability list",
      "No definition of 'higher operational temperatures' threshold"
    ]
  },
  "raw_profile": "```json\n{...}```"
}
```

### Results Summary (25 TILs)
| Metric | Value |
|--------|-------|
| TILs Extracted | 25 (top-25 curated list) |
| Extraction Success Rate | 100% (25/25 completed) |
| Avg Extraction Confidence | 92.0% (range 91-93%) |
| Parser Used | Foundation (100%) |
| Method Used | foundation (100%) |
| PDF Match Type | exact_til_number (100%) |
| Profile Found | True (100%) |

---

## Comparison: Options A, B, C

### Option A: Full-Document ai_query Semantic Markdown
**What it does:**
- Parse PDF with ai_parse_document → extract full text/tables
- Pass to ai_query LLM endpoint → generate semantic cleaned markdown
- Output: Full-document markdown (like our 1937-R2 result)

**Pros:**
- ✅ Semantic normalization (fixes language, structure)
- ✅ Works with ai_parse_document (Databricks native, no external API)
- ✅ Rich context preserved for downstream chunking
- ✅ Proven working (we have ai_query_results.csv)

**Cons:**
- ❌ **No structured fields** → can't extract TIL number, compliance code, recommended interval
- ❌ Can't be used directly for applicability logic
- ❌ Requires post-processing to extract metadata from markdown
- ❌ Not what DS team validated (their downstream applicability step expects structured profile)
- ❌ Missing SBOM flags, usage counter requirements, severity signals
- ❌ Loses explainability (source snippets)

**Verdict:** **Not suitable for P1 (metadata extraction)**. Better for retrieval/chunking context. Could be Option D (P2 content source).

---

### Option B: Page-1 pdfplumber + Structured Field Extraction
**What it does:**
- Extract page 1 only with pdfplumber
- Run simple regex patterns to find key fields (TIL number, compliance, dates)
- Fallback to LLM for unstructured fields
- Output: Flat JSON with 10-15 fields

**Pros:**
- ✅ Fast (page 1 only)
- ✅ Lightweight (no external API calls)
- ✅ Simple error handling
- ✅ Used successfully in FSR pipeline for FSR documents

**Cons:**
- ❌ **Misses 90% of TIL content** (scope, recommendations, risk, parts, MLI numbers all on pages 2+)
- ❌ Missing SBOM flags, usage counters, severity signals (all required for downstream)
- ❌ Regex patterns brittle across layout variations
- ❌ Can't detect multipage configuration-dependent rules
- ❌ **Not what DS team used** (they extract full document)
- ❌ Would require manual post-processing to fill gaps

**Verdict:** **Not suitable for TILs**. Works for FSR (1-page reports) but TILs are 5-20 pages.

---

### Option C (Recommended): Full-Document Extraction + LLM Structured Profile
**What it does:**
- Extract full PDF text + tables (Foundation or ai_parse_document)
- Pass extracted text to LLM with comprehensive field extraction prompt
- LLM generates structured JSON profile (40 fields)
- Normalize schema, add defaults, render markdown for review
- Output: profile_response.json (structured) + markdown

**Pros:**
- ✅ **Proven by DS team** on 25 TILs with 92% avg confidence
- ✅ Full document context → captures all metadata, scope, recommendations, risk, parts, MLI, counters
- ✅ Structured JSON output → direct input to applicability logic
- ✅ SBOM aware (parts, MLI numbers, configuration flags)
- ✅ Safety/damage language detection
- ✅ Usage counter requirements extracted (critical for interval calculation)
- ✅ Source snippets for explainability
- ✅ Extraction confidence score for quality monitoring
- ✅ Markdown rendering for human verification
- ✅ Handles multi-page configuration-dependent rules
- ✅ Configuration variables extracted (frame, fuel, serial applicability)
- ✅ Post-extraction schema normalization prevents downstream errors

**Cons:**
- ⚠️ External API calls (Foundation or LLM gateway)
- ⚠️ Higher latency (full document processing)
- ⚠️ Cost (Foundation API + LLM calls)
- ⚠️ LLM hallucination risk (mitigated by "do not infer" prompt instruction)
- ⚠️ Need robust error handling and retry logic

**Verdict:** **Recommended**. Follows proven DS team pattern, addresses all downstream requirements.

---

## Technical Implementation Path (Option C)

### Step 1: Choose Parser
**Options:**
1. **Foundation API** (DS team choice)
   - Pros: Better extraction quality, handles complex layouts
   - Cons: External service, cost, requires authentication
   
2. **ai_parse_document + pdfplumber hybrid**
   - Pros: Databricks native (ai_parse_document), free pdfplumber fallback
   - Cons: ai_parse_document returns VARIANT (needs JSON casting)
   - Recommended: Use as Foundation alternative if cost prohibitive

3. **pdfplumber only**
   - Pros: Free, lightweight
   - Cons: Lower quality on complex PDFs

**Recommendation:** Start with ai_parse_document (Databricks native), add Foundation fallback if quality insufficient.

### Step 2: Adapt DS Team's LLM Prompt
**File to use as template:** 
`SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/prompts/til_profile_extraction_pilot_v2026-06-02a.txt`

**Adaptations needed:**
- Change database references from PowerNow to our catalog
- Add any TIL-specific fields we need beyond their 40 fields
- Adjust temperature/model based on our LLM gateway
- Add guardrails for our document set

### Step 3: Implement Process 1 Notebook
**Template:**
`pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py` (FSR P1)

**New file:**
`pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_til_metadata.py` (TIL P1)

**Key components:**
```python
# 1. PDF discovery (from til_profile_extraction.py)
discover_tils(spark, volume_paths) → DataFrame

# 2. Parser selection (ai_parse_document or pdfplumber)
extract_document(pdf_bytes, method) → (text, tables, raw_response, method_used)

# 3. Build user prompt with extracted text
build_user_prompt(pdf_text, labeled_tables) → str

# 4. Call LLM
run_profile_extraction(system_prompt, user_prompt, model) → (parsed_profile, raw_response)

# 5. Normalize schema
normalize_profile_schema(profile) → normalized_profile

# 6. Store to Delta
write_to_metadata_table(til_id, profile, latency, confidence)
```

### Step 4: Validation & Testing
**On our 5 validation PDFs (or DS team's 25):**
- [ ] Extract all fields
- [ ] Compare with DS team results (field agreement)
- [ ] Calculate per-field accuracy
- [ ] Identify parser-specific gaps
- [ ] Refine prompt if needed
- [ ] Measure latency and cost per TIL

---

## Recommended Full TIL Pipeline (Phase 2)

```
P0 (Bronze): Raw PDF ingestion
  ↓
P1 (Silver): Profile extraction (Option C)
  - Parser: ai_parse_document or Foundation
  - LLM extraction: 40+ structured fields
  - Output: profile_response.json
  ↓
P1 Validation: Schema checks, mandatory field validation
  ↓
P2 (Gold): Chunking + Embedding
  - Input: profile_response.json + full markdown
  - Strategy: Section-based (scope, recommendations, applicability) 
            + semantic (usage counter requirements)
  - Output: chunks with embeddings
  ↓
Vector Index: Sync golden chunks to vector search
  ↓
App Layer: Applicability logic (uses profile fields)
```

---

## Why NOT Option A or B

### Why Not Option A (Full-Doc Semantic Markdown)?
- **Missing critical metadata:** compliance_category_code, timing_code, TIL_number, usage_counters, SBOM flags
- **Can't extract:** Part numbers, MLI references, configuration variables
- **Downstream incompatibility:** Applicability logic expects structured profile, not markdown
- **Lost explainability:** No source snippets, confidence scores
- **Duplicates work:** Would need to post-process markdown to extract fields anyway (defeats purpose)

→ **Better use for Option A:** As P2 content source (full semantic markdown for retrieval chunks)

### Why Not Option B (Page-1 Structured)?
- **Misses 90% of required content:** TILs are 5-20 pages, metadata on pages 2-5+
- **Missing required fields:**
  - Scope of work (pages 2-3)
  - Service recommendations (pages 2-4)
  - Part numbers, MLI references (pages 3-5, tables)
  - Usage counter requirements (pages 3-4)
  - Configuration applicability (scattered throughout)
  - Severity signals, failure consequences (pages 1-3, risk section)
- **Regex brittleness:** Patterns don't generalize across 25 TIL variants
- **FSR ≠ TIL:** FSR is 1-page report; TIL is structured multi-page technical document
- **Not DS team's approach:** They validated full-document extraction

→ **Better use for Option B:** Only if restricted to simple 1-page formats (like FSR)

---

## Implementation Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| LLM hallucination | Medium | High | Use "do not infer" prompt rule + validation checks |
| Parser quality variations | Medium | Medium | Test both Foundation + ai_parse_document |
| External API failures | Medium | High | Implement fallback chains + retry logic |
| Schema drift | Low | Medium | Version control prompt template + schema |
| Cost overruns | Low | Medium | Batch processing + caching + cost monitoring |

---

## Decision Summary

**Recommendation: Option C (Hybrid)**

**Why:**
1. **DS team validated it** on 25 TILs with 92% avg confidence
2. **Covers all downstream requirements** (applicability logic, SBOM, safety)
3. **Preserves full document context** (multipage rules, configuration variables)
4. **Structured output** directly usable by applicability engine
5. **Explainability built-in** (source snippets, confidence scores)
6. **Quality signals** (missing info flags, extraction confidence)

**Next Steps:**
1. Confirm architecture decision (Option C)
2. Identify 5 validation PDFs (can use DS team's or subset)
3. Adapt DS team's extraction prompt for our catalog + LLM gateway
4. Implement P1 notebook using ds team pattern as template
5. Validate on 5 PDFs against DS team results (if available)
6. Scale to full corpus (25+ TILs)
7. Design P2 chunking strategy (section-based + semantic)

