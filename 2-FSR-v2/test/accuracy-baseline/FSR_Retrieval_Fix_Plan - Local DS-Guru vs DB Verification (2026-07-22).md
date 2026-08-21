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

---

## Deep Dive: ESN 290T483 — Unlabeled ESN in Document Text (2026-07-22)

### Background

ESN `290T483` is a Generator at Dynegy Corp. Moss Landing Power Plant, associated with sibling Generator ESN `270T483` via IBAT train `UNI036485`.

### Document

| Field | Value |
|-------|-------|
| document_id | `35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report` |
| pdf_name | `MAGIC_270T483_2018.pdf` |
| primary_esn | `270T483` |
| primary_equip_type | Generator |
| gen_esn | `270T483` |
| pages | 85 |

### Equipment Map Status

| ESN | In `fsr_document_equipment_map_v2`? | Retrievable? |
|-----|-------------------------------------|-------------|
| 270T483 | ✅ Yes (Generator, primary, 84 regions) | ✅ |
| 290T483 | ❌ No | ❌ |

### Local Preprocessor Results

| Field | DB Value | Local DS Guru | Match? |
|-------|----------|---------------|--------|
| primary_esn | 270T483 | 270T483 | ✅ |
| primary_equip_type | Generator | Generator | ✅ |
| Regions | 84 | 2 | ❌ (different preprocessor versions) |
| 290T483 detected | No | No | ✅ Same gap |

### Why Preprocessor Cannot Detect 290T483

`290T483` appears on **11 pages** but **never with a recognized label pattern**:

| Page | Context | Pattern match? |
|------|---------|---------------|
| 3 | `"performed on unit 290T483 at Dynegy Corp. Moss Landing"` | ❌ No label prefix |
| 31 | `MLPP_290T483_FIELD TESTING_COMPLETED.PDF` | ❌ Embedded in filename |
| 33 | `290T483 PHOTO LAYOUT.PDF` | ❌ Filename reference |
| 51 | `290T483 PHOTO ID.PDF` | ❌ Filename reference |
| 73 | `MLPP_290T483_STATOR ARMATURE WINDING RESISTANCE_COMPLETED.PDF` | ❌ Filename |
| 74-79 | `MLPP_290T483_STATOR DC LEAKAGE_...PDF` (6 pages) | ❌ Filename references |

The preprocessor requires ESNs adjacent to structured labels:
- `Equipment Serial #: 270T483` → detected ✅ (via GENERIC_LABELS)
- `"performed on unit 290T483"` → NOT detected ❌ (no matching regex)
- `MLPP_290T483_STATOR...` → NOT detected ❌ (embedded in filename)

### Comparison: 290T483 vs 954X205

| Aspect | 954X205 | 290T483 |
|--------|---------|---------|
| Appears in text | ✅ (4 pages) | ✅ (11 pages) |
| Has structured label | ✅ "Generator Serial No. 954X205" | ❌ No label — only prose/filenames |
| Why preprocessor misses it | Only captures first ESN (954X204) | No regex pattern matches the context |
| Fix via label-based regex | ✅ Possible (capture all matches) | ❌ Not possible (no label to match) |
| Fix via full-text ESN scan | ✅ Would work | ✅ Would work |
| Fix via IBAT sibling lookup | N/A | ✅ 270T483 → train → 290T483 |

### Root Cause Classification

This is a **different class of problem** from 954X205:
- **954X205**: ESN appears with a label but preprocessor only captures the first match
- **290T483**: ESN appears in natural prose and filenames — no label-based regex can detect it

### Recommended Fix

**Option 1: IBAT sibling expansion at map-build time (recommended for this case)**
- Preprocessor detects `270T483` → pipeline looks up IBAT train `UNI036485` → finds `290T483` as sibling
- Auto-adds `290T483` to `fsr_document_equipment_map_v2` with `is_primary_esn=False`
- Effort: requires IBAT API call during ingestion; already available in the system

