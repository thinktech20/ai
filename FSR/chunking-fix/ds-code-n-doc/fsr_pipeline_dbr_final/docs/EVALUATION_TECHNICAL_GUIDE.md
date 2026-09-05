# FSR Databricks Evaluation Guide

This document describes the evaluation path in `fsr_pipeline_dbr_final`, including how the notebook drives the evaluator and what the shipped metrics CSV says about the tested retrieval variants.

---

## 1) Entry points

Evaluation notebook:
- `run_evaluation.py`

Evaluation engine:
- `src/evaluate_retrieval.py`

Reference metrics snapshot:
- `docs/fsr_retrieval_metrics_final.csv`

Ground-truth source workbooks:
- `Heat Map - Unified Structure v0.1.xlsx`
- `FSR_citations_processed_20260305_135321.xlsx`

---

## 2) Notebook controls

`run_evaluation.py` resolves `src/` inside the Databricks workspace, then exposes these top-level controls:

- `VS_ENDPOINT_OVERRIDE`
- `SECRET_SCOPE_OVERRIDE`
- `MAX_K`
- `MAX_ISSUES`
- `INCLUDE_EVAL_CRITERIA`

Default behavior in the shipped notebook:

- `MAX_K = 20`
- `MAX_ISSUES = None`
- `INCLUDE_EVAL_CRITERIA = True`

The notebook then calls:

`evaluate_all(max_k=MAX_K, max_issues=MAX_ISSUES, include_criteria=INCLUDE_EVAL_CRITERIA)`

---

## 3) Pre-flight validation

Before evaluation starts, `run_evaluation.py` performs a Spark-side sanity check against the Delta table from `src/config.py`:

- counts total rows in `EMBEDDINGS_TABLE`
- measures how many rows still have `NULL generator_serial`
- lists distinct serials present in the index source table
- compares those serials with the GT ESNs returned by `load_ground_truth()`

If rows still have `NULL generator_serial`, the notebook attempts a non-fatal repair via:

- `delta_store.merge_ref_view_metadata(spark)`

This uses `FSR_REF_VIEW` to overwrite `generator_serial` and `report_date` in the Delta table.

---

## 4) Evaluation flow in `src/evaluate_retrieval.py`

The current Databricks evaluator emits four modes only. The larger 16-column comparison in `docs/fsr_retrieval_metrics_final.csv` includes those Databricks results plus historical custom baselines that are not produced by `src/evaluate_retrieval.py`.

### Query generation

- `load_queries(include_criteria=False)` reads GEN + Rotor rows from the Heat Map workbook.
- When `include_criteria=True`, `_build_issue_query()` appends severity criteria 0-4 to the base issue prompt.
- The evaluator tracks the active query mode in `query_variant`:
  - `issue_prompt_only`
  - `issue_prompt_plus_criteria_0_4`

### Ground-truth loading

- `load_ground_truth()` reads `results/citations_parsed.csv`.
- If that parsed CSV is missing, `_ensure_ground_truth_csv()` rebuilds it from `FSR_citations_processed_20260305_135321.xlsx`.
- GT is represented per `(issue_name, esn)` pair with:
  - cited PDF/page evidence
  - snippet evidence

### Retrieval modes

For each relevant `(serial, issue)` pair, the evaluator makes exactly four calls:

1. `ann_retrieval`
2. `ann_reranking`
3. `hybrid_retrieval`
4. `hybrid_reranking`

The query layer prefers the Databricks Vector Search SDK and falls back to REST when necessary:

- SDK path supports `DatabricksReranker`
- REST fallback does not provide reranking

### Hit logic

Each returned chunk is scored against GT using two complementary signals:

- page-based hit
  - PDF stem matches and cited page falls within `page_number .. page_number + PAGE_WINDOW`
- text-based hit
  - any GT snippet is found in `chunk_text` after NFKC normalization and alpha-only fallback

`check_match()` treats either signal as a hit.

### Metrics

For every mode and every `k` from `1..MAX_K`, the evaluator records:

- `recall_at_k`
- `precision_at_k`
- `matches_in_top_k`
- `num_returned`
- `gt_citation_count`

---

## 5) Output artifacts

`evaluate_all()` writes timestamped CSVs under `results/`:

- `eval_raw_<variant>_<timestamp>.csv`
- `eval_summary_<variant>_<timestamp>.csv`

The returned DataFrame also exposes metadata in `df.attrs`:

- `raw_path`
- `summary_path`
- `query_variant`

`run_evaluation.py` surfaces those paths in notebook output and also returns them as JSON through `dbutils.notebook.exit(...)` for Jobs API callers.

---

## 6) What the shipped metrics CSV says

`docs/fsr_retrieval_metrics_final.csv` is a comparison snapshot spanning 16 variants across:

- custom local-style retrieval strategies
- Databricks built-in ANN/HYBRID/reranked variants
- prompt-only vs criteria-appended query text

Only the four Databricks modes listed above come from the shipped `run_evaluation.py` + `src/evaluate_retrieval.py` path. The BM25/FAISS/custom-hybrid rows are reference baselines retained for side-by-side comparison.

Key takeaways from the CSV:

- Best Databricks low-k baseline:
  - `HYBRID` with criteria reached `Recall@1 = 45.5`, `Recall@5 = 67.4`, and `Recall@10 = 78.8`.
- Best Databricks deep-recall result:
  - built-in `Reranked` with criteria reached `Recall@20 = 86.4`.
- Best custom `Recall@10`:
  - `Hybrid_70_30` without criteria reached `81.8`.
- Best custom `Recall@20`:
  - `Hybrid_70_30` with criteria reached `88.6`.
- Criteria text was not universally beneficial:
  - it improved some low-k hybrid results,
  - but hurt some reranked variants.

Practical interpretation:

- if you want the strongest built-in Databricks default for shallow retrieval, start with `HYBRID` plus criteria text;
- if recall deeper in the ranking matters more than latency, reranking remains worth testing;
- the older custom hybrid stack still benchmarks competitively, especially at higher k.

---

## 7) Operational notes

- `run_evaluation.py` is notebook-first and expects a Databricks cluster plus workspace-resolved `src/` files.
- The evaluation path depends on the Delta table being populated and the Vector Search index being queryable.
- The pre-flight check is not optional noise; it is the fastest way to detect the common failure mode where `generator_serial` is missing or the GT ESNs are absent from the indexed data.

---