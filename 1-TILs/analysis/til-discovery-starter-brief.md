# TIL Discovery Starter Notes and Brief

Date: 2026-06-05
Sources reviewed:
- TILs/input/TIL_Discovery_Architecture_Overview.md
- TILs/input/TILs - Discussion.docx

## Starter Questions
1. What are TILs?
2. What information they contain?
3. What are the format of documents for TILs?
4. What is the volume of data?
5. What are the requirements around TILs for OSA Agent?
6. What are the most critical thngs to start with?
7. What are the unknowns?
8. Anything else?

## Brief (Evidence-Based)

### 1) What are TILs?
- TIL means Technical Information Letter.
- In the 9-step flow, TIL is Step 6 in SDG.
- ISM provides pre-dispositioned TIL candidates; SDG re-validates (not first-pass discovery).
- SDG returns per-TIL, per-ESN verdict and reasoning back to ISM.

### 2) What information they contain?
From the architecture overview and transcript, extracted/profiled TIL information includes:
- compliance_category
- operational_triggers
- part_numbers with inspection_type tags
- service_recommendation_line_items
- usage_counter_requirements
- scope_of_work
- raw extracted text/image descriptions for lookup

Step 6 is expected to answer:
- Does it apply to this unit?
- What work does it generate?
- Who pays?

### 3) What are the format of documents for TILs?
- Primary source format: PDF.
- Current extraction outputs shown as markdown artifacts:
  - profile_response.md
  - extracted_document.md
- Integration payload between ISM and SDG is discussed as JSON contract/payload.

### 4) What is the volume of data?
Confirmed numbers in source materials:
- 31 TILs per event (29 GT + 2 Gen).
- 4,011 of 7,007 outage workscopes include TIL references (57%).
- A 25-TIL pilot is referenced for extraction/applicability work.

Scale note from discussion:
- Production is expected to be much larger than pilot examples, but exact production sizing is not finalized in these docs.

### 5) What are the requirements around TILs for OSA Agent?
- Confirmed at high level only: OSA is Step 7 and is described as a similar re-validation pattern with a different object.
- No detailed OSA schema, field contract, or acceptance criteria are defined in the reviewed inputs.

### 6) What are the most critical thngs to start with?
Recommended starting points directly supported by current docs:
- Finalize ISM-SDG contract for Step 6 input/output payloads.
- Complete operational_triggers structuring from prose to JSON.
- Confirm data access patterns for unit context, SBOM, FSR/ER, and external calculator signal.
- Define activity-label mapping for generated work (Q2).
- Keep ownership boundary clear:
  - SDG: verdict, reasoning, recommendations
  - ISM: schedule/WBS insertion and final decision

### 7) What are the unknowns?
Open items explicitly unresolved in current material:
- Integration mechanism details (API vs pickup/store pattern).
- Exact source views/tables for all Step 6 supporting inputs.
- Baseline-equivalency extraction/cross-check behavior.
- Deterministic PO rule implementation for Q3.
- Detailed OSA requirements and contract.

### 8) Anything else?
- The discussion emphasizes train/event context where one event can involve multiple ESNs/equipment, and mapping can be many-to-many.
- TIL documents are treated as static source docs; extracted profiles act as reusable knowledge artifacts.

## Suggested Next Discovery Checklist
1. Get the latest ISM-SDG interface spec (INT-SA-001 in, INT-SA-005 out).
2. Verify where payloads live in dev (table/view/object store/API).
3. Pull 3-5 real event samples and trace end-to-end Step 6 inputs to expected verdict outputs.
4. Capture OSA Step 7 contract separately (fields, decisions, acceptance tests).
5. Convert unresolved items above into owner-tagged questions for architecture sync.
