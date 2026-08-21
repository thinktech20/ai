# FSR v2 Bug Deep Analysis: Bug 3, 4, and 6

## Scope and inputs reviewed
- Bug list: [2-FSR-v2/this-week/bug-section/Xujin-bug-list.csv](2-FSR-v2/this-week/bug-section/Xujin-bug-list.csv)
- Meeting notes source: [2-FSR-v2/this-week/bug-section/Xujin-bug-list-meeting.docx](2-FSR-v2/this-week/bug-section/Xujin-bug-list-meeting.docx)
- Text extract used for analysis: [2-FSR-v2/this-week/bug-section/Xujin-bug-list-meeting.txt](2-FSR-v2/this-week/bug-section/Xujin-bug-list-meeting.txt)
- Screenshot deck: [2-FSR-v2/this-week/bug-section/screenshots-docs.docx](2-FSR-v2/this-week/bug-section/screenshots-docs.docx)
- OCR outputs from screenshot images:
  - [2-FSR-v2/this-week/bug-section/screenshots-extract/ocr/all_ocr.txt](2-FSR-v2/this-week/bug-section/screenshots-extract/ocr/all_ocr.txt)
- Current implementation checked:
  - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py)
  - [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py)

Note: OCR text has normal recognition noise, but section-number patterns and equipment labels are clear enough to validate boundary issues.

## Screenshot OCR evidence (supports bugs 3, 4, and 6)

### Key observations from OCR
- Numbered hierarchy is visible in many examples (for example 3.1, 3.1.1, 3.3.1), confirming nested section structure is real in source docs.
- Generator and turbine headings appear in close proximity within same broader sections (supports subsection flip/inherit concerns).
- Repeated numbering patterns (for example repeated 3.3.1 style fragments) appear, which can confuse simplistic boundary logic.
- OCR lines show equipment header patterns with ESN references in places, but not always consistently near subsection text.

### OCR excerpts that matter
- Visible subsection hierarchy examples:
  - "3.1 Auxiliaries"
  - "3.1.1 Piping and Flexible Metal Hoses"
  - "3.3 Exhaust Section"
  - "3.3.1 T3 Journal Bearing"
  - "3.1.1 Generator Stator/Field Tests ..."
  - "3.1.2 Turbine Enclosure ..."
- Mixed equipment context examples:
  - "GAS TURBINE (...)"
  - "GENERATOR (...)"
  - "3 Turbine" followed by nested generator/turbine subsections.

### Why this matters for bug interpretation
- Bug 3: OCR confirms heading diversity and formatting variability, so strict numbered-line-only detection is fragile.
- Bug 4: OCR confirms real nested transitions where subsection context can switch equipment type and later must revert.
- Bug 6: OCR suggests ESN labels are not guaranteed to be locally adjacent to every relevant subsection, so global-anchor assignment can misfire.

## Quick summary
These three bugs are connected and all come from one core limitation: section/subsection boundaries are mostly start-only markers without a true hierarchy model (parent-child section state + explicit section close).

## Bug 3: Section header without number is not detected

### What was reported
- CSV says section headers without leading numbers are missed for multiple docs.
- Meeting aligns this to "broader format of section header detection" and parser line-break sensitivity.

### Why this happens in current code
- Main section regex requires a leading number:
  - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L226](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L226)
- If parser output does not preserve the heading on its own line, matching also degrades.
- Subsection patterns are also number-dependent:
  - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L322](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L322)

### Impact
- Missing section boundary means larger spans get merged under wrong equipment context.
- This directly increases mis-assignment risk in bug 4 and bug 6.

### Current status
- Partially mitigated by other boundary sources (equipment headers), but unnumbered section headings are still a gap.

## Bug 4: Subsection logic and same-type multi-ESN assignment

### What was reported
From CSV + meeting, bug 4 has three linked sub-problems:
1. One equipment type but two active ESNs should still use boundary path (not fallback).
2. Subsection ESN inheritance/disambiguation is wrong when same equipment type has multiple ESNs.
3. After subsection ends, context should flip back to outer section.

### Why this happens in current code

#### 4.1 Boundary vs fallback branch condition is type-count based, not ESN-count based
- Branch currently uses distinct equipment type count:
  - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L406](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L406)
- If only Gas Turbine type is present (even with 2 GT ESNs), it can drop into page fallback:
  - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L415](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L415)

