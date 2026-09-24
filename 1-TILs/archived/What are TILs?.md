# TIL Quick Reference

## What are TILs?
TILs are Technical Information Letters used in outage scoping. In the SDG 9-step flow, TIL applicability is Step 6 and acts as the first major AI validation step.

## What information do TILs contain?
Current extracted/profiled fields include:
- compliance category
- operational triggers (for example FFH/FFS/ECRT conditions)
- part references and inspection tags
- service recommendation line items
- usage-counter requirements
- scope text and supporting extracted document content

## What format are TIL documents?
- Primary source format: PDF
- Working extraction artifacts: markdown files (profile + extracted content)
- Integration exchange format between systems: structured payload (JSON contract)

## What is the data volume?
Known planning numbers from current architecture notes:
- 31 TILs per event (29 GT + 2 Gen)
- 4,011 of 7,007 historical outage workscopes contain TIL references (57%)
- Initial pilot coverage references 25 TILs

## What are the OSA-agent requirements related to TIL?
Only high-level linkage is confirmed in current notes: OSA is Step 7 and follows Step 6 outputs. Detailed Step 7 field contract and acceptance criteria are still open and should be documented separately.

## What should we start with first?
1. Finalize INT-SA-001 input and INT-SA-005 output contract boundaries for Step 6.
2. Convert operational trigger prose into deterministic JSON.
3. Lock decision policy for Q1 statuses: Applicable, Not Applicable, Conditional, Baseline-Equivalent.
4. Confirm source-of-truth and access for SBOM, FSR/ER evidence, and calculator outputs.

## What are the biggest unknowns?
- Final integration mechanism and runtime payload location.
- Baseline-equivalency detection design.
- Deterministic policy ownership for PO recommendation.
- Complete Step 7 OSA schema and acceptance tests.

## Where to go deeper
- Architecture narrative: TILs/input/TIL_Discovery_Architecture_Overview.md
- Discovery notes: TILs/analysis/til-discovery-starter-brief.md
- Execution plan: TILs/analysis/til-discovery-workplan.md