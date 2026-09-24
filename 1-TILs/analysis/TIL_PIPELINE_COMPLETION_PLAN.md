# TIL Pipeline Completion & DS Validation Plan

**Goal:** Complete the TIL extraction pipeline (Process 1) and validate against DS team's results on 5 reference PDFs.

---

## Phase 1: Understand Current Architecture & Alignment

### 1.1 Review TIL Pipeline Design vs. FSR Pattern
**Status:** Design doc exists at `1-TILs/design/til-design.md`

**Current State:**
- **Architecture**: Medallion (Bronze → Silver → Gold)
- **Silver (P1)**: Metadata extraction (parser + profile LLM normalization)
- **Gold (P2)**: Chunking + embedding
- **Pluggable modules**: Parser, chunker, embedder behind stable interfaces

**FSR Precedent (pw_sdg_ai_ser_repo):**
- Process 1 = Page-1 metadata extraction + LLM field normalization
- Uses pdfplumber on page 1 only
- LLM prompt extracts FSR-specific fields (ESN, Equipment Type, Event Type, dates, project IDs)
- Validates mandatory fields and enriches with IBAT/Event Vision/PSOT

**Key Question:** Should TIL Process 1 follow FSR pattern (metadata extraction) or full-document approach?

**Action:** 
- [ ] Review `1-TILs/design/til-design.md` section "Silver: Metadata Extraction" to confirm TIL metadata fields
- [ ] Compare TIL field set with FSR field set (FSR has ~15 normalized fields)
- [ ] Identify TIL-specific fields needed for applicability (TIL number, title, compliance category, timing code, revision reason, scope, recommendation)

---

### 1.2 Understand DS Team's Approach
**Current State:** DS team code/results referenced at "SDG_Scoping_Feedback_Loop (/user/alexis-scoping branch)" but not yet located in workspace

**What We Know:**
- DS team has shared experimentation code and results
- They have extracted til profile results from 5 PDFs
- They likely have their own LLM normalization after parsing

**Actions:**
- [ ] Locate DS team's code (check `/user/alexis-scoping` branch or shared backend folder)
- [ ] Review their parsing method (pdfplumber, foundation, databricks_ai, or custom)
- [ ] Review their LLM normalization approach (system prompt, field extraction, validation)
- [ ] Review their extracted profile schema (field names, types, required fields)
- [ ] Review their results on the 5 reference PDFs (format, completeness, quality)
- [ ] Document the 5 PDF names/paths being used for validation

**Deliverable:** Comparison document: "DS Team Approach vs. Our Planned TIL P1"

---

## Phase 2: Assess Current Code Quality & Brittleness

### 2.1 Review Pipeline Code in pw_sdg_ai_ser_repo
**Current State:** TIL-specific pipeline code exists in `pw_sdg_ai_ser_repo/silver/src/tils/`

**Files to Review:**
- `parsers/databricks_ai_parser.py` — ai_parse_document adapter (✅ reviewed, uses v2.0, VARIANT handling)
- `parsers/pdfplumber_parser.py` — pdfplumber adapter
- `parsers/foundation_parser.py` — foundation HTTP API adapter
- `evaluators/til_parser_evaluator_config.py` — regex patterns for field detection
  - `TIL_REQUIRED_FIELDS_RE` = TIL number, revision, compliance, timing code, issue date, title, scope, recommendation, applicable
  - `TIL_FORMULA_RE` = numeric/formula patterns
- `til_profile_extraction.py` — TIL discovery and loading

**Actions:**
- [ ] Review regex brittleness: Are `TIL_REQUIRED_FIELDS_RE` patterns robust across 5 PDFs?
  - Test against actual extracted text from our ai_query results
  - Check if patterns capture field labels correctly across different layouts
- [ ] Review parser adapters: Do they emit JSON output consistent with FSR pipeline?
  - Compare schema with FSR output (check `ExtractedProfile` interface)
- [ ] Check for hardcoded heuristics: Field extraction, page selection, splitting logic
- [ ] Document any environment-specific assumptions (Databricks version, pdfplumber version)

**Deliverable:** Brittleness assessment report with regex pattern test results

---

### 2.2 Compare Analysis Code with Pipeline Code
**Current State:** Analysis notebooks differ from production pipeline

**Analysis Code (1-TILs/analysis/notebooks/):**
- `2.2 - Parse Documents to Structured Data.py` — Uses ai_parse_document, handles VARIANT types explicitly
- `2.3 - Clean, Transform, and Chunk Parsed Text.py` — Uses ai_query for semantic cleaning (markdown output)
- Evaluation notebook — Compares parsers via proxy metrics (char_count, formula_hits, noise_ratio, etc.)

