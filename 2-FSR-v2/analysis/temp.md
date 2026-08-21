# Preprocessor Knobs & Layer Impact

## Table of Contents

1. [Two-Phase Implementation Approach](#two-phase-implementation-approach)
2. [FSR Pipeline Architecture (Context)](#fsr-pipeline-architecture-context)
3. [Knobs & Layer Impact](#knobs--layer-impact)
4. [Layer-by-Layer Summary (Files & Changes)](#layer-by-layer-summary-files--changes)
5. [Impact by Document Type](#impact-by-document-type)
6. [Expected Accuracy Impact](#expected-accuracy-impact-fix-2-implementation)
7. [POC Validation](#poc-validation)
8. [Critical: PDF Parser Alignment (P1 ↔ P2)](#critical-pdf-parser-alignment-p1--p2)
9. [Metadata Table Schema Changes](#metadata-table-schema-changes)
   - [Existing Columns](#existing-columns-no-change)
   - [MODIFIED Column](#modified-column-schema-evolution)
   - [NEW Columns](#new-columns-added-for-preprocessor-integration)
   - [DDL & Schema Evolution](#ddl--schema-evolution)
   - [P1 Integration Points](#p1-integration-how-to-build-structured-all_esns)
   - [P2 Integration](#p2-integration-how-to-use-structured-all_esns)
10. [Summary: What Gets Written to Metadata Table](#summary-what-gets-written-to-metadata-table)

---

## Two-Phase Implementation Approach

**Phase 1 (Immediate - In Progress):** Metadata UPDATE on existing chunks
- **What:** Run preprocessor on all 458 multi-equipment FSRs
- **Output:** Page-range accuracy (82.6% → 86.7%+) via page-range scorer and SAGE smoke tests
- **Deployment:** SQL UPDATE statement on chunk_table TBD column name (no re-chunking or re-ingestion)
- **Timeline:** Days (reversible, low risk)
- **Reference:** FSR_Retrieval_Fix_Plan.md 

**Phase 2 (Long-term - Pipeline Integration):** Preprocessor integrated into production pipeline for new documents
- **What:** Integrate preprocessor into STEP 1, store per-region boundaries, use char-offset matching in STEP 2
- **Implementation:** Preprocessor called in P1, per-chunk equipment attribution via char-offset matching in P2 (requires pdfplumber in P2)
- **Benefit:** No retrospective fixing needed; forward-going documents are correct by design
- **Timeline:** Weeks (full pipeline refactor + testing)

---

## FSR Pipeline Architecture (Context)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        FSR INGESTION PIPELINE                               │
└──────────────────────────────────────────────────────────────────────────────┘

STEP 1: METADATA EXTRACTION (P1 — nb_sdg_fsr_metadata.py)
├─ Discovers new PDFs from:
│  • /Volumes/viud/ing_ud_fieldvision/fv_field_service_report
│  • /Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports
├─ Extracts text via pdfplumber
├─ Calls preprocessor on full PDF text + page_offsets
├─ Stores preprocessor outputs in metadata_table **[PHASE 1]**
│  • doc-level metadata
│  • preprocessor_regions
│  • inactive_esns
├─ Existing P1 LLM normalization call may be enhanced with preprocessor hints **[PHASE 1 optional]**
│  • Same LLM call as today's metadata normalization step; no additional LLM call is introduced
│  • Purpose: steer extraction of ESN / equipment type / dates when page-1 fields are ambiguous
│  • Input remains page-1 extracted fields, augmented with preprocessor hints from full-document analysis
├─ Enriches with IBAT + Event Vision
│  • Current enrichment is deterministic table joins, not an LLM call
├─ Applies DS Guru-style merge precedence **[PHASE 2]**: preprocessor-region > preprocessor-doc > LLM-output > upload/reference tags
│  (this uses the output of the existing P1 LLM normalization call; it does not require a second LLM call)
│  (use per-section metadata first, then preprocessor doc-level metadata, then normalized LLM output, then ref/upload tags)
│
├─ ┌─ NESTED: PRE-PARSING ENRICHMENT (preprocessor_v2_fix1_fix2.py — runs inside P1)
│  │  ├─ Sandboxed execution (child process, no imports, no I/O)
│  │  ├─ Scans full PDF text for:
│  │  │  • Section headers: "GENERATOR (337X766 | SY0072576)" regex
│  │  │  • Numbered TOC headers: "2 Turbine", "3 Generator"
│  │  │  • GE form numbers: D316xxxx (Gen), GTxxxx (GT)
│  │  │  • Keyword density: equipment-specific signals
│  │  │  • Inactive markers: "not applicable", "no work performed"
│  │  │  • **Full-text header re-scan** (finds embedded headers mid-document)
│  │  │  • **Nested subsection patterns** ("3.1.1 Generator Stator...")
│  │  ├─ Outputs (3 parts):
│  │  │  • metadata   → doc-level: {esn_to_equip_type: {esn→equip_type mapping}, inactive_esns, dates}
│  │  │  • hints      → text for LLM prompt
│  │  │  • regions    → [{start_char, end_char, metadata_per_region}] (includes all boundaries from headers + subsections)
│  │  └─ Runtime: < 1 sec per document
│  └─
│
└─ Outputs → metadata_table:
   ├─ Existing columns: esn, equipment_type, equipment_sys_id, equipment_class_code, ... (unchanged)
  ├─ LEGACY column: all_esns (deprecated; retained only for backward compatibility)
  └─ NEW columns: preprocessor_regions (JSON), inactive_esns (string/array) **[PHASE 1 / foundation for Phase 2]**

STEP 2: CHUNKING (P2 — nb_sdg_fsr_chunks.py)
├─ Reads completed metadata from metadata_table
├─ For existing chunk rows, attach enriched metadata where current chunk anchors / join strategy allow it **[PHASE 1]**
│  • Goal: improve retrieval filters and enable QA validation without re-chunking or re-embedding
│  • Candidate updates: corrected primary_equip_type, esn_details, related per-ESN metadata
├─ Extracts full PDF text via pdfplumber (NOT PyMuPDF)
│  ⚠️  **CHANGE REQUIRED:** Current impl uses PyMuPDF; must switch to pdfplumber for char-offset alignment with P1 **[PHASE 2]**
├─ Chunks using RecursiveCharacterTextSplitter (4000 chars, 200 overlap) **[PHASE 2]**
├─ For each chunk:
│  • For existing chunk rows: attach corrected metadata from persisted preprocessor outputs **[PHASE 1 where feasible]**
│  • For re-derived chunks: match char offset to preprocessor region (requires same parser as P1) **[PHASE 2]**
│  • Assign chunk.primary_equip_type from region (not doc-level) **[PHASE 1 update target / PHASE 2 full derivation]**
│  • Embed esn_details: array of {esn, equip_type, ...} on each chunk (no row duplication) **[PHASE 1 if metadata-only update is enough; PHASE 2 if chunk rewrite is needed]**
├─ Batch embeds via LiteLLM (32 chunks/request, 8 threads) **[PHASE 2]**
├─ Writes to chunk_table (Gold zone) **[PHASE 1 for metadata-only updates on existing rows / PHASE 2 for re-derived chunks]**
└─ Triggers Vector Search index sync **[PHASE 1 after metadata updates; PHASE 2 after re-derived chunks]**

STEP 3: INDEXING & STORAGE (Vector Search)
├─ Indexes: embedding_vector (3072-dim) + primary_equip_type metadata
└─ Enables fast ANN search by equipment type + semantic similarity

STEP 4: SQL QUERY FSR

4 — FSR Document Search (by ESN):
├─ Query: "Find all FSRs for ESN 338X447"
├─ Lookup: Query chunk_table metadata JSON where esn_details contains ESN and ESN not in inactive_esns
├─ Return: All documents associated with that ESN
├─ Impact: Correct document lookup from chunk metadata source of truth

STEP 5: RETRIEVAL 

5 — Risk Evaluation (through Chunks):
├─ Query: "What are the risks for ESN 338X447?"
├─ Step 1 - Find all chunks: Vector Search returns top-k chunks where:
-- pass 1- derive active_esns at retrieval time (from esn_details - inactive_esns) and include esn-equip type mapping to LLM
│   • pass -2 -- primary_equip_type = equipment_type(338X447) [from pass 1]
│   • chunk embedding is semantically similar to query
├─ Step 2 - Filter by relevance: Chunks must match BOTH equipment type AND semantic content
│   ⚠️  Critical: Without preprocessor fix, wrong chunks (GT content) would be returned for Gen ESN
├─ Step 3 - LLM analysis: Feed filtered chunks to LLM → generate risk assessment
├─ Step 4 - Return: Risk findings based on correct, equipment-specific chunks
└─ Impact: Correct equipment type per chunk → correct risk findings (no cross-equipment confusion)

**Why the preprocessor matters for retrieval:**
- **Without fix:** Multi-ESN docs return mixed Gen+GT chunks labeled with wrong equipment type → LLM gets confused data → wrong risks
- **With fix:** Each chunk correctly labeled with its actual equipment type → LLM gets clean, equipment-specific data → accurate risks
```

---

## Implementation Comparison: Exists Today vs. New (with Preprocessor)

| Step | Exists Today | New Implementation (with Fix 2 Preprocessor) |
|---|---|---|
| **STEP 1: Metadata Extraction (P1)** | • Extract page-1 text only<br/>• LLM extracts single ESN + equipment_type<br/>• Doc-level all_esns as flat array ["ESN1", "ESN2"]<br/>• No region boundaries<br/>• No inactive_esns tracking | • Extract full PDF text<br/>• Call preprocessor_v2_fix1_fix2 on full text<br/>• Build retrieval metadata payload (esn_details + inactive_esns)<br/>• Store preprocessor_regions (char-offset boundaries)<br/>• Keep all_esns only as legacy compatibility field |
| **STEP 2: Preprocessing** | ✗ Does not exist (no preprocessor today) | • Full-text header scanning (finds embedded headers)<br/>• Nested subsection detection (e.g., "3.1.1 Generator")<br/>• Content-weighted primary ESN selection<br/>• Outputs: regions, metadata dict, LLM hints |
| **STEP 3: Chunking (P2)** | • Re-extract via PyMuPDF<br/>• Assign single doc-level equipment_type to ALL chunks<br/>• Write one chunk row per ESN (duplicated content)<br/>All ESN copies labeled with same equipment_type | • Re-extract via pdfplumber (same parser as P1 for alignment)<br/>• Match chunk char-offset to preprocessor_regions<br/>• Write ONE chunk row per document with esn_details array<br/>• esn_details: [{esn, equip_type, ...}, ...] for each ESN<br/>• No row duplication; per-ESN metadata embedded once |
| **STEP 4: Indexing** | • Index: embedding + doc-level equipment_type | • Index: embedding + per-chunk primary_equip_type (now correct per ESN) |
| **STEP 5A: FSR Search (by ESN)** | • Query metadata_table where all_esns contains ESN<br/>• Return all docs (ESNs not properly typed) | • Query chunk metadata JSON where esn_details contains ESN and ESN is active<br/>• Return doc + ESN equipment attributes from esn_details |
| **STEP 5B: Risk Evaluation** | • Vector Search returns chunks for ESN<br/>• ✗ Problem: Chunks may be mislabeled (Gen chunks labeled GT)<br/>• LLM processes wrong-equipment chunks → wrong risks | • Vector Search returns chunks filtered by primary_equip_type<br/>• ✓ Chunks correctly labeled (per-region attribution)<br/>• LLM processes correct-equipment chunks → accurate risks |

---

## Knobs & Layer Impact

**⚠️ Implementation Decision:** We are implementing **Fix 2 (v2_fix1_fix2) directly** as the production preprocessor. This table shows the progression for reference, but Fix 2 is the target since it includes all improvements from Fix 1 plus additional fixes for hidden headers and nested subsections.

| Knob | What It Does | Why It Helps | Metadata Extraction | Chunking | Embedding | Retrieval |
|---|---|---|---|---|---|---|
| **Preprocessor (v1)** | Regex-scans page-1 for section headers, GE form numbers, ESN labels. Detects inactive ESNs. Maps regions as char-offset boundaries. Outputs: metadata (doc-level), hints (for LLM), regions (char ranges with per-section metadata). | Provides accurate equipment attribution per section **before** chunking occurs. Enables per-chunk equipment type assignment instead of doc-level assignment. | • Calls preprocessor on full PDF text<br/>• Stores preprocessor_regions JSON (char offsets)<br/>• Stores doc-level metadata + inactive_esns<br/>• Passes hints to LLM extraction<br/>• Merges 4-level: region > preprocessor > LLM > tags | • Reads preprocessor_regions<br/>• For each chunk: matches char offset to region<br/>• Assigns chunk.primary_equip_type from matched region (not doc-level)<br/>• Skips chunks for inactive ESNs | No change. Uses chunk.primary_equip_type from P2. | No change. Filters by chunk.primary_equip_type (now correct). |
| **Preprocessor Fix 1 (v2_fix1)** | Adds GT_SIGNATURES keyword list. Switches primary ESN selection from alphabetical to **content-weighted**: byte-share from boundaries + keyword density on full document. Fixes per-page fallback: uses doc-level primary instead of first-sorted ESN. | Fixes root cause of multi-ESN mislabeling. Doc-level primary now reflects which equipment **owns most content**, not arbitrary sorting. Per-page fallback no longer alphabetically misorders ESNs. | • Same preprocessor flow as v1<br/>• **NEW:** Compute byte-share per boundary<br/>• **NEW:** Count GT_SIGNATURES + GEN_SIGNATURES<br/>• **NEW:** Pick primary via content dominance (20%+ threshold)<br/>• **NEW:** Per-page fallback uses _choose_primary() result<br/>• Result: doc-level primary = correct equipment | No change. Regions still use char offsets; P2 logic unchanged. | No change. | No change. |
| **Preprocessor Fix 2 (v2_fix1_fix2)** | **Fix 2A:** Re-scans **full_text** (not just page-1) for HEADER pattern. Finds embedded "GENERATOR (ESN)" headers mid-document (pages 30+).<br/>**Fix 2B:** Detects nested subsection headers: "3.1.1 Generator Stator/Field Tests...". Creates boundaries at subsection transitions (e.g., page 145 mid-report). | Catches equipment sections that were invisible in page-1-only scan. Detects subsection-level equipment boundaries nested under top-level sections. Prevents entire Generator sub-report from being misattributed to Gas Turbine. | • Same Fix 1 logic<br/>• **NEW:** re.finditer(HEADER) on full_text (not just title[:6])<br/>• **NEW:** Scan for SUBSEC_GEN pattern "3.1.1 Generator"<br/>• **NEW:** Scan for SUBSEC_GT pattern "3.1.1 Turbine/Combustion"<br/>• **NEW:** Create boundaries at subsection transitions<br/>• Result: region_map includes hidden + nested headers | No change. Regions still char-offset based; P2 logic unchanged. More precise regions passed from P1. | No change. | No change. |

---

## Layer-by-Layer Summary (Files & Changes — Fix 2 Implementation)

| Layer | File | Implementation |
|---|---|---|
| **Metadata Extraction (P1)** | `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py` | Calls `preprocessor_v2_fix1_fix2.py` with full-text scan, content-weighted primary selection, full-text header re-scan, nested subsection detection |
| **Chunking (P2)** | `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py` | Reads preprocessor_regions from P1, matches char offsets to chunks, assigns equipment type per region (no doc-level). Uses pdfplumber (not PyMuPDF) for parser alignment. |
| **Embedding** | `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py` (same) | Uses chunk equipment type from P2 (now correct due to per-region attribution) |
| **Retrieval** | Risk Evaluation Service | Filters by chunk.primary_equip_type (now accurate across multi-ESN documents) |

---

## Expected Accuracy Impact (Fix 2 Implementation)

| Document Pattern | Baseline (v1) | Fix 2 Result |
|---|---|---|
| **Clean single-equipment** | ✓ Correct (82%+) | ✓ Correct (no regression) |
| **Riverside (Gen-only, GT ESN first)** | ✗ 38% mislabeled GT | ✓ Fixed: Doc-level primary → Gen, all pages labeled Gen |
| **b775cf29 (GT title, Gen buried)** | ✗ 145 Gen pages labeled GT | ✓ Fixed: Full-text re-scan finds embedded GENERATOR header mid-document, creates boundary |
| **GT12 (GT+Gen, nested Generator subsection)** | ✗ Boundary drift at page 160+ | ✓ Fixed: Subsection pattern detects "3.1.1 Generator" at page 170, creates correct boundary |

**Projected overall accuracy:** 82.6% (baseline) → ~90-93% (Fix 2 combining all improvements)

---

## POC Validation

**Approach (adopted from Vince's sdg-autotest harness):** Two checks — a page-range scorer for accuracy numbers, and an end-to-end smoke test in SAGE.

### 1. Page-Range Scorer (Chunk Accuracy %)

For each chunk in the test set, compare the preprocessor-assigned `primary_equip_type` against a manually verified ground truth CSV:

```
document_name              page_start  page_end  expected_label
─────────────────────────  ──────────  ────────  ──────────────
GT12_Major_Inspection...   1           161       Gas Turbine
GT12_Major_Inspection...   162         350       Generator
Riverside_Generator...     1           999       Generator
b775cf29...                1           24        Gas Turbine
b775cf29...                25          169       Generator
b775cf29...                170         325       Gas Turbine
HGPI___IDC...              1           999       Gas Turbine
Unit_10B...                1           999       Gas Turbine

Accuracy = correct chunks / total chunks
Baseline (v1):  82.6%  (613/742 correct)
Fix 1:          86.7%  (+4.0 pp, zero regressions) — VALIDATED ✓
Fix 2 target:   ~90-93%
```

> Page boundaries are ±5 pages approximate — good enough to measure relative improvement between versions.

### 2. End-to-End Smoke Test (SAGE Discovery)

Upload test PDFs to DS Guru (SAGE, localhost:8005), filter by equipment type, and verify correct results:

| Document | Filter | Query | Expected |
|---|---|---|---|
| Riverside (693 pages, Generator report) | Equipment Type = Generator | "stator rewind findings" | Lamination/winding details ✓ |
| b775cf29 (nested Gen under Turbine) | Equipment Type = Generator | "generator stator test results" | IR/PI/Hipot test data ✓ |
| GT12 (clean multi-equip) | Equipment Type = Gas Turbine | "turbine blade inspection" | GT-specific findings only ✓ |

**Regression:** Single-equipment docs (HGPI, Unit_10B) must return same results before and after fix.

### 3. Pass Criteria (Before Production Rollout)

- Page-range scorer ≥ 90% on test set
- Zero regressions on clean single-equipment docs
- SAGE smoke test returns correct results for Riverside + b775cf29

---

## Critical: PDF Parser Alignment (P1 ↔ P2)

**Problem:**
- P1 uses **pdfplumber** to extract text → computes char offsets for preprocessor_regions
- Current P2 uses **PyMuPDF** to re-extract text
- Different parsers extract text differently (spacing, font handling, etc.) → char offsets misalign
- Result: P2 can't find the correct region boundaries, equipment types assigned incorrectly

**Solution:**
- **P1:** Keep pdfplumber (already in use)
- **P2:** Change from PyMuPDF → **pdfplumber** (same parser as P1)
- Ensures char offset consistency between preprocessor_regions (computed in P1) and chunk matching (in P2)

**Files to change:**
- `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py`: Replace `fitz` (PyMuPDF) imports with `pdfplumber`
- Update text extraction loop to use pdfplumber API

**Impact:**
- ✓ Guarantees char-offset alignment
- ✓ No storage bloat (avoids storing raw text in metadata_table)
- ✓ Minimal performance cost (~200-500ms re-extraction per doc, negligible vs. embedding time)

---

## Metadata Table Schema Changes

### Existing Columns (no change)
- `esn` — resolved single ESN (from LLM, page-1, or fsr_pdf_ref)
- `equipment_type` — equipment type from LLM extraction
- `all_esns` — **LEGACY / DEPRECATED** — retained temporarily for backward compatibility only
- `equipment_sys_id`, `equipment_class_code`, `report_issued_date`, `outage_start_date`, `outage_end_date`, etc.

### LEGACY Column (deprecated)

**Column: `all_esns`** (STRING, deprecated)
- **Old format (flat array):** `["298250", "338X447", "UNKNOWN"]`
- **New format (dict with equipment metadata):**
  ```json
  {
    "298250": {"equip_type": "Gas Turbine", "technology_code": "7FA.03"},
    "338X447": {"equip_type": "Generator", "technology_code": "7FH2"},
    "UNKNOWN": {"equip_type": null, "technology_code": null}
  }
  ```
- **Populated by:** Preprocessor output in P1 (combines all ESNs found with their equipment types from preprocessor_regions)
- **Used by:** Legacy reads only; not used as retrieval source of truth.
- **Purpose:** Backward compatibility during migration.
- **DDL change:** Column already exists; content format changes at the application layer (P1 preprocessor integration)

### NEW Columns (added for preprocessor integration)

**Column 1: `preprocessor_regions`** (STRING, nullable)
- **Type:** JSON array serialized as string
- **Sample value:**
  ```json
  [
    {"start": 0,     "end": 84320,  "metadata": {"primary_esn": "298250",  "primary_equip_type": "Gas Turbine", "primary_technology_code": "7FA.03"}},
    {"start": 84320, "end": 198440, "metadata": {"primary_esn": "338X447", "primary_equip_type": "Generator", "primary_technology_code": "7FH2"}}
  ]
  ```
- **Populated by:** Preprocessor output in P1 (step 1)
- **Used by:** P2 chunking — matches char offsets to assign `chunk.primary_equip_type`
- **Purpose:** Enables per-section equipment attribution instead of doc-level
- **DDL change:** `ALTER TABLE METADATA_TABLE ADD COLUMNS (preprocessor_regions STRING COMMENT '...')`

**Column 2: `inactive_esns`** (STRING, nullable)
- **Type:** Comma-separated ESN list OR JSON array (needs to match preprocessor output format)
- **Sample values:**
  - CSV: `"298250,UNKNOWN,SY1234567"`
  - JSON: `["298250", "UNKNOWN", "SY1234567"]`
- **Populated by:** Preprocessor output in P1 (step 1)
- **Used by:** P2 chunking — skips chunk emission for ESNs in this list
- **Purpose:** Prevents chunks from being written for ESNs marked "no work performed"
- **DDL change:** `ALTER TABLE METADATA_TABLE ADD COLUMNS (inactive_esns STRING COMMENT '...')`

### DDL & Schema Evolution

**File:** `pw_sdg_ai_ser_repo/common/fsr_config.py`
- **Change:** Add column definitions to `METADATA_TABLE_DDL_COLS` string (used by CREATE TABLE IF NOT EXISTS)

**File:** `pw_sdg_ai_ser_repo/silver/src/ddl/nb_sdg_fsr_ddl.py`
- **Change:** Add idempotent ALTER TABLE statements for schema evolution
- **Why idempotent:** Allows incremental schema updates on existing tables without re-creating them

### P1 Integration Points (Code Changes Needed)

1. **Extract Full PDF** (currently only page-1 is extracted)
   - Location: `nb_sdg_fsr_metadata.py`, PDF extraction loop (~line 853)
   - Change: Add full PDF text extraction via pdfplumber
   - Output: Store as `extractions[document_id]["full_text"]`

2. **Call Preprocessor**
   - Location: Same file, after full text extraction
   - Input: `{"full_text": full_text, "page_count": page_count, "fields": llm_fields}`
   - Output: `{"metadata": {...}, "hints": "...", "regions": [...]}`
   - Store in: `extractions[document_id]["preprocessor_output"]`

3. **Add to Success Records**
   - Location: `nb_sdg_fsr_metadata.py`, ~line 1035 where `rec` dict is built
   - Changes:
     ```python
     rec["preprocessor_regions"] = json.dumps(preprocessor_output["regions"]),
     rec["inactive_esns"] = preprocessor_output["metadata"].get("inactive_esns", ""),
     ```

4. **Update MERGE Statement**
   - Location: `nb_sdg_fsr_metadata.py`, ~line 1366 (MERGE INTO METADATA_TABLE)
   - Changes: Add to both INSERT and UPDATE clauses:
     ```sql
     tgt.preprocessor_regions = src.preprocessor_regions,
     tgt.inactive_esns = src.inactive_esns,
     ```

### P1 Integration (How to Build Structured `all_esns`)

**File:** `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py`

**Current behavior (without preprocessor):**
```python
# From fsr_pdf_ref or LLM
all_esns_set = set(ref_esns)
if resolved_esn:
    all_esns_set.add(resolved_esn)
all_esns = json.dumps(sorted(all_esns_set))  # ["298250", "338X447", "UNKNOWN"]
```

**New behavior (with preprocessor):**
```python
# 1. Get ESN→equip_type mapping from preprocessor.metadata
preprocessor_esn_to_equip = preprocessor_output["metadata"].get("esn_to_equip_type", {})

# 2. Build all_esns dict by enriching all discovered ESNs with equipment type
all_esns_dict = {}
for esn in all_esns_set:  # all_esns_set = union of ref_esns + resolved_esn
    equip_type = preprocessor_esn_to_equip.get(esn)
    all_esns_dict[esn] = {
        "equip_type": equip_type,
        "technology_code": preprocessor_esn_to_equip.get(f"{esn}_tech_code")
    }

# 3. Store as JSON
all_esns = json.dumps(all_esns_dict)
# Result: {"298250": {"equip_type": "Gas Turbine", ...}, "338X447": {"equip_type": "Generator", ...}}
```

**Where this happens:** In `nb_sdg_fsr_metadata.py` when building the `rec` dict (~line 1035) before writing to metadata_table.

---

### P2 Integration (Use chunk metadata JSON as source of truth)

**File:** `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py`

**Current behavior (doc-level equipment type):**
```python
# All chunks use the single doc-level equipment_type
chunk["primary_equip_type"] = row["equipment_type"]
```

**New behavior (per-ESN equipment type):**
```python
# 1. Read ESN metadata from chunk metadata JSON
chunk_metadata = json.loads(row["metadata"])
esn_details = chunk_metadata.get("esn_details", [])
inactive_esns = set(chunk_metadata.get("inactive_esns", []))

# 2. Resolve active ESNs at retrieval time
for esn_metadata in esn_details:
  esn = esn_metadata.get("esn")
    if esn in inactive_esns:
        continue
    
    equip_type = esn_metadata.get("equip_type")
    
    # Create chunk rows for this ESN with its correct equipment type
    for chunk_index, chunk_text in enumerate(chunks):
        chunk_row = {
            "document_id": document_id,
            "esn": esn,
            "primary_equip_type": equip_type,  # From metadata.esn_details, not doc-level
            "chunk_text": chunk_text,
            ...
        }
```

**Why this works:**
- P2 no longer relies on doc-level `equipment_type` column
- Each ESN gets its correct equipment type from `metadata.esn_details`
- Eliminates the root cause of multi-ESN mislabeling

---

## Summary: What Gets Written to Metadata Table

| Column | Source | Format | Example |
|---|---|---|---|
| `esn` | LLM (existing) | STRING | "338X447" |
| `equipment_type` | LLM (existing) | STRING | "Generator" |
| **`all_esns`** | **Preprocessor (MODIFIED)** | **JSON object** | **`{"298250": {"equip_type": "Gas Turbine", "technology_code": "7FA.03"}, "338X447": {"equip_type": "Generator", "technology_code": "7FH2"}}`** |
| **`preprocessor_regions`** | **Preprocessor (NEW)** | **JSON** | **`[{"start":0, "end":84320, "metadata":{...}}]`** |
| **`inactive_esns`** | **Preprocessor (NEW)** | **STRING or JSON** | **"298250,UNKNOWN"** |

### P2: Embed esn_details Metadata on Single Chunk Row

**Instead of duplicating chunk rows per ESN**, embed all ESN metadata in a structured array on a single chunk row:

```python
# Read all_esns from metadata table
all_esns_dict = json.loads(row["all_esns"])  # {"298250": {...}, "338X447": {...}}

# Build esn_details array, skipping inactive ESNs
esn_details = []
esn_list = []  # Helper for vector search filtering

for esn, esn_metadata in all_esns_dict.items():
    if esn in inactive_esns:
        continue
    
    esn_details.append({
        "esn": esn,
        "equip_type": esn_metadata.get("equip_type"),
        "technology_code": esn_metadata.get("technology_code"),
        # ... other per-ESN attributes
    })
    esn_list.append(esn)

# ONE chunk row per document (not per ESN)
chunk_row = {
    "document_id": document_id,
    "esn": esn_details[0]["esn"],  # primary (rank 0)
    "esns": esn_list,  # Array for vector search filtering
    "esn_details": esn_details,  # Struct array: per-ESN metadata
    "embedding": embedding_vector,
    "content": chunk_text,
    ...
}
```

**Why this design:**
- **No duplication:** One chunk row per document, even with multiple ESNs
- **Complete metadata:** Each ESN's equipment type and attributes travel together (no cross-ESN confusion)
- **Vector search:** Filter by `exists(esn_details, x -> x.esn = 'E1' AND x.equip_type = 'Generator')`
- **Phase 1 friendly:** For existing chunks, just UPDATE the metadata columns (esn_details, esns) in place — no re-chunking needed

**Note:** The preprocessor structures `all_esns` as a dict that preserves equipment type per ESN. P2 embeds this directly into chunk row's `esn_details` array — no row fan-out required.

---

## References & Code Locations

### Preprocessor (New Implementation)

| Component | Path | Purpose |
|---|---|---|
| **Preprocessor v2_fix1_fix2** | `/home/u560060992/dbx/ds-guru/app/preprocessor_v2_fix1_fix2.py` | Production preprocessor — full-text scanning, content-weighted primary selection, nested subsection detection |
| **Preprocessor v2_fix1** | `/home/u560060992/dbx/ds-guru/app/preprocessor_v2_fix1.py` | Reference only — validated intermediate version (+4.0pp accuracy) |
| **Preprocessor v1** | `/home/u560060992/dbx/ds-guru/app/preprocessor.py` | Reference only — baseline (82.6% accuracy) |

### FSR Pipeline (Existing + Changes)

| Step | File | Purpose |
|---|---|---|
| **P1: Metadata Extraction** | `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py` | Extracts PDFs, calls preprocessor, enriches with IBAT/EV, writes metadata_table<br/>**Changes needed:** Full-text extraction, preprocessor integration, region/inactive_esns storage and chunk metadata alignment |
| **P1: DDL** | `pw_sdg_ai_ser_repo/silver/src/ddl/nb_sdg_fsr_ddl.py` | Creates/updates metadata_table schema<br/>**Changes needed:** Add preprocessor_regions, inactive_esns columns |
| **P1: Config** | `pw_sdg_ai_ser_repo/common/fsr_config.py` | Defines table schemas, volume paths, constants<br/>**Changes needed:** Update METADATA_TABLE_DDL_COLS with new columns |
| **P2: Chunking** | `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py` | Reads metadata, chunks, embeds, writes chunk_table<br/>**Changes needed:** Replace PyMuPDF with pdfplumber, persist esn_details/inactive_esns in chunk metadata JSON for retrieval |
| **Vector Search** | Databricks Vector Search (managed) | Indexes chunks for semantic retrieval<br/>**No changes:** Works with updated chunk schema |

### Configuration & Secrets

| Item | Location | Purpose |
|---|---|---|
| **Volume paths** | `pw_sdg_ai_ser_repo/common/fsr_config.py` → `PDF_VOLUME_PATHS` | Source volumes for PDF discovery (set via job parameters) |
| **Table names** | `pw_sdg_ai_ser_repo/common/fsr_config.py` → METADATA_TABLE, CHUNK_TABLE, etc. | Set via job parameters (different per env) |
| **LLM gateway** | `pw_sdg_ai_ser_repo/common/fsr_config.py` → LITELLM_BASE_URL, LITELLM_API_KEY | LiteLLM endpoint for extraction |
| **IBAT enrichment** | `pw_sdg_ai_ser_repo/common/fsr_config.py` → IBAT_EQUIPMENT_TABLE | Reference table for equipment enrichment |
| **Event Vision** | `pw_sdg_ai_ser_repo/common/fsr_config.py` → EVENT_VISION_SOT_TABLE | Reference table for event enrichment |

### Key Related Documents

- **Vince-Experiment-Summary.md** — POC results and root cause analysis
- **Preprocessor-Integration-Plan.md** — Job A (new docs) and Job B (backfill) implementation details
- **fsr_config.py** — Central config hub (table schemas, volume paths, constants)
