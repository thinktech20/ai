# Databricks notebook source
# -------------------------------------------------------------------------
# FSR Retrieval Evaluation
# Compute: ai-pw-ser-ds-dev-apc  (DEV workspace)
# -------------------------------------------------------------------------

# COMMAND ----------

# MAGIC %pip install --quiet \
# MAGIC   pandas \
# MAGIC   openpyxl \
# MAGIC   requests \
# MAGIC   databricks-vectorsearch

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import sys
import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

# ── Resolve src/ directory ──────────────────────────────────────────────────
try:
    _ctx     = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    _nb_path = _ctx.notebookPath().get()
    _ws_dir  = "/Workspace" + str(Path(_nb_path).parent)
    _src_dir = _ws_dir + "/src"
except Exception:
    _src_dir = str(Path(__file__).parent / "src") if "__file__" in dir() else "./src"

if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

print(f"[OK] src path: {_src_dir}")
print(f"[OK] Files:    {sorted(os.listdir(_src_dir))}")

# COMMAND ----------

# ── Configuration ────────────────────────────────────────────────────────────
# Override these if needed:

VS_ENDPOINT_OVERRIDE = ""
SECRET_SCOPE_OVERRIDE = "fsr-pipeline"

# Maximum k to evaluate (recall/precision computed for k=1..MAX_K)
MAX_K = 20

# Limit evaluation to the first N issues (set to None for all 19 issues)
MAX_ISSUES = None

# If True, append severity criteria 0-4 to each issue prompt before querying.
INCLUDE_EVAL_CRITERIA = True

# COMMAND ----------

if VS_ENDPOINT_OVERRIDE:
    os.environ["VS_ENDPOINT_NAME"] = VS_ENDPOINT_OVERRIDE
    print(f"VS_ENDPOINT_NAME overridden -> {VS_ENDPOINT_OVERRIDE}")

if SECRET_SCOPE_OVERRIDE:
    os.environ["DBR_SECRET_SCOPE"] = SECRET_SCOPE_OVERRIDE
    print(f"DBR_SECRET_SCOPE overridden -> {SECRET_SCOPE_OVERRIDE}")

