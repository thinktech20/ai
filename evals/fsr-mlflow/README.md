# FSR MLflow Eval - Implementation and Test Steps

## Branch confirmation

Current implementation exists on branch: fsr_eval in repo pw_sdg_ai_ser_repo.

Recent commits include:
- 8f7c24d: Add lightweight FSR retrieval coverage eval harness
- 48c1c3f: Add heatmap case2 eval serving harness and docs

FSR eval implementation is present and separate from heatmap serving work.

## What is implemented for FSR eval

### 1) Lightweight retrieval eval harness with MLflow logging

Main entrypoint:
- [pw_sdg_ai_ser_repo/eval/fsr/harness.py](pw_sdg_ai_ser_repo/eval/fsr/harness.py)

What it does:
- Runs probe queries against FSR vector index.
- Measures how much of the known FSR document set for each ESN is surfaced by retrieval.
- Logs run params, key metrics, tags, and artifacts to MLflow.
- Continues even if individual probes fail and logs failed probes separately.

### 2) Thin retriever with retrieval-shape knobs

Retriever module:
- [pw_sdg_ai_ser_repo/eval/fsr/retriever.py](pw_sdg_ai_ser_repo/eval/fsr/retriever.py)

Knobs implemented:
- top_k
- max_per_doc

Design intent:
- Keep one clear retrieval path for A/B comparison of retrieval shape changes.

### 3) Probe set builder (stratified by ESN FSR count)

Probe set definition:
- A probe set is the fixed list of test queries used in one eval run.
- Each probe row includes: `esn`, `query`, known FSR `document_id` set, and bucket label.
- In this harness, the query template is `field service report findings for unit {esn}`.
- Default sample size is stratified by bucket (small/medium/large), typically 15 ESNs per bucket (about 45 probes total).
- It is read-only and pinned to a specific Delta table version for reproducibility.

Probe set module:
- [pw_sdg_ai_ser_repo/eval/fsr/probe_set.py](pw_sdg_ai_ser_repo/eval/fsr/probe_set.py)

What it does:
- Builds read-only in-memory probe set pinned to a Delta table version.
- Groups ESNs into small/medium/large buckets by FSR count and samples from each bucket.
- Returns version used so runs are reproducible.

Current retrieval notebook behavior:
- Preferred mode for experiment 2: load a fixed saved probe table and use that same ESN/query set for both baseline and candidate runs.
- Fallback mode: sample probes in memory from metadata when no saved probe table is provided.

Why this matters:
- We do not want baseline and candidate compared on different ESN populations.
- A fixed probe table keeps the evaluation slice stable and makes subset testing practical without scanning the full corpus.

### 4) Embedding adapter for direct-access vector index

Embedder module:
- [pw_sdg_ai_ser_repo/eval/fsr/embedder.py](pw_sdg_ai_ser_repo/eval/fsr/embedder.py)

What it does:
- Calls LiteLLM embedding endpoint.
- Includes retry and timeout handling.
- Uses the same endpoint fallback pattern as FSR chunking (`/v1/embeddings` then `/embeddings`) for gateway compatibility.

### 5) Metrics definitions

Metrics module:
- [pw_sdg_ai_ser_repo/eval/fsr/metrics.py](pw_sdg_ai_ser_repo/eval/fsr/metrics.py)

Key outputs:
- retrieved_vs_exists_ratio
- known_fsr_count
- retrieved_fsr_count
- retrieved_known_fsr_count

Definitions (per probe = one ESN + one query):
- known_fsr_count:
	Number of distinct FSR document IDs known to exist for the ESN from metadata.
- retrieved_fsr_count:
	Number of distinct FSR document IDs returned by retrieval for that probe.
- retrieved_known_fsr_count:
	Number of retrieved document IDs that overlap with the known document set.
- retrieved_vs_exists_ratio:
	Coverage ratio = retrieved_known_fsr_count / known_fsr_count.

Quick example:
- known_fsr_count = 10
- retrieved_fsr_count = 6
- retrieved_known_fsr_count = 4
- retrieved_vs_exists_ratio = 0.40

Interpretation:
- These are retrieval-coverage metrics (structural), not semantic correctness metrics.
- Harness logs per-probe values and MLflow reports run-level averages.

### 5A) Suggested layered knobs and metrics

Use a layer-based view so each experiment answers one clear question.

Layer 1: Chunking and indexing layer
- Typical knobs:
	chunk_size, chunk_overlap, section splitting strategy, metadata filters, embedding model.
- Suggested metrics:
	average chunks per document, index coverage rate, duplicate-chunk rate, chunk-size distribution.

Example layer-1 metric definition:
- chunk_doc_coverage_ratio:
	COUNT(DISTINCT document_id in chunk table) / COUNT(metadata_status = completed in metadata table)
	Interpretation: how much of completed metadata docs are represented in chunk rows.

Layer 2: Retrieval layer (current harness focus)
- Current knobs:
	top_k, max_per_doc.
- Current metrics:
	retrieved_vs_exists_ratio, known_fsr_count, retrieved_fsr_count, retrieved_known_fsr_count.
- Optional additions:
	latency p50/p95, doc diversity per query, failure rate.

Layer 3: End-to-end response layer (future)
- Typical knobs:
	prompt variants, reasoning settings, post-processing rules.
- Suggested metrics:
	SME match rate, precision/recall on golden set labels, parse success rate, cost per run.

Recommended experiment pattern:
- Change knobs in one layer at a time.
- Keep upstream layers fixed while comparing variants.
- Promote only when layer metrics improve without regressions in broader checks.

Suggested MLflow experiment naming (semantic, no numeric layers):
- fsr_eval_chunking_index
- fsr_eval_retrieval
- fsr_eval_end2end

