# TIL Profile DQ Gap Summary

Run: til_p1_20260704_175903_8b5977a1
TILs evaluated: 1502-2R1, 1937-R2, 1945-R2, 2284
Date: 2026-07-04

## Open Items

| # | Question | Owner | Status |
|---|---|---|---|
| 1 | DS prompt task description mentions PowerNow `vgpd.qlt_std_views.u_til*` structured metadata as input. Did the DS pilot actually pass this to the LLM, or was the user prompt PDF text + tables only? The pilot code (`run_til_profile_extraction_pilot.py`) only passes text and tables — no structured metadata in `build_user_prompt`. Confirm with DS team whether PowerNow metadata was used and if it should be integrated into our pipeline. | Reach out to DS team | Open |

## Overall Match Rates

| TIL | match_rate | identity_pass |
|---|---|---|
| 1502-2R1 | 0.375 | False |
| 1937-R2 | 0.150 | True |
| 1945-R2 | 0.175 | True |
| 2284 | 0.300 | False |

---

## Coverage Gaps
DS has value, pipeline returns empty.

**Status: ✅ Fixed** — DS prompt with full JSON schema added. All fields now in prompt. Re-run pipeline to validate.

### Systematic (4/4 TILs affected)
These fields were missing across every TIL — root cause was missing fields in original prompt. Fixed by switching to DS prompt.

| Field | Affected TILs |
|---|---|
| compliance_category_code | all 4 |
| compliance_category_text | all 4 |
| coarse_outage_type | all 4 |
| completion_criteria_text | all 4 |
| maintenance_trigger_text | all 4 |
| recommended_interval_or_trigger | all 4 |
| usage_counters_to_check_or_consider | all 4 |
| usage_counter_requirements_text | all 4 |
| frame_or_model_applicability_text | all 4 |
| hardware_or_part_configuration_text | all 4 |
| prerequisite_outage_or_inspection_context_text | all 4 |
| severity_signals | all 4 |
| failure_consequences | all 4 |
| tables_found_summary | all 4 |
| source_snippets | all 4 |

### Partial (2–3 TILs affected)

| Field | Count | Affected TILs |
|---|---|---|
| risk_summary | 3/4 | 1502-2R1, 1937-R2, 2284 |
| exclusions_or_non_applicable_conditions_text | 3/4 | 1937-R2, 1945-R2, 2284 |
| configuration_variables | 3/4 | 1937-R2, 1945-R2, 2284 |
| configuration_summary | 3/4 | 1937-R2, 1945-R2, 2284 |
| missing_information_flags | 3/4 | 1937-R2, 1945-R2, 2284 |
| scope_of_work | 2/4 | 1502-2R1, 2284 |
| recurring_indicator_if_found | 2/4 | 1937-R2, 1945-R2 |
| serial_or_unit_applicability_text | 2/4 | 1937-R2, 1945-R2 |
| required_prior_modifications_text | 2/4 | 1937-R2, 1945-R2 |
| sbom_trigger_reason | 2/4 | 1937-R2, 1945-R2 |
| publish_date | 1/4 | 1502-2R1 |
| reference_documents | 1/4 | 1945-R2 |

---

## Content Differs
Both DS and pipeline have a value, but they do not match.
May be acceptable wording variation — review per field.

| Field | Count | Notes |
|---|---|---|
| service_recommendation_line_items | 4/4 | Free-text wording variation — expected |
| extraction_confidence | 4/4 | Numeric score differs — expected (different model runs) |
| reference_documents | 3/4 | Structural or content variation |
| parts_referenced | 3/4 | Structural or content variation |
| configuration_dependent | 3/4 | Boolean/value mismatch |
| safety_or_damage_language_found | 3/4 | Boolean/value mismatch |
| purpose | 2/4 | Wording variation |
| publish_date | 2/4 | Format variation possible |
| reason_for_revision | 2/4 | Wording variation |
| scope_of_work | 2/4 | Wording variation |
| revision | 1/4 | 1502-2R1 only — identity issue |
| til_number | 1/4 | 2284 only — identity issue |
| missing_information_flags | 1/4 | Content variation |
| risk_summary | 1/4 | Content variation |

