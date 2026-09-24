# TIL Discovery Workplan

Date: 2026-06-08
Primary inputs:
- TILs/input/TIL_Discovery_Architecture_Overview.md
- TILs/analysis/til-discovery-starter-brief.md

## Goal
Make Step 6 (TIL applicability re-validation) ready for predictable dev implementation by closing schema, data-contract, and evidence gaps.

## Scope for this work cycle
- In scope: Step 6 input/output contract, trigger structuring, applicability signal wiring, top-TIL prioritization.
- Out of scope: full Step 7 OSA implementation, final commercial policy automation for all edge cases.

## Priority Outcomes
1. Freeze Step 6 contract for INT-SA-001 input and INT-SA-005 output.
2. Convert `operational_triggers` from prose into deterministic JSON schema.
3. Define minimal decision policy for Q1/Q2 outputs with auditable reasoning fields.
4. Confirm data-source ownership and access path for SBOM, FSR/ER evidence, and external calculator signal.

## Execution Plan

### Workstream 1: Contract Finalization
Deliverables:
- Step 6 input schema doc (INT-SA-001 subset).
- Step 6 output schema doc (INT-SA-005 subset).
- Field-level validation rules (required vs optional, allowed enums, null policy).

Acceptance checks:
- Sample payload validates with no schema errors.
- One golden sample and one edge sample round-trip end to end.

### Workstream 2: Trigger Structuring
Deliverables:
- `operational_triggers` JSON model covering FFH/FFS/ECRT thresholds.
- Mapping guide from extracted prose to normalized fields.
- Unknown/ambiguous trigger handling policy.

Acceptance checks:
- At least 25 pilot TIL profiles parse into JSON with no manual edits.
- Ambiguous trigger cases produce explicit `confidence` and `requires_review` flags.

### Workstream 3: Applicability Logic (Q1)
Deliverables:
- Decision table for `Applicable | Not Applicable | Conditional | Baseline-Equivalent`.
- Rule precedence across profile signals, unit counters, SBOM evidence, and prior FSR/ER completion.
- Reasoning template for auditable output.

Acceptance checks:
- Reproducible verdicts for repeated runs on same payload.
- Conflict cases (for example: trigger says apply, SBOM missing part) return deterministic conditional outcomes.

### Workstream 4: Work Generation Signal (Q2)
Deliverables:
- Mapping approach from `service_recommendation_line_items` to WBS-ready activity labels.
- Initial label dictionary for highest-volume TIL set.
- Placeholder policy when no reliable label mapping exists.

Acceptance checks:
- Top-priority TILs generate stable, non-empty activity labels.
- Unmapped cases are explicitly flagged, not silently dropped.

## Top TILs to start with
Based on current notes, prioritize this implementation order:
- 1509
- 1638
- 1603
- 1907
- 1937
- 1945
- 1724

Reason:
- Highest observed share of historical volume and strongest near-term impact.

## Open Decisions
1. Canonical source of truth for TIL profiles at runtime.
2. Where baseline-equivalency logic lives (Step 6 engine vs external template service).
3. Minimum evidence needed to emit `Applicable` without manual review.
4. Final owner for deterministic PO recommendation policy in Step 6 output.

## Risks and Mitigations
- Risk: Schema drift between ISM and SDG payload versions.
  Mitigation: versioned schema IDs and backward-compatible optional fields only.
- Risk: Over-reliance on prose extraction quality.
  Mitigation: strict JSON trigger normalization and fallback review flags.
- Risk: Missing source joins for SBOM/FSR evidence in early runs.
  Mitigation: treat missing evidence as explicit conditional path, not not-applicable.

## Suggested 2-Week Sprint Cut
Week 1:
- Freeze contract.
- Implement trigger JSON normalization for pilot set.
- Build first decision table for Q1.

Week 2:
- Add SBOM + calculator signal wiring.
- Validate top-priority TIL subset end to end.
- Produce readiness report with pass/fail checklist.

## Definition of Ready for Step 6 Dev Build
- Contract docs approved and versioned.
- Pilot payload fixtures available in dev.
- Trigger normalization passes on pilot set.
- Decision table signed off for Q1 statuses.
- Known unresolved items logged with owners and due dates.