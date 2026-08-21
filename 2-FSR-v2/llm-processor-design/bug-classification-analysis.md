# Bug Classification Analysis

## Scope and Method

This analysis reviews `Bugs_prepared_by_Xujin.csv` using the decision model in `llm-processor-design/README.md`.

I intentionally did not use the existing Bug_classification or fixes columns as decision inputs. I only used the bug descriptions and mapped them to the architecture rules:

- Deterministic processor fix:
  - canonical region/section boundary logic
  - ESN pattern extraction and normalization
  - active vs inactive filtering
  - section stack enter/exit behavior
  - deterministic routing to resolved/ambiguous/unresolved
- LLM preprocessor:
  - ambiguous attribution from semantic evidence
  - missing/implicit ESN where text meaning must be inferred
  - shared multi-assign sections when deterministic evidence is insufficient
  - cases that may require LLM first, then IBAT fallback

## Classification Summary

- Deterministic processor fix: 12 bugs
- LLM preprocessor: 3 bugs

## Classification Rules (Quick Summary)

Use these rules in order for each bug.

1. Classify as Deterministic processor fix when the issue is about structure, extraction, or state logic.
   - Section/header/boundary detection problems
   - ESN regex/format parsing and normalization
   - Active vs inactive ESN filtering
   - Context stack enter/exit and fallback path bugs
   - Deterministic unresolved tagging for low-information docs

2. Classify as LLM preprocessor when attribution is ambiguous and needs semantic inference.
   - Apply this category only for Bug IDs 7, 12, and 14 per review alignment.
   - These are the cases where deterministic and IBAT-first handling still leaves semantic ambiguity.

3. Use deterministic plus IBAT-first routing for all other cases.
   - If text alone cannot identify ESN, deterministic stage marks ambiguity and routes to IBAT before LLM.

4. For mixed bugs, split handling by stage.
   - Deterministic stage must detect ambiguity and avoid forced wrong assignment
   - LLM stage resolves only ambiguous canonical regions
   - IBAT stage resolves truly unresolved cases

5. Guardrail: parser quality defects are deterministic prerequisites.
   - If region boundaries are wrong, do not treat this as an LLM-first fix.
   - Fix extraction/segmentation first, then run ambiguity routing.

## Bug-by-Bug Decision Table

| Bug ID | Classification | Confidence | Why |
|---|---|---:|---|
| 1 | Deterministic processor fix | Medium | Summary/shared sections should be handled by deterministic shared-tagging rules in this version, not LLM routing. |
| 2 | Deterministic processor fix | High | ESN format detection gaps (for example variant serial formats and punctuation) are regex/normalization extraction issues. |
| 3 | Deterministic processor fix | High | Section header detection without numbering and line-break sensitivity are canonical segmentation/parser robustness issues. |
| 4 | Deterministic processor fix | High | Core failure is boundary stack and fallback logic when subsection context changes and reverts. This is deterministic control-flow correctness. |
| 5 | Deterministic processor fix | High | Active/inactive ESN misclassification due to footer contamination is deterministic filtering/scoping logic. |
| 6 | Deterministic processor fix | High | Deterministic ambiguity detection plus IBAT-first routing should prevent forced wrong assignment before any optional LLM escalation. |
| 7 | LLM preprocessor | Medium | Cross-train inconsistency and title/body semantic conflict require semantic disambiguation and likely external validation; not safely resolvable by fixed rules alone. |
| 8 | Deterministic processor fix | Medium | Document contains only a referral to another report. Processor should deterministically mark unresolved/insufficient evidence and avoid false attribution. |
| 9 | Deterministic processor fix | High | Generator-vocabulary triggers should be deterministic ambiguity rules with IBAT-first enrichment before considering LLM. |
| 10 | Deterministic processor fix | High | Phrase-level precedence rule (for example "Gas Turbine Generator" should map to Generator section) is deterministic keyword precedence logic. |
| 11 | Deterministic processor fix | Medium | QCP/PIPI standalone handling is a deterministic shared/section-policy rule in this categorization. |
| 12 | LLM preprocessor | High | No generator header but generator mentioned in short auxiliary text is semantic inference with weak structural cues. |
| 13 | Deterministic processor fix | High | Appendix sub-report TOC/header non-detection is structural parsing/segmentation. |
| 14 | LLM preprocessor | Medium | Two appendix sub-reports with no ESN in body text create attribution ambiguity; likely requires semantic inference and possibly IBAT fallback if still unresolved. |
| 15 | Deterministic processor fix | High | Incorrect fallback strategy when one equipment type exists but section boundaries are present is deterministic decision-path bug. |

