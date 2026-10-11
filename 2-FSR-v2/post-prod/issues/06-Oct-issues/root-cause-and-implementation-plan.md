# 06-Oct Active Issues: Root Cause and Implementation Plan

Updated: 2026-10-07
Status: Local implementation in place; validation against the affected PDFs remains pending

## Scope

This plan covers only the active findings in [review-summary.md](review-summary.md):

- O6-02: Executive Summary paragraph split in `00f23784-d121-4595-b61d-49d223253a05`
- O6-03: Work Scope table split and section-path pollution in the same document
- O6-08: Embedded subreport path in `796f4d53-a8ad-42e1-af4d-53a8add2e1a4`

The heading/body ordering findings for `00f...` and `93c...` are paused pending SME feedback about the required quality of final-master chunks and the value of a parser-level fix. The 36-UUID heading-only and repeated-vertical-heading findings remain postponed. Metadata lookup O6-04 is resolved and requires no code change. These exclusions match the October 7 meeting transcript and the current issue summaries.

## Evidence and Confidence

The persisted October 6 examples are recorded in `dev-issue-evidence-20261006.json`. They establish the output symptoms, but do not include the P1 candidate trace or region boundaries needed to identify the exact candidate type and offset that created every path.

The September 29 RCA, `../01-04-date-09-28-issues/root-cause-analysis.md`, identifies table-derived section candidates and missing restoration of outer hierarchy after embedded subreports as known failure modes. The current source code and regression tests support those mechanisms. The local source checkout is at `d24b62a`; the October 6 evidence does not record the deployed code commit or preprocessor version, so it is not possible to determine from these artifacts whether that exact checkout produced the persisted rows.

### O6-02: Executive Summary paragraph boundary

**Observed:** chunk 2 ends with “Engineering also provided a new”; chunk 3 begins “alignment criteria for the unit...”. There are zero shared boundary characters. Chunk 3 has the prose fragment `alignment criteria for the unit.The new alignment specification is fot the generator to be` as `section_1`. Chunk 4 inherits that same fragment as its parent path before `1.3 Work Scope`.

**Cause assessment: reproduced malformed ToC page-hint candidate.** The persisted prose fragment matches a sentence-like, unnumbered ToC row ending in a page number. With realistic page offsets, the page hint resolves the title to the body occurrence and emits it as a `TOC` heading candidate. That candidate becomes `section_1`, creating a region boundary inside the paragraph; P2 then preserves the P1 boundary and cannot overlap across it.

**Implementation:** long unnumbered ToC titles containing a sentence boundary (lowercase letter, sentence punctuation, then uppercase text) are excluded from page-hinted heading candidates. The focused regression uses the persisted phrase and a page-7 body offset, and verifies the prose no longer appears in any region path. No cross-region overlap was added. The original PDF's raw ToC/candidate trace still needs verification.

### O6-03: Work Scope table and section paths

**Observed:** chunk 4 contains the `1.3 Work Scope` heading and the Gas Turbine/Steam Turbine rows. Chunk 5 contains `Generator`, `Mechanical`, and `Support Systems`, with `section_path = [Generator]`. Chunk 4 also carries the Executive Summary prose fragment as its parent path.

**Cause assessment: reproduced false heading promotion from table content; shared pollution with O6-02 is not yet proven.** The prior RCA identifies table/ToC lines being accepted as headings and then retained as active hierarchy context. A focused fixture reproduces the `Generator` Work Scope row being accepted as an unnumbered equipment heading when it appears in a multi-equipment list. The exact candidate and source line in the affected PDF still need confirmation against the P1 trace.

**Implementation:** the local preprocessor suppresses a standalone equipment label only when it is part of a contiguous run of at least two recognized equipment labels inside a numbered Work Scope block. A separate regression verifies a later, separated `Generator` heading remains eligible. The actual PDF still needs confirmation against its parsed page layout.

### O6-08: Embedded subreport path

**Observed:** chunk 91 has `section_path = [Generator, 4.7 1A BFP]`; the expected enclosing main-report path includes sections 3, 3.4, and 3.4.1. The review confirms that local subreport headings should remain useful for chunking while section metadata retains the enclosing main-report path.

