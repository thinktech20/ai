# TIL Profile Comparison Plan (AI Parse Doc vs DS Baseline)

## Goal
Compare pipeline profile outputs against DS baseline in three batches:
1. First 1 TIL
2. Next 5 TILs
3. Next 10 TILs

## Current Status (Updated)
- Script is now lightweight (exact normalized comparison only, no similarity scoring).
- Multiple fix waves were applied in pipeline code and pushed on `feature/706551_til_pipeline`.
- Latest second-run comparison (`til-metadata-2.csv`) overlap is 2 TILs: `1502-2R1`, `1945-R2`.
- `1937-R2` currently exists in export but is `llm_parse_failed` due to gateway read timeout.

## Resolution Snapshot (2026-07-03)

Status legend: `resolved`, `in_progress`, `pending`.

1. Canonicalize `til_number` vs `revision` — `resolved`
2. Tighten `parts_referenced` extraction rules — `resolved`
3. Fix `coarse_outage_type` over-collapse — `in_progress`
4. Improve table-to-profile mapping for `parts_referenced` — `in_progress`
5. Preserve interval logic in `service_recommendation_line_items` — `in_progress`
6. Preserve operational detail in `scope_of_work` — `in_progress`
7. Remove duplicate table payload from prompt path — `resolved`
8. Revisit explicit `max_tokens` after prompt cleanup — `resolved` (gateway-default mode enabled)
9. Add explicit failure classification for output-budget exhaustion — `resolved`
10. Reduce over-compression on narrative TILs — `in_progress`
11. Add validation flags for suspicious profile shapes — `resolved`
12. Refactor notebook code without losing troubleshooting visibility — `pending`

Latest generic additions applied after second-run review:
- Preserve dropped generic component detail in `hardware_or_part_configuration_text` when filtering `parts_referenced` entries without explicit `part_number`.
- Add table-driven fallback enrichment for explicit `parts_referenced` part numbers (regex-based on parser table content, no TIL-specific branching).

## Working Branch Context
- Pipeline repo: `/home/u560060992/dbx/pw_sdg_ai_ser_repo`
- Active branch: `feature/706551_til_pipeline`
- Note: `1-TILs` folder is not a git repo; branch context applies to pipeline code changes.

### Completed Today
- Ran latest second-run comparison using:
  - `python3 compare_til_profiles.py --our-metadata-csv metadata-table-results/til-metadata-2.csv --tils 1502-2R1 1937-R2 1945-R2`
- Latest output folder:
  - `outputs/compare_20260703_142225/`
- Validated mismatch focus for current run:
  - `1502-2R1`: identity and compression issues remain
  - `1945-R2`: parsing recovered; detail coverage gap remains
  - `1937-R2`: excluded due to gateway timeout (`llm_parse_failed`)

### Current Blocker
- Comparison depth is currently blocked by unstable overlap and one timeout:
  - overlap in latest run is 2/3 requested TILs
  - `1937-R2` failed with gateway read timeout, so it cannot be compared yet

## Sources
- DS baseline root:
  - `/home/u560060992/dbx/1-TILs/analysis/ds-team-til-profile-results/til_profile_pilot_20260609_110447/til_profile_pilot_20260609_110447`
- Current pipeline output (active comparison export):
  - `/home/u560060992/dbx/1-TILs/compare-til-profile/metadata-table-results/til-metadata-2.csv`

## Matching Logic
- Primary comparison key: normalized TIL id.
- DS key: `requested_til` from each `profile_response.json`.
- Current key: `matched_til_number` from metadata export CSV in `metadata-table-results/`.
- Normalization:
  - uppercase
  - remove leading `TIL `
  - remove spaces

## Plan Hygiene Fixes (Moved To Active Queue)

These were open documentation/process gaps and are now tracked as explicit fixes.

1. Keep status sections aligned with latest run outputs and overlap counts.
2. Keep source paths aligned to the actively used metadata export file.
3. Keep run commands aligned to current script invocation pattern.
4. Track implementation sequence with explicit status (`resolved`, `in_progress`, `pending`).
5. Add a verification checkpoint for table-part fallback enrichment impact.

## Comparison Rules (Lightweight)
- Exact normalized comparison only.
- Lists are compared order-insensitive via normalized sorted values.
- Null handling: null/empty/NA variants treated as empty.

## Fields Compared
- `til_number`
- `revision`
- `title`
- `publish_date`
- `compliance_category_code`
- `coarse_outage_type`
- `scope_of_work`
- `service_recommendation_line_items`
- `parts_referenced`
- `extraction_confidence`

## How To Run (Current Script)
- Phase 1 (first record):
  - `python3 compare_til_profiles.py --phase 1 --offset 0`
