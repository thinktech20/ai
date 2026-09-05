# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# FSR Hybrid Retrieval Pipeline
# Compute: Serverless (or cluster ai-pw-ser-ds-dev-apc if needed)  (DEV workspace)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet \
# MAGIC   typing_extensions>=4.12.0 \
# MAGIC   langchain-core>=0.1.24 \
# MAGIC   langchain-text-splitters>=0.0.1 \
# MAGIC   PyMuPDF>=1.23.0 \
# MAGIC   pandas \
# MAGIC   httpx \
# MAGIC   python-dotenv \
# MAGIC   requests \
# MAGIC   databricks-vectorsearch \
# MAGIC   openpyxl

# COMMAND ----------

# Restart Python so the freshly installed typing_extensions is loaded
# instead of the older version bundled with the Databricks runtime.
dbutils.library.restartPython()

# COMMAND ----------

import sys
import os
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
    category=UserWarning,
)

# ── Resolve src/ directory ──────────────────────────────────────────────────
# Notebooks are stored at e.g.  /Users/you@ge.com/fsr_pipeline/run_pipeline
# Source files live at         /Workspace/Users/you@ge.com/fsr_pipeline/src/
try:
    _ctx          = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    _nb_path      = _ctx.notebookPath().get()           # /Users/.../run_pipeline
    _ws_dir       = "/Workspace" + str(Path(_nb_path).parent)
    _src_dir      = _ws_dir + "/src"
except Exception:
    # Fallback when running as a script outside Databricks
    _src_dir = str(Path(__file__).parent / "src") if "__file__" in dir() else "./src"

if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

print(f"[OK] src path: {_src_dir}")
print(f"[OK] Files:    {sorted(os.listdir(_src_dir))}")

# COMMAND ----------

# ── Optional parameters ─────────────────────────────────────────────────────
# Set FORCE_RESET = True to truncate the chunk / embedding Delta tables and
# reprocess every PDF from scratch.  Leave False for incremental runs.
try:
    from config import FORCE_RESET as CONFIG_FORCE_RESET
except Exception:
    CONFIG_FORCE_RESET = False

FORCE_RESET = bool(CONFIG_FORCE_RESET)

# Allow Jobs API base_parameters to override (e.g. {"FORCE_RESET": "false"}).
try:
    _force_reset_param = dbutils.widgets.get("FORCE_RESET")
    if str(_force_reset_param).strip() != "":
        FORCE_RESET = str(_force_reset_param).strip().lower() in (
            "1", "true", "t", "yes", "y", "on"
        )
        print(f"FORCE_RESET overridden via job parameter -> {FORCE_RESET}")
except Exception:
    pass

# Limit the number of PDFs to chunk/embed. Set to None to process all.
# Useful for testing – e.g. set to 5 to process only the first 5 PDFs.
MAX_PDFS = None

# Optional source table whose pdf_name values define a targeted reingest subset.
# Example: main.gp_services_sdg_poc.field_service_report_gt_litellm
DOC_SOURCE_TABLE = ""
try:
    _doc_source_param = dbutils.widgets.get("DOC_SOURCE_TABLE")
    if str(_doc_source_param).strip() != "":
        DOC_SOURCE_TABLE = str(_doc_source_param).strip()
        print(f"DOC_SOURCE_TABLE overridden via job parameter -> {DOC_SOURCE_TABLE}")
except Exception:
    pass

# When targeting a subset, delete existing base-table rows for those PDFs before reprocessing.
REPLACE_EXISTING_DOCS = False
try:
    _replace_existing_param = dbutils.widgets.get("REPLACE_EXISTING_DOCS")
    if str(_replace_existing_param).strip() != "":
        REPLACE_EXISTING_DOCS = str(_replace_existing_param).strip().lower() in (
            "1", "true", "t", "yes", "y", "on"
        )
        print(f"REPLACE_EXISTING_DOCS overridden via job parameter -> {REPLACE_EXISTING_DOCS}")
except Exception:
    pass

# Override the Vector Search endpoint name if it differs from the default in config.py
# Leave as "" to use the value from config.py / environment variable.
VS_ENDPOINT_OVERRIDE = ""
try:
    _vs_endpoint_param = dbutils.widgets.get("VS_ENDPOINT_OVERRIDE")
    if str(_vs_endpoint_param).strip() != "":
        VS_ENDPOINT_OVERRIDE = str(_vs_endpoint_param).strip()
        print(f"VS_ENDPOINT_OVERRIDE overridden via job parameter -> {VS_ENDPOINT_OVERRIDE}")