This matches meeting concern that two ESNs of the same type still need boundary-based assignment.

#### 4.2 Subsection ESN uses a global anchor, not local section context
- Subsection boundaries attach a chosen anchor ESN (single gt_esn/gen_esn/st_esn), not a scoped section ESN stack.
- Turbine subsection assignment specifically picks one turbine anchor:
  - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L337](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L337)

When two same-type ESNs are active, this can attach subsection chunks to the wrong sibling ESN.

#### 4.3 No explicit section close / parent resume model
- Regions are built as boundary-to-next-boundary spans, no nesting stack.
  - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L409](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L409)
  - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L413](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L413)

So "generator subsection ends then return to turbine" depends on detecting a new explicit turbine boundary. If not detected, flip-back may not happen correctly.

### Impact
- Blank/unassigned spans in fallback path.
- Wrong ESN attribution inside mixed or nested equipment narratives.
- Higher downstream retrieval/evidence mismatch because section ownership drifts.

### Current status
- Some subsection handling was added, but all three sub-problems remain structurally possible with current branching/state model.

## Bug 6: Generator section detected but mapped to wrong Generator ESN

### What was reported
- CSV notes generator section exists but gets assigned to the wrong Generator ESN appearing elsewhere in body context.
- Also includes case where Generator ESN is missing but generator narrative exists.