**Pipeline Code (pw_sdg_ai_ser_repo/silver/src/etl/):**
- `nb_sdg_fsr_metadata.py` — Process 1 production notebook (page-1 extraction + LLM normalization)
- Uses pdfplumber on page 1 only
- LLM prompt extracts structured fields (not markdown)

**Key Difference:** Analysis code uses ai_query for full-document semantic normalization; pipeline likely needs field extraction, not markdown conversion

**Actions:**
- [ ] Document which approach fits TIL Process 1:
  - **Option A:** Full-document ai_query (semantic cleaning) like analysis code
    - Pros: Rich context, semantic normalization, works with chunking
    - Cons: Not structured field extraction, may be overkill for metadata
  - **Option B:** Page-1 pdfplumber + LLM field extraction like FSR pipeline
    - Pros: Fast, focused, structured output, field validation
    - Cons: Misses content, may not capture all TIL metadata
  - **Option C:** Hybrid: ai_parse_document full doc + structured LLM prompt
    - Pros: Best of both, structured + semantic
    - Cons: More complex, higher compute cost
- [ ] Determine which fields must be extracted vs. indexed as full text
- [ ] Decide on JSON schema for TIL profile output

**Deliverable:** Architecture decision document recommending Option A/B/C with rationale

---

## Phase 3: Design TIL Process 1 LLM Extraction

### 3.1 Define TIL Metadata Field Schema
**Inputs:**
- TIL design doc requirements
- DS team's field schema
- Analysis notebook's regex patterns (TIL_REQUIRED_FIELDS_RE)

**Expected TIL Fields (draft from ai_query results & design):**
- **Identifiers:** til_number, title, revision, publish_date, issue_date
- **Classification:** compliance_category (A/C/M/S), timing_code (1–6)
- **Content Summary:** scope, purpose, application, recommendation
- **Metadata:** background_discussion, reason_for_revision
- **Lineage:** supersedes (other TIL numbers), related_tils
- **Quality Signals:** page_count, section_count, table_count, formula_count

**Actions:**
- [ ] Review TIL documents (our ai_query results) to extract field patterns
- [ ] Compare with DS team's field schema
- [ ] Define validation rules per field (mandatory, format, length, valid values)
- [ ] Document allowed values for enum fields (compliance category, timing code)
- [ ] Define fallback/null handling strategy

**Deliverable:** TIL metadata schema specification (JSON schema or table DDL)

---

### 3.2 Design LLM Extraction Prompt
**Inputs:**
- TIL field schema
- FSR precedent (System Prompt + Normalization Prompt Suffix from nb_sdg_fsr_metadata.py)
- DS team's prompt approach (if available)

**Tasks:**
- [ ] Write SYSTEM_PROMPT (similar to FSR: expert in structuring technical data)
- [ ] Write TIL-specific EXTRACTION_PROMPT with:
  - Field list and definitions
  - Extraction rules (TIL number in title, compliance in page 0, etc.)
  - Date normalization (YYYY-MM-DD)
  - Allowed values for enums
  - Handling of missing fields (empty string vs. null)
  - JSON output format requirement
- [ ] Include examples of expected output (2–3 TIL samples)
- [ ] Test prompt against our 5 validation PDFs with LLM (dry-run)

**Deliverable:** Prompt specification document + draft prompt text

---

## Phase 4: Implement TIL Process 1 Extraction

### 4.1 Create TIL Profile Extraction Notebook
**Template:** Adapt FSR's `nb_sdg_fsr_metadata.py` for TIL pipeline

**Scope:**
- PDF discovery from TIL volumes
- Parser selection (ai_parse_document or pdfplumber)
- LLM-based field extraction (via LiteLLM)
- Validation and quality gates
- Result storage to Delta table

**Actions:**
- [ ] Create `silver/src/etl/nb_sdg_til_metadata.py` (Process 1 for TILs)
- [ ] Use shared utilities from `til_profile_extraction.py` for PDF discovery
- [ ] Implement parser adapter selection logic
- [ ] Implement LLM extraction with retry logic and error handling
- [ ] Add field-level validation
- [ ] Add logging and progress tracking
- [ ] Handle VARIANT type output from ai_parse_document (cast to JSON string)

**Deliverable:** Working Process 1 notebook with logging and error handling

---

