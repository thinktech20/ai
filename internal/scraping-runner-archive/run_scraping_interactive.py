# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# FSR Scraping Pipeline — Interactive / Dev Runner
#
# SAFE wrapper around the DS-team scraping pipeline.
# Defaults: 10 PDFs only, writes to a __dev_tmp table, FORCE_RESET=True.
#
# Attach to: ai-pw-ser-ds-dev-apc  (or Serverless)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet pdfplumber litellm openpyxl

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# ── SAFE OVERRIDES ───────────────────────────────────────────────────────────
# These env vars are read by the pipeline *before* widget defaults kick in.
# They ensure we never accidentally write to the real table.
import os

# ⚠️  TEMPORARY output table — not the real one
_DEV_OUTPUT = "main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref__dev_tmp"
os.environ["FSR_OUTPUT_TABLE"] = _DEV_OUTPUT

# Process only a small sample by default (change to "" or unset for all)
os.environ.setdefault("FSR_MAX_PDFS", "10")

# Force fresh run each time during dev
os.environ.setdefault("FORCE_RESET", "true")

# Keep concurrency low for interactive use
os.environ.setdefault("FSR_BATCH_SIZE", "4")
os.environ.setdefault("FSR_BATCH_THREADS", "2")
os.environ.setdefault("FSR_LLM_CONCURRENCY", "2")

print(f"Output table:  {_DEV_OUTPUT}")
print(f"Max PDFs:      {os.environ.get('FSR_MAX_PDFS', 'ALL')}")

# COMMAND ----------

# ── Run the actual pipeline ──────────────────────────────────────────────────
# The %run magic executes the original notebook in this notebook's context,
# inheriting the env-var overrides set above.

# MAGIC %run ../../poc/ds-experimentation-code/fsr_scraping/run_scraping_pipeline

# COMMAND ----------

# ── Post-run inspection ─────────────────────────────────────────────────────
from pyspark.sql import SparkSession
spark = SparkSession.builder.getOrCreate()

print(f"\n{'='*60}")
print(f"Dev output table: {_DEV_OUTPUT}")
print(f"{'='*60}\n")

df = spark.read.table(_DEV_OUTPUT)
print(f"Total rows: {df.count()}")
print(f"Distinct PDFs: {df.select('pdf_name').distinct().count()}")
print(f"\nNull rates:")
for c in df.columns:
    null_count = df.filter(df[c].isNull() | (df[c] == "")).count()
    print(f"  {c}: {null_count}/{df.count()} ({100*null_count/max(df.count(),1):.0f}%)")

display(df.limit(20))

# COMMAND ----------

# ── Cleanup (uncomment when done) ───────────────────────────────────────────
# spark.sql(f"DROP TABLE IF EXISTS {_DEV_OUTPUT}")
# print(f"Dropped {_DEV_OUTPUT}")