- Next 5 (after first 1):
  - `python3 compare_til_profiles.py --phase 5 --offset 1`
- Next 10 (after first 1+5):
  - `python3 compare_til_profiles.py --phase 10 --offset 6`
- Focused rerun on current target TILs with latest export:
  - `python3 compare_til_profiles.py --our-metadata-csv metadata-table-results/til-metadata-2.csv --tils 1502-2R1 1937-R2 1945-R2`

## Outputs
Each run writes to `outputs/compare_<timestamp>/`:
- `summary.csv`
- `mismatch_details.jsonl`
- `run_info.json`

## Tomorrow Restart Plan
1. Re-run pipeline for more TILs that also exist in DS baseline set.
2. Refresh export file in `metadata-table-results/` (for example `til-metadata-<run>.csv`).
3. Verify overlap count again.
4. Run phase 5 and phase 10 commands above.
5. Share mismatch summary for review.

## Fix List From Current Comparison Review

This fix list is based on review of:
- `1502-2R1`
- `1937-R2`

Implementation guardrail:
- Fixes must be generic across TILs.
- Do **not** add TIL-specific conditions such as `if til_number == ...` or one-off parsing rules for specific documents.
- Target behavior should improve the contract for all TILs, especially table-heavy and revisioned documents.

Priority order is by impact on correctness, not implementation effort.

### P0: Correctness bugs

1. **Canonicalize `til_number` vs `revision`**
   - Problem seen on `1937-R2`:
     - DS: `til_number = "TIL 1937"`, `revision = "R2"`
     - Ours: `til_number = "TIL 1937-R2"`, `revision = "R2"`
   - Required fix:
     - strip revision suffix from `til_number` when `revision` is separately present
     - keep `revision` as the only revision field

2. **Tighten `parts_referenced` extraction rules**
   - Problem seen on `1502-2R1`:
     - generic hardware/context mentions are being emitted as parts
   - Required fix:
     - only include explicit part-number-like references or true structured part entries
     - do not treat CDC / blade rows / generic component mentions as `parts_referenced`

3. **Fix `coarse_outage_type` over-collapse**
   - Problem seen on `1937-R2`:
     - ours collapsed to `Major Inspection`
     - DS has broader trigger semantics (`Next Scheduled Outage`)
   - Required fix:
     - prefer document-level outage/trigger summary over repeated maintenance subtype phrases

### P1: Structured extraction gaps

4. **Improve table-to-profile mapping for `parts_referenced`**
   - Problem seen on `1937-R2`:
     - DS extracts many table-driven part numbers; ours under-extracts
   - Required fix:
     - strengthen prompt / post-processing for table-heavy TILs
     - ensure ai_parse table content survives into profile in a more structured way

5. **Preserve interval logic in `service_recommendation_line_items`**
   - Problem seen on `1937-R2`:
     - ours summarizes too aggressively and loses inspection interval distinctions
   - Required fix:
     - preserve config-dependent timing/trigger clauses
     - avoid flattening interval tables into generic recommendation bullets

6. **Preserve operational detail in `scope_of_work`**
   - Problem seen on `1937-R2`:
     - ours compresses staffing, duration, and prerequisite details
   - Required fix:
     - keep key execution details when present (cleaning method, blade removal prerequisite, duration)

7. **Remove duplicate table payload from the prompt path**
   - Problem seen on long/table-heavy TILs like `1945-R2`:
     - current pipeline appends table content into `pdf_text`
     - and also passes the same tables again as structured `labeled_tables` JSON to the prompt
   - Why this matters:
     - increases prompt size significantly
     - likely contributed to `1945-R2` hitting output-budget exhaustion
   - Required fix:
     - do not send the same table content twice
     - keep structured table JSON, but avoid duplicating full table payload inside main document text

8. **Revisit explicit `max_tokens` after prompt cleanup**
   - DS behavior:
     - truncates extracted text to 40,000 chars
     - does not set explicit `max_tokens` in the shared runtime helper
   - Our current behavior:
     - truncates text to 40,000 chars
     - sets explicit `max_tokens = 16000`
   - Required fix:
     - after prompt de-duplication, test DS-style behavior where the gateway/model default decides output length
     - do not change char limit first; DS also uses 40,000 chars

9. **Add explicit failure classification for output-budget exhaustion**
   - Problem seen on `1945-R2`:
     - `finish_reason = length`
     - `message.content = null`
     - high reasoning-token consumption, no usable output text
   - Required fix:
     - classify this separately from generic `llm_parse_failed`
     - capture enough telemetry to distinguish:
       - no-text response
       - malformed JSON response
       - request failure

### P2: Quality improvements (not hard bugs)

