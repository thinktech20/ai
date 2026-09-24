# Implementation Plan

Updated: 2026-09-15
Issue: Section path / UUID chunking

## Goal

Implement the section-based chunking and heading-quality fix in the shared path for the roughly `50K+` document population, so each smallest section becomes its own chunking unit and full section labels are preserved. Use stronger structural TOC checks only when extraction quality is sufficient, and treat the four meaningful UUID no-TOC outliers as observable exceptions for now.

## Proposed steps

1. Reproduce the issue on one affected UUID sample and one non-UUID control sample in the standalone preprocessor flow.
2. Confirm that Generator/Turbine spans and ESN attribution are already correct on the affected sample.
3. Check the earlier preprocessor findings: TOC-derived section detection starting late and page-join/OCR noise being accepted as headings.
4. Identify where section-to-chunk granularity is too coarse and where full section labels are being shortened.
5. Add a TOC-quality decision: reliable numbered TOCs may use exact section-number and normalized-title guardrails; incomplete TOCs must not become authoritative.
6. Update the section-based chunking path so the smallest intended sections are emitted as separate chunking units without changing Generator/Turbine span logic.
7. Preserve full section labels in `section_path` and `section_1` through `section_5`.
8. Add unit coverage for numbered TOC matches, missing TOC entries, known unnumbered exceptions, and multiline/table artifacts.
9. Validate on a small regression set:
   - one affected UUID sample
   - one normal UUID doc with standard TOC
   - one doc with table-like rows that must not become headings
   - one doc with OCR or page-join artifacts
10. Run targeted QA reprocessing only for the affected docs after validation.
11. Compare chunk counts, `section_path`, `section_1` through `section_5`, and retrieval behavior before and after.
12. Record confidence and reason codes for ambiguous heading decisions so future LLM-assisted review can be evaluated without changing the primary deterministic output.
13. Measure diagnostic reason-code volume on a representative sample before proposing a dedicated diagnostics table or LLM review queue schema.
14. Add a narrow `Quality Checkpoint (QCP)` root-heading rule and regression test.
15. Add confidence-gated generic subsection support under Generator `-1` headers using `c9ed4e93-8408-4371-9f90-4e8641dd1ee6` as the primary regression case.
16. Add explicit sub-report/attachment context handling so reused local section numbers do not inherit an unrelated main-report sibling, while retaining the content for chunking.
17. Trace the long-label example through extraction, preprocessing, and persistence. Keep any fix only if it is local and passes the broader regression set; otherwise defer it.
18. Validate sub-report context on `N Attachments`, `N Appendix`, and `N Sub Reports` examples, including local numbers absent from the primary TOC.
19. Keep the existing two-leader/page-number TOC continuation threshold unchanged; do not expand TOC continuation detection in this cycle.

## Code areas expected to change

- `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`
- `pw_sdg_ai_ser_repo/tests/fsr_v2/test_preprocessor_v2.py`
- downstream chunking tests for section metadata propagation, if changed boundaries affect them

## Validation gates

Implementation should only be accepted if all of these are true:

- the affected UUID sample preserves the current Generator/Turbine boundary and ESN attribution behavior
- the affected UUID sample emits one chunk unit per smallest intended section
- full section labels are preserved in `section_path` and `section_1` through `section_5`
- no new false-positive section headers appear in the narrow regression set
- reliable TOCs strengthen validation without causing valid sections to disappear when a TOC is incomplete
- downstream chunk output inherits the corrected section metadata
- ambiguous cases remain observable and do not trigger unversioned LLM changes in the primary ingestion path
- heading diagnostics remain additive JSON metadata and do not change relational chunk filtering fields
- Quality Checkpoint headings are detected without broadening unrelated root-heading matches
- Generator generic sections improve in the cited document without reintroducing table/value false positives
- sub-report content remains chunkable but is not assigned a misleading reused main-report path
- local sub-report numbering is scoped under an attachment/appendix/sub-report context when detected
- incomplete primary TOC coverage does not cause valid sub-report content to be discarded
- sparse final TOC continuation pages remain an accepted low-impact edge case for this cycle
- long-label preservation is optional and must not introduce material regression

## Rollout scope

Preferred rollout order:

1. local or standalone preprocessor validation
2. QA targeted reprocessing for affected docs
3. QA retrieval verification
4. wider rollout only if the narrow fix remains stable

Operational batch execution and overwrite auditing are described separately in `operationalization-plan.md`. The scope-table mode should be implemented before attempting a large document reprocessing run.

## Open decision before implementation

Operational direction from the latest discussion:

- do not add a separate UUID parser or raw exact-title matching path
- focus on the shared section-based chunking and heading-quality fix first
- use normalized structural TOC guardrails only when TOC quality is reliable
- handle the four meaningful UUID no-TOC outliers manually if needed, with fallback reasons recorded; the latest addition is `92387bdc-55df-41ab-8db3-f7fec0b15fa5`
- do not change the current Generator/Turbine span or ESN logic for this fix

The four reviewed follow-up fixes should be implemented and validated as separate slices. Do not combine them into one global relaxation of numbered heading detection.

## Future LLM evaluation boundary

Do not add LLM calls to the current production fix. First establish deterministic confidence signals and regression baselines. A later LLM evaluation may classify low-confidence headings, suggest normalized labels, or route cases for review, but it must run as a versioned and auditable secondary process before any result is allowed to affect persisted section metadata.