# COMMAND ----------
# ── Delta table pre-flight check ─────────────────────────────────────────────
# Check whether generator_serial is populated in the Delta table.
# If all NULLs, the VS index won't match any filter — this is the root cause
# of all-zero recall results.
try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    from config import EMBEDDINGS_TABLE, FSR_REF_VIEW
    spark = SparkSession.builder.getOrCreate()
    _df = spark.table(EMBEDDINGS_TABLE)
    _total = _df.count()
    _null_serial  = _df.filter(F.col("generator_serial").isNull()).count()
    _nunique = _df.filter(F.col("generator_serial").isNotNull()).select("generator_serial").distinct().count()
    print(f"[PRE-FLIGHT] Delta table {EMBEDDINGS_TABLE}:")
    print(f"  total rows     : {_total}")
    print(f"  NULL serial    : {_null_serial}  ({100*_null_serial/max(_total,1):.0f}%)")
    print(f"  distinct serial: {_nunique}")
    _all_serials = sorted([
        r["generator_serial"]
        for r in _df.filter(F.col("generator_serial").isNotNull())
                    .select("generator_serial").distinct().collect()
    ])
    print(f"  all serials in index ({len(_all_serials)}): {_all_serials}")

    # Cross-reference against GT serials
    from evaluate_retrieval import load_ground_truth
    _gt, _gt_serials = load_ground_truth()
    _in_index  = [s for s in _gt_serials if s in _all_serials]
    _missing   = [s for s in _gt_serials if s not in _all_serials]
    print(f"\n[PRE-FLIGHT] GT serials ({len(_gt_serials)}): {_gt_serials}")
    print(f"  FOUND in index  ({len(_in_index)}): {_in_index}")
    print(f"  MISSING from index ({len(_missing)}): {_missing}")
    if _missing:
        print(f"\n[PRE-FLIGHT] WARNING: {len(_missing)} GT serials have NO chunks in the index.")
        print("  These PDFs may not have been ingested, or the serial enrichment")
        print("  join (pdf_name -> s3_filename -> esn) failed for these machines.")
        # Show which pdf_names exist for each missing serial (via ref view if accessible)
        try:
            _ref = spark.sql(f"""
                SELECT esn, COUNT(*) AS pdf_count, COLLECT_LIST(s3_filename)[0] AS sample_pdf
                FROM {FSR_REF_VIEW}
                WHERE esn IN ({','.join(repr(s) for s in _missing)})
                GROUP BY esn
            """)
            print(f"\n[PRE-FLIGHT] ref_view entries for missing serials:")
            _ref.show(20, truncate=False)
        except Exception as _ref_e:
            print(f"[PRE-FLIGHT] Could not query ref_view: {_ref_e}")
    if _null_serial > 0:
        print(f"\n[PRE-FLIGHT] {_null_serial} rows have NULL serial — attempting ref_view enrichment fallback...")
        from delta_store import merge_ref_view_metadata
        merge_ref_view_metadata(spark)
        _after_null = spark.table(EMBEDDINGS_TABLE).filter(F.col("generator_serial").isNull()).count()
        _after_distinct = spark.table(EMBEDDINGS_TABLE).filter(F.col("generator_serial").isNotNull()).select("generator_serial").distinct().count()
        print(f"  After ref_view fallback: {_after_null} still NULL, {_after_distinct} distinct serials")
        if _after_null > 0:
            print("  Some rows still have NULL generator_serial after ref_view enrichment.")
            print("  The cleaned package no longer includes the old text-based backfill path.")
            print("  Re-run the pipeline or repair serials upstream if these rows matter for evaluation.")
        # Re-check GT overlap
        _all_serials_after = sorted([
            r["generator_serial"]
            for r in spark.table(EMBEDDINGS_TABLE)
                        .filter(F.col("generator_serial").isNotNull())
                        .select("generator_serial").distinct().collect()
        ])
        _in_after  = [s for s in _gt_serials if s in _all_serials_after]
        _miss_after = [s for s in _gt_serials if s not in _all_serials_after]
        print(f"  GT serials FOUND after fallback ({len(_in_after)}): {_in_after}")
        print(f"  GT serials STILL MISSING ({len(_miss_after)}): {_miss_after}")
except Exception as _e:
    print(f"[PRE-FLIGHT] Spark check failed (non-fatal): {_e}")

# COMMAND ----------

from evaluate_retrieval import evaluate_all

df = evaluate_all(
    max_k=MAX_K,
    max_issues=MAX_ISSUES,
    include_criteria=INCLUDE_EVAL_CRITERIA,
)
print(f"\nEvaluation complete: {len(df)} rows")
print(f"Raw CSV    : {df.attrs.get('raw_path', 'n/a')}")
print(f"Summary CSV: {df.attrs.get('summary_path', 'n/a')}")
print(f"Query mode : {df.attrs.get('query_variant', 'n/a')}")

# COMMAND ----------

# ── Display results ─────────────────────────────────────────────────────────
import pandas as pd

# Summary table (avg metrics by mode and k)
summary = (
    df.groupby(["query_variant", "mode", "k"])
    .agg(
        n_queries=("serial", "count"),
        avg_recall=("recall_at_k", "mean"),
        avg_precision=("precision_at_k", "mean"),
    )
    .reset_index()
)

# Show key k values
mode_order = [
    "ann_retrieval",
    "ann_reranking",
    "hybrid_retrieval",
    "hybrid_reranking",
]
for mode in mode_order:
    mdf = summary[summary["mode"] == mode]
    if mdf.empty:
        continue
    print(f"\n{mode.upper()}:")
    display(mdf[mdf["k"].isin([1, 3, 5, 10, 15, 20])])

# COMMAND ----------

# Full raw results (scroll to explore)
display(df)

# COMMAND ----------

# Return compact result metadata to Jobs API callers.
import json

summary_k = summary[summary["k"].isin([1, 3, 5, 10, 15, 20])].copy()
payload = {
    "status": "SUCCESS",
    "raw_csv": df.attrs.get("raw_path", ""),
    "summary_csv": df.attrs.get("summary_path", ""),
    "query_variant": df.attrs.get("query_variant", ""),
    "summary": summary_k.to_dict(orient="records"),
}
dbutils.notebook.exit(json.dumps(payload))
