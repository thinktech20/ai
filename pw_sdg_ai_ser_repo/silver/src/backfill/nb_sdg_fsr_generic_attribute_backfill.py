# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_generic_attribute_backfill — Notebook wrapper for the generic
# attribute backfill runner.
#
# Thin wrapper that:
#   1. Installs runtime libraries (%pip install pdfplumber)
#   2. Loads the generic_attribute_backfill runner via %run (FSR house style)
#   3. Reads job parameters via get_runtime_param (env → widget → default)
#      and exports them as env vars so the runner's argparse env-var defaults
#      pick them up
#   4. Invokes main() with an empty argv so argparse falls back to defaults
#
# Aligns task shape with the rest of the FSR fleet (notebook_task on default
# job compute) — no spark_python_task, no job_clusters block in bundle YAML.
#
# Run params (all optional, defaults match generic_attribute_backfill._parse_args):
#   FSR_METADATA_TABLE
#   FSR_BACKFILL_NAME           (default: "document_summary_toc")
#   FSR_BACKFILL_BATCH_SIZE     (default: "200")
#   FSR_BACKFILL_SAMPLE_LIMIT   (default: "0" — 0 means no limit)
#   FSR_BACKFILL_DRY_RUN        (default: "false")
#   FSR_DQ_LOG_TABLE
#   FSR_RUN_LOG_TABLE
#   FSR_CHUNK_TABLE
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet pdfplumber

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

# MAGIC %run ./generic_attribute_backfill

# COMMAND ----------

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.generic_backfill_nb")

_PARAM_NAMES = (
    "FSR_METADATA_TABLE",
    "FSR_BACKFILL_NAME",
    "FSR_BACKFILL_BATCH_SIZE",
    "FSR_BACKFILL_SAMPLE_LIMIT",
    "FSR_BACKFILL_DRY_RUN",
    "FSR_DQ_LOG_TABLE",
    "FSR_RUN_LOG_TABLE",
    "FSR_CHUNK_TABLE",
)

for _name in _PARAM_NAMES:
    _val = get_runtime_param(_name, "")
    if _val:
        os.environ[_name] = _val

log.info("=== FSR Generic Attribute Backfill (notebook wrapper) ===")
for _name in _PARAM_NAMES:
    log.info(f"  {_name:28s} = {os.environ.get(_name, '')!r}")

# Bypass argparse sys.argv parsing — let env-var defaults supply every flag.
sys.argv = ["generic_attribute_backfill"]
main()  # noqa: F821 — supplied by %run above