Suggested common tags across all experiments:
- eval_suite=fsr_eval
- eval_layer=chunking_index | retrieval | end2end
- candidate_id=<change_id>
- dataset_version=<version>

Candidate table guidance (record count expectations):
- For chunking/index eval, compare baseline vs candidate tables/indexes.
- Candidate should be written by pipeline run with the new knob settings; do not overwrite baseline tables in place.
- Record count does not have to match baseline exactly in early tuning runs.

Recommended staged approach:
- Stage 1 (fast tuning): run on a subset candidate corpus (for example 5k-10k docs) to iterate quickly.
- Stage 2 (promotion gate): run on full candidate corpus (for example all ~50k docs) before final decision.

How to interpret candidate record counts:
- If candidate is subset by design, lower total rows are expected and not a failure.
- If candidate is intended full corpus, large row/count gaps versus baseline indicate a pipeline or coverage issue.
- Always compare using explicit tags: candidate_id, dataset_version, and eval_layer.

### 5B) Nomenclature to keep consistent

Use these terms consistently across notebooks, MLflow, and deck updates:

- Knobs:
	Input settings you intentionally change between experiment variants.
	Examples: chunk_size, chunk_overlap, top_k, max_per_doc, prompt variant.

- Metrics:
	Numeric measurements used to compare variants.
	Examples: retrieved_vs_exists_ratio, chunk_doc_coverage_ratio, probes_failed, SME match rate.

- Outputs:
	All run results produced by an experiment (metrics + params + artifacts + tags + run_id).

- Artifacts:
	Detailed files attached to a run for debugging/audit (for example per_probe JSONL, config JSON).

Quick mapping:
- knobs answer: what did we change?
- metrics answer: what moved?
- outputs answer: what did this run produce overall?

### 6) Databricks notebook runner

Notebook:
- [pw_sdg_ai_ser_repo/eval/fsr/notebooks/nb_fsr_eval_harness.py](pw_sdg_ai_ser_repo/eval/fsr/notebooks/nb_fsr_eval_harness.py)

What it does:
- Installs minimal deps.
- Configures widgets for endpoint/index/metadata/probe settings.
- Runs embedding smoke test.
- Executes harness and prints MLflow run id.

## Test steps

### Step 1 - Sync code to Databricks workspace

Use your existing sync flow to copy folder:
- source: pw_sdg_ai_ser_repo/eval/fsr
- target: your Databricks workspace path

### Step 2 - Open and run notebook

Run:
- [pw_sdg_ai_ser_repo/eval/fsr/notebooks/nb_fsr_eval_harness.py](pw_sdg_ai_ser_repo/eval/fsr/notebooks/nb_fsr_eval_harness.py)

Expected early checks:
- Dependency install succeeds.
- Python restart succeeds.
- Repo imports succeed.

### Step 3 - Set notebook widgets

Required widgets to verify:
- FSR_VS_ENDPOINT
- FSR_VS_INDEX
- FSR_METADATA_TABLE
- PROBE_SET_TABLE
- MLFLOW_EXPERIMENT
- TOP_K
- MAX_PER_DOC
- LITELLM_BASE_URL
- LITELLM_API_KEY
- EMBEDDING_MODEL

Widget usage note:
- If `PROBE_SET_TABLE` is filled, the notebook loads probes from that table and uses the same set for baseline and candidate runs.
- If `PROBE_SET_TABLE` is blank, the notebook samples probes from metadata using `PROBE_PER_BUCKET`, `PROBE_SEED`, and `METADATA_VERSION`.

### Step 4 - Run embedding smoke test cell

Expected:
- Returns embedding vector length.
- Completes in a few seconds.

If this fails:
- Check LiteLLM URL and key.
- Check model name and gateway access.

### Step 5 - Run full harness cell

Expected terminal output:
- Loaded probe set count from saved table, or loaded probe set count with metadata version.
- Printed MLflow run id.

### Step 6 - Validate in MLflow

Open experiment path from widget MLFLOW_EXPERIMENT and verify:

Params:
- endpoint_name
- index_name
- top_k
- max_per_doc
- probe_set_size
- probe metadata fields
- probe_set_table or metadata sampling fields

Metrics:
- avg_retrieved_vs_exists_ratio
- avg_retrieved_known_fsr_count
- avg_known_fsr_count
- probes_succeeded
- probes_failed

Artifacts:
- per_probe JSONL
- config JSON
- failed_probes JSONL (if any failures)

## Recommended A/B test sequence

### Recommended sequence for experiment 2

1. Build or reuse one fixed probe table for the ESN subset you want to test.
2. Run baseline retrieval on that probe table.
3. Change only retrieval knobs for the candidate run.
4. Run candidate retrieval on that same probe table.
5. Compare MLflow runs; do not change the ESN subset between the two runs.

### Run A - baseline
- TOP_K = 10
- MAX_PER_DOC = blank

### Run B - spread control
- TOP_K = 10
- MAX_PER_DOC = 3

### Run C - recall ceiling
- TOP_K = 20
- MAX_PER_DOC = 3

Compare runs primarily on:
- avg_retrieved_vs_exists_ratio
- probes_failed
- avg latency indicator from per_probe artifact

## Pass/fail sanity checks

Minimum sanity for a healthy run:
- probes_succeeded > 0
- MLflow run artifacts are present
- avg_retrieved_vs_exists_ratio is populated

If probes_failed is high:
- inspect failed_probes artifact first
- verify VS endpoint/index and LiteLLM embedding path

## Current scope limitations

Current FSR harness does not yet include:
- SME-labeled semantic golden-set scoring
- Serving wrapper for FSR harness
- Scheduled workflow YAML in this module

These are future extensions after baseline metric stability is established.
