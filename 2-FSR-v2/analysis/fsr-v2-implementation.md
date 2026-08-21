# Preprocessor Knobs & Implementation Details

This document contains implementation and validation details for the design in [../design/FSR-v2-design.md](../design/FSR-v2-design.md).

If implementation behavior changes here, update the design assumptions in [../design/FSR-v2-design.md](../design/FSR-v2-design.md).

---

## Implementation Comparison: Exists Today vs. New (with Preprocessor)

| Step | Exists Today | New Implementation (with Fix 2 Preprocessor) |
|---|---|---|
| **STEP 1: Metadata Extraction (P1)** | • Extract page-1 text only<br/>• LLM extracts single ESN + equipment_type<br/>• Doc-level all_esns as flat array ["ESN1", "ESN2"]<br/>• No region boundaries<br/>• No inactive_esns tracking | • Extract full PDF text<br/>• Call preprocessor_v2_final on full text<br/>• Persist preprocessor outputs in metadata_table (preprocessor_regions, inactive_esns, ESN/equipment mapping)<br/>• Keep all_esns only as legacy compatibility field |
| **STEP 2: Preprocessing** | ✗ Does not exist (no preprocessor today) | • Full-text header scanning (finds embedded headers)<br/>• Nested subsection detection (e.g., "3.1.1 Generator")<br/>• Content-weighted primary ESN selection<br/>• Outputs: regions, metadata dict, LLM hints |
| **STEP 3: Chunking (P2)** | • Re-extract via PyMuPDF<br/>• Assign single doc-level equipment_type to ALL chunks<br/>• Write one chunk row per ESN (duplicated content)<br/>All ESN copies labeled with same equipment_type | • Re-extract via pdfplumber (same parser as P1 for alignment)<br/>• Read persisted P1 outputs from metadata_table<br/>• Match chunk char-offset to preprocessor_regions<br/>• Materialize retrieval fields on chunk rows: primary_equip_type, inactive_esns (and esn_details only if downstream materialization is enabled)<br/>• Keep metadata JSON mirror only for transition compatibility<br/>• No row duplication; per-ESN metadata embedded once |
| **STEP 4: Indexing** | • Index: embedding + doc-level equipment_type | • Index: embedding + per-chunk primary_equip_type (now correct per ESN) |
| **STEP 5: FSR Search + Retrieval Prep (ESN Resolution)** | • Query metadata_table where all_esns contains ESN<br/>• Return all docs (ESNs not properly typed) | • Query chunk_table retrieval metadata (Gold) using preprocessor-derived keys (primary_esn / gt_esn / gen_esn, excluding inactive_esns); if esn_details is materialized, it can be used as equivalent source<br/>• Build retrieval targets (`esn_list`, `equipment_type_list`, `document_scope`) |
| **STEP 6: Risk Evaluation (Pass-Based)** | • Vector Search returns chunks for ESN<br/>• ✗ Problem: Chunks may be mislabeled (Gen chunks labeled GT)<br/>• LLM processes wrong-equipment chunks → wrong risks | • Pass 1: strict ESN + equipment-type + semantic filters<br/>• Pass 2: adaptive knob tuning when recall is low (k/threshold/filter strictness)<br/>• ✓ LLM processes equipment-correct chunks with retrieval diagnostics |

---

## Retrieval Flow Reference

Canonical retrieval and risk-evaluation flow lives in [../design/FSR-v2-design.md](../design/FSR-v2-design.md).

Implementation file focus:
- concrete file-level changes
- parser and schema alignment details
- validation approach and rollout criteria

---

## Knobs & Layer Impact

**Implementation decision:** Implement **Fix 2 (v2_fix1_fix2)** directly as the production preprocessor. Table below keeps the progression for reference.

