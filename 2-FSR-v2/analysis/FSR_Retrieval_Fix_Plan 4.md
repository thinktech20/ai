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

**Key point:** The actual production fix uses the validated preprocessor logic. Phased approach: Phase 1 (new chunking + metadata for target docs in QA) → Phase 2 (full fleet + remove inflation) → Phase 3 (ongoing improvements).

**Update (2026-07-17):** Madhurima flagged that old chunking (PyMuPDF) char offsets don't align with preprocessor regions. Phase 1 now includes re-chunking for the target QA documents (limited set, fast). Jonathan approved approach in functional review.

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

**Note: Two different uses of IBAT (don't confuse them):**

```
IBAT for RETRIEVAL (Phase 1 — deploy now):
  User queries ESN "337X581" → IBAT says same train as "298464"
  → search for FSR PDFs containing "298464" → FOUND
  This is Problem 1 (zero-result ESNs). Already validated.

IBAT for MULTI-ESN RESOLUTION (Phase 2 — Fix 2 refinement):
  Inside a document with Gen1=814639, Gen2=337X581
  → Which Gen ESN belongs to this Generator subsection?
  → IBAT lookup: which Gen pairs with this section's GT ESN?
  This is a Fix 2 edge case for docs with multiple Gen ESNs.
```

The 5 new ESNs mapped to FSR PDFs (below) = IBAT for RETRIEVAL = Phase 1.

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

- **Phase 1:** New chunking + metadata for target QA docs (10-15 docs, ~2-3 days). Re-chunking required because old PyMuPDF char offsets don't align with preprocessor regions.
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

## Meeting Outcomes (2026-07-15)

### Meeting: "Finalize FSR multi-equipment approach" (with Vince)

**Key Decisions:**

1. **QA environment first** — Deploy to QA for SME validation before production. Subset of ESNs only.
2. **Automated batch test** — Vince wants a script that runs through 15+ FSRs and produces a metadata assignment test report. Not full risk assessment — just verify chunks got the right `primary_esn` and `primary_equip_type`.
3. **App changes required** — App team (Abhinaya) needs to pass through `primary_equip_type` for filtering. Similar to how dates were added for chronology.
4. **LLM step after preprocessor** — Vince's full pipeline has a SECOND step where an LLM helps determine metadata for the harder cases. Preprocessor alone gets 80%+, LLM step improves further.
5. **Industry benchmark** — LLM-as-judge accuracy across industries is typically 65-75%. Our first attempts were already close to that. Doesn't need to be perfect.
6. **Future work after this** — Retrieval optimization + prompt optimization (FOD, vibration, contamination — the ambiguous cases).

**Key Technical Points:**

- App needs new filter on `primary_equip_type` in retrieval
- New table in QA with updated metadata (keep baseline for comparison)
- Automated test = download chunks → check metadata assignment → produce report
- Vince will run his own tests against our preprocessor improvements

---

### Meeting: "FSR - Approach and Estimation" (internal team)

**Attendees:** Tao, Xujin, Madhurima, Abhinaya, Namruth

**Key Decisions:**

1. **Madhurima's pipeline integration confirmed** — Preprocessor runs inside metadata extraction step (Step 1)
2. **No retrieval filter initially** (Xujin) — Don't hard-filter by equipment type at retrieval. Still retrieve all chunks for the FSR. Pass metadata to LLM as guidance instead.
3. **Timeline: Dev by Jul 16, QA by Jul 18** — Start with 5 ESNs from Abhinaya + 7 from Vince
4. **New table approach** — Keep baseline intact, create new table with updated metadata. Label records with "phase 1 update" for tracking.
5. **Namruth supports deployments** — Follow up with DNA team during IST hours
6. **Section_1-5 metadata** (Xujin) — Already exists in chunks, should be passed to LLM along with new preprocessor metadata

**Key Technical Points:**

- Preprocessor output stored in chunk metadata JSON (not separate table)
- `all_esns` field changes from flat array → dictionary with ESN→equipment_type mapping
- Inactive ESNs excluded from FSR lookup query
- Vector index must sync with updated chunk table
- PDF library mismatch (PyPDF vs PDFplumber) — known issue, Phase 2
- Re-chunking required for Phase 1 target docs (PyMuPDF misalignment with preprocessor — flagged by Madhurima 7/17)
- Abhinaya needs contract for app changes (equipment type filter + new table pointer) by EOD Jul 15
- Two retrieval options to test: with equipment type filter vs without (let SMEs compare)

---

## Functional Review with Jonathan (2026-07-17) — APPROVED

Jonathan reviewed our tagging logic presentation and approved the approach:
- "Makes sense to me. Best economics of doing this rather than running full chunks through an LLM."
- "I can't think of anything you would want to enhance."
- Acknowledged edge cases (DC leakage tucked in GT report without TOC entry) — "These things happen."
- Wants future "review pipeline" to check FSRs before submission.
- Re-chunking: "I'll leave it up to you all."

**Raylan Dawkins** (new team member, did similar work previously):
- Recommends threshold-based LLM fallback: if deterministic tool captures < X% of expected info → trigger LLM
- "Deterministic logic is better for building a foundation, then LLM captures the rest."
- Validates our Phase 1 (deterministic) → Phase 2 (LLM) progression.

**Madhurima's re-chunking flag (same day):**
- Old PyMuPDF chunking char offsets don't align with preprocessor regions
- Chunk-to-region attribution unreliable at equipment boundaries
- Phase 1 now includes re-chunking for target QA documents (limited set)
- Production full fleet re-chunk = Phase 2 (takes days)

---

## Jon's ESN Tagging Logic — Alignment Confirmed (2026-07-16)

Business owner Jon presented his approach to find missing ESNs. His method:
1. Use IBAT train to find sibling ESNs for each document
2. Scan document text for Generator keywords (32 terms)
3. If keywords found → "Gap Confirmed" → document is missing a Generator tag

**Alignment with our approach:**

| Aspect | Jon's Method | Our Preprocessor |
|--------|-------------|-----------------|
| IBAT train lookup | ✓ Same | ✓ Same |
| Keyword detection | 32 Generator keywords | 24 → now 37 (added Jon's) |
| Section boundaries | ✗ (doc-level only) | ✓ (per-chunk regions) |
| Output | "Gap confirmed" list | Per-chunk correct labels |

Jon's approach = **detection** (which docs have the problem).
Our approach = **fix** (correct the labels on those docs).
Fully aligned — same signals, same ESNs, we go one step further.

**Keywords added from Jon's list** (to `GEN_SIGNATURES` in `preprocessor_v2_final.py`):
`magic inspection`, `belly band`, `oil deflector`, `collector ring`, `fan blade`, `sub-slot`, `inner gas shield`, `high voltage bushing`, `end shield`, `pole jumper`, `ac impedance`, `dlro`, `step iron`

### Preprocessor vs IBAT: When is IBAT still needed?

Ideally, the preprocessor finds the right ESNs directly from the PDF — no IBAT "fishing net" needed. IBAT becomes a safety net for edge cases only.

```
┌─────────────────────────────────────────────────────────────────────┐
│  PREPROCESSOR IS ENOUGH (no IBAT needed):                            │
│                                                                     │
│  FSR title page says:                                               │
│    "Gas Turbine ESN: 298250"                                        │
│    "Generator ESN: 338X447"                                         │
│                                                                     │
│  Preprocessor finds BOTH → assigns per-chunk → user queries         │
│  338X447 → chunk has esn=338X447 → FOUND. Done.                     │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  IBAT STILL NEEDED (edge cases):                                     │
│                                                                     │
│  Case 1: ESN not mentioned anywhere in the PDF                      │
│    Title says only "GT ESN: 298250"                                 │
│    Generator ESN 338X447 appears NOWHERE in text                    │
│    → IBAT: 338X447 → same train as 298250 → search                 │
│                                                                     │
│  Case 2: ESN format unrecognizable                                  │
│    Appears as "Unit S/N: 3384-47" (non-standard)                    │
│    Preprocessor regex doesn't match                                 │
│    → IBAT as fallback                                               │
│                                                                     │
│  Case 3: Scanned PDFs (no extractable text)                         │
│    Preprocessor gets nothing                                        │
│    → IBAT is the ONLY way to associate ESNs                         │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  PROGRESSION:                                                       │
│                                                                     │
│  Today:         preprocessor finds ~80% of ESNs, IBAT for ~20%     │
│  After Phase 1: preprocessor finds ~90%, IBAT for ~10%              │
│  After Phase 2 (LLM step): preprocessor finds ~95%+                │
│                 IBAT only for scanned PDFs / truly absent ESNs      │
│                                                                     │
│  GOAL: Preprocessor replaces IBAT for ESN detection.                │
│  IBAT stays as safety net, not primary mechanism.                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Rollout Plan (from Madhurima's `rollout-fsr-v2.md`)

### Steps

| Step | What | Owner | Status |
|------|------|-------|--------|
| 1a | Metadata extraction: include preprocessor | Madhurima/Tao | ◻ In dev |
| 1b | Chunking: add enriched ESN details to metadata JSON | Madhurima | ◻ In dev |
| 1c | UPDATE job for existing rows (not re-ingest) | Madhurima | ◻ After 1a/1b |
| 2 | App changes: point to new tables, metadata filter | Abhinaya | ◻ Needs contract |
| 3 | Validation plan: compare new vs old | Xujin/team | ◻ Dashboard ready |
| 4a | Populate new tables: `fsr_metadata_v2`, `fsr_chunk_v2`, `fsr_vs_index_v2` | Madhurima | ◻ |
| 4b | Validate against 7 confirmed + known production issues | Team | ◻ |
| 4e | Run UPDATE job for all 458 multi-equipment FSRs | Madhurima | ◻ After validation |
| 4f | Regression test for updated 458 FSRs | Team | ◻ |
| 5 | SME Validation in QA | SMEs | ◻ After steps 1-4 |
| 6 | Decide next iteration | Team | ◻ |

### New Tables (separate from existing to avoid breaking production)

- `fsr_metadata_v2` — metadata with preprocessor output (regions, ESN→equipment mapping)
- `fsr_chunk_v2` — chunks with per-chunk `primary_equip_type` in metadata JSON
- `fsr_vs_index_v2` — vector search index with metadata filter support

### Golden Test Dataset

- 7 from Vince (confirmed failures)
- 5 from Abhinaya (SME support ESNs → mapped to ~14 FSR PDFs)
- 5 from Tao (uploaded to shared drive)
- Joe Worden's list (upcoming units with known issues)
- Total first batch: ~30-40 FSRs
- Full rollout: 458 multi-equipment FSRs (from IBAT analysis)

### Timeline vs Jonathan's Expectation

Jonathan expects Friday 7/18 for QA review. Reality check:

**Achievable by Friday 7/18 (show approach + early results):**
- ✓ Approach documented (this plan + rollout-fsr-v2.md)
- ✓ Preprocessor validated end-to-end in DS Guru (done Jul 14)
- ✓ Dashboard showing current state ("Gen HIDDEN" on all 5 docs)
- ◻ New tables created in dev (Madhurima targeting Jul 16 EOD)

**NOT achievable by Friday:**
- App changes (Abhinaya needs contract → implement → test)
- Full QA with SME validation
- 458-document UPDATE job

**Realistic timeline:**
- Jul 16-17: Dev tables ready + preprocessor integrated
- Jul 18: Show approach + dev results to Jonathan (not full QA)
- Jul 21-22: App changes + QA promotion
- Jul 23-25: SME validation in QA
- After SME sign-off: Production rollout

### Gaps to Resolve

| Gap | Action Needed |
|-----|---------------|
| Vector index API contract change | Madhurima to research metadata filter format; coordinate with DNA team (Vinayaka) |
| App system prompt changes | Xujin drafting prompt to include section_1-5 + equipment type |
| "458 multi-equipment FSRs" list | Where does this come from? Need definitive list for UPDATE job |
| Validation metric | Use `chunk_dashboard.py` — "can user find Generator? yes/no" (not percentages) |
| Preprocessor file reference | Use `ds-guru/preprocessors/preprocessor_v2_final.py` |

---

## Task Assignments — Updated 2026-07-16

| Task | Owner | Due | Status |
|------|-------|-----|--------|
| Fix 1+2: Preprocessor validated | Tao | Jul 14 | ✓ Done |
| Add Jon's keywords to GEN_SIGNATURES | Tao | Jul 16 | ✓ Done |
| Create new tables in dev (metadata_v2, chunk_v2, index_v2) | Madhurima | Jul 16 EOD | ◻ In progress |
| Research vector index API metadata filter format | Madhurima | Jul 16 EOD | ◻ In progress |
| Provide app contract to Abhinaya (new filter + table) | Madhurima/Xujin | Jul 17 | ◻ Urgent |
| App changes: metadata filter + new table pointer | Abhinaya | Jul 18-21 | ◻ After contract |
| System prompt draft (section_1-5 + equip type) | Xujin | Jul 17 | ◻ Pending |
| Friday 7/18 review with Jonathan: show approach + dev results | Tao/team | Jul 18 7:30AM ET | ◻ Prep needed |
| Populate new tables with first batch (~30-40 FSRs) | Madhurima | Jul 17-18 | ◻ After tables ready |
| Validate with chunk_dashboard.py | Tao | After population | ◻ Tool ready |
| Coordinate with DNA team (Vinayaka) on index config | Madhurima/Namruth | Jul 17 | ◻ If needed |
| QA promotion | Madhurima/Namruth | Jul 21-22 | ◻ After dev validation |
| SME validation in QA | SMEs | Jul 23-25 | ◻ After QA ready |
| Fix 2 refinements (stack-based boundary, IBAT multi-ESN) | Tao/Xujin | Phase 2 | ◻ After Phase 1 |
| Fix 3: Content-signal flip | — | ON HOLD | ✗ Too risky |

| Task | Owner | Due | Status |
|------|-------|-----|--------|
| Fix 1: Content-weighted primary + fallback | Tao | Jul 14 | ✓ Validated in DS Guru |
| Fix 2: Boundary detection (initial) | Tao | Jul 14 | ✓ Validated in DS Guru |
| Fix 2 refinement: Stack-based boundary reset | Tao/Xujin | Jul 16 | ◻ Implement + test |
| Fix 2 refinement: ESN via IBAT enrichment | Tao | Jul 16 | ◻ Implement |
| Integrate preprocessor into production pipeline (dev) | Madhurima | Jul 16 | ◻ In progress |
| Provide app contract to Abhinaya (equipment type filter) | Madhurima/Xujin | Jul 15 EOD | ◻ Today |
| App changes: equipment type filter + new table | Abhinaya | Jul 17 | ◻ After contract |
| Run on 5+7 ESNs in dev | Madhurima | Jul 17 | ◻ After integration |
| Promote to QA environment | Madhurima/Namruth | Jul 18 | ◻ After dev validation |
| Automated batch test script (metadata check) | Tao | Jul 17 | ◻ Align with Vince's approach |
| Namruth: deployment support + DNA team follow-up | Namruth | Ongoing | ◻ IST hours |
| Get more problem ESNs from Namruth (production issues) | Madhurima | Jul 16 | ◻ Pending |
| Unify PDF library (PyPDF vs PDFplumber) | Madhurima | Phase 2 | ◻ After Phase 1 |
| Fix 3: Content-signal flip | — | ON HOLD | ✗ Too risky (footer issue) |

---

## New ESNs to Map (from Abhinaya's SME Support request 2026-07-14)

5 additional ESNs with negative feedback. Investigated via IBAT + PDF text scan:

| ESN | Train | Sibling ESN | In PDF text? | Gen content? | Action |
|-----|-------|-------------|---|---|---|
| 290T483 | UNI036485 | 270T483 | **YES** (2 of 12 PDFs) | YES | Preprocessor can fix ✓ |
| 316X914 | UNI276487 | 155360 | **YES** (1 PDF, 27 chunks) | YES | Preprocessor can fix ✓ |
| 337X581 | UNI026935 | 298464 | **YES** (7 of 9 PDFs) | YES | Preprocessor can fix ✓ |
| 954X205 | UNI248367 | 890337 | **NO** (0 of 3 GT PDFs) | **NO** (in GT PDFs) | Gen FSR exists under 954X204 (`39_v1.0(17)`) |
| GG10676 | UNI755683 | 899039 | **NO** (0 of 6 PDFs) | **NO** (0 Gen sigs) | Cannot fix — no Gen content |

### Verified Finding (2026-07-16, updated 2026-07-21): IBAT Association for 954X205 and GG10676

Downloaded all PDFs from Databricks and scanned full text:

**954X205:** The 3 sibling PDFs retrieved via GT ESN `890337` (CI, HGPI, Upgrade) are pure GT reports — zero Generator content. However, the IBAT association IS VALID: document `39_v1.0(17)` (Generator Field Modification, New Assiut Power Plant) explicitly confirms "Serial Numbers: 954X204, 954X205 & 954X206 associated with...Gas Turbine with serial number 890334, 890337 & 890338 respectively." The Generator FSR exists but is filed under sibling ESN `954X204`, not retrievable via the GT ESN path.

**GG10676:** All 6 sibling PDFs (MI, BI, CI, Call Outs) are pure GT reports for `899039`. Zero Generator signatures. ESN `GG10676` never mentioned anywhere.

```
┌─────────────────────────────────────────────────────────────────┐
│  IMPORTANT LESSON: IBAT "fishing net" returns CORRECT ESN       │
│  associations but the RETRIEVAL PATH may be wrong.              │
│                                                                 │
│  954X205: IBAT association is VALID (Generator for GT 890337).  │
│  But retrieval via GT sibling PDFs returns GT-only content.     │
│  The actual Gen FSR is filed under 954X204 (multi-unit report). │
│                                                                 │
│  GG10676: No Gen FSR found anywhere in the system.              │
│                                                                 │
│  KEY INSIGHT:                                                   │
│  IBAT tells you the association EXISTS, but the Gen FSR may be: │
│  a) Filed under a sibling Gen ESN (multi-unit report)           │
│  b) Not yet ingested                                            │
│  c) Never written                                               │
│                                                                 │
│  DO NOT blindly associate GT PDFs with Gen ESNs without         │
│  content verification — but DO search for Gen-filed reports.    │
└─────────────────────────────────────────────────────────────────┘
```

### Correct PDFs for the 3 ESNs That DO Have Content

**290T483** (Generator — verified in PDF text)

| PDF Name | Doc ID | Contains 290T483? |
|---|---|---|
| MAGIC_with_Partial_Re-Wedged_Wedge_Shimming_and_Electrical_Testing...270T483_2018-03-01 | `35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report` | YES (4 chunks) |
| g_GE_Energy_Services_STEAM_TURBINE...Major_Inspection...270T483_2009-10-05 | `37211_270t483-97we0631-carlosrivero-10052009` | YES (1 chunk) |

**316X914** (Generator — verified, 27 chunks mention it)

| PDF Name | Doc ID |
|---|---|
| Field_Service_Report_ProjectID_FSP-261874_C-10329409.pdf | `5b688732-39f2-48d2-a887-3239f258d28b` |

**337X581** (Generator — verified, found in 7 of 9 PDFs)

| PDF Name | Doc ID |
|---|---|
| Field_Service_Report_ProjectID_A-1417004_FSP-256477_C-10325956.pdf | `fcb1511e-596a-4a56-b151-1e596afa569c` |
| Field_Service_Report_ProjectID_A-1679448_EV-105871_EVP-502315.pdf | `bdd56c7a-ebe5-4bf7-904a-5bb63091ba20` |
| + 5 more older reports (Cairo North MI, CI, Upgrade) | See verify script output |

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

## Edge Case: Multi-GT ESN Boundary Assignment (2026-07-16)

**Confirmed common pattern — NOT a rare edge case.**

### The Problem

Many FSR documents contain 2 Gas Turbine sections (GT1 + GT2), each with their own nested Generator subsection. Vince's preprocessor assigns ALL Generator boundaries to the same "primary" Generator ESN, regardless of which GT section they're under.

```
DOCUMENT STRUCTURE (common for multi-unit plants):
  1 Summary
  2 Technical
  3 Turbine __________ (GT1: 296405)
    3.1.1 Generator    ← should map to Gen paired with 296405
  4 Controls System
  5 Turbine __________ (GT2: 296406)
    5.1.1 Generator    ← should map to Gen paired with 296406

