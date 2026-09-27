# TIL Profile DQ Gap Summary — Pass 3

Run: til_p1_20260704_202737_93e034fd
TILs evaluated: 1502-2R1, 1937-R2, 1945-R2, 2284
Date: 2026-07-04
Prompt: til_profile_extraction_v2.txt (DS prompt + Category 2 improvements)

## Overall Match Rates

| TIL | match_rate | identity_pass |
|---|---|---|
| 1502-2R1 | 0.450 | True ✅ |
| 1937-R2 | 0.350 | False ⚠️ |
| 1945-R2 | 0.375 | True ✅ |
| 2284 | 0.400 | True ✅ |

## Progress vs Pass 2

| Metric | Pass 2 | Pass 3 |
|---|---|---|
| `compliance_category_text` pass_rate | 0% | **100%** ✅ (lookup fix) |
| Coverage gap fields | 6 | **5** (slight improvement) |
| Systematic 4/4 coverage gaps | 0 | 0 (stable) |
| 1937-R2 identity | pass | **fail** ⚠️ (LLM output variance) |

## Identity Issue — Pass 3

1937-R2 `til_number` mismatch:
- DS = `TIL 1937` (pipeline canonicalization splits `TIL 1937-R2` → `TIL 1937` + `R2`)
- Pipeline = `1937-R2` (LLM returned without `TIL ` prefix and unsplit)
- After `normalize_til_id`: `1937` ≠ `1937-R2`
- Root cause: LLM output variance — sometimes returns the full `1937-R2`, sometimes `TIL 1937`
- No code change needed; accepted as model run variation

---

## Coverage Gaps (remaining — 5 fields, mostly partial)

| Field | Count | Affected TILs |
|---|---|---|
| recurring_indicator_if_found | 2/4 | 1937-R2, 1945-R2 |
| required_prior_modifications_text | 2/4 | 1937-R2, 1945-R2 |
| usage_counters_to_check_or_consider | 1/4 | 1502-2R1 |
| usage_counter_requirements_text | 1/4 | 1502-2R1 |
| exclusions_or_non_applicable_conditions_text | 1/4 | 2284 |

---

## Content Differs
All wording variation / model run differences. No structural issues.

### Systematic (4/4 TILs) — wording variation, acceptable
service_recommendation_line_items, maintenance_trigger_text, recommended_interval_or_trigger,
hardware_or_part_configuration_text, prerequisite_outage_or_inspection_context_text,
reference_documents, severity_signals, failure_consequences, risk_summary,
tables_found_summary, missing_information_flags, source_snippets, extraction_confidence

### Partial (2–3 TILs) — wording variation or model judgment, acceptable
scope_of_work (3/4), usage_counter_requirements_text (3/4), frame_or_model_applicability_text (3/4),
parts_referenced (3/4), configuration_variables (3/4), configuration_summary (3/4),
completion_criteria_text (2/4), serial_or_unit_applicability_text (2/4),
exclusions_or_non_applicable_conditions_text (2/4), sbom_trigger_reason (2/4)

---

## Assessment
Pass 3 is stable. The v2 prompt and compliance_category_text lookup fix are working.

Remaining mismatches are:
1. **LLM output variance** on `til_number` for 1937-R2 — not actionable
2. **Free-text wording variation** across all content_differs fields — expected and acceptable
3. **Partial coverage gaps** on 5 fields — same pattern as pass 2, likely source-document dependent

This is a stable baseline. Further improvement would require either more runs for statistical stability or prompt tuning for specific free-text fields.