**Option 2: Broad ESN scan (full-text regex without label requirement)**
- Scan for all `\d{3}[A-Z]\d{3}` patterns appearing 3+ times → candidate ESNs
- Risk: may pick up false positives (form numbers, part numbers that match the pattern)
- Would also solve 954X205 case

**Option 3: `all_esns` from chunk text (post-chunking scan)**
- After chunking, scan each chunk's text for ESN patterns
- Populate `all_esns` field per chunk regardless of preprocessor output
- Most reliable for text-present ESNs but doesn't help if ESN never appears in text

---

## Deep Dive: ESNs 316X914 and 337X581 — Local Verification (2026-07-22)

### Documents Tested

| File | Document ID | GT ESN | Target Gen ESN |
|------|------------|--------|----------------|
| `5b688732-316X914.pdf` | `5b688732-39f2-48d2-a887-3239f258d28b` | 155360 | 316X914 |
| `fcb1511e-337X581.pdf` | `fcb1511e-596a-4a56-b151-1e596afa569c` | 298464 | 337X581 |
| `bdd56c7a-298464.pdf` | `bdd56c7a-ebe5-4bf7-904a-5bb63091ba20` | 298464 | 337X581 |

### Results

#### 5b688732 (316X914) — ⚠️ Generator ESN detectable, but Steam Turbine boundary MISSED

| Field | DB Value | Local DS Guru | Ground Truth | Match? |
|-------|----------|---------------|--------------|--------|
| primary_esn | 155360 (GT) | 316X914 (Gen) | Both: 155360=ST, 316X914=Gen | ❌ See below |
| gen_esn | 316X914 | 316X914 | 316X914 | ✅ |
| equip type for 155360 | Gas Turbine | Gas Turbine | **Steam Turbine** | ❌ Misclassified |
| In equipment map | ✅ (Generator, 1 region) | 5 regions, ALL Generator | ST(p46-241) + Gen(p242+) | ❌ |
| 316X914 in regions | ✅ | ✅ | ✅ | ✅ |

**Generator ESN `316X914`** is fully detectable (appears on 124 pages with labels). No gap for Generator retrieval.

**However, per ground truth (Excel):**
- Pages 46–241 are **Steam Turbine (155360)** content
- Pages 242+ are **Generator (316X914)** content
- DS Guru tags ALL 5 regions as Generator (316X914) — Steam Turbine section completely lost

##### Root Cause: Steam Turbine detection blind spot

1. **ESN type misclassification**: `155360` has no letter → classified as "Gas Turbine" by heuristic (`re.search(r'[A-Z]', esn)`), but it's actually Steam Turbine. Page 1 clearly says `Steam Turbine ESN: 155360` but the label prefix is ignored.