CURRENT BEHAVIOR (wrong):
  Both Generator sections → mapped to SAME primary Gen ESN
  (first alphabetically sorted Generator ESN)

CORRECT BEHAVIOR:
  Section under GT1 → Gen ESN paired with GT1 (via IBAT train)
  Section under GT2 → Gen ESN paired with GT2 (via IBAT train)
```

### Example Documents

| PDF | Pattern |
|-----|---------|
| `Field_Service_Report_ProjectID_EV-109513_C-10363469.pdf` | Two GT ESNs with "3 Turbine" |
| `Field_Service_Report_ProjectID_EV-110424_C-10349817.pdf` | Same pattern |

### How Common Is This?

**Very common.** Query of chunk table for chunks containing more than one "3 Turbine __________" in table of contents shows many results. Standard FSR structure for multi-unit plants is:

```
1 Summary
2 Technical
3 Turbine (Unit 1)
4 Controls System
...repeat for Unit 2...
```

Any plant with 2+ gas turbines in one FSR will have this pattern.

### Decision

- **Phase 1:** Document but don't fix. Current logic assigns to primary ESN (imperfect but functional — content still discoverable, just under one Gen ESN instead of being split).
- **Phase 2:** Use section proximity + IBAT train pairing to resolve correct ESN per boundary.

### Why It's Deferred

The fix requires IBAT lookup DURING preprocessing (not just for retrieval). This adds a dependency on external data during the tagging step. For Phase 1, the single-primary-ESN approach still makes Generator content discoverable — just associated with one Gen ESN instead of being split between two. User can still find it.

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

---

## Deep Dive: ESN 954X205 — Multi-Unit Generator Report (2026-07-21)

### Background

ESN `954X205` is a Generator (9A5 class) at New Assiut Power Plant, Egypt (Unit 22), associated with Gas Turbine `890337` via IBAT train `UNI248367`.

### Discovery Path

1. **IBAT retrieval via GT 890337** → returns 3 PDFs (CI, HGPI, Upgrade) — all pure GT content, zero Generator data
2. **Direct search `esn = '954X205'`** → no row exists in `biz_metadata_field_service_report`
3. **`all_esns` search** → no row (extraction missed it)
4. **`document_summary` full-text search** → found in document `39_v1.0(17)` (filed under sibling ESN `954X204`)

### The Document

| Field | Value |
|-------|-------|
| document_id | `39_v1.0(17)` |
| pdf_name | `GENERATOR_INSPECTION_REPORT_Generator_Field_Modification_for_MINISTRY_OF_DEFENSE_New_Assiut_Power_Plant_Unit_21__22_23_Generator_954X204_2015-06-04` |
| volume_path | `/Volumes/viup/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports/39_V1.0(17).pdf` |
| esn (metadata) | `954X204` |
| equipment_type | Generator |
| pages | 46 |
| all_esns (metadata) | `["954X204"]` ← incomplete, should include 954X205, 954X206 |

### Document Content (verified via pdfplumber scan)

The document is a **multi-unit Generator field modification report** covering 3 generators:

| Generator ESN | Gas Turbine ESN | Unit |
|--------------|----------------|------|
| 954X204 | 890334 | Unit 21 |
| **954X205** | **890337** | **Unit 22** |
| 954X206 | 890338 | Unit 23 |

**954X205 appears on 4 pages:**
| Page | Content |
|------|---------|
| 6 | Job summary: "Serial Numbers: 954X204, 954X205 & 954X206 associated with...890334, 890337 & 890338 respectively" |
| 25 | **Unit-specific data**: "Generator Serial No. 954X205, Turbine Serial No. 890337" — Field Clearance (Drive End) |
| 26 | **Unit-specific data**: "Generator Serial No. 954X205, Turbine Serial No. 890337" — Field Clearance (Collector End) |
| 30 | Job summary referencing all 3 units |

### Preprocessor Results (DS Guru local)

| Field | Result |
|-------|--------|
| primary_esn | 954X204 (first ESN detected) |
| primary_equip_type | Generator |
| gt_esn | 890334 (first GT detected) |
| gen_esn | 954X204 |
| Regions | 4 — all tagged `esn=954X204, equip=Generator` |

**Problem:** Preprocessor only captures the first Generator ESN. Does not create separate regions for Unit 22 (954X205) or Unit 23 (954X206).

### Chunking Results (DS Guru section strategy, 127 chunks)

| Chunk | Contains 954X205 | Metadata ESN | Content |
|-------|-----------------|--------------|---------|
| 20 | ✅ | (none) | Job summary listing all 3 generators |
| 75 | ✅ | (none) | **Generator Field Clearance (Drive End) — "Generator Serial No. 954X205"** |
| 83 | ✅ | (none) | **Generator Field Clearance (Collector End) — "Generator Serial No. 954X205"** |
| 113 | ✅ | (none) | Job summary referencing all 3 units |

**Key issue:** Chunks 75 and 83 have unit-specific inspection data for 954X205, but metadata tags show `esn=(none)` — not filterable by ESN.

### Retrieval Analysis

| Method | Finds 954X205 content? | Why |
|--------|----------------------|-----|
| `WHERE primary_esn = '954X205'` | ❌ No | No chunk has this ESN in metadata |
| `WHERE primary_esn = '954X204'` | ❌ Partial | Gets the document but no unit-specific targeting |
| IBAT via GT 890337 | ❌ No | Returns different PDFs (GT-only reports) |
| Vector search "954X205 generator clearance" | ✅ Yes | Text contains the ESN literally |
| `document_summary LIKE '%954X205%'` | ✅ Yes | Full-text match in summary field |

### Root Cause

This is a **multi-unit same-type** document — three generators covered in one report. The current preprocessor is designed for **multi-equipment-type** documents (GT vs Generator sections), not for distinguishing between multiple units of the same type.

### Recommended Fix (from simplest to most complete)

**Option B (recommended): `all_esns` metadata field**
- Preprocessor scans document for all ESN patterns (regex already exists)
- Populates `all_esns: ["954X204", "954X205", "954X206"]` in doc-level and chunk metadata
- Retrieval filter becomes: `WHERE all_esns CONTAINS '954X205'`
- Effort: small — extend existing regex to return all matches, not first
- Also fixes the `biz_metadata_field_service_report.all_esns` column which currently only has `["954X204"]`

**Option A: Per-unit region detection (harder)**
- Preprocessor detects "Generator Serial No. XXXXXX" as region boundaries
- Creates separate regions per unit with unit-specific ESN
- Challenge: multi-unit-same-type boundary detection is less structured than equipment-type boundaries
- Effort: medium — new boundary detection logic

**Option C: Hybrid retrieval (no code change)**
- Vector search already finds the content via text similarity
- Accept that metadata filtering won't cover this case
- Risk: relies on embedding quality and query phrasing

### Impact Assessment

| Scope | Estimate |
|-------|----------|
| How many multi-unit-same-type reports exist? | Unknown — need query on `biz_metadata` for documents with multiple ESNs in summary |
| Is this a common FSR pattern? | Yes for large plants (New Assiut has 3 identical units, Jamnagar has similar) |
| Priority | Medium — vector search provides a workaround, but metadata filtering is the primary retrieval path |