## Important Nuance (Mixed Bugs)

Some bugs contain both deterministic and LLM aspects. The split above uses primary root cause.

- Bug 4: primary is deterministic boundary-state logic, but after deterministic fix it should still route unresolved same-type ESN ambiguity to LLM/IBAT instead of hard fallback.
- Bug 6: handled as deterministic in this classification; the key requirement is deterministic ambiguity detection plus IBAT-first routing to avoid forced wrong assignment.
- Bug 14: remains LLM category after deterministic and IBAT-first passes if ambiguity still remains.

## Recommended Execution Order

### Phase 1: Deterministic-first hardening (do first)

Implement these before expanding LLM scope:

1. Canonical section boundary and header detection hardening
   - Covers Bugs 3, 13, and part of 15
2. ESN extraction/normalization broadening
   - Covers Bug 2
3. Section stack enter/exit and parent-context restore
   - Covers Bug 4
4. Active/inactive ESN scoping with footer suppression
   - Covers Bug 5
5. Deterministic unresolved signaling for low-information referrals
   - Covers Bug 8
6. Rule precedence updates for lexical equipment cues
   - Covers Bug 10
7. Boundary-first mode when section evidence exists, even with one equipment type
   - Covers Bug 15

### Phase 2: LLM preprocessor routing and resolution

1. Route ambiguous regions only (not full document) for:
   - train/context inconsistency (Bug 7)
   - weak-structure auxiliary mention cases (Bug 12)
   - appendix multi-report ambiguity (Bug 14)
2. Keep IBAT-first routing before LLM for all ambiguous cases, then use LLM only for the remaining hard ambiguity.

## Final Classification Lists

### Deterministic processor fix

- 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 13, 15

### LLM preprocessor

- 7, 12, 14

## Document Coverage Map

This map shows which document instances were considered under each bug ID.

| Bug ID | Document instances seen in CSV |
|---|---|
| 1 | Most of the document |
| 2 | 0be4a3ad-7395-41ea-8ec2-e7669c9c15aa; cdd0cca4-93ba-43b0-98e5-3d1ea2312c19.; 3f5a1ea8-8f35-4e97-9a1e-a88f358e9768 |
| 3 | 35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report; 806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report; 5b688732-39f2-48d2-a887-3239f258d28b |
| 4 | 32689520-afed-4dd4-a895-20afed7dd4d2; b25c94da-d954-4283-9c94-dad954a28307; b1cdbc80-364f-4240-8dbc-80364f1240fa; fcb1511e-596a-4a56-b151-1e596afa569c; af693a98-1e5c-499d-aa10-cccc54885c64 |
| 5 | d3b1da8a-03b4-4ea6-aa7b-0482edb532ce; 111adf26-dcec-4b33-9adf-26dcec6b334e |
| 6 | b775cf29-8b42-4a83-af21-53075fef0802; b7b347fd-0b59-4c67-b609-9ad2c35105cc |
| 7 | 796f4d53-a8ad-42e1-af4d-53a8add2e1a4 |
| 8 | d9b6c08b-d098-4939-a549-d113964e3150 |
| 9 | b775cf29-8b42-4a83-af21-53075fef0802; Unit_10B_Borescope_Inspection_Spring_2026_.pdf |
| 10 | None specified in CSV |
| 11 | None specified in CSV |
| 12 | bdd56c7a-ebe5-4bf7-904a-5bb63091ba20 |
| 13 | 0be4a3ad-7395-41ea-8ec2-e7669c9c15aa; 796f4d53-a8ad-42e1-af4d-53a8add2e1a4 |
| 14 | a1f6ca9b-f5db-4f22-b6ca-9bf5db7f227a |
| 15 | 4597a853-5ffb-40bb-b0be-bd6307b0acdc; 69dfe261-34b0-4740-ab89-498e7d0072df |

## Risk Notes

- If parser quality is unstable (line breaks, TOC preservation), LLM quality will be noisy because region boundaries become unreliable.
- For ambiguous multi-ESN cases, deterministic should avoid forced assignment and emit ambiguous/unresolved status early.
- For referral-only reports (Bug 8), forcing LLM attribution may increase false positives; unresolved is safer.