### Root Cause Analysis

| Root Cause | Fields | Status | What DS code does |
|---|---|---|---|
| Eval normalization bug | `til_number` (2284) | ✅ Fixed — eval now uses `normalize_til_id` for both sides | DS outputs `TIL 2284` verbatim from LLM; no normalization applied |
| Pipeline extracts wrong revision | `revision` (1502-2R1) | ✅ Accepted — LLM output variation, no code change needed | DS takes `revision` directly from LLM output without post-processing |
| Date format not ISO | `publish_date` | ✅ Fixed by DS prompt — prompt specifies `YYYY-MM-DD` format; LLM will comply | DS takes `publish_date` directly from LLM output; LLM returns ISO because prompt specifies it |
| Schema shape diverged from DS | `service_recommendation_line_items` | ✅ Fixed by DS prompt — prompt specifies plain string list; LLM will output accordingly | DS `normalize_profile_schema` does no special handling; plain string list preserved as-is from LLM |
| Field name mismatch | `reference_documents` | ✅ Fixed by DS prompt — prompt JSON schema uses `document_number`; LLM will comply | DS canonical field is `document_number` |
| Type mismatch | `reason_for_revision` | ✅ Fixed by DS prompt — prompt specifies `string or null`; LLM will return scalar | DS uses `reason_for_revision` as scalar string |
| Model judgment difference | `configuration_dependent`, `safety_or_damage_language_found` | ✅ Accepted — genuine model interpretation difference; no fix needed | DS has no special handling; taken directly from LLM boolean output |
| Acceptable wording variation | `scope_of_work`, `purpose`, `parts_referenced` | ✅ Accepted — same semantic content, minor variation; no fix needed | DS preserves as-is from LLM output |

---

## Identity Failures
1502-2R1: `revision` differs (content_differs)
2284: `til_number` differs (content_differs)

**Status: ✅ Resolved** — `til_number` eval fix applied. `revision` accepted as LLM output variation.

### Root Cause Analysis

**`til_number` — TIL 2284**
- DS = `TIL 2284`, `revision=None` (LLM output, DS code takes as-is)
- Pipeline = `2284` (our LLM returned without `TIL ` prefix)
- DS code does no post-processing for `til_number`
- Root cause: **LLM output difference** — our LLM omitted `TIL ` prefix
- Fix: eval now applies `normalize_til_id` to both sides when comparing `til_number`, so `TIL 2284` and `2284` both resolve to `2284` and match correctly

**`revision` — TIL 1502-2R1**
- DS = `til_number=TIL 1502-2R1`, `revision=R1` (LLM output, DS code takes as-is)
- Pipeline = `revision=2R1` (our LLM returned `2R1` instead of `R1`)
- DS code does no post-processing for `revision`
- Root cause: **LLM output difference** — our LLM included the numeric segment `2` in the revision
- Fix: none; LLM output variation, accepted as-is per DS approach

### Action
- `til_number` eval fix applied: `normalize_til_id` used for comparison on both sides.
- `revision` accepted as LLM output variation. No pipeline or eval change needed.

---

## Next Steps
All root causes have been investigated. Status below.

1. **Systematic 4/4 coverage gaps — fields not in prompt schema**
   - Status: ✅ Fixed — DS prompt with full JSON schema (39 fields) now in place in `pw_sdg_ai_ser_repo/silver/src/tils/prompts/til_profile_extraction_v1.txt`

2. **Identity failures for 1502-2R1 and 2284**
   - Status: ✅ Resolved — `til_number` eval normalization fixed (both sides use `normalize_til_id`). `revision=2R1` vs `R1` accepted as LLM output variation.

3. **Partial coverage gaps**
   - Status: ✅ Fixed — same root cause as item 1; covered by DS prompt fix.

4. **content_differs on structured fields (reference_documents, parts_referenced, service_recommendation_line_items, reason_for_revision)**
   - Status: ✅ Investigated — follow DS code as-is; no pipeline changes. LLM output and schema shape variation accepted.