### 4.2 Run Process 1 on 5 Validation PDFs
**Setup:**
- [ ] Identify the exact 5 PDF paths used by DS team
- [ ] Configure notebook parameters (volume paths, PDF names, LLM model, batch size)
- [ ] Set `TARGET_PDF_NAMES` or `MAX_PDFS=5` to limit scope

**Execution:**
- [ ] Run notebook on each PDF individually (capture per-PDF results)
- [ ] Capture logs and timings
- [ ] Inspect output for:
  - JSON validity
  - Field completeness (which fields are missing?)
  - LLM parsing quality (correct extractions?)
  - Latency per PDF

**Deliverable:** Process 1 results table with 5 rows (1 per PDF) + execution logs

---

## Phase 5: Compare Results with DS Team

### 5.1 Harmonize Output Formats
**Problem:** Our ai_query results (full-document markdown) vs. our Process 1 results (structured fields) vs. DS team's results (unknown format)

**Actions:**
- [ ] Export our Process 1 results to CSV/JSON (same 5 PDFs)
- [ ] Obtain DS team's results in comparable format
- [ ] Normalize field names across our pipeline and DS team results
  - E.g., `til_number` vs. `til #` vs. `TIL Number`
- [ ] Align date formats (YYYY-MM-DD)
- [ ] Handle missing field representation (empty string vs. null vs. "N/A")

**Deliverable:** Harmonized results CSV with columns: pdf_path, field_name, our_value, ds_team_value

---

### 5.2 Implement Comparison Metrics
**Goal:** Quantify agreement between our extraction and DS team's extraction

**Metrics:**
- **Field-level agreement:** For each field, calculate:
  - Exact match rate (% of PDFs where values match exactly)
  - Partial match rate (similarity score if fuzzy matching needed)
  - Missing rate (% of PDFs where our system or DS missed the field)
- **PDF-level agreement:** For each PDF:
  - Fields correctly extracted (exact match)
  - Fields partially correct (semantic match)
  - Fields missing or incorrect
  - Overall extraction quality score (0–100)
- **Aggregate metrics:**
  - Field extraction quality (% correctly extracted across all fields and PDFs)
  - Extraction consistency (std dev of per-PDF scores)
  - Major error categories (missing mandatory fields, wrong format, LLM hallucination)

**Actions:**
- [ ] Write Python script to compute field-level agreement
- [ ] Generate comparison matrix (PDF rows × fields columns, color-coded by match status)
- [ ] Summarize findings in a comparison report
- [ ] Identify patterns (which fields are consistently missed, which PDFs are problematic)

**Deliverable:** Comparison report with metrics + visual matrix

---

### 5.3 Root-Cause Analysis of Discrepancies
**For fields/PDFs where our extraction differs significantly:**

**Actions:**
- [ ] Review raw parsed output from both parsers (ai_parse_document vs. DS approach)
- [ ] Compare extracted text quality:
  - Does ai_parse_document preserve the field correctly?
  - Does the LLM prompt correctly identify the field?
- [ ] Review our ai_query results for context (does semantic cleaning distort field values?)
- [ ] Check regex patterns: Are they matching/not matching expected text?
- [ ] Propose fixes:
  - Prompt refinement (clarify field definition, add examples)
  - Parser selection (switch parser if ai_parse_document underperforms)
  - Post-processing (regex cleanup, fuzzy matching, validation rules)

**Deliverable:** Per-field root-cause summary with recommended fixes

---

## Phase 6: Validate & Iterate (if needed)

### 6.1 Apply Fixes (if comparison shows gaps)
**Iterate based on Phase 5 findings:**
- [ ] Update LLM prompt if field definitions are unclear
- [ ] Adjust parser selection if extraction quality is poor
- [ ] Add post-processing rules for format normalization
- [ ] Re-run Process 1 on 5 PDFs
- [ ] Re-compare results

**Repeat until agreement is satisfactory (e.g., ≥95% exact match rate on mandatory fields)**

**Deliverable:** Improved Process 1 notebook + re-comparison metrics

---

## Phase 7: Operationalize for Full Corpus

### 7.1 Scale to Full TIL Corpus
**Prerequisites:**
- [ ] Process 1 is validated on 5 PDFs
- [ ] Prompt and parser are stable
- [ ] Error handling and logging are production-ready

