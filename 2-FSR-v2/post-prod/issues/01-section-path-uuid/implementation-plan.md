# Implementation Plan

Updated: 2026-09-15
Issue: Section path / UUID chunking

## Goal

Implement the section-based chunking fix in the main path first, so each smallest section becomes its own chunking unit and full section labels are preserved, while treating the three meaningful UUID no-TOC outliers as manual exceptions for now.

## Proposed steps

1. Reproduce the issue on one affected UUID sample in the standalone preprocessor flow.
2. Confirm that Generator/Turbine spans and ESN attribution are already correct on the affected sample.
3. Identify where section-to-chunk granularity is too coarse and where full section labels are being shortened.
4. Update the section-based chunking path so the smallest intended sections are emitted as separate chunking units without changing Generator/Turbine span logic.
5. Preserve full section labels in `section_path` and `section_1` through `section_5`.
6. Add unit coverage for the affected pattern in `tests/fsr_v2/test_preprocessor_v2.py` and any chunking-layer tests needed for section metadata propagation.
7. Validate on a small regression set:
   - one affected UUID sample
   - one normal UUID doc with standard TOC
   - one doc with table-like rows that must not become headings
   - one doc with OCR or page-join artifacts
8. Run targeted QA reprocessing only for the affected docs after validation.
9. Compare chunk counts, `section_path`, `section_1` through `section_5`, and retrieval behavior before and after.

## Code areas expected to change

- `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`
- `pw_sdg_ai_ser_repo/tests/fsr_v2/test_preprocessor_v2.py`

## Validation gates

Implementation should only be accepted if all of these are true:

- the affected UUID sample preserves the current Generator/Turbine boundary and ESN attribution behavior
- the affected UUID sample emits one chunk unit per smallest intended section
- full section labels are preserved in `section_path` and `section_1` through `section_5`
- no new false-positive section headers appear in the narrow regression set
- downstream chunk output inherits the corrected section metadata

## Rollout scope

Preferred rollout order:

1. local or standalone preprocessor validation
2. QA targeted reprocessing for affected docs
3. QA retrieval verification
4. wider rollout only if the narrow fix remains stable

## Open decision before implementation

Operational direction from the latest discussion:

- do not add a separate `36UUID` no-TOC fallback at this time
- focus on the section-based chunking fix first
- handle the three meaningful UUID no-TOC outliers manually if needed
- do not change the current Generator/Turbine span or ESN logic for this fix
