# FSR V2 Pipeline — Implementation Tracker

Last updated: 2026-08-12

---

## Branch

fsr_v2 in pw_sdg_ai_ser_repo
Working dir: /home/u560060992/dbx/pw_sdg_ai_ser_repo

---

## Commit History (Recent, fsr_v2)

| Hash | Description |
|------|-------------|
| 7e08f6a | feat(fsr-v2): split standalone jobs workflow and move to workflows/fsr_v2 |
| a4bbfa5 | feat(fsr-v2): implement P3 index stage and retrieval validation |
| 8e42c71 | feat(fsr-v2): wire P1 metadata orchestrator stages 1-4 |
| 753312e | feat(fsr-v2): align chunk attribution and wire stage-5 orchestration |
| f0fe5dc | docs: remove local design path reference in TIL DDL notebook |
| 972d476 | feat: P1 stage 4 — enrichment.py (ds-guru LLM pattern + IBAT/EV/PSOT + MERGE); parsing adds volume_path |
| e71600e | feat: P1 stage 3 — metadata_processor.py + copy preprocessor_v2_final to common/fsr_v2/ |
| c72fc90 | feat: P1 stage 2 — parsing.py full-text extraction + page offsets; update preprocessor ref |
| c1f2c6d | feat: P1 stage 1 — input.py volume scan implementation |
| ae9c21b | feat: v2 DDL notebook + schema definitions (fsr_metadata_v2, fsr_chunks_v2) |

---

## Implementation Status

### P1 — Metadata Extraction (Silver)

| Stage | File | Status | Notes |
|-------|------|--------|-------|
| Stage 1 — Input | silver/src/etl/fsr_v2/input.py | ✅ committed | Volume scan + cross-volume dedup, volume_list mode |
| Stage 2 — Parsing | silver/src/etl/fsr_v2/parsing.py | ✅ committed | pdfplumber extraction with page offsets |
| Stage 3 — Metadata Processor | silver/src/etl/fsr_v2/metadata_processor.py | ✅ committed | preprocessor execution + normalized metadata payload |
| Stage 4 — Enrichment | silver/src/etl/fsr_v2/enrichment.py | ✅ committed | ds-guru aligned LLM extraction + IBAT/EV/PSOT enrichment + MERGE |
| P1 orchestrator | silver/src/etl/nb_sdg_fsr_v2_metadata.py | ✅ committed | Full stages 1-4 wiring + failed-row MERGE handling |

### P2 — Chunking & Embedding (Gold)

| Stage | File | Status | Notes |
|-------|------|--------|-------|
| Stage 5 — Chunking | gold/src/etl/fsr_v2/chunking.py | ✅ committed | chunk + embed + MERGE; char-offset aligned attribution |
| Region attribution helper | common/fsr_v2/region_utils.py | ✅ committed | overlap-based region attribution for chunk spans |
| P2 orchestrator | gold/src/etl/nb_sdg_fsr_v2_chunks.py | ✅ committed | runtime params + chunking run orchestration |

### P3 — Vector Search (VS)

| Stage | File | Status | Notes |
|-------|------|--------|-------|
| Stage 6 — Index ops | vs/src/etl/fsr_v2/vector_index.py | ✅ committed | create/sync/check/poll support |
| P3 orchestrator | vs/src/etl/nb_sdg_fsr_v2_index.py | ✅ committed | notebook wiring for endpoint/index/index_mode |

### Validation

| File | Status | Notes |
|------|--------|-------|
| validation/fsr_v2/nb_fsr_v2_retrieval.py | ✅ committed | retrieval smoke/validation query implemented |

### Workflow & Bundle

