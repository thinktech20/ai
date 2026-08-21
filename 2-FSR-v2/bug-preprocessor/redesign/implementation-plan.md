# FSR v2 Bug Preprocessor Redesign — Implementation Plan

Status: Reviewed
Owner: Copilot
Started: 2026-08-07

## Scope
- Implement a new preprocessor path as `preprocessor_v2.py` without modifying behavior in existing `preprocessor.py`.
- Implement the architecture in `proposed-design-changes.md` with Pydantic schemas and Enum-based fixed values.
- Keep `metadata_processor_v2.py` thin and route through the new preprocessor.
- Add tests folder and focused unit tests for preprocessor, parsed-volume IO, and region-first chunking.

## Work Items
1. Create `common/fsr_v2/preprocessor_v2.py` with organized method-wise structure.
   - Status: Complete
2. Add Pydantic models + Enums for section spans, regions, metadata provenance.
   - Status: Complete
3. Copy regex patterns from legacy preprocessor and call out any intentional additions/changes.
   - Status: Complete
4. Implement Phase 1-4 flow in method-wise design (ESN discovery, spans, ESN resolution incl. IBAT, regions+summary).
   - Status: Complete
5. Integrate with `silver/src/etl/fsr_v2/metadata_processor_v2.py` (thin adapter, pass `raw_pages`).
   - Status: Complete
6. Add `pw_sdg_ai_ser_repo/tests/fsr_v2/` and focused unit tests for the redesign path.
   - Status: Complete
7. Implement parse-once persisted parsed-document flow for P1/P2.
   - Status: Complete
8. Implement region-first chunking and direct region metadata inheritance in P2.
   - Status: Complete
9. Validate static errors and executable tests for touched files, then update plan to Ready for Review.
   - Status: Complete
10. Enforce parse-once contract end-to-end (no optional fallback in P2 path).
   - Status: Complete
11. Implement TOC page-number hint anchoring in heading candidate resolution.
   - Status: Complete
12. Align strict `all_esns` semantics (`all_esns` from structured signals only; `broad_esns` for diagnostics/coverage).
   - Status: Complete
13. Add hierarchy audit + guardrails from design (`level_conflict`, large-gap neighbor fallback protections).
   - Status: Complete
14. Align P2 default chunking policy values with redesign defaults.
   - Status: Complete

## IBAT Query Contract
- Added to `2-FSR-v2/bug-preprocessor/redesign/proposed-design-changes.md` under Phase 3.

## Progress Log
- 2026-08-07: Plan file created.
- 2026-08-07: Added `common/fsr_v2/preprocessor_v2.py` with method-wise redesign structure.
- 2026-08-07: Switched `silver/src/etl/fsr_v2/metadata_processor_v2.py` to a thin adapter for `preprocessor_v2`.
- 2026-08-07: Replaced placeholder tests with focused unit tests runnable via stdlib `unittest`.
- 2026-08-07: Static error check completed for touched files (no errors).
- 2026-08-07: Added persisted parsed-document support (`parsed_volume_path`, parser version capture, save/load helpers).
- 2026-08-07: Switched P2 to load persisted parsed docs when available and chunk region-first.
- 2026-08-07: Focused redesign unit tests passed via `python -m unittest` (11 tests).
- 2026-08-07: Enforced parse-once contract: P1 now requires `FSR_PARSED_DOC_VOLUME_ROOT`; P2 requires `parsed_volume_path` (no live parse fallback).
- 2026-08-07: Implemented TOC page-hint anchoring for heading candidate placement; retained global fallback when local page-window match is unavailable.
- 2026-08-07: Implemented strict `all_esns` semantics (structured set output), added `level_conflict` audit flag, and added large-gap guardrails for gap fallback attribution.
- 2026-08-07: Aligned P2 defaults to redesign policy (`chunk_size=2000`, `chunk_overlap=150`, `min_chunk_size=450`).
- 2026-08-07: Expanded focused unit tests and revalidated (14 tests passing).
- 2026-08-07: Code reviewed and approved by user.

## Implementation Notes
- Intentional adjustment: persisted parsed-document pointers are stored directly on `fsr_metadata_v2` (`parsed_volume_path`, `parsed_parser_version`) instead of introducing a separate pointer table in this pass.
- Reason: this keeps the change set smaller while still enabling parse-once behavior for both P1 and P2.
- Confirmed decision: no separate extraction notebook is required for this pass; parse-once enforcement is implemented within existing P1/P2 orchestration.

## Open Items
- Exciter ESN surfacing remains open by design:
   - Current behavior keeps Exciter in the Generator bucket for active-by-type aggregation.
   - Follow-up (not implemented in this pass): add dedicated `exciter_esn`, keep `gen_esn` strictly Generator-only, and update downstream consumers accordingly.

## Ready for Review Checklist
- [x] New preprocessor file created and organized.
- [x] Pydantic/Enum schema added.
- [x] `metadata_processor_v2.py` switched to new path.
- [x] Focused unit tests added.
- [x] Persisted parsed-document flow added.
- [x] Region-first chunking added.
- [x] Parse-once contract enforced end-to-end.
- [x] TOC page-hint anchoring implemented.
- [x] Strict `all_esns` semantics + hierarchy/gap guardrails implemented.
- [x] Chunking defaults aligned to redesign values.
- [x] Executable validation completed.
- [x] Final status set to Ready for Review.
- [x] Code review completed.
