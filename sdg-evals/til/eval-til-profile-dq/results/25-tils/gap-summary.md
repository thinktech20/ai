# 25-TIL Eval Summary

## Overall
- TILs evaluated: 25
- Run ID: til_p1_20260704_235852_30f3ba3a
- Average match rate: 0.41
- Median match rate: 0.40
- Min/Max match rate: 0.325 / 0.575
- Identity pass: 16/25
- Identity fail: 9/25

## Identity Fails
- 1562-R1
- 1584-R1
- 1615-R1
- 1850-R3
- 1907-R1
- 1937-R2
- 2045-R2
- 2342-R1
- 2558

### Identity mismatch pattern
- til_number mismatches: 7 (mostly revision handling differences like "TIL 1562-R1" vs "TIL 1562")
- title mismatches: 3 (OCR/spelling/style differences)
- revision mismatches: 0

## Strong Fields (pass_rate >= 0.75)
- revision (1.00)
- publish_date (1.00)
- compliance_category_code (1.00)
- combustion_or_fuel_configuration_text (0.96)
- mli_numbers (0.96)
- safety_or_damage_language_found (0.96)
- reason_for_revision (0.92)
- configuration_dependent (0.92)
- title (0.88)
- compliance_category_text (0.88)
- usage_counters_to_check_or_consider (0.76)
- sbom_dependency_flag (0.76)

## Low/Zero Fields
- Zero pass-rate fields include: service_recommendation_line_items, maintenance_trigger_text, recommended_interval_or_trigger, hardware_or_part_configuration_text, prerequisite_outage_or_inspection_context_text, parts_referenced, severity_signals, risk_summary, tables_found_summary, missing_information_flags, source_snippets, extraction_confidence.

## Top Coverage Gaps (DS has value, pipeline empty)
- recurring_indicator_if_found: 16
- exclusions_or_non_applicable_conditions_text: 6
- completion_criteria_text: 4
- required_prior_modifications_text: 4
- sbom_trigger_reason: 4
- tables_found_summary: 4

## Notes
- A large share of low pass-rate fields are structure/wording differences rather than total extraction failure.
- Identity failures are primarily til_number formatting/revision representation drift.