**Cause assessment: hierarchy-context loss is reproduced by a focused fixture.** The preprocessor builds section paths through a parent stack. Previously, an intervening local `4.7` heading could receive only the equipment root as its path even though a later `3.4.2` section resumed under the main report. The earlier RCA reports the same stack-restoration gap.

**Implementation:** `_section_path_for_span` only maps an intervening numbered span to the enclosing main-report subsection when the local heading is absent from a reliable primary ToC, and a later heading exactly matches that ToC under the enclosing parent. The local span remains a separate region and its heading remains in chunk text. Tests cover the `3 -> 3.4 -> 3.4.1 -> 4.7 -> 3.4.2` case, a ToC-listed `4.1 Control System` that must keep its own path, and an incomplete-ToC case where resumed body content must not be dropped.

## Investigation Findings in Code and Tests

- `common/fsr_v2/preprocessor_v2.py` owns heading candidate collection, hierarchical span construction, and emitted `section_path` generation.
- `gold/src/etl/fsr_v2/chunk_splitter.py` consumes P1 regions as authoritative boundaries and projects region `section_path` values into chunk section fields.
- Existing regression coverage includes generic ToC/table artifact filtering, retention of genuine short regions, and local numbering under an attachment context.
- The Work Scope fixtures verify contiguous table-row suppression and preservation of a separated equipment heading.
- The subreport fixtures verify ToC-gated enclosing-path restoration, preserve a ToC-listed cross-root section, and retain resumed content with incomplete ToC coverage.
- The malformed sentence-like ToC fixture reproduces the O6-02 path when the page hint resolves beyond the 8,000-character search window; the new filter prevents it from seeding the body path.
- The focused active-issue regressions pass (6 passed, 107 deselected). They establish local behavior, not persisted output for the three affected PDFs.

## Implementation and Validation Plan

1. Capture the P1 trace for the actual affected pages: raw parsed page text, page offsets, accepted/rejected candidates with type and reason, emitted region boundaries, and each region's section path. Use the same parser/preprocessor version as the intended test run.
2. Compare the sentence-like ToC row and body page offset for O6-02 with the reproduced fixture; verify the paragraph and Work Scope paths are corrected without changing valid ToC headings.
3. Compare O6-03 against the real extracted PDF; confirm table text coverage, later section paths, and existing equipment/ESN attribution.
4. Validate O6-08 against the real `796...` P1 spans and primary ToC; confirm the `4.7 1A BFP` boundary remains and its section fields recover the `3.4.1` path only when the resumed section is authoritatively ToC-matched.
5. Run the complete focused preprocessor/chunk-splitter module, then compare affected region paths, chunk text coverage, section fields, and retrieval results against the October 6 evidence.
6. Only after source-level and local validation, reprocess the approved documents in an isolated test scope. Do not reprocess production/dev as part of this implementation.

## Acceptance Criteria

- No prose fragment from the Executive Summary is emitted as a section heading or parent path.
- The paragraph is not split at a false section boundary; any size-driven split remains within the correct section and uses within-region overlap.
- The Work Scope table is fully retained; table cells do not create section/equipment headings or change subsequent paths.
- Genuine short sections and their content remain available; no broad short-chunk merge is introduced.
- Embedded subreport content remains chunkable, while the section fields retain the correct outer main-report path and transition when the main report resumes.
- Incomplete ToC evidence does not cause valid body or subreport sections to be discarded.
- Existing Generator/Turbine attribution, ESN assignment, and non-target section paths do not regress.

## Open Verification Items

- The October 6 persisted evidence does not identify the deployed source commit/preprocessor version.
- The original P1 candidate type, raw ToC line, and region offsets for the `alignment criteria...` path fragment have not been captured; the mechanism is reproduced in a focused fixture.
- The precise outer-path transition around subreport chunk 91 needs the surrounding P1 spans and primary ToC entries.
- O6-02, O6-03, and O6-08 have focused synthetic coverage but still require validation against the actual parsed source pages and persisted output.
- Final-master parser-level heading/body alignment remains on hold pending SME feedback; do not fold it into this implementation without a new scope decision.