10. **Reduce over-compression on narrative TILs**
   - Problem seen on `1502-2R1`:
     - `scope_of_work` and recommendations are semantically close but more compressed than DS output
   - Improvement goal:
     - retain detail without forcing exact DS wording

11. **Add validation flags for suspicious profile shapes**
   - Suggested rules:
     - if `til_number` still contains revision and `revision` is populated, flag it
     - if extracted tables > 0 and `parts_referenced` is empty for table-heavy docs, flag it
     - if `parts_referenced` contains entries with no explicit part number, flag for review

12. **Refactor notebook code without losing troubleshooting visibility**
   - Current issue:
     - `nb_sdg_til_metadata.py` mixes runtime setup, extraction, prompt shaping, canonicalization, persistence, and MLflow logging in one notebook body
   - Requirement:
     - any refactor must preserve current notebook-run logging quality
   - Guardrail:
     - keep notebook as execution shell / log surface
     - shared modules may hold logic, but must log through the same logger family and not swallow exceptions
   - Success criteria:
     - same high-signal run logs remain visible during notebook execution (`pending -> processing`, parser warnings, LLM warnings, completion/failure lines)

### Suggested implementation sequence

1. Fix `til_number` / `revision` canonicalization (`resolved`)
2. Tighten `parts_referenced` eligibility rules (`resolved`)
3. Remove duplicate table payload from prompt construction (`resolved`)
4. Improve `coarse_outage_type` extraction behavior (`in_progress`)
5. Re-test `1945-R2` after prompt cleanup (`in_progress`)
6. Revisit explicit `max_tokens` behavior only after prompt cleanup (`resolved`)
7. Re-run `1937-R2` and `1502-2R1` (`in_progress`)
8. Re-compare against DS baseline before widening to more TILs (`in_progress`)
9. Validate table-part fallback enrichment impact on `parts_referenced` coverage (`in_progress`)

## DS Normalization Review Notes

Source reviewed:
- `/home/u560060992/dbx/SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_til_profile_extraction_pilot.py`

Key conclusion:
- DS SME-signed-off behavior is not defined by normalization alone.
- The signed-off quality comes from the combination of:
  - Foundation extraction output
  - `labeled_tables` + cleaned document text in the prompt
  - LLM profile extraction
  - light post-LLM normalization

Implication for our implementation:
- We should treat DS normalization as the minimum output contract.
- We should not assume copying normalization alone will reproduce DS-quality results.
- Our output must be **no less complete** than DS on correctly extracted fields.
- Improvements are allowed only if they preserve DS-correct outputs and add signal rather than changing meaning.

### DS normalization contract we must preserve

The DS code guarantees these optional fields exist even when empty/null:
- `usage_counters_to_check_or_consider`
- `usage_counter_requirements_text`
- `frame_or_model_applicability_text`
- `combustion_or_fuel_configuration_text`
- `hardware_or_part_configuration_text`
- `serial_or_unit_applicability_text`
- `exclusions_or_non_applicable_conditions_text`
- `required_prior_modifications_text`
- `prerequisite_outage_or_inspection_context_text`
- `mli_numbers`
- `parts_referenced`
- `reference_documents`
- `tables_found_summary`
- `source_snippets`

The DS code also lightly normalizes nested shapes for:
- `mli_numbers`
- `parts_referenced`

### What normalization does NOT solve in DS code

The DS normalization does **not** fix these by itself:
- base `til_number` vs `revision` separation
- over-compressed `scope_of_work`
- over-compressed `service_recommendation_line_items`
- wrong `coarse_outage_type` abstraction
- weak table-to-`parts_referenced` conversion
- prompt duplication / output-budget exhaustion issues

So these remain implementation work in our pipeline, not just schema-default work.

### Guardrail before implementation

Before making pipeline changes:
1. Preserve the DS field contract exactly or as a strict superset.
2. Do not reduce richness from `ai_parse_document` just to match DS wording.
3. Validate every fix against DS outputs for known-good TILs.
4. Accept improvements only when DS-correct fields remain correct and additional detail is additive.
5. Keep implementation generic; no document-specific branches or TIL-specific parsing exceptions.
6. If code is reorganized, preserve notebook-level troubleshooting logs and exception visibility.

### DS script review note on TIL-specific logic

The reviewed DS script does not appear to use TIL-specific parsing logic.

What it does use:
- generic TIL selection for pilot inputs
- generic exact/base revision matching
- generic extraction method switching (`foundation`, `pdfplumber`, `auto`)
- generic prompt + normalization flow

So our fixes should follow the same pattern:
- improve generic prompting
- improve generic post-LLM canonicalization
- improve generic table-to-structure mapping
- avoid hardcoding behavior for specific TIL ids
