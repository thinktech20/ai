# FSR v2 Top-k Evaluation: Databricks Run Instructions

## Goal

Compare `ura_current` with `ura_with_shared_impl` on the same eight-probe
dataset. The first experiment uses hybrid search and evaluates top-k values
`5`, `10`, `20`, and `40`.

The notebook creates one MLflow run per strategy and top-k pair: 2 strategies
x 4 top-k values = 8 runs.

## Inputs

| Input | Value |
|---|---|
| Notebook | `fsr/notebooks/nb_fsr_v2_topk_eval.py` |
| Probe set | `fsr/probe-sets/probe-set.csv` |
| Probe count | 8 (`P-001` through `P-008`) |
| Strategies | `ura_current,ura_with_shared_impl` |
| Top-k values | `5,10,20,40` |
| Query type | `HYBRID` |
| Recency window | `120` months |

Use `probe-set.csv` for this run. It contains the current eight workbook-derived
probes. Do not use the default `probe-set-resolved.csv`, which is an older
three-probe artifact.

## 1. Preflight

From the local `sdg-evals` checkout, confirm tests and Databricks authentication:

```bash
cd /home/u560060992/dbx/sdg-evals
python -m unittest discover -s fsr/tests -p 'test_*.py' -q
databricks auth describe --profile dev-dbr-profile
```

Expected test result: `Ran 8 tests ... OK`.

## 2. Sync to Databricks

Use a dedicated sandbox folder. This is a one-way local-to-workspace sync; do
not edit the synced files in the Databricks UI.

```bash
databricks sync --full \
  /home/u560060992/dbx/sdg-evals \
  /Users/madhurima.saxena@gevernova.com/sandbox/fsr-v2-topk-eval/sdg-evals \
  --profile dev-dbr-profile
```

For iteration after the initial upload, use:

```bash
databricks sync --watch \
  /home/u560060992/dbx/sdg-evals \
  /Users/madhurima.saxena@gevernova.com/sandbox/fsr-v2-topk-eval/sdg-evals \
  --profile dev-dbr-profile
```

Open this synced notebook in the Databricks workspace:

`/Users/madhurima.saxena@gevernova.com/sandbox/fsr-v2-topk-eval/sdg-evals/fsr/notebooks/nb_fsr_v2_topk_eval`

## 3. Set Notebook Widgets

Set these values before running the notebook from the first cell. Copy and
paste this block into a Databricks Python cell. Keep all other object-name
widgets at their notebook defaults unless the dev workspace uses different
verified objects.

```python
dbutils.widgets.text(
  "PROBE_CSV_PATH",
  "/Workspace/Users/madhurima.saxena@gevernova.com/sandbox/fsr-v2-topk-eval/sdg-evals/fsr/probe-sets/probe-set.csv",
)
dbutils.widgets.text("PROBE_SET_VERSION", "workbook_2026-08-19")
dbutils.widgets.text("STRATEGIES", "ura_current,ura_with_shared_impl")
dbutils.widgets.text("TOP_K_VALUES", "5,10,20,40")
dbutils.widgets.text("OVERFETCH_K", "")
dbutils.widgets.text("RECENCY_WINDOW_MONTHS", "120")
dbutils.widgets.text("QUERY_TYPE", "HYBRID")
dbutils.widgets.text(
  "MLFLOW_EXPERIMENT",
  "/Users/madhurima.saxena@gevernova.com/fsr_v2_topk_eval",
)
dbutils.widgets.text("RUN_NAME_PREFIX", "fsr_v2_topk_workbook_20260819")
dbutils.widgets.text("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
dbutils.widgets.text("LITELLM_API_KEY", "")
dbutils.widgets.text("EMBEDDING_MODEL", "azure-text-embedding-3-large-1")
dbutils.widgets.text("LLM_VERIFY_SSL", "false")
```

After running the cell, enter the valid gateway key into the
`LITELLM_API_KEY` widget in the Databricks UI. Do not place the key in this
document, the source repository, or an MLflow parameter.

### Rerunning after a new sync

Databricks does not use git for the sandbox path. Nothing needs to be pulled
in the workspace UI; the local `databricks sync --full` command already
updates the notebook and probe CSV in the workspace.

Before rerunning the notebook after a sync:

1. Detach and reattach the cluster, or run `dbutils.library.restartPython()`,
   so the cluster re-imports the updated `fsr` Python modules.
2. Reset the probe-path widget so a stale prior value is not reused:

   ```python
   dbutils.widgets.remove("PROBE_CSV_PATH")
   dbutils.widgets.text(
       "PROBE_CSV_PATH",
       "/Workspace/Users/madhurima.saxena@gevernova.com/sandbox/fsr-v2-topk-eval/sdg-evals/fsr/probe-sets/probe-set.csv",
   )
   ```

3. Run all cells from the top.

## 4. Run and Verify Completion

Run all notebook cells on a cluster that can access the configured SQL tables,
Vector Search endpoint, MLflow, and embedding gateway.

The setup cell must print:

```text
Loaded 8 probes from: .../fsr/probe-sets/probe-set.csv
```

The loop must print eight completion messages, one for every strategy/top-k
combination. The final two displays show:

1. One summary row for each run.
2. A four-row delta table comparing shared implementation against current URA
   for each top-k value.

Stop and record the error rather than comparing partial results if any run has
`probes_failed > 0`.

## 5. Export Run Evidence


For each of the eight MLflow runs, record its run ID and download these
artifacts:

- `summary/*.json`
- `per_probe/*.jsonl`
- `config/*.json`
- `failed_probes/*.jsonl`, if present

Also copy the notebook's final run-summary and delta tables. Save all exported
files in a new dated subfolder here, for example:

`2-FSR-v2/evals/fsr-v2-top-k-eval/results-analysis/2026-08-19-initial-run/`

## 6. Select Top-k First


Top-k is the primary decision for this experiment. For each strategy, compare
the four values in ascending order: `5`, `10`, `20`, then `40`.

For each value, record:

| K | Strategy | `avg_doc_recall_at_k` | `avg_cited_doc_page_hit_rate` | `avg_f1_at_k` | `avg_retrieval_filter_match_rate_at_k` | `p95_latency_ms` | Failed probes |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5 | current/shared | | | | | | |
| 10 | current/shared | | | | | | |
| 20 | current/shared | | | | | | |
| 40 | current/shared | | | | | | |

Choose the smallest K that meets all of these gates for a strategy:

1. `probes_failed` is `0`.
2. `avg_retrieval_filter_match_rate_at_k` is `1.0`.
3. Increasing K no longer produces a meaningful gain in document or cited-page
  coverage. Treat an absolute gain below `0.05` as a plateau for this initial
  eight-probe set.
4. The selected K does not reduce `avg_f1_at_k` versus the preceding K.

If no value plateaus, choose the K with the highest cited-page hit rate; use
document recall, F1, and latency to break a tie. Record the result as, for
example, `selected_k_current=10` and `selected_k_shared=20`.

## 7. Compare Strategies at the Selected K


Compare `ura_with_shared_impl` with `ura_current` at each strategy's selected
K. If the selected K differs, also compare both strategies at the same K values
so the strategy effect is separated from the top-k effect.

Prefer the shared implementation only when it improves or preserves document
and cited-page coverage without a filter-fidelity regression. Report the
latency increase separately from retrieval-quality findings.