**Actions:**
- [ ] Increase `MAX_PDFS` to full corpus size (estimate: 500–2000 TILs)
- [ ] Enable incremental processing (don't reprocess already-extracted PDFs)
- [ ] Monitor throughput and cost
- [ ] Implement retry logic for transient LLM failures
- [ ] Set up alerting for extraction failures
- [ ] Generate quality reports (% successful extraction, field distribution)

**Deliverable:** Full corpus extraction results + observability dashboards

---

### 7.2 Implement Process 2 (Chunking & Embedding)
**Inputs:** Process 1 results (structured TIL profiles) + our ai_query results (semantic markdown)

**Design Decision:** 
- Use full-document ai_query markdown for retrieval chunks (rich context)
- Or chunk the structured fields separately and index metadata
- Or hybrid: index markdown chunks + embed structured fields as context

**Actions (high-level for now):**
- [ ] Design chunking strategy (section-based, semantic, table-aware)
- [ ] Implement chunker adapter
- [ ] Implement embedder adapter
- [ ] Run Process 2 on extracted PDFs
- [ ] Validate chunk quality (coverage, overlap, semantic coherence)

**Deliverable:** Process 2 implementation plan (defer full build to Phase 2 of overall project)

---

## Timeline & Deliverables Summary

| Phase | Task | Est. Effort | Key Deliverable |
|-------|------|-------------|-----------------|
| 1.1   | Design alignment | 2–4 hrs | TIL field schema + design decision |
| 1.2   | DS team investigation | 3–5 hrs | DS approach comparison doc |
| 2.1   | Code review (brittleness) | 3–4 hrs | Regex pattern test report |
| 2.2   | Analysis vs. pipeline | 2–3 hrs | Architecture decision (Option A/B/C) |
| 3.1   | Field schema design | 4–6 hrs | TIL metadata schema spec |
| 3.2   | LLM prompt design | 4–6 hrs | Prompt spec + dry-run test results |
| 4.1   | P1 notebook implementation | 6–8 hrs | Working Process 1 notebook |
| 4.2   | Run on 5 PDFs | 2–3 hrs | P1 results table + logs |
| 5.1   | Format harmonization | 2–3 hrs | Harmonized results CSV |
| 5.2   | Comparison metrics | 3–4 hrs | Comparison report + matrix |
| 5.3   | Root-cause analysis | 2–4 hrs | Per-field fix recommendations |
| 6.1   | Iterate (if needed) | TBD | Improved P1 + re-comparison |
| 7.1   | Full corpus scaling | 4–6 hrs | Full extraction results |
| 7.2   | Process 2 planning | 2–3 hrs | Chunking/embedding plan |

**Total Estimate:** 44–72 hours (depends on DS team feedback and iteration cycles)

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| DS team data not accessible | Can't validate | Locate code/results early (Phase 1.2) |
| LLM prompt too brittle | Low extraction quality | Thorough testing on 5 PDFs before scale |
| Parser selection mismatch | Systematic failures | Test all 3 parsers on sample PDFs |
| VARIANT type issues (DBR env) | Notebook crashes | Explicit JSON casting (proven in 2.2 notebook) |
| Field extraction conflicts | Reconciliation blocker | Prioritize mandatory fields, allow empty optional |
| Cost overrun (LLM calls) | Budget impact | Implement batching, caching, cost monitoring |

---

## Next Immediate Steps (Week 1)

1. **Action: Locate DS Team Code** (Priority 1)
   - Check `/user/alexis-scoping` branch in backend repo
   - Contact DS team Slack/email for shared results/approach documentation
   - Extract: field schema, prompt, 5 PDF paths, extraction results

2. **Action: Review til-design.md** (Priority 1)
   - Finalize TIL field requirements
   - Decide: Option A (full-doc semantic), B (page-1 structured), or C (hybrid)

3. **Action: Test Regex Patterns** (Priority 2)
   - Run TIL_REQUIRED_FIELDS_RE against our ai_query results from TIL 1937-R2
   - Document pattern hit rates
   - Identify missing patterns

4. **Action: Design TIL Field Schema** (Priority 2)
   - Create JSON schema for TIL profile
   - Align with DS team's schema

5. **Action: Draft LLM Prompt** (Priority 3)
   - Write first draft extraction prompt
   - Prepare for dry-run testing

---

## Decision Points (Awaiting Your Input)

- [ ] **Architecture Choice:** Option A (full-doc ai_query), B (page-1 pdfplumber + LLM), or C (hybrid)?
- [ ] **5 Validation PDFs:** Which PDFs are the DS team using? (Need to run on same corpus)
- [ ] **Field Schema:** Should we extract TIL metadata only, or include content summary (scope, purpose)?
- [ ] **Comparison Criteria:** What threshold counts as "success"? (e.g., ≥95% exact match on mandatory fields)

