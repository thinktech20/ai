# Debug Plan: FSR ESN/Equipment-Type Mismatch (Issue 29083)

## Goal

Identify where the mismatch is introduced for this document:

- Header/footer indicate `270T483`
- Executive summary body references `290T483`
- Metadata/map currently surface `270T483` + `Generator`

Target output of this plan:

1. Confirm whether the issue originates in preprocessor extraction, enrichment/mapping, chunk attribution, or retrieval filters.
2. Produce a minimal fix scope (code/config/data correction) with evidence.

---

## Scope Document

- `35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270T483-Final_Master_Report.pdf`

---

## Working Hypotheses

1. Preprocessor doc-level ESN extraction may over-weight title/footer tokens (`270T483`) versus section-body context (`290T483`).
2. Region extraction may be incomplete or misbounded, causing incorrect primary attribution to propagate.
3. IBAT/EV enrichment may be swapping semantic meaning between `equipment_type` and `driven_equipment`.
4. Chunk-level merge priority could be correct, but wrong source metadata is being fed into it.
5. `fsr_pdf_ref` may contain historical inconsistencies (`270T83` noted in issue) that can confuse manual validation.

---

## Step-by-Step Debug Flow (Architecture Aligned)

## P0: Build a Repro Packet

Run these once and save results in this folder for traceability.

```sql
-- Canonical metadata row
SELECT *
FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
WHERE document_id = '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report';

-- Document equipment map rows
SELECT *
FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2
WHERE document_id = '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report';

-- Chunk-level attribution sample
SELECT document_id, chunk_id, primary_esn, primary_equip_type, metadata
FROM vaid.ai_std_con_field_service_report.fsr_chunks_v2
WHERE document_id = '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report'
LIMIT 200;
```

Expected:

- Single resolved `document_id`
- Complete view of doc-level vs chunk-level attribution for that document

---

## P1-A: Run Preprocessor in Isolation (First Priority)

Objective: validate what preprocessor alone returns before LLM and enrichment.

Actions:

1. Run only the preprocessor logic on this PDF text (same parser version used in prod run).
2. Capture full preprocessor output:
	- `metadata`
	- `hints`
	- `regions` with `start/end` and region-level ESN/equipment fields
3. Save raw JSON output under this folder for later comparison.

What to check:

1. Doc-level `primary_esn`, `primary_equip_type`
2. Any extracted secondary ESNs (does `290T483` appear?)
3. Region-level attribution near the executive summary section (page 3 context)
4. Inactive flags and region coverage gaps (unattributed spans)

Decision:

- If preprocessor output is already wrong, root cause is in parser+preprocessor logic/rules.
- If preprocessor output is correct, move downstream (merge/enrichment/chunking/retrieval).

---

## P1-B: Validate Parser Impact

Objective: isolate whether parser text shape is causing extraction drift.

Actions:

1. Re-run preprocessor with current parser (`pypdf2_v1.0`) and one alternate parser used by v2 (`pdfplumber_v1.0`, if available).
2. Compare extracted tokens around:
	- cover/header/footer mentions of `270T483`
	- executive summary sentence containing `290T483`
3. Compare resulting preprocessor `metadata/hints/regions` between parser variants.

Expected:

- If parser swap changes ESN attribution, parser layout artifacts are likely causal.

---

## P1-C: Validate Document Merge + Enrichment

Objective: confirm if good preprocessor values are being overwritten or mis-enriched.

Checks:

1. Compare preprocessor output vs final `fsr_metadata_v2` row field-by-field.
2. Verify merge precedence actually applied as intended (preprocessor authoritative for ESN/equip fields).
3. Trace IBAT/EV joins for `270T483` and `290T483`:

```sql
SELECT equipment_sys_id, equip_serial_number, driven_equipment, equipment_type
FROM vgpd.prm_std_views.IBAT_EQUIPMENT_MST
WHERE equip_serial_number IN ('270T483','290T483');
```