2. **No section boundaries detected**:
   - HEADER pattern (`STEAM TURBINE (155360 | SY...)`) — **0 matches** (doc doesn't use this format)
   - SECTION_HDR pattern (`\d+ STEAM TURBINE`) — **0 matches** (doc uses generic numbered sections like "2 Technical", "4 Controls System")
   - SUBSEC_GT matches only TOC entries (`3.3.1 Turbine Casing`) — doesn't create useful boundaries

3. **No Steam Turbine signatures**: The preprocessor only has `GEN_SIGNATURES` and `GT_SIGNATURES`. Steam Turbine-specific terms (steam path, wheel clearance, diaphragm, packing ring, gland seal, etc.) are not recognized. With 45 pages having 2+ ST signatures, all get misassigned to Generator via the doc-level primary fallback.

4. **Page-by-page fallback**: Since no distinct equipment-type boundaries exist, the preprocessor uses page-level signatures. Since no GT_SIGNATURES fire (this is ST content, not GT) and no ST_SIGNATURES list exists, pages default to the doc-level primary → all Generator.

##### Fixes needed for Steam Turbine documents

| Fix | Description |
|-----|-------------|
| **Add ST_LABELS pattern** | `r'Steam\s*Turbine\s*(?:ESN\|Serial...)...\s*(\d{3}[A-Z]?\d{3})'` — captures ESN from "Steam Turbine ESN: 155360" |
| **Add ST_SIGNATURES list** | steam path, wheel clearance, diaphragm, packing ring, gland seal, hp/lp turbine, extraction valve, blade erosion |
| **Fix ESN→type heuristic** | Don't rely solely on letter presence. If label says "Steam Turbine ESN", classify as Steam Turbine regardless of format |
| **Add `st_esn` variable** | Preprocessor only tracks `gt_esn` and `gen_esn` — needs a third slot for Steam Turbine |

**Verdict:** Generator ESN (316X914) retrieval works. But Steam Turbine content (155360, pages 46–241) is entirely misclassified as Generator. This affects any query targeting Steam Turbine findings in this document.

#### fcb1511e (337X581) — ✅ Working correctly

| Field | DB Value | Local DS Guru | Match? |
|-------|----------|---------------|--------|
| primary_esn | 298464 | 337X581 (Gen) | ❌ Different primary |
| primary_equip_type | shared | Generator | Different |
| gen_esn | 337X581 | 337X581 | ✅ |
| In equipment map | ✅ (Generator, 10 regions) | 1 Gen + 1 GT region | Region count differs |
| 337X581 in regions | ✅ | ✅ | ✅ |

ESN `337X581` appears on **394 pages** with label:
- Page 1: `Generator ESN: 337X581`
- Pages 2+: Footer `GEGEGE MI - 298464, 337X581`

**Verdict:** Fully detectable. No gap.

#### bdd56c7a (337X581) — ❌ Regex gap found

| Field | DB Value | Local DS Guru | Match? |
|-------|----------|---------------|--------|
| primary_esn | 298464 | 298464 | ✅ |
| primary_equip_type | Gas Turbine | Gas Turbine | ✅ |
| gen_esn | NaN | (empty) | ✅ Same gap |
| In equipment map | GT only (298464, 136 regions) | GT only (298464, 10 regions) | ✅ Same gap |
| 337X581 in regions | ❌ | ❌ | ✅ |

ESN `337X581` appears on **only 1 page** (page 1):
```
Generator Field Serial Number: 337X581
```

**Root cause:** The current GEN_LABELS regex requires "Generator" immediately followed by "Serial":
```
Gen(?:erator)?\s*(?:ESN|Serial\s*(?:No|#|Number))
```

But the document uses **"Generator Field Serial Number"** — the word "Field" between "Generator" and "Serial" breaks the match.

**Fix:** Add optional `Field\s*` to the regex:
```python
# Current (broken for this case):
r'Gen(?:erator)?\s*(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]\d{3})'

# Fixed:
r'Gen(?:erator)?\s*(?:Field\s*)?(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]\d{3})'
```

This single regex change makes `337X581` detectable in bdd56c7a.

### Summary: All ESN Detection Gaps by Root Cause

| Root Cause | ESNs Affected | Fix (Next Phrase?) |
|-----------|---------------|-----|
| **Regex gap**: "Generator Field Serial Number" not matched | 337X581 (in bdd56c7a) | Add `(?:Field\s*)?` to GEN_LABELS regex |
| **First-match-only**: preprocessor captures first ESN, ignores siblings | 954X205 (in 39_v1.0(17)) | Capture all regex matches, not just first |
| **No label in text**: ESN appears only in prose/filenames | 290T483 (in 270T483 doc) | IBAT sibling expansion or broad text scan |
| **No FSR exists**: ESN not in any document | GG10676 | Cannot fix — no content to find |
| **Steam Turbine blind spot**: no ST ESN label, no ST signatures, no ST type slot | 155360 (in 5b688732) — pages 46-241 misclassified as Generator | Add ST_LABELS, ST_SIGNATURES, `st_esn` variable; fix ESN→type heuristic |
<!-- | **Generator ESN absent from doc text**: preprocessor correctly has no ESN | GT12 (875127), HGPI (899053) | Pipeline fallback should use null, not doc-level ESN | -->