| Area | File | Status | Notes |
|------|------|--------|-------|
| V2 job definitions | workflows/fsr_v2/pw_sdg_fsr_v2_jobs.yml | ✅ committed | 4 independent jobs: P1/P2/P3/Validation |
| Bundle include | databricks.yaml | ✅ committed | includes workflows/fsr_v2/*.yml |

---

## Working Tree

- Status: clean
- Uncommitted changes: none

---

## Current Notes

- Chunk attribution is aligned to Vince method (region overlap-based assignment).
- INPUT_MODE remains volume_list only. csv_list is kept as future placeholder comment only.
- Validation job naming and task key updates are reflected in v2 workflow file.

---

## 2026-07-18

- Added 4 additional chunking strategies for comparison alongside the default approach.
- Set up isolated outputs for each strategy so testing can be done cleanly.
- Added basic run tracking for chunking experiments.
- Documented the dev test flow for strategy-by-strategy validation.

---

## Next Steps

1. Run end-to-end dev validation for the 4 independent jobs (P1/P2/P3/Validation) using current workflow layout.
2. Capture runtime outputs and any tuning actions in 2-FSR-v2/implementation notes.
3. Update rollout checklist after first successful full dev cycle.

---

## 2026-08-06 WSR Update

### Last Week (shared WSR)

- Finished FSR v2 implementation end-to-end, including preprocessor integration and per-chunk ESN attribution wiring.
- Ingested a set of docs and shared with SME for validation.

### This Week

- Completed FSR v2 ingestion for SME testing and shared the validation set.
- Fixed issue 765/766 and tracked updates in 2-FSR-v2/this-week/bug-3337X75.
- Reviewed potential LLM-assisted preprocessor flow and where it should complement deterministic logic.
- Identified key preprocessor bug categories and started fixes; deterministic redesign work is in progress.
- Started MLflow experiment setup for DS top-K and retrieval strategy testing.

### Next Week

- Finish deterministic preprocessor fixes and validate on SME test documents.
- Decide whether LLM preprocessor support is needed after deterministic behavior stabilizes.
- Complete MLflow setup for DS experimentation and start top-K comparison runs.

---

## 2026-08-11 WSR Addendum (Preprocessor)

- Closed Bug 1 and Bug 2 workstream in current cycle:
	- Bug 1: untyped subsection flip-back logic completed and generalized across subsection levels.
	- Bug 2: page-join header detection issue fixed with page-aware section-header detection and page-offset type handling.
- Updated standalone validation notebook:
	- output path moved to `/Workspace/Users/madhurima.saxena@gevernova.com/fsr-preprocessor-v2-output`
	- added synthetic Bug 2 verification checks.
- Full regression rerun status:
	- `total_cases=23`, `ok=20`, `skipped_missing_in_volume=3`, `error=0`.
- Current risk note:
	- primary ESN/equipment outputs are stable, but boundary count/shape drift in a subset of docs may affect downstream chunking/section-level analytics and needs targeted follow-up checks.

---

## 2026-08-12 WSR Update (Preprocessor Hardening)

### Completed

- Worked with SME to confirm expected section and ESN attribution behavior.
- Hardened preprocessor behavior for:
	- bare Turbine headings: inherit explicit Steam/Gas parent or use the sole available turbine type;
	- untyped numbered subsection boundaries: handle parser output with or without Markdown heading markers and use nearest position-scoped equipment context;
	- table-only equipment text: TOC-gated suppression with explicit ESN/SY exception;
	- Generator section keyword detection: Electrical, Electrification, and DC leakage;
	- GG Generator ESNs: detect multiline Equipment ID (SY) plus Equipment SN (GG) evidence without promoting SY-only IDs or nameplate serials.
- Moved compound PDF filename discovery into the pipeline target-discovery path while retaining UUID document IDs.

### Validation

- Validated against the SME bug list and supplied PDFs.
- Latest standalone regression run: `ok=27`, `skipped=0`, `error=0`.
- Confirmed target outcomes for Turbine inheritance/flip-back, GG ESN detection, and compound filename discovery.

### Remaining

- One region-count increase remains under review for downstream chunking impact.
- SME will confirm readiness to move the validated preprocessor changes to QA.

---

## 2026-08-16 WSR Update

### Last Week

- QA deployment of FSR v2 was completed, with deterministic preprocessor issues resolved across subsection flip-back handling, page-join section-header detection, GG/SY ESN evidence, and compound filename discovery; regression validation completed with no runtime errors.
- Built the MLflow experiment flow for comparing retrieval and top-K strategies, giving the data science team a repeatable way to run larger-scale evaluations and make data-driven decisions.

### Next Week

- Identify and document the rules for when to use the deterministic processor versus the LLM preprocessor.
- Update the MLflow experiment with the data and evaluation inputs needed to measure FSR retrieval accuracy.