Focus:

- Whether downstream code maps `driven_equipment` vs `equipment_type` consistently
- Whether enrichment is replacing type fields when it should only supplement

---

## P1-D: Validate Map Materialization (Stage 5)

Objective: ensure `document_equipment_map_v2` is built from the intended in-memory attribution.

Checks:

1. Re-run P1 for this single document in an isolated run scope.
2. Inspect map rows generated before MERGE (debug print/log capture).
3. Compare pre-MERGE rows with persisted map rows.

Expected:

- Map should include every attributed ESN from regions/doc-level logic.
- If `290T483` never appears in map despite region evidence, Stage 5 build logic is suspect.

---

## P2: Validate Chunk Attribution Merge

Objective: verify region-overlap merge picks the expected ESN/equipment for chunks in the executive summary area.

Actions:

1. Re-run chunking only for this document.
2. For sample chunks near the sentence mentioning `290T483`, log:
	- `chunk_start`, `chunk_end`
	- best-overlap region start/end
	- selected region metadata
	- final `primary_esn` and `primary_equip_type`
3. Compare with chunk metadata persisted in `fsr_chunks_v2`.

Expected:

- Chunks covering page-3 executive summary should map to the ESN/equipment indicated by the region they overlap most.

---

## P3: Validate Index Sync

Objective: confirm corrected chunk metadata reaches vector index.

Checks:

1. Verify chunk rows are updated first.
2. Run index sync.
3. Query index for this `document_id` and inspect returned `primary_esn` / `primary_equip_type` fields.

Expected:

- Index payload matches source chunk table after sync.

---

## P4/P5: Validate Retrieval Gates and Results

Objective: determine user-facing impact and detect where filtering masks/exposes issue.

Checks:

1. Data readiness query path (`GET /equipment/{esn}` behavior):
	- test with `270T483`
	- test with `290T483`
2. Retrieval query path (`POST /retrieve` behavior):
	- query with both ESNs and same prompt text
3. Inspect if results are coming from:
	- strict primary_esn filter path
	- fallback unattributed-chunk path

Expected:

- If map and chunks are correct, both APIs should behave consistently with equipment context.

---

## Evidence Matrix to Fill During Debug

| Stage | Evidence Artifact | Status | Notes |
|---|---|---|---|
| P1-A Preprocessor isolation | Raw `metadata/hints/regions` JSON | TODO | |
| P1-B Parser comparison | Side-by-side diff | TODO | |
| P1-C Merge + enrich | Field diff preproc vs metadata_v2 | TODO | |
| P1-D Map materialization | Pre-MERGE map rows vs table rows | TODO | |
| P2 Chunk attribution | Chunk/region overlap logs | TODO | |
| P3 Index sync | Index payload sample | TODO | |
| P4/P5 Retrieval behavior | API result comparison (`270T483` vs `290T483`) | TODO | |

---

## Likely Fix Paths (Based on Findings)

1. Preprocessor rule fix:
	- adjust ESN/equipment confidence weighting between section body vs footer/header
	- improve region boundary extraction around executive summary
2. Enrichment mapping fix:
	- correct field mapping if `driven_equipment` and `equipment_type` are being interpreted incorrectly
3. Stage 5 map fix:
	- ensure all region-attributed ESNs are emitted into `document_equipment_map_v2`
4. Guardrail fix:
	- add validation rule: if doc contains conflicting ESN mentions with different equipment semantics, flag for review instead of hard single-primary assignment

---

## Immediate Next Run Order

1. P1-A preprocessor-only run for this PDF and save JSON output.
2. P1-C compare preprocessor output to persisted `fsr_metadata_v2` row.
3. P2 inspect chunk-level attribution for executive summary chunks.
4. P4/P5 run retrieval checks for both ESNs.

This order should quickly localize whether the bug is extraction-time or retrieval-time.
