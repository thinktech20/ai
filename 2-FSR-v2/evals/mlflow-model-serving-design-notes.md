# FSR v2 - Evals + MLflow/Model Serving Notes (Draft)

Yes - the technical term is evals.
For this work, use:
- Offline RAG evals (before promotion)
- Online serving evals (champion/challenger after deploy)

## 1) Top-k retrieval for FSR chunks

How it helps:
- Tunes recall vs noise in retrieval.
- Makes tradeoff visible with metrics, not intuition.

What to implement:
- Run k sweep in MLflow: k = 5, 10, 20, 40.
- Keep probe set fixed across runs.
- Log params: parser_version, chunker_version, embedding_model, k.
- Log metrics: recall_at_k, precision_at_k, avg_retrieved_vs_exists_ratio, p95_latency_ms.

How to test:
- Offline probes with known ESN -> expected FSR set (probe/weak-label set, not a strict gold set).
- Compare candidate vs baseline on same probes.
- Promotion gate: no recall drop and latency within SLO.

## 2) ESN -> equipment type mapping at larger corpus scale

How it helps:
- Prevents chunk mislabeling in multi-equipment documents.
- Reduces cross-ESN retrieval misses.

What to implement:
- Version metadata extraction and chunk attribution outputs.
- Persist per-chunk fields: primary_esn, primary_equip_type, active_esns, attribution_provenance.
- Add changed-file detection (file_last_modified) for incremental reprocessing.

How to test:
- Gold labeled set for region/chunk attribution correctness.
- Metrics: esn_accuracy, equipment_type_accuracy, cross_esn_miss_rate, unknown_label_rate.
- Scale test on larger corpus slice for throughput and consistency.

## 3) MLflow + model serving pattern

How it helps:
- Every pipeline configuration is measurable, versioned, and rollback-safe.

What to implement:
- Log each config as MLflow run with params + retrieval/latency metrics + artifacts.
- Register promoted config in model registry.
- Deploy champion/challenger versions with traffic split.
- Add auto rollback trigger based on online SLO breach.

How to test:
- Pre-deploy gate from offline eval thresholds.
- Post-deploy checks: latency, error rate, retrieval quality parity, answer quality proxy.

Note:
- Section 1 does not require a strict gold set; a stable probe/weak-label set is enough for ranking and trend comparison.
- Section 2 should use a gold-labeled set for attribution accuracy measurement.
- Section 3 does not require a gold set; it is mainly experiment tracking and online serving health/quality monitoring.

## Data format guidance: probe/weak-label set vs gold set

### Probe/weak-label set (for retrieval tuning)

Purpose:
- Measure relative movement between baseline and candidate runs.

Minimum columns:
- probe_id: unique id for the query case.
- query_text: user-style retrieval question.
- esn: target ESN for filter/query context.
- equip_type: expected equipment type scope.
- expected_fsr_ids: list of likely relevant FSR document ids (from existing mapping/heuristics).
- label_source: source of weak labels (document-equipment map, prior run, heuristic rule).
- confidence: optional weak-label confidence (high/medium/low or numeric).

Example row shape:
- probe_id=P-001; query_text="history of bearing vibration"; esn=ESN123; equip_type=generator; expected_fsr_ids=[FSR-9,FSR-21,FSR-44]; label_source=document_equipment_map; confidence=high

Recommended checks:
- Keep probes fixed across all runs.
- Freeze versioned probe file per experiment cycle.
- Track coverage: probes with at least 1 expected_fsr_id.

### Gold set (for ESN/equipment attribution correctness)

Purpose:
- Measure true labeling correctness at region/chunk level.

Minimum columns (chunk-level):
- record_id: unique id.
- fsr_id: source document id.
- chunk_id or region_id: attribution unit.
- chunk_text_span: start/end offsets or canonical region key.
- true_primary_esn: human-validated ESN.
- true_primary_equip_type: human-validated equipment type.
- true_active_esns: full validated ESN set in the span.
- adjudication_notes: optional reviewer rationale for hard cases.
- reviewer_id and reviewed_at: auditability fields.

Example row shape:
- record_id=G-1042; fsr_id=FSR-21; chunk_id=C-08; chunk_text_span=11240-11980; true_primary_esn=ESN456; true_primary_equip_type=generator; true_active_esns=[ESN456,ESN457]; reviewer_id=rev02; reviewed_at=2026-08-01

Recommended checks:
- Dual review on ambiguous multi-equipment records.
- Stratified sampling (single-equipment vs multi-equipment, old scans vs clean PDFs).
- Report per-class accuracy and confusion matrix, not only overall accuracy.

## Suggested minimum eval matrix

- Top-k sweep: 4 values x fixed probe set.
- Parser/chunker candidate vs baseline: 1:1 comparison.
- ESN mapping regression suite: gold set on every pipeline change.
- Serving canary: 5-10% traffic before full rollout.

## FSR-only clean-start decision

Decision:
- Ignore TIL eval framework for this effort.
- Focus only on FSR v2 evals for:
	- 1) Top-k retrieval behavior
	- 2) ESN to equipment-type mapping quality
- Prefer simple, robust implementation over hard interface-driven abstraction.

Practical coding style for this effort:
- Keep the eval runner as plain Python modules plus small Databricks entry notebooks.
- Keep config in one place (YAML or JSON) and avoid deep inheritance trees.
- Favor explicit DataFrame transformations and clear metric functions.
- Add only the minimum reusable utilities needed by both eval tracks.

Proposed stale FSR cleanup scope (stepwise, with review at each step):
- Candidate stale retrieval validation notebooks:
	- validation/fsr_v2/retrieval/nb_fsr_v2_retrieval_uc1.py
	- validation/fsr_v2/retrieval/nb_fsr_v2_retrieval_uc2_current.py
	- validation/fsr_v2/retrieval/nb_fsr_v2_retrieval_uc2_future.py
- Candidate stale workflow pointing to non-current validation entry:
	- workflows/fsr_v2/pw_sdg_fsr_v2_p4_validation.yml

Important guardrail before deletion:
- Do not remove FSR MLflow logging currently referenced by active P2 code until replacement is in place.
- Existing active reference:
	- gold/src/etl/fsr_v2/chunking.py imports common/fsr_v2/mlflow_logger.py

## Regression testing strategy for larger corpus

Use a 3-layer cadence:
- Fast gate (per change): fixed stratified subset (about 2-5%).
- Daily regression: larger rotating slice (about 15-30%) + fixed anchor set.
- Weekly benchmark: full corpus end-to-end.

Stratification slices (must-have):
- Multi-equipment vs single-equipment documents.
- Low OCR quality vs clean PDFs.
- Long documents vs short documents.
- Recent years vs older years.

Metrics to monitor:
- Retrieval (point 1): recall_at_k, precision_at_k, avg_retrieved_vs_exists_ratio, p95_latency_ms.
- Mapping (point 2): esn_accuracy, equipment_type_accuracy, cross_esn_miss_rate, unknown_label_rate.
- Always report slice-level metrics, not only overall averages.

Pass/fail policy:
- Hard fail: critical metric below threshold in any critical slice.
- Warn: small degradation within tolerance band.
- Promote only if fast gate + daily regression pass; use weekly full run as release confidence checkpoint.

Operational best practices:
- Version run inputs: dataset_version, pipeline_version, index_version, model/chunker params.
- Keep a fixed canary query replay set for human-readable regression checks.
- Log every run to MLflow with params, metrics, and slice artifacts for auditability.