except Exception:
    pass

# Override the Databricks secret scope name if it differs from the default "fsr-pipeline".
# Leave as "" to use the default.
SECRET_SCOPE_OVERRIDE = "fsr-pipeline"
try:
    _secret_scope_param = dbutils.widgets.get("SECRET_SCOPE_OVERRIDE")
    if str(_secret_scope_param).strip() != "":
        SECRET_SCOPE_OVERRIDE = str(_secret_scope_param).strip()
        print(f"SECRET_SCOPE_OVERRIDE overridden via job parameter -> {SECRET_SCOPE_OVERRIDE}")
except Exception:
    pass

# Override the ESN-identification chat model for this run.
# Leave as "" to use the default from esn_identifier.py.
ESN_LLM_MODEL_OVERRIDE = ""
try:
    _esn_llm_model_param = dbutils.widgets.get("ESN_LLM_MODEL_OVERRIDE")
    if str(_esn_llm_model_param).strip() != "":
        ESN_LLM_MODEL_OVERRIDE = str(_esn_llm_model_param).strip()
        print(f"ESN_LLM_MODEL_OVERRIDE overridden via job parameter -> {ESN_LLM_MODEL_OVERRIDE}")
except Exception:
    pass

# Set to True to run retrieval evaluation after the pipeline finishes.
RUN_EVALUATION = True
try:
    _run_evaluation_param = dbutils.widgets.get("RUN_EVALUATION")
    if str(_run_evaluation_param).strip() != "":
        RUN_EVALUATION = str(_run_evaluation_param).strip().lower() in (
            "1", "true", "t", "yes", "y", "on"
        )
        print(f"RUN_EVALUATION overridden via job parameter -> {RUN_EVALUATION}")
except Exception:
    pass

# Maximum k for evaluation metrics (Recall@K, Precision@K for k=1..MAX_K)
EVAL_MAX_K = 20

# COMMAND ----------

if VS_ENDPOINT_OVERRIDE:
    os.environ["VS_ENDPOINT_NAME"] = VS_ENDPOINT_OVERRIDE
    print(f"VS_ENDPOINT_NAME overridden → {VS_ENDPOINT_OVERRIDE}")

if SECRET_SCOPE_OVERRIDE:
    os.environ["DBR_SECRET_SCOPE"] = SECRET_SCOPE_OVERRIDE
    print(f"DBR_SECRET_SCOPE overridden → {SECRET_SCOPE_OVERRIDE}")

if ESN_LLM_MODEL_OVERRIDE:
    os.environ["ESN_LLM_MODEL"] = ESN_LLM_MODEL_OVERRIDE
    print(f"ESN_LLM_MODEL overridden → {ESN_LLM_MODEL_OVERRIDE}")

# COMMAND ----------

from pipeline import main

main(
    force_reset=FORCE_RESET,
    max_pdfs=MAX_PDFS,
    doc_source_table=DOC_SOURCE_TABLE or None,
    replace_existing_docs=REPLACE_EXISTING_DOCS,
)
print("\n✅ Pipeline completed successfully")

# COMMAND ----------

# ── Retrieval Evaluation ────────────────────────────────────────────────────
# Runs ground-truth evaluation against Heat Map queries and FSR citations.
# Set RUN_EVALUATION = False above to skip.

if RUN_EVALUATION:
    from evaluate_retrieval import evaluate_all
    eval_df = evaluate_all(max_k=EVAL_MAX_K)
    print(f"\nEvaluation complete: {len(eval_df)} result rows")
else:
    print("Evaluation skipped (RUN_EVALUATION = False)")

# COMMAND ----------

# ── Evaluation results ──────────────────────────────────────────────────────
if RUN_EVALUATION:
    if eval_df.empty:
        print(
            "Evaluation produced 0 rows; skipping summary display. "
            "This means no evaluable ground-truth (issue, ESN) pairs overlapped "
            "with the configured heat map query set.")
    else:
        summary = (
            eval_df.groupby(["mode", "k"])
            .agg(
                n_queries=("serial", "count"),
                avg_recall=("recall_at_k", "mean"),
                avg_precision=("precision_at_k", "mean"),
            )
            .reset_index()
        )
        for mode in ("retrieval", "reranking"):
            print(f"\n{mode.upper()}:")
            mdf = summary[summary["mode"] == mode]
            display(mdf[mdf["k"].isin([1, 3, 5, 10, 15, 20])])
