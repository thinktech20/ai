# FSR Retrieval & Tagging Fix — Status and Plan

**Date:** 2026-07-15 (updated)  
**Team:** Madhurima, Xujin, Aditi, Abhinaya, Tao  
**Stakeholder:**  

---

## Executive Summary

Multi-equipment FSR documents have chunks incorrectly labeled, causing the risk evaluation to confuse equipment findings (e.g., Generator rotor issues attributed to Gas Turbine). A separate issue causes some ESN queries to return zero results.

**Current status:**
- Reproduced the problem on 7 (from Vince https://gevernova.box.com/s/csbs8cl4fcjcquy7i5m879zmpzjuol42) confirmed-failure documents
- **END-TO-END VALIDATED in DS Guru** (2026-07-14): Riverside and b775cf29 Generator reports correctly return stator findings when filtered by Equipment Type = Generator
- The fix is a **metadata UPDATE on existing chunks** — no document re-ingestion required


**Timeline:**
- POC validation complete: **end of this week (July 18)**
- Full remediation estimate: **provided after POC**
- Deployment approach: ad-hoc fix on priority documents first, broader rollout after

**Key point:** The actual production fix is a targeted metadata update using the validated preprocessor logic. Phased approach: Phase 1 (metadata update) → Phase 2 (unify PDF library + remove inflation) → Phase 3 (re-chunking if needed).

---

## The Two Problems

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  User queries: "338X447 — Generator Rotor FOD"                      │
│                                                                     │
│       │                                                             │
│       ▼                                                             │
│  ┌────────────────────────────────────────────┐                     │
│  │  PROBLEM 1: RETRIEVAL                      │                     │
│  │  (ESN mismatch — zero results)             │                     │
│  │                                            │                     │
│  │  FSR title uses GT ESN "298250"            │                     │
│  │  but user queries Gen ESN "338X447"        │                     │
│  │  → no chunks found                        │                     │
│  │                                            │                     │
│  │  Fix: IBAT train expansion                 │                     │
│  │  338X447 → same train as 298250 → search   │                     │
│  │  both                                      │                     │
│  │                                            │                     │
│  │  Status: ✓ 7/7 test ESNs validated         │                     │
│  │  Impact: recovers 17% of zero-result ESNs  │                     │
│  └────────────────────────────────────────────┘                     │
│       │                                                             │
│       ▼  (chunks found)                                             │
│                                                                     │
│  ┌────────────────────────────────────────────┐                     │
│  │  PROBLEM 2: TAGGING                        │                     │
│  │  (wrong equipment label — confused LLM)    │                     │
│  │                                            │                     │
│  │  FSR has GT + Generator sections.          │                     │
│  │  Chunks in Gen section labeled "GT"        │                     │
│  │  → LLM confuses GT rotor with Gen rotor   │                     │
│  │                                            │                     │
│  │  Fix: Preprocessor re-labels chunks        │                     │
│  │  by detecting equipment section boundaries │                     │
│  │                                            │                     │
│  │  Status: Fix 1+2 validated in DS Guru      │                     │
│  └────────────────────────────────────────────┘                     │
│       │                                                             │
│       ▼  (correctly-labeled chunks)                                 │
│                                                                     │
│  ┌────────────────────────────────────────────┐                     │
│  │  LLM Risk Evaluation                      │                     │
│  │  → Correct assessment                     │                     │
│  └────────────────────────────────────────────┘                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## End-to-End Proof (2026-07-14)

Demonstrated in DS Guru (SAGE, localhost:8005):

### Fix 1: Riverside Generator Report

| | Before (v1 preprocessor) | After (v2 + Fix 1) |
|---|---|---|
| Document | Riverside Generator Partial Restack & Full Rewind (693 pages) |
| primary_equip_type | "Gas Turbine" ← WRONG | "Generator" ← CORRECT |
| Discovery: filter Generator | "No context available" | Stator rewind findings ✓ |
| Details returned | — | Lamination fragmentation slots 5-6, EL-CID test, Core Ring test, Full Rewind |

### Fix 2: b775cf29 (Thomas A. Smith GT+Gen T&I)

| | Before (v2 + Fix 1 only) | After (v2 + Fix 1 + Fix 2) |
|---|---|---|
| Document | b775cf29 (325 pages, Gen nested under "3.1.1 Generator Stator/Field Tests") |
| gen_esn | MISSING (not detected) | "337X766" ← DETECTED |
| Discovery: filter Generator | "No context available" | Stator IR/PI/Hipot data ✓ |
| Details returned | — | IR: 3.19 GΩ, PI: 7.04, DC leakage: 3.5 µA @ 40 kVDC |

**Note on b775cf29:** This document does NOT have a `GENERATOR (337X766 | SY...)` header. The ESN appears only as `"Hydrogen Cooled Generator SN 337X766"` in body text. Generator content is a subsection under `"3 Turbine"`.

**Production preprocessor file:** `ds-guru/preprocessors/preprocessor_v2_final.py`

---

## The Fixes (All to the Same Preprocessor Function)

All fixes are patches to **one ~350-line Python function** — Vince's preprocessor. Not separate systems. Just fixing labeling logic.

```
┌─────────────────────────────────────────────────────────────────────┐
│  VINCE'S PREPROCESSOR (one Python function, ~350 lines)              │
│                                                                     │
│  Step 1: Find ESNs on title page              ← works fine          │
│  Step 2: Find section headers → regions       ← BUG (Fix 2)        │
│  Step 3: Per-page fallback (no header found)  ← BUG (Fix 1)        │
│  Step 4: Tag chunks from regions              ← BUG (Fix 3, HOLD)  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Fix 1: Fallback uses wrong default           ✓ VALIDATED           │
│  ┌──────────────────────────────────────┐                           │
│  │ When no section header found,        │                           │
│  │ page has no form number signal →     │                           │
│  │ picks first ESN alphabetically       │                           │
│  │ "298250" (GT) < "338X447" (Gen)      │                           │
│  │ → wrongly tags Gen pages as GT       │                           │
│  │                                      │                           │
│  │ FIX: Use content-weighted doc-level  │                           │
│  │ primary (gen_sig_hits vs gt_sig_hits)│                           │
│  └──────────────────────────────────────┘                           │
│                                                                     │
│  Fix 2: Section boundary detection             PARTIAL (see below)  │
│  ┌──────────────────────────────────────┐                           │
│  │ Problem: Generator content nested    │                           │
│  │ under "3 Turbine" not detected.      │                           │
│  │                                      │                           │
│  │ Initial implementation (validated    │                           │
│  │ on b775cf29 in DS Guru):             │                           │
│  │ a) Scan body text to register ESN    │                           │
│  │ b) Detect subsection headers         │                           │
│  │    ("3.1.1 Generator...") as         │                           │
│  │    boundaries                        │                           │
│  │ c) Fix SECTION_HDR regex (same line) │                           │
│  │                                      │                           │
│  │ Still needs (from team review):      │                           │
│  │ • ESN detection via IBAT instead     │                           │
│  │   of expanding regex (Decision 1)    │                           │
│  │ • Stack-based boundary reset logic   │                           │
│  │   (Decision 2)                       │                           │
│  └──────────────────────────────────────┘                           │
│                                                                     │
│  Fix 3: Content-signal chunk override         ON HOLD               │
│  ┌──────────────────────────────────────┐                           │
│  │ Flip label when chunk has 5+ sigs    │                           │
│  │ from one side, 0 from other.         │                           │
│  │                                      │                           │
│  │ RISK: Generator data form pages      │                           │
│  │ contain GT ESN in footers/tables.    │                           │
│  │ Flip logic would incorrectly count   │                           │
│  │ these and flip correct Gen chunks.   │                           │
│  │                                      │                           │
│  │ STATUS: ON HOLD until footer         │                           │
│  │ stripping is implemented.            │                           │
│  └──────────────────────────────────────┘                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Team Meeting Decisions (2026-07-14)

Discussed with Xujin and Madhurima:

### Decision 1: ESN Detection → Use IBAT enrichment

Don't keep expanding regex for every ESN format. Instead:
- Scan cover page + TOC for ESNs (smaller scope = safer regex)
- Enrich with IBAT train expansion for missing ESNs
- Avoids false matches from voltage readings / test data in body text

### Decision 2: Boundary Reset → Stack-based logic

```
3 Turbine          → push "Gas Turbine" as default for this section
  3.1.1 Generator  → push "Generator" (override)
  3.1.2 Lift Oil   → pop → reverts to parent "Gas Turbine"
  3.1.3 Generator  → push "Generator" again
  3.2 Compressor   → pop → reverts to "Gas Turbine"
```

Key rules:
- Same equipment type repeats → inherit ESN from previous boundary
- Lower hierarchy with no equipment keyword → revert to parent
- Only explicit equipment change creates new boundary

### Decision 3: Fix 3 → ON HOLD

Generator data form pages contain GT ESN in footers and table headers. Flip logic too risky.

### Decision 4: Pre-filtering approach

~20% of chunks legitimately reference both equipment types. Tag metadata correctly, but instruct LLM:
> "Use primary_equip_type metadata as your primary guide. If you see strong evidence contradicting the label, use the evidence but flag the inconsistency."

### Decision 5: Phased deployment

- **Phase 1:** Metadata UPDATE only. No re-chunking. (~2-3 days for priority docs)
- **Phase 2:** Unify PDF extraction library + remove inflation (fan-out). (~1 week)
- **Phase 3:** Full re-ingestion with improved chunking if needed.

---

## How the Approach Works (for team members)

### The Problem

A single FSR PDF describes BOTH a Gas Turbine AND a Generator. Chunks get a label saying which equipment they're about. **Labels are currently wrong** — Generator content gets labeled "Gas Turbine" because the system defaults to GT.

### The Fix

Run a Python script (the "preprocessor") that reads the PDF and figures out which pages are about which equipment. Then UPDATE the label on each chunk.

### What the Preprocessor Does

```
INPUT:  A 693-page PDF about a Generator (Riverside)
        Title page says: "Gas Turbine ESN: 298250, Generator ESN: 338X447"

WHAT IT DOES:
  1. Reads title page → finds both ESNs
  2. Counts keywords in the whole document:
     - "stator", "winding", "hipot", "collector"... = 438 Generator hits
     - "combustion", "nozzle", "compressor"...      = 21 Gas Turbine hits
  3. Decides: 438 >> 21 → this is a Generator document
  4. Labels ALL chunks as: primary_equip_type = "Generator", primary_esn = "338X447"

OUTPUT: Each chunk now has the correct label.
TIME: < 2 seconds per document. No AI. No API calls. Just pattern matching.
```

### What Gets Tagged on Each Chunk

Regions carry BOTH equipment type AND ESN:

```
GT12_Major_Inspection_2024.pdf (350 pages):

  Pages 1-161: Gas Turbine content
    → primary_equip_type = "Gas Turbine", primary_esn = "875127"

  Pages 162-350: Generator content
    → primary_equip_type = "Generator", primary_esn = "GG10525"

  Query for ESN "GG10525" → returns ONLY Generator chunks (pages 162+)
```

### Deployment: Re-label, Don't Re-chunk

The fix is an UPDATE on existing chunks — no re-ingestion required:

```sql
UPDATE chunk_table
SET primary_equip_type = 'Generator', primary_esn = 'GG10525'
WHERE document_name = 'GT12_Major_Inspection_2024.pdf'
  AND page_number BETWEEN 162 AND 350;
```

---

## How to Validate (DS Guru)

1. Open local **http://localhost:8005** or sandbox **http://10.244.236.206:8040** (DS Guru / SAGE)
2. Collections → select `fsr-multi-equip`
3. Ensure preprocessor is installed (check Metadata Schema → Preprocessor enabled)
4. Upload a test PDF with "Extract custom metadata" checked
5. Go to Discovery → filter `Equipment Type = Generator`
6. Ask a Generator question → should return relevant content

**Test the preprocessor without uploading:**
- Click Test in the Preprocessor section → paste/upload a PDF → check output

**Production preprocessor file:** `ds-guru/preprocessors/preprocessor_v2_final.py`

---

## Task Assignments — Updated 2026-07-14

| Task |  Due | Status |
|------|-----|--------|
| Fix 1: Content-weighted primary + fallback | Jul 14 | ✓ Validated in DS Guru |
| Fix 2: Boundary detection (initial — works for b775cf29) | Jul 14 | ✓ Validated in DS Guru |
| Fix 2 refinement: Stack-based boundary reset (Decision 2) | Jul 16 | ◻ Implement + test |
| Fix 2 refinement: ESN via IBAT enrichment (Decision 1) | Jul 16 | ◻ Implement |
| Integrate preprocessor into production metadata extraction | Jul 16 | ◻ Starting |
| Run on Vince's 7 test PDFs in production pipeline | Jul 17 | ◻ After integration |
| Run on 5 new ESNs from Abhinaya (PDFs found) | Jul 17 | ◻ After integration |
| Get more problem ESNs for Production Support | Jul 16 | ◻ Pending |
| Investigate Unify PDF library| | ◻ Phase 2 |
| Check if page_number stored reliably on existing chunks |Jul 16 | ◻ More Research Needed|
| Write up ETA + scope estimate for PM |Jul 18 | ◻ After POC |
| Fix 3: Content-signal flip | ON HOLD | ✗ Too risky |

---

## New ESNs to Map (from Abhinaya's SME Support request 2026-07-14)

5 additional ESNs with negative feedback. All mapped to FSR PDFs via IBAT:

| ESN | Train | GT ESN (FSR title) | Technology |
|-----|-------|-------------------|------------|
| 290T483 | UNI036485 | 270T483 | 7FH2 |
| 316X914 | UNI276487 | 155360 | 6FA |
| 337X581 | UNI026935 | 298464 | 9FA.03 |
| 954X205 | UNI248367 | 890337 | HRSG |
| GG10676 | UNI755683 | 899039 | 9HA.02 |

### FSR PDFs Found (from Databricks)

**290T483** (via 270T483)

| PDF Name | Event Type | S3 UUID |
|---|---|---|
| Field_Service_Report_ProjectID_A-1694598_EV-116650_C-10366425.pdf | Call-Out | `4e588cce-4964-46bd-8c0a-8bed1f6276da` |

**316X914** (via 155360)

| PDF Name | Event Type | S3 UUID |
|---|---|---|
| Field_Service_Report_ProjectID_FSP-261874_C-10329409.pdf | Major Inspection | `5b688732-39f2-48d2-a887-3239f258d28b` |

**337X581** (via 298464, Cairo North)

| PDF Name | Event Type | S3 UUID |
|---|---|---|
| Field_Service_Report_ProjectID_A-1543636_EV-104843_C-10334992.pdf | CI | `27866c5c-78d1-44e1-9d0c-2f025563d3ac` |
| Field_Service_Report_ProjectID_A-1679448_EV-105871_EVP-502315.pdf | HGPI | `bdd56c7a-ebe5-4bf7-904a-5bb63091ba20` |
| Field_Service_Report_ProjectID_A-1417004_FSP-256477_C-10325956.pdf | MI | `fcb1511e-596a-4a56-b151-1e596afa569c` |

**954X205** (via 890337)

| PDF Name | Event Type | S3 UUID |
|---|---|---|
| Field_Service_Report_ProjectID_A-1524486_EV-105389_C-10331342_EVP-500767.pdf | CI | `48b0505d-7d0f-4a8f-ada7-912f3437b818` |
| Field_Service_Report_ProjectID_A-1396770_EV-102868_C-10289156.pdf | HGPI | `ac61f40e-af31-4a5c-a1f4-0eaf31fa5ce2` |
| Field_Service_Report_ProjectID_EV-103029_C-10359516.pdf | Upgrade | `794be8ab-c67c-4808-8be8-abc67c0808a9` |

**GG10676** (via 899039, 370T028)

| PDF Name | Event Type | S3 UUID |
|---|---|---|
| Field_Service_Report_ProjectID_NEX-P-247964_SP-EA0-005222.pdf | Minor Inspection | `b1b0da2c-1dd2-4500-b0da-2c1dd2c50016` |
| Field_Service_Report_ProjectID_A-1863250_EV-161118_EVP-542343.pdf | BI | `633bd587-606a-4426-a7bc-5b0f638fce28` |
| Field_Service_Report_ProjectID_A-1847776_EV-161124_EVP-539688.pdf | CI | `35214721-245b-4b55-bfa6-aa7f3afa498f` |
| Field_Service_Report_ProjectID_C-80050912.pdf | Call Out | `de4cf02b-234e-40c1-87df-08c432d7c02b` |
| Field_Service_Report_ProjectID_C-80050854.pdf | Call Out | `786ed128-c022-488f-95de-c41798ec11ff` |
| Field_Service_Report_ProjectID_C-80050901.pdf | Call Out | `c2201296-06f3-4baf-95f6-4497c19e5cee` |

---

## Deployment Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: Ad-Hoc Fix (Priority Documents)              ~2-3 days    │
│  ┌────────────────────────────────────────────────────┐             │
│  │ 1. Run preprocessor on priority negative-feedback   │             │
│  │    FSRs → get equipment page ranges                │             │
│  │ 2. UPDATE primary_equip_type on existing chunks    │             │
│  │ 3. DELETE inflated duplicate rows                  │             │
│  │ 4. Verify in DS Guru Discovery → correct results   │             │
│  └────────────────────────────────────────────────────┘             │
│                                                                     │
│  PHASE 2: Unify + De-inflate                           ~1 week      │
│  ┌────────────────────────────────────────────────────┐             │
│  │ 1. Unify PDF extraction (PDFplumber everywhere)    │             │
│  │ 2. Remove multi-ESN fan-out (no more inflation)    │             │
│  │ 3. Add equipment_type filter to retrieval query    │             │
│  │ 4. Add IBAT expansion to retrieval query           │             │
│  └────────────────────────────────────────────────────┘             │
│                                                                     │
│  PHASE 3: Full Fleet                                   ~1-2 weeks   │
│  ┌────────────────────────────────────────────────────┐             │
│  │ 1. Run preprocessor on all multi-equipment FSRs    │             │
│  │ 2. Re-chunk if needed (section-aware boundaries)   │             │
│  │ 3. Monitor SME feedback for improvement            │             │
│  └────────────────────────────────────────────────────┘             │
│                                                                     │
│  ROLLBACK: Store original values in backup column before UPDATE     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Fix causes regression on single-equip FSRs | Low | High | Regression test before deploy |
| Preprocessor misidentifies sections (edge cases) | Medium | Medium | Start with priority docs, expand gradually |
| PDF library mismatch (char offsets don't align) | Medium | Medium | Verify before Phase 1; fix in Phase 2 |
| Footer/table GT ESNs confuse labeling | Medium | Low | Don't deploy Fix 3; rely on boundary logic |
| Scanned PDFs not processable | Known | Low | Separate OCR workstream; flag and skip |
| ~20% chunks reference both equipment types | Known | Low | LLM system prompt guidance (don't hard-filter) |