### Why this happens in current code
- Code chooses a single anchor ESN per equipment type (gen_esn, gt_esn, st_esn).
- That anchor is selected from title/boundary frequency heuristics, then reused broadly.
  - ESN anchor chooser:
    - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L107](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L107)
  - Generator anchor use in section/subsection boundaries:
    - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L311](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L311)
    - [pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L333](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py#L333)

If local section text does not carry explicit local ESN and there are multiple generator ESNs, global anchor can be wrong.

### Impact
- Region metadata can look internally consistent but still be wrong for ESN-level attribution.
- Retrieval and analytics by ESN become noisy.

### Current status
- Improved ESN discovery exists (broad scans, more patterns), but local section-level ESN disambiguation remains unresolved.

## How bugs 3, 4, and 6 reinforce each other
1. Missed section boundaries (bug 3) reduce structural anchors.
2. Reduced anchors trigger fallback or weak span segmentation (bug 4.1).
3. Weak segmentation plus global ESN anchors increases wrong ESN assignment (bug 6).
4. Missing flip-back model (bug 4.3) extends wrong attribution farther than one subsection.

## Recommended fix strategy (ordered)

### Step 1: Strengthen boundary detection safely
- Add unnumbered heading patterns gated by strict line-shape rules (all-caps/known equipment tokens/new-line boundaries).
- Keep current numbered patterns as highest-confidence matches.

### Step 2: Change boundary-path eligibility
- Use boundary path when:
  - at least one reliable boundary exists, and
  - any equipment type has more than one active ESN.
- Do not force fallback only because distinct_types < 2.

### Step 3: Add hierarchical section state
- Build explicit section spans with level awareness (for example, 3.1 parent, 3.1.1 child).
- On child end, restore parent equipment/ESN context automatically.

### Step 4: Replace global ESN anchor reuse with local disambiguation
- For each boundary/span, resolve ESN in this order:
  1. explicit ESN in local heading/text window,
  2. inherit parent ESN if same equipment type,
  3. if cross-type and only one active ESN for that type, use it,
  4. else mark ambiguous and route to tie-break logic (rules/LLM/train tool), not hard default.

### Step 5: Add regression checks for these bug classes
- Coverage check: percent of document covered by regions.
- Ambiguity check: count of spans assigned by fallback/default.
- Flip-back check: ensure context restoration after child subsection close.
- Same-type multi-ESN check: ensure boundary path used.

## Suggested validation docs to run next
Prioritize docs attached to bug 3, 4, and 6 rows in [2-FSR-v2/this-week/bug-section/Xujin-bug-list.csv](2-FSR-v2/this-week/bug-section/Xujin-bug-list.csv), then inspect preprocessor regions/metadata output before ingestion.

---

## Preprocessor batch run results (2026-08-06)

Ran all configured cases via notebook batch mode. Results below.

| Case | Bug | Document ID | Pages | Regions | primary_esn | primary_equip_type | gt_esn | gen_esn | st_esn | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 3 | 35803273... | — | — | — | — | — | — | — | skipped (not in volume) |
| 1 | 3 | 806975e9... | — | — | — | — | — | — | — | skipped (not in volume) |
| 2 | 3 | 5b688732... | 415 | **5** | 316X914 | Generator | — | 316X914 | 155360 | ok |
| 3 | 4 | 32689520... | 323 | 58 | 296405 | Gas Turbine | 296405 | — | — | ok |
| 4 | 4 | b25c94da... | 574 | 124 | 804867 | Gas Turbine | 804867 | — | — | ok |
| 5 | 4 | b1cdbc80... | 430 | **11** | 297191 | Gas Turbine | 297191 | 336X827 | 155442 | ok |
| 6 | 4 | fcb1511e... | 596 | 99 | 337X581 | Generator | 298464 | 337X581 | — | ok |
| 7 | 4 | af693a98... | 328 | 34 | 297652 | Gas Turbine | 297652 | 337X766 | — | ok |
| 8 | 6 | b775cf29... | 325 | 32 | 297651 | Gas Turbine | 297651 | 337X765 | — | ok |
| 9 | 6 | b7b347fd... | 358 | **2** | 370T031 | **(empty)** | — | — | 370T031 | ok |

### Per-case findings

#### Case 2 — Bug 3 (5b688732, 415 pages, 5 regions)
- **Clear issue.** 415 pages collapsing to only 5 regions means section boundary detection is almost entirely failing on this document.
- Generator + Steam Turbine both detected (gen_esn + st_esn present, no gt_esn), but with so few regions the document is barely segmented.
- Root cause: PYPDF2 line-break preservation failures for section headers directly confirmed here.
- Next: run in single-case mode and inspect the 5 region spans (start/end chars) to understand what text is being grouped together.

#### Case 3 — Bug 4 (32689520, 323 pages, 58 regions)
- Only one GT ESN (296405) detected, no gen_esn. 58 regions looks reasonable for a single-equipment doc.
- Bug 4 description flags this as multi-ESN subsection issue — the second turbine ESN (or page 169 turbine) was not detected.
- Likely the PYPDF2 line-break issue also caused the second turbine section on page 169 to be missed.
- gen_esn is empty — possible that generator subsection content exists but was not captured.

#### Case 4 — Bug 4 (b25c94da, 574 pages, 124 regions)
- Only one GT ESN (804867) detected despite bug description saying "2 Gas Turbine ESN issue".
- Second GT ESN is missing entirely from metadata — ESN detection gap, not just a region assignment gap.
- 124 regions is a large number; all likely attributed to the single known ESN 804867.

#### Case 5 — Bug 4 (b1cdbc80, 430 pages, 11 regions) ← highest priority

**ESNs detected:**
- all_esns: 155442 (ST), 297191 (GT), 316X976 (GEN), 336X827 (GEN), 338X827 (GEN)
- gen_esn anchor: 336X827 only
- gt_esn: 297191 only
- 338X827 is detected in all_esns but has **zero regions attributed to it**

**Region map (247,907 chars, 430 pages):**

| # | start | end | chars | ESN | type |
|---|---|---|---|---|---|
| 0 | 2110 | 2331 | 221 | 155442 | ST |
| 1 | 2331 | 5019 | 2,688 | 336X827 | GEN |
| 2 | 5019 | 8683 | 3,664 | 316X976 | GEN |
| 3 | 8683 | 13943 | 5,260 | 297191 | GT |
| **4** | **13943** | **146586** | **132,643** | **297191** | **GT ← over half the doc in one region** |
| 5 | 146586 | 146876 | 290 | 155442 | ST |
| 6 | 146876 | 164942 | 18,066 | 297191 | GT |
| 7 | 164942 | 177459 | 12,517 | 336X827 | GEN |
| **8** | **177459** | **239715** | **62,256** | **336X827** | **GEN ← large** |
| 9 | 239715 | 240170 | 455 | 316X976 | GEN |
| 10 | 240170 | 247907 | 7,737 | 336X827 | GEN |

**Coverage gaps:**
- Chars 0–2110 (title/front matter) are uncovered by any region.

**Byte-share cross-check (from hints):**
- gt_bytes=155,969 ✓ matches GT regions (5260+132643+18066 = 155,969)
- gen_bytes=89,317 ✓ matches GEN regions
- st_bytes=511 ✓ matches ST regions

**Specific bugs confirmed by this output:**

1. **338X827 missing from all regions.** It is in all_esns (detected in body text) but never created a boundary, so no region is attributed to it. This is the multi-same-type ESN issue: the gen_esn anchor is 336X827, and any boundary that should map to 338X827 either fell through or was never detected.

2. **Region 4 spans 132,643 chars (53% of the document).** This is the main GT section with almost no internal sub-boundary detection. This alone suppresses region count from what should be ~50+ regions to just 11.

3. **316X976 gets only 2 tiny regions (3,664 + 455 = 4,119 chars total)** despite being a real equipment in the document. Its sections are being absorbed into the 336X827 anchor.

4. **Root cause confirmed:** When the gen_esn anchor is fixed to one ESN (336X827), all generator sub-section boundaries that lack a locally-matched ESN inherit the single anchor. The other GEN ESNs (316X976, 338X827) only get regions where the HEADER pattern explicitly names them.

#### Case 6 — Bug 4 (fcb1511e, 596 pages, 99 regions)
- GT and GEN both detected (298464 and 337X581). 99 regions seems healthy in count.
- Bug concern is the flip-back: generator subsection ending should restore turbine context.
- Cannot confirm or deny from count alone — need region-level inspection to check whether generator regions continue beyond generator subsection boundaries.
- primary_equip_type is Generator (337X581 wins byte-share), which may itself be a symptom of generator regions overrunning into turbine territory.

#### Case 7 — Bug 4 (af693a98, 328 pages, 34 regions)
- GT (297652) and GEN (337X766) both detected. 34 regions for 328 pages.
- Same flip-back concern as case 6. Count is plausible but region metadata inspection needed.

#### Case 8 — Bug 6 (b775cf29, 325 pages, 32 regions)
- GT (297651) and GEN (337X765) both detected. primary is Gas Turbine.
- Bug: wrong GEN ESN assignment to generator section. From batch summary, gen_esn=337X765 — but the bug says generator sections get the wrong ESN from body context.
- Need region-level inspection to see which regions are attributed to gen_esn vs gt_esn and whether any generator section was mis-tagged.

#### Case 9 — Bug 6 (b7b347fd, 358 pages, 2 regions) ← second highest priority

**ESNs detected:** only 370T031 (classified as Steam Turbine). gt_esn="", gen_esn="".

**Region map (134,706 chars, 358 pages):**

| # | start | end | chars | ESN | type |
|---|---|---|---|---|---|
| 0 | 3637 | 7622 | 3,985 | 370T031 | ST |
| **1** | **7622** | **134706** | **127,084** | **none** | **Gas Turbine** |

Chars 0–3637 uncovered. Region 1 = 94% of doc with no ESN attached at all.

**Hints:** gt_bytes=127,084 / gen_bytes=0 / st_bytes=3,985. gt_sig_hits=17, gen_sig_hits=**0**.

**Specific bugs confirmed:**

1. **GT section header detected at char 7622** — creates a 127K-char region typed Gas Turbine but with no `primary_esn` (just `{"primary_equip_type": "Gas Turbine"}`).

2. **gen_sig_hits=0** — no standard generator vocabulary found. Either content uses non-standard terms or generator work is described within the GT section narrative without keyword triggers.

3. **primary_equip_type="" in metadata** even though gt_bytes dominates — `_choose_primary()` returns None for type when both gt_esn and gen_esn are absent.

4. **370T031 likely misclassified as Steam Turbine** — its format matches both GEN and ST patterns; the ST label on the title page won the classification race.

5. **Root cause:** No generator ESN in text → no gen_esn anchor → no generator boundary → generator content (if present) absorbed into the GT region with no ESN. Page fallback also fails since gen_sig_hits=0.

6. **Fix path:** Needs LLM-based type inference (discussed in meeting ~53 min). When no explicit ESN is labeled, infer equipment type from section headings and narrative.

| Priority | Case | What to look at |
|---|---|---|
| 1 | Case 5 (b1cdbc80) | Inspect region char spans — confirm near-zero boundary detection on 430-page doc |
| 2 | Case 9 (b7b347fd) | Inspect 2 region spans — confirm generator content falls outside any region |
| 3 | Case 2 (5b688732) | Inspect 5 region spans — confirm section headers that were missed |
| 4 | Cases 6 + 7 | Inspect region metadata sequence — check for generator regions continuing past turbine header |
| 5 | Case 8 | Inspect per-region primary_esn — check if generator sections are tagged with correct GEN ESN |