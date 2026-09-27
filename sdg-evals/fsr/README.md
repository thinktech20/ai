# FSR Retrieval Evaluation

Evaluation package for comparing the current URA retrieval behavior with the
proposed shared-region implementation and testing retrieval knobs.

## Structure

| Area | Location | Responsibility |
|---|---|---|
| Retrieval strategies | `retrieval/` | `ura_current` and `ura_with_shared_impl` behind one interface |
| Probe loading | `retrieval_eval/probe_set.py` | Load DS-owned probe templates and resolved probe artifacts |
| Validation rules | `retrieval_eval/validation.py` | Validate probe labels independently from retrieval code |
| Metrics | `retrieval_eval/metrics.py` | Document, page/evidence, chunk, and filter metrics |
| Evaluation harness | `retrieval_eval/harness.py` | Run probes, aggregate metrics, and log MLflow artifacts |
| Tests | `tests/` | Unit tests for retrieval, validation, and metrics |
| Probe sets | `probe-sets/` | Probe templates and resolved artifacts used by eval runs |
| Mapping evaluation | `mapping-eval/` | Separate ESN and equipment-type mapping quality evaluation |
| Databricks entrypoints | `notebooks/` | Run the evaluation in Databricks |

## Quick start: run the top-k eval

The complete runbook (with troubleshooting, decision plan, and post-run
analysis steps) lives at
`2-FSR-v2/evals/fsr-v2-top-k-eval/results-analysis/run-instructions.md`.
Short version:

1. **Preflight (local).**

   ```bash
   cd sdg-evals
   python -m unittest discover -s fsr/tests -p 'test_*.py' -q
   databricks auth describe --profile dev-dbr-profile
   ```

2. **Sync to a Databricks sandbox folder.** Replace the target path with
   your own sandbox.

   ```bash
   databricks sync --full \
     /path/to/sdg-evals \
     /Users/<you>@gevernova.com/sandbox/fsr-v2-topk-eval/sdg-evals \
     --profile dev-dbr-profile
   ```

3. **Open the notebook** at
   `.../sandbox/fsr-v2-topk-eval/sdg-evals/fsr/notebooks/nb_fsr_v2_topk_eval`
   in Databricks.

4. **Set the widgets.** Paste this into a Python cell, then edit the paths
   for your workspace. Enter `LITELLM_API_KEY` directly in the widget UI
   after running the cell; do not commit it.

   ```python
   dbutils.widgets.text(
     "PROBE_CSV_PATH",
     "/Workspace/Users/<you>@gevernova.com/sandbox/fsr-v2-topk-eval/sdg-evals/fsr/probe-sets/probe-set.csv",
   )
   dbutils.widgets.text("PROBE_SET_VERSION", "probe-set-YYYY-MM-DD")
   dbutils.widgets.text("STRATEGIES", "ura_current,ura_with_shared_impl")
   dbutils.widgets.text("TOP_K_VALUES", "5,10,20,40")
   dbutils.widgets.text("OVERFETCH_K", "")
   dbutils.widgets.text("RECENCY_WINDOW_MONTHS", "120")
   dbutils.widgets.text("QUERY_TYPE", "HYBRID")
   dbutils.widgets.text(
     "MLFLOW_EXPERIMENT",
     "/Users/<you>@gevernova.com/fsr_v2_topk_eval",
   )
   dbutils.widgets.text("RUN_NAME_PREFIX", "fsr_v2_topk")
   dbutils.widgets.text("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
   dbutils.widgets.text("LITELLM_API_KEY", "")
   dbutils.widgets.text("EMBEDDING_MODEL", "azure-text-embedding-3-large-1")
   dbutils.widgets.text("LLM_VERIFY_SSL", "false")
   ```

   Use `probe-sets/probe-set.csv` (the authored probe inputs) for a normal
   run. Use `probe-sets/probe-set-resolved.csv` only if you have separately
   resolved cited pages against a specific chunk-table version.

5. **Run all cells.** The setup cell must print
   `Loaded N probes from: .../probe-set.csv`. The evaluation loop prints
   one completion message per (strategy, K) pair.

6. **Verify.** Every MLflow run should show `probes_failed = 0`. If any
   probe would trigger the legacy fallback, the eval raises a
   `RuntimeError` naming the ESN instead of silently succeeding — this is
   intentional (v2-only guard).

7. **Compare in MLflow.** Filter to the successful runs and use the Bar
   Chart tab. Recommended Y-axes:

   - `avg_doc_recall_at_k` — coverage across K and strategy.
   - `avg_precision_at_k` — shows how precision drops as K grows for
     `ura_with_shared_impl`.
   - `avg_n_returned` — shows `ura_current` saturating at ~10.
   - `avg_retrieval_filter_match_rate_at_k` — filter fidelity by strategy.
   - `p95_latency_ms` — latency profile.

### Rerunning after code or probe changes

Rerun the `databricks sync --full` command after any local change. In the
notebook, either detach/reattach the cluster or run
`dbutils.library.restartPython()` so the cluster re-imports the updated
`fsr` modules. Reset any widget whose value changed:

```python
dbutils.widgets.remove("PROBE_CSV_PATH")
dbutils.widgets.text(
    "PROBE_CSV_PATH",
    "/Workspace/Users/<you>@gevernova.com/sandbox/fsr-v2-topk-eval/sdg-evals/fsr/probe-sets/probe-set.csv",
)
```

## Retriever strategies

- `ura_current`: reproduces the current URA app behavior, including the
  current ESN-only v2 filter, single search request, current de-duplication,
  and Vector Search ranking order.
- `ura_with_shared_impl`: evaluates the proposed behavior with eligible shared
  regions, merged candidate results, `chunk_id` de-duplication, score ranking,
  and final `top_k` selection.

Both strategies use the same `Retriever` interface and can be selected with
`create_retriever(strategy=...)`.

## Probe data

The internal probe-set files are in `probe-sets/`. The probe contract and scoring
rules are defined in:

`2-FSR-v2/evals/fsr-v2-top-k-eval/retrieval-scoring-spec.md`

Required DS labels:

- `expected_document_ids`
- `expected_cited_doc_pages`

Optional exact chunk labels:

- `expected_chunk_ids`
- `chunk_table_version`

Document/page labels are the default quality ground truth. Exact chunk metrics
are only reported when chunk IDs are tied to a specific chunk-table version.

### Template files

- `probe-sets/probe-set.csv` contains the authored probe inputs.
- `probe-sets/probe-set-resolved.csv` is the generated artifact consumed by the
  eval runner after the template is joined with the DS-owned Heat Map.

The large chunk table and Heat Map workbook are intentionally not copied into
this repository. Keep their source paths and versions in evaluation run
metadata.

## Run locally

From the repository root:

```bash
PYTHONPATH=. python -m unittest discover -s fsr/tests -p 'test_*.py' -v
```

The Databricks notebooks require the Vector Search endpoint, SQL tables, and
embedding gateway configuration. Local tests use injected fake providers and
do not require Databricks credentials.

## Notebook widgets reference

The Databricks notebook `notebooks/nb_fsr_v2_topk_eval.py` exposes these
widgets. Defaults target the dev v2 objects and are safe for a first run.

| Widget | Purpose |
|---|---|
| `PROBE_CSV_PATH` | Path to the probe CSV. Defaults to `probe-sets/probe-set.csv` (authored probes). |
| `PROBE_SET_VERSION` | Free-form version tag logged to MLflow. |
| `STRATEGIES` | Comma-separated strategies, normally `ura_current,ura_with_shared_impl`. |
| `TOP_K_VALUES` | K values to test, normally `5,10,20,40`. |
| `OVERFETCH_K` | Optional candidate count for the shared implementation; leave blank for default behavior. |
| `RECENCY_WINDOW_MONTHS` | Document lookback window used by the SQL eligibility gate; normally `120`. |
| `QUERY_TYPE` | Search mode: `HYBRID` or `ANN` (vector-only). Normally `HYBRID`. |
| `FSR_VS_ENDPOINT` | Databricks Vector Search endpoint. |
| `FSR_VS_INDEX` | v2 multi-ESN index. |
| `FSR_LEGACY_INDEX` | Legacy fallback index. Used only if a probe’s ESN has no eligible v2 documents; the eval currently guards this and raises instead. |
| `FSR_V2_MAPPING_TABLE` | v2 document-to-equipment mapping table. |
| `FSR_V2_METADATA_TABLE` | v2 metadata table. |
| `FSR_LEGACY_METADATA_TABLE` | Legacy metadata table (guarded). |
| `FSR_LEGACY_CHUNKS_TABLE` | Legacy chunks table (guarded). |
| `LITELLM_BASE_URL`, `LITELLM_API_KEY` | Query embedding service configuration. Enter the key in the widget UI only; never commit it. |
| `EMBEDDING_MODEL` | Embedding model name at the gateway. |
| `LLM_VERIFY_SSL` | `false` for the dev gateway self-signed cert. |
| `MLFLOW_EXPERIMENT` | Destination for run metrics and artifacts. |
| `RUN_NAME_PREFIX` | Prefix for MLflow run names. |

Notebook defaults use the dev v2 objects:

- `vaid.ai_sot_field_service_report.fsr_metadata_v2`
- `vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2`
- `vaid.ai_std_con_field_service_report.fsr_chunks_v2`
- `vaid.ai_std_con_field_service_report.fsr_vs_index_v2`

## What the notebook records

Each (strategy, K) combination is one MLflow run. Every run records the
strategy, configuration, per-probe results, aggregate retrieval metrics,
and latency. Main quality metrics are page/evidence-level by default:

- Recall@K, Precision@K, and F1@K.
- Document recall and cited-page hit rate.
- Shared-aware filter fidelity.
- p95 latency.

Exact chunk metrics are only reported when `expected_chunk_ids` and
`chunk_table_version` are provided in the probe CSV.

## Run the mapping evaluation

The mapping evaluation is separate from retrieval scoring. Use
`mapping-eval/README.md` for its gold-label and prediction commands:

```bash
python fsr/mapping-eval/mapping_eval_runner.py --strict
```

Run this when validating the ESN and equipment-type metadata used by the
retrieval filters, not as a replacement for the retrieval evaluation.

## Evaluation order

Recommended workflow:

1. Run local unit tests.
2. Validate mapping labels with `mapping-eval` when mapping data changes.
3. Run `ura_current` on the fixed resolved probe set.
4. Run `ura_with_shared_impl` on the same probe set and K values.
5. Compare metrics and latency in MLflow.
6. Change one retrieval knob at a time and repeat the comparison.
