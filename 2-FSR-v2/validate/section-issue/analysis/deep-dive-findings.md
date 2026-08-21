# FSR v2 Section Issue Deep Dive

Date: 2026-07-27

## Scope
- Investigated the section metadata and chunk-splitting behavior reported by Xujin.
- Traced FSR v2 code path end to end and compared with FSR v1 hierarchical behavior where relevant.
- Mapped screenshot symptoms to specific implementation points.

## Screenshot Symptoms Mapped
- Repeated section label behavior like section_1=FORM across many chunks is consistent with heading-marker-driven sectioning, where repeated heading-like lines become section anchors.
- Section path anomalies like section_1 as sentence-like text and section_2=FORM are consistent with nested heading-stack construction from injected ##/### markers.
- Sentence split across adjacent chunks without overlap is visible in the page-break example where one chunk ends with "...in exhaust" and next starts with "casing...".
- Footer/legal text entering chunk_text is visible in the screenshot where legal/footer lines appear as content and even sit near synthetic headings.

## v2 Code Path (what currently happens)
1. P2 extraction uses pypdf2 path via [pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/text_extraction.py](pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/text_extraction.py#L15) and [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py#L117).
2. During parsing, heading markers are injected by heuristic in [_inject_pdf_heading_markers](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py#L79).
3. P2 chunking uses section strategy by default in [pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py](pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py#L195).
4. Section boundaries are found by markdown heading regex in [pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py#L30) and parsed in [_extract_sections](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py#L453).
5. section_1..section_5 are emitted from the heading breadcrumb path in [get_section_metadata](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py#L495) and attached in [pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py](pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py#L455).

## Findings

### 1) False heading promotion is a primary root cause
Severity: High

Evidence in code:
- Numbered and uppercase lines are promoted to headings in [_inject_pdf_heading_markers](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py#L96), [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py#L104), [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py#L108).
- The all-caps rule is broad enough that non-structural lines can become headings.

Why this causes your observed output:
- Any false positive heading gets parsed as real section boundary by [pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py#L454).
- Breadcrumb stack logic turns these into section_1..section_5 values, which explains noisy paths such as sentence-like section_1 and FORM as a child/peer level.

### 2) Hard section boundaries create split-without-overlap behavior
Severity: High

Evidence in code:
- Section strategy chunks per extracted section in [_chunk_by_sections](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py#L431).
- Overlap is applied only when recursively splitting an oversized single section, not across different sections.

Why this causes your observed output:
- If a false heading occurs near a page break or mid-thought, the text is cut at that boundary.
- Since these are separate sections, no cross-section overlap is carried, so sentence continuity breaks exactly as shown in the screenshot.

### 3) Footer/legal lines are not suppressed in the pypdf2 section path
Severity: High

Evidence in code:
- pypdf2 parse path captures page text and injects markers, but does not perform positional/repetition boilerplate filtering in [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py#L117).
- v1 hierarchical explicitly computes repeated lines and removes boilerplate/header/footer-zone lines in [pw_sdg_ai_ser_repo/common/fsr_v2/hierarchical_chunking_v1.py](pw_sdg_ai_ser_repo/common/fsr_v2/hierarchical_chunking_v1.py#L267), [pw_sdg_ai_ser_repo/common/fsr_v2/hierarchical_chunking_v1.py](pw_sdg_ai_ser_repo/common/fsr_v2/hierarchical_chunking_v1.py#L321), [pw_sdg_ai_ser_repo/common/fsr_v2/hierarchical_chunking_v1.py](pw_sdg_ai_ser_repo/common/fsr_v2/hierarchical_chunking_v1.py#L354).

Why this causes your observed output:
- Legal/footer text survives in v2 section chunking and can be pulled directly into chunk_text.
- Those lines can also distort local structure when they appear near heading-like tokens.

### 4) Heading tokens are retained inside chunk_text
Severity: Medium

Evidence in code:
- Each section starts at heading match start and section text includes that heading line in [pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py#L463).

Impact:
- chunk_text is polluted with repeated synthetic prefixes like ## FORM, reducing readability and introducing repetitive noise in embeddings.

### 5) Parser-mode drift risk has been closed for new runs (pypdf2-only)
Severity: Informational

Evidence in code:
- P1 parser mode is now enforced to `pypdf2_v1.0` only in [pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py#L127).
- P2 extraction path uses the same pypdf2 helper in [pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py](pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py#L398).

Impact:
- New runs will stay in one offset space across P1 and P2.
- For this dev phase, historical cleanup is out of scope because data will be deleted and re-ingested.

## Why v1 looked better in your example
- v1 hierarchical path includes explicit boilerplate suppression and visual-structure filtering, which often removes recurring footer/legal artifacts before chunk assembly.
- v1 can still misclassify some body lines as headers in other docs, but for this example it avoided the specific section-boundary and footer issues you highlighted.

## Practical Root-Cause Summary
- The issue is not one bug.
- It is a combination of:
  - broad heading-marker heuristics,
  - strict section-based splitting without cross-section overlap,
  - and missing footer/boilerplate suppression in the v2 section path.

## Recommended Fix Plan (ordered)
1. Tighten heading injection heuristics in [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py#L79).
2. Add footer/boilerplate suppression before section extraction for pypdf2 text, reusing v1-style repeated-line and legal-pattern logic from [pw_sdg_ai_ser_repo/common/fsr_v2/hierarchical_chunking_v1.py](pw_sdg_ai_ser_repo/common/fsr_v2/hierarchical_chunking_v1.py#L267).
3. Add optional cross-section overlap when a section boundary is adjacent to sentence-continuation patterns.
4. Strip synthetic heading markers from stored chunk_text while preserving section metadata fields.
5. No historical cleanup task: treat this as a fresh implementation in dev, delete existing data, then run a clean end-to-end re-ingest after fixes 1-4.

## Alex Comparison Outcome and Priority Fixes
Yes. Based on the Alex comparison and latest query outputs, these are the fixes needed to meet Xujin's ask.

### Priority Fixes
1. Make section detection TOC-aware using structural logic, not only heading regex.
  - Why: TOC-style lines are still being treated as section anchors in current output.
  - Fix in [pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py#L517), and align behavior with structural detection patterns in [pw_sdg_ai_ser_repo/common/fsr_chunking.py](pw_sdg_ai_ser_repo/common/fsr_chunking.py#L742).
  - Change: build section paths from content after TOC/front-matter exclusion, then emit section_1 to section_5.

2. Add hard guard so TOC-like section paths are never written to chunk metadata.
  - Why: defensive filter is needed even if upstream detection improves.
  - Fix in [pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py](pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py#L153).
  - Change: reject section values that match TOC/index patterns before metadata attach.

3. Keep two page-text views: raw pages for summary extraction, cleaned pages for chunking.
  - Why: parser-side TOC cleanup can reduce Stage 3 summary extraction quality.
  - Fix in [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py#L41) and [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py#L66).
  - Change: store raw and cleaned page variants, and route each consumer to the correct one.

4. Tighten cross-section overlap gating for non-prose boundaries.
  - Why: boundary fragments are still visible in query drill-down.
  - Fix in [pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py#L487).
  - Change: disable overlap at section starts when either side is TOC/legal/index-like.

5. Add ingestion completeness gate for target-doc validation runs.
  - Why: validation is not conclusive when target docs are missing.
  - Fix in [pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest.py](pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest.py).
  - Change: fail run if any target document is absent from metadata/chunks/map.

### Acceptance Criteria for Xujin Ask
1. Query 1 and Query 2 return zero missing target docs in metadata, chunks, and doc-equipment map.
2. Query 6 and Query 7 no longer show TOC/legal/footer-heavy content as dominant chunk heads for the affected docs.
3. Query 3 shows section_1 values aligned to real body sections, not TOC/index-style labels.
4. Query 5 flagged boundary count trends down materially versus current baseline for the same document set.

### Execution Sequence (Implement All Fixes)
1. Phase 0: Baseline snapshot and guardrails.
  - Freeze current query outputs for the target doc set as baseline.
  - Baseline files are frozen under [2-FSR-v2/validate/section-issue/test/6-query-results](2-FSR-v2/validate/section-issue/test/6-query-results).
  - Baseline snapshot details:
    - Query 1 result file: [2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11.csv](2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11.csv)
    - Query 2 result file: [2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11 (1).csv](2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11%20(1).csv)
    - Query 3 result file: [2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11 (2).csv](2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11%20(2).csv)
    - Query 4 result file: [2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11 (3).csv](2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11%20(3).csv)
    - Query 5 result file: [2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11 (4).csv](2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11%20(4).csv)
    - Query 6 sample file: [2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11 (5).csv](2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11%20(5).csv)
    - Query 7 sample file: [2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11 (6).csv](2-FSR-v2/validate/section-issue/test/6-query-results/New_Query_2026_07_27_14_13_11%20(6).csv)
  - Baseline metrics to beat:
    - Coverage: 7 of 9 target docs present; 2 missing across metadata/chunks/doc_equipment_map.
    - Missing docs: 35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report and 39_v1.0(17).
    - Section quality (Query 3): section1_missing appears in 6 of 7 processed docs (1 each); section1_short_allcaps_like is highest at 40 for 27314604-ed52-402f-921f-34737a048841.
    - Footer/page regex hits (Query 4): legal_footer_hits=0 and page_number_hits=0 for all 7 processed docs, but this does not capture TOC/legal variants seen in samples.
    - Boundary signal (Query 5): flagged_boundaries totals by doc are 101, 69, 73, 40, 61, 139, 74 respectively (sum=557 across 7 processed docs).
  - Qualitative baseline (Query 6 and Query 7):
    - Early chunks still contain "Table Of Contents" and confidentiality/export-control strings as dominant content.
    - section_1 labels are frequently TOC-like entries with leader underscores in early chunks.
    - Chunk heads show carry-over fragments, indicating noisy section boundaries.
  - Add completeness gate in [pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest.py](pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest.py).
  - Exit criterion: re-ingest run fails fast when any target document is missing.

2. Phase 1: Parser data-model split (raw vs cleaned pages).
  - Update [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py) to persist raw pages and cleaned pages.
  - Update [pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py) to read TOC/summary from raw pages only.
  - Keep chunking path on cleaned text.
  - Exit criterion: document_summary extraction quality is unchanged or better on sampled docs.

3. Phase 2: Structural sectioning first, regex second.
  - Refactor [pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py) to apply TOC-aware structural section detection before regex fallback.
  - Reuse strategy ideas from [pw_sdg_ai_ser_repo/common/fsr_chunking.py](pw_sdg_ai_ser_repo/common/fsr_chunking.py#L742) for TOC/front-matter exclusion and section path build.
  - Exit criterion: early chunks no longer inherit TOC rows as section labels.

4. Phase 3: Metadata hard guard.
  - Add defensive filter in [pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py](pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py#L153) to reject TOC/index-like section values before persisting metadata.
  - Exit criterion: Query 3 has no TOC/index-like section_1 values.

5. Phase 4: Boundary quality hardening.
  - Finalize overlap gating in [pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py](pw_sdg_ai_ser_repo/common/fsr_v2/chunker.py#L487) to skip non-prose boundaries and section-start noise.
  - Exit criterion: Query 5 flagged boundaries trend down versus baseline and chunk heads do not start with broken carry-over fragments.

6. Phase 5: Full targeted re-ingest and sign-off check.
  - Delete and re-ingest only target docs in dev.
  - Run Query 1 to Query 7 from [2-FSR-v2/validate/section-issue/test/section-issue-validation-queries.md](2-FSR-v2/validate/section-issue/test/section-issue-validation-queries.md).
  - Exit criterion: all acceptance criteria pass and samples show no TOC/legal dominance.

## 2026-07-27 Rerun Root-Cause Update (Before vs After Evidence)

### Current Verdict
- Xujin issue is partially fixed, not fully closed.
- TOC/legal contamination in sampled chunk content improved materially.
- Coverage and section-label quality criteria are still not met.

### Evidence Summary from Validation Artifacts
- Compared files under:
  - [2-FSR-v2/validate/section-issue/test/before-section-fix](2-FSR-v2/validate/section-issue/test/before-section-fix)
  - [2-FSR-v2/validate/section-issue/test/after-section-fix](2-FSR-v2/validate/section-issue/test/after-section-fix)
- Coverage (Query 2): still 2 missing targets in both before and after.
  - Missing docs remain:
    - 35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report
    - 39_v1.0(17)
- Section quality (Query 3):
  - section1_missing sum: 6 -> 6 (no improvement)
  - section1_short_allcaps_like sum: 79 -> 209 (regression)
- Boundary signal (Query 5):
  - flagged_boundaries absolute count: 557 -> 484 (improved)
  - flagged/chunk ratio: 0.2474 -> 0.2632 (regression after normalization)
- Content contamination in samples (Query 6 and Query 7):
  - chunk heads with TOC/legal patterns dropped to zero in after samples
  - chunk_text TOC/confidential/export-control matches dropped to zero in after samples
  - leader/noise patterns in chunk text reduced significantly

### Updated Root Cause for Remaining Gap
1. Ingest coverage gap is operational/input matching, not chunker logic.
  - Two target identifiers are still absent from metadata/chunks/map in both before and after snapshots.
  - This indicates they were not materialized in P1, so downstream P2/P3 cannot include them.
  - Most likely causes are target-to-source mismatch (identifier vs exact source file name) or source-volume mismatch for those two files.

2. Section label heuristics are still too permissive for all-caps short headings in some documents.
  - Even with TOC/legal cleanup gains, Query 3 shows increased short all-caps-like section_1 labels.
  - This points to residual false-positive heading promotion and/or fallback section labeling behavior.

3. Boundary tuning improved absolute count but not normalized quality.
  - Reduced total chunks changed denominator effects.
  - Current boundary strategy needs one more tuning pass using rate-based acceptance, not only absolute counts.

### What Still Needs to be Fixed
1. Add a preflight target resolution check before P1.
  - For each target, resolve whether it exists in source volumes by exact filename and normalized basename.
  - Fail fast with explicit missing-target list before running P1.
  - Keep this check simple and non-regex-heavy in notebook orchestration.

2. Keep ingest orchestrator simple and non-blocking.
  - Continue with P1 -> P2 -> P3 sequence and summary snapshots.
  - Avoid complex in-notebook regex gates; perform strict pass/fail in separate validation queries.

3. Tighten heading promotion thresholds in parser/chunker.
  - Reduce acceptance of short all-caps tokens as top-level section anchors.
  - Prefer structural context over token casing alone.

4. Add normalized metric to boundary acceptance.
  - Track flagged_boundaries/chunk_rows trend by doc, not just raw flagged count.
  - Require non-regression in rate for sign-off.

### Sign-off Conditions to Close Xujin Issue
1. Coverage: 0 missing docs across metadata/chunks/map for the full target list.
2. Section quality: section1_missing decreases and section1_short_allcaps_like does not regress.
3. Content quality: no TOC/legal dominance in Query 6/7 samples.
4. Boundary quality: flagged boundary rate non-regressing vs baseline on same target set.

### Rollback / Safety Rules
1. If Phase 1 harms document_summary extraction, keep raw-page route unchanged and isolate cleaning to chunking input only.
2. If Phase 2 introduces section coverage drop, keep structural pass but relax fallback threshold instead of widening regex globally.
3. Do not merge Phase 3 to 5 changes without a complete Query 1 to 7 result set for the same ingest run.

## Confidence
- High confidence for findings 1 to 4 (directly evidenced by code path and screenshot behavior).
- High confidence for finding 5 status for new runs, based on current parser-mode enforcement in code.
