# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "1"
# ///
dbutils.library.restartPython()

# COMMAND ----------

# ─────────────────────────────────────────────────────────────────────────────
# TIL Pipeline DDL — Create core pipeline tables (idempotent, safe)
#
# Purpose:
#   Ensures all TIL pipeline tables exist with correct schemas before jobs run.
#   Idempotent: CREATE TABLE IF NOT EXISTS means this is safe to run multiple times.
#   No destructive operations (no DROP, no TRUNCATE, no FORCE_RESET).
#
# Tables created (v1):
#   - til_metadata: Document-level registry + status for metadata and chunk stages
#   - til_elements: Optional granular extraction elements for traceability
#   - til_chunks: Retrieval-ready chunks with embeddings
#   - til_validation_results: Quality findings per document/rule
#   - til_evaluation_results: Method-comparison metrics (Process 1, Process 2, etc.)
#   - til_pipeline_run_audit: Run-level outcomes per job
#   - til_profile: Legacy profile-extraction output
#
# Design reference: TIL design doc
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

import logging
import sys

from common.tils.til_config import JB_ENV, TIL_CATALOG, TIL_SCHEMA
from contracts.table_specs.tils import (
    TIL_CHUNKS_TABLE,
    TIL_CHUNKS_TABLE_DDL_COLS,
    TIL_ELEMENTS_TABLE,
    TIL_ELEMENTS_TABLE_DDL_COLS,
    TIL_EVALUATION_RESULTS_TABLE,
    TIL_EVALUATION_RESULTS_TABLE_DDL_COLS,
    TIL_METADATA_TABLE,
    TIL_METADATA_TABLE_DDL_COLS,
    TIL_PIPELINE_RUN_AUDIT_TABLE,
    TIL_PIPELINE_RUN_AUDIT_TABLE_DDL_COLS,
    TIL_PROFILE_TABLE,
    TIL_PROFILE_TABLE_DDL_COLS,
    TIL_VALIDATION_RESULTS_TABLE,
    TIL_VALIDATION_RESULTS_TABLE_DDL_COLS,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    force=True,
)
for handler in logging.getLogger().handlers:
    handler.setLevel(logging.WARNING)
logging.getLogger("py4j").setLevel(logging.WARNING)
logging.getLogger("py4j.clientserver").setLevel(logging.WARNING)
log = logging.getLogger("til.ddl")
log.setLevel(logging.INFO)
log.propagate = False
if not any(getattr(h, "name", "") == "til-ddl-stdout" for h in log.handlers):
    _handler = logging.StreamHandler(sys.stdout)
    _handler.name = "til-ddl-stdout"
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s"))
    log.addHandler(_handler)

# Configuration (driven by shared TIL config)
ENVIRONMENT = JB_ENV or "dev"  # dev | staging | prod

# Derive table names
prefix = f"{TIL_CATALOG}.{TIL_SCHEMA}"
tables_metadata = TIL_METADATA_TABLE
tables_elements = TIL_ELEMENTS_TABLE
tables_chunks = TIL_CHUNKS_TABLE
tables_validation = TIL_VALIDATION_RESULTS_TABLE
tables_evaluation = TIL_EVALUATION_RESULTS_TABLE
tables_audit = TIL_PIPELINE_RUN_AUDIT_TABLE
tables_profile = TIL_PROFILE_TABLE
tables_all = [
    tables_metadata,
    tables_elements,
    tables_chunks,
    tables_validation,
    tables_evaluation,
    tables_audit,
    tables_profile,
]

log.info(f"Environment: {ENVIRONMENT}")

# COMMAND ----------

# ── Ensure schema exists ────────────────────────────────────────────────────

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {prefix}")
log.info(f"Schema ready: {prefix}")

# COMMAND ----------

# ── Create til_metadata ─────────────────────────────────────────────────────
# Registry and profile extraction output per TIL document.
# Key-driving table for metadata extraction stage (Stage A).

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {tables_metadata} (
        {TIL_METADATA_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'TIL metadata registry: document-level profile extraction outcomes'
    TBLPROPERTIES (
        'delta.feature.allowColumnDefaults' = 'supported',
        'delta.enableChangeDataFeed' = 'true',
        'delta.autoOptimize.optimizeWrite' = 'true'
    )
""")
log.info(f"Table ready: {tables_metadata}")

# Databricks SQL runtime in this workspace does not support CREATE UNIQUE INDEX.
# Keep uniqueness logically enforced via unique_key generation + merge semantics.

# COMMAND ----------

# ── Create til_elements (optional, for traceability) ───────────────────────

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {tables_elements} (
        {TIL_ELEMENTS_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'TIL extraction elements: granular traceability for parsing audits'
    TBLPROPERTIES (
        'delta.feature.allowColumnDefaults' = 'supported',
        'delta.enableChangeDataFeed' = 'true'
    )
""")
log.info(f"Table ready: {tables_elements}")

# COMMAND ----------

# ── Create til_chunks ───────────────────────────────────────────────────────
# Retrieval-ready chunks with embeddings.
# Source table for Vector Search Delta Sync index.

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {tables_chunks} (
        {TIL_CHUNKS_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'TIL chunks with embeddings: retrieval-ready, Vector Search source'
    TBLPROPERTIES (
        'delta.feature.allowColumnDefaults' = 'supported',
        'delta.enableChangeDataFeed' = 'true',
        'delta.deletedFileRetentionDuration' = 'interval 30 days'
    )
""")
log.info(f"Table ready: {tables_chunks}")

# COMMAND ----------

# ── Create til_validation_results ───────────────────────────────────────────
# Quality findings per document/rule (before deployment to retrieval).

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {tables_validation} (
        {TIL_VALIDATION_RESULTS_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'TIL validation findings: quality gates before retrieval'
    TBLPROPERTIES (
        'delta.feature.allowColumnDefaults' = 'supported',
        'delta.enableChangeDataFeed' = 'true'
    )
""")
log.info(f"Table ready: {tables_validation}")

# COMMAND ----------

# ── Create til_evaluation_results ───────────────────────────────────────────
# Method-comparison results (P1 parser eval, P2 chunker+embedder eval, etc).

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {tables_evaluation} (
        {TIL_EVALUATION_RESULTS_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'TIL method evaluation results: parser selection, quality drift detection'
    TBLPROPERTIES (
        'delta.feature.allowColumnDefaults' = 'supported',
        'delta.enableChangeDataFeed' = 'true'
    )
""")
log.info(f"Table ready: {tables_evaluation}")

# COMMAND ----------

# ── Create til_pipeline_run_audit ───────────────────────────────────────────
# Run-level outcomes per job (SQL-joinable with stage outputs).

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {tables_audit} (
        {TIL_PIPELINE_RUN_AUDIT_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'TIL pipeline run outcomes: job-level observability'
    TBLPROPERTIES (
        'delta.feature.allowColumnDefaults' = 'supported',
        'delta.enableChangeDataFeed' = 'true'
    )
""")
log.info(f"Table ready: {tables_audit}")

# COMMAND ----------

# ── Create til_profile ─────────────────────────────────────────────────────
# Output of the TIL profile ingestion notebook.

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {tables_profile} (
        {TIL_PROFILE_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'TIL profile extraction output'
    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true'
    )
""")
log.info(f"Table ready: {tables_profile}")

# COMMAND ----------

log.info(f"TIL Pipeline DDL complete | schema={prefix} | tables={len(tables_all)}")