| Knob | What It Does | Why It Helps | Metadata Extraction | Chunking | Embedding | Retrieval |
|---|---|---|---|---|---|---|
| **Preprocessor (v1)** | Regex-scans page-1 for section headers, GE form numbers, ESN labels. Detects inactive ESNs. Maps regions as char-offset boundaries. Outputs: metadata (doc-level), hints (for LLM), regions (char ranges with per-section metadata). | Provides accurate equipment attribution per section before chunking occurs. Enables per-chunk equipment type assignment instead of doc-level assignment. | • Calls preprocessor on full PDF text<br/>• Stores preprocessor_regions JSON (char offsets)<br/>• Stores doc-level metadata + inactive_esns<br/>• Passes hints to LLM extraction<br/>• Merges 4-level: region > preprocessor > LLM > tags | • Reads preprocessor_regions<br/>• For each chunk: matches char offset to region<br/>• Assigns chunk.primary_equip_type from matched region (not doc-level)<br/>• Skips chunks for inactive ESNs | No change. Uses chunk.primary_equip_type from P2. | No change. Filters by chunk.primary_equip_type (now correct). |
| **Preprocessor Fix 1 (v2_fix1)** | Adds GT_SIGNATURES keyword list. Switches primary ESN selection from alphabetical to content-weighted: byte-share from boundaries + keyword density on full document. Fixes per-page fallback: uses doc-level primary instead of first-sorted ESN. | Fixes root cause of multi-ESN mislabeling. Doc-level primary now reflects which equipment owns most content, not arbitrary sorting. | • Same preprocessor flow as v1<br/>• NEW: Compute byte-share per boundary<br/>• NEW: Count GT_SIGNATURES + GEN_SIGNATURES<br/>• NEW: Pick primary via content dominance (20%+ threshold)<br/>• NEW: Per-page fallback uses _choose_primary() result | No change. Regions still use char offsets; P2 logic unchanged. | No change. | No change. |
| **Preprocessor Fix 2 (v2_fix1_fix2)** | Fix 2A: Re-scans full_text (not just page-1) for HEADER pattern. Finds embedded GENERATOR headers mid-document.<br/>Fix 2B: Detects nested subsection headers like 3.1.1 Generator and creates boundaries at subsection transitions. | Catches equipment sections invisible in page-1 scan and nested subsection boundaries. | • Same Fix 1 logic<br/>• NEW: re.finditer(HEADER) on full_text<br/>• NEW: Scan SUBSEC_GEN / SUBSEC_GT patterns<br/>• NEW: Create subsection boundaries | No change. Regions still char-offset based; P2 logic unchanged. | No change. | No change. |

---

## Layer-by-Layer Summary (Files & Changes — Fix 2 Implementation)

| Layer | File | Implementation |
|---|---|---|
| **Metadata Extraction (P1)** | `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py` | Calls `preprocessor_v2_final.py` with full-text scan, content-weighted primary selection, full-text header re-scan, nested subsection detection |
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

Projected overall accuracy: 82.6% baseline to about 90-93% with Fix 2.

---

## POC Validation

### 1. Page-Range Scorer (Chunk Accuracy %)

Compare preprocessor-assigned `primary_equip_type` vs ground-truth ranges:

- Baseline (v1): 82.6% (613/742)
- Fix 1: 86.7% (+4.0 pp, zero regressions)
- Fix 2 target: about 90-93%

### 2. End-to-End Smoke Test (SAGE Discovery)

- Riverside: Filter Generator, query stator rewind findings
- b775cf29: Filter Generator, query generator stator test results
- GT12: Filter Gas Turbine, query turbine blade inspection

Regression: single-equipment docs must remain unchanged.

### 3. Pass Criteria

- Page-range scorer >= 90%
- Zero regressions on clean single-equipment docs
- SAGE smoke test passes for Riverside + b775cf29

---

## Critical: PDF Parser Alignment (P1 ↔ P2)

- P1 computes char offsets with pdfplumber.
- If P2 uses PyMuPDF, offsets can misalign.
- For full phase-2 derivation, P2 should use pdfplumber too.

Impact:
- guarantees char-offset alignment
- avoids mis-assigned chunk equipment types

---

## Summary: What Gets Written to Metadata Table

| Column | Source | Format |
|---|---|---|
| `esn` | Legacy (deprecated) | STRING (compatibility only; drop later once confirmed unused) |
| `equipment_type` | Legacy (deprecated) | STRING (doc-level compatibility only; drop later once confirmed unused) |
| `all_esns` | Legacy (deprecated) | STRING/JSON (compatibility only; drop later once confirmed unused) |
| `preprocessor_regions` | Preprocessor (new) | JSON |
| `esn_details` | Downstream materialization (optional) | JSON (per-ESN attributes when retriever/P2 materialization is enabled) |
| `inactive_esns` | Preprocessor (new) | STRING or JSON |

Note:
- `primary_equip_type` is chunk-level and is materialized by P2 onto chunk rows.
- Canonical persisted preprocessor outputs are `preprocessor_regions` and `inactive_esns` (plus doc-level ESN fields emitted by preprocessor).
- `esn_details` is optional and only present when downstream retriever/P2 materialization is explicitly implemented.

---

## References & Code Locations

- Preprocessor v2_final: `/home/u560060992/dbx/2-FSR-v2/analysis/preprocessor_v2_final.py`
- Metadata extraction job: `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py`
- Chunking job: `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py`
- Config: `pw_sdg_ai_ser_repo/common/fsr_config.py`

Back-link to design doc: [../design/FSR-v2-design.md](../design/FSR-v2-design.md)
