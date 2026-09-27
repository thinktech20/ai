# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_v2_ddl — Create FSR v2 pipeline tables (metadata_v2 + chunks_v2)
#
# Idempotent by default: uses CREATE TABLE IF NOT EXISTS.
# Run once before P1/P2/P3 to ensure tables, index, and parsed-doc volume exist.
#
# Set RESET_FSR_V2=true for a full dev reset before recreation. This drops the
# configured tables, vector-search index, and parsed-doc volume contents.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

dbutils.widgets.text("METADATA_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_metadata_v2")  # noqa: F821
dbutils.widgets.text("CHUNK_TABLE_V2",    "vaid.ai_std_con_field_service_report.fsr_chunks_v2")     # noqa: F821
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")  # noqa: F821
dbutils.widgets.text("RUN_LOG_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_run_log_v2")  # noqa: F821
dbutils.widgets.text("DQ_LOG_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_data_quality_log_v2")  # noqa: F821
dbutils.widgets.text("FSR_ATTACHMENT_EXECUTION_TABLE", "vaid.ai_std_con_field_service_report.sdg_user_attachments_execution_log_psot")  # noqa: F821
dbutils.widgets.text("VS_INDEX_V2",       "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")  # noqa: F821
dbutils.widgets.text("VS_ENDPOINT_V2",    "pw-ser-sdg-vector-search")                              # noqa: F821
dbutils.widgets.text("FSR_PARSED_DOC_VOLUME_ROOT", "/Volumes/vaid/ai_sot_field_service_report/fsr_parsed_docs")  # noqa: F821
dbutils.widgets.text("FSR_V2_PARSER_VERSION", "pymupdf_v1.0")  # noqa: F821
dbutils.widgets.dropdown("RESET_FSR_V2", "false", ["true", "false"])  # noqa: F821

# COMMAND ----------

# MAGIC %run ../../common/fsr_v2/config

# COMMAND ----------

import logging
import re

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fsr.v2.ddl")
log.info(f"  Metadata table v2 : {METADATA_TABLE_V2}")
log.info(f"  Chunk table v2    : {CHUNK_TABLE_V2}")
log.info(f"  Equip map table v2: {DOC_EQUIPMENT_MAP_TABLE_V2}")
log.info(f"  Run log table v2  : {RUN_LOG_TABLE_V2}")
log.info(f"  DQ log table v2   : {DQ_LOG_TABLE_V2}")
log.info(f"  FSR attach exec tbl: {FSR_ATTACHMENT_EXECUTION_TABLE}")
log.info(f"  VS index v2       : {VS_INDEX_V2}")
log.info(f"  jb_env            : {JB_ENV or 'unset'}")

FSR_PARSED_DOC_VOLUME_ROOT = get_runtime_param("FSR_PARSED_DOC_VOLUME_ROOT", "").strip()  # noqa: F821
FSR_V2_PARSER_VERSION = get_runtime_param("FSR_V2_PARSER_VERSION", "pymupdf_v1.0").strip()  # noqa: F821
RESET_FSR_V2 = get_runtime_param("RESET_FSR_V2", "false").strip().lower() == "true"  # noqa: F821
log.info(f"  Reset FSR v2      : {RESET_FSR_V2}")

if RESET_FSR_V2:
    if JB_ENV == "prod":  # noqa: F821
        raise ValueError("RESET_FSR_V2 is not allowed when jb_env=prod")
    log.warning("RESET_FSR_V2=true: dropping configured FSR v2 tables before recreation")
    for table_name in [
        CHUNK_TABLE_V2,
        DOC_EQUIPMENT_MAP_TABLE_V2,
        METADATA_TABLE_V2,
        RUN_LOG_TABLE_V2,
        DQ_LOG_TABLE_V2,
        FSR_ATTACHMENT_EXECUTION_TABLE,
    ]:
        if table_name:
            spark.sql(f"DROP TABLE IF EXISTS {table_name}")
            log.warning(f"Dropped table: {table_name}")

# COMMAND ----------

# ── Create fsr_metadata_v2 (silver) ──────────────────────────────────────────
# New v2 columns vs v1:
#   preprocessor_regions — JSON char-offset regions for per-chunk ESN attribution
#   inactive_esns        — JSON array of ESNs not applicable this outage
# Removed vs v1:
#   all_esns, esn_detect_status — v1 fan-out artefacts, not needed in v2

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {METADATA_TABLE_V2} (
        {METADATA_TABLE_V2_DDL_COLS}
    )
    USING DELTA
    COMMENT 'FSR v2 document-level metadata registry with preprocessor region attribution'
    TBLPROPERTIES (
        'delta.enableChangeDataFeed'           = 'true',
        'delta.autoOptimize.optimizeWrite'     = 'true'
    )
""")
log.info(f"Metadata v2 table ready: {METADATA_TABLE_V2}")

# COMMAND ----------

# ── Create fsr_document_equipment_map_v2 (serving helper) ───────────────────
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {DOC_EQUIPMENT_MAP_TABLE_V2} (
        {DOC_EQUIPMENT_MAP_TABLE_V2_DDL_COLS}
    )
    USING DELTA
    COMMENT 'FSR v2 retrieval serving helper: one row per (document_id, esn)'
    TBLPROPERTIES (
        'delta.enableChangeDataFeed'           = 'true',
        'delta.autoOptimize.optimizeWrite'     = 'true'
    )
""")
log.info(f"Document equipment map v2 table ready: {DOC_EQUIPMENT_MAP_TABLE_V2}")

# COMMAND ----------

# ── Create fsr_chunks_v2 (gold) ───────────────────────────────────────────────
# New v2 columns vs v1:
#   region_primary_equip_type — top-level VS filtering column (attributed per chunk via region)
#   region_primary_esn        — region-attributed, one row per chunk (not fan-out)
# Key change vs v1:
#   metadata JSON varies per chunk based on which preprocessor_region the chunk falls in

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CHUNK_TABLE_V2} (
        {CHUNK_TABLE_V2_DDL_COLS}
    )
    USING DELTA
    COMMENT 'FSR v2 chunk rows with per-region ESN attribution and embeddings'
    TBLPROPERTIES (
        'delta.enableChangeDataFeed'                = 'true',
        'delta.deletedFileRetentionDuration'        = 'interval 30 days',
        'delta.autoOptimize.optimizeWrite'          = 'true'
    )
""")
log.info(f"Chunk v2 table ready: {CHUNK_TABLE_V2}")

# COMMAND ----------

# ── Create fsr_run_log_v2 (operational) ─────────────────────────────────────

if RUN_LOG_TABLE_V2:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {RUN_LOG_TABLE_V2} (
            {RUN_LOG_TABLE_V2_DDL_COLS}
        )
        USING DELTA
        COMMENT 'FSR v2 pipeline run audit log'
    """)
    log.info(f"Run log v2 table ready: {RUN_LOG_TABLE_V2}")
else:
    log.info("RUN_LOG_TABLE_V2 not configured — skipping run log table creation")

# COMMAND ----------

# ── Create fsr_data_quality_log_v2 (operational) ────────────────────────────

if DQ_LOG_TABLE_V2:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {DQ_LOG_TABLE_V2} (
            {DQ_LOG_TABLE_V2_DDL_COLS}
        )
        USING DELTA
        COMMENT 'FSR v2 validation and pipeline data quality findings'
    """)
    log.info(f"DQ log v2 table ready: {DQ_LOG_TABLE_V2}")
else:
    log.info("DQ_LOG_TABLE_V2 not configured — skipping DQ log table creation")

# COMMAND ----------

# ── Create FSR attachment execution table (sdg_user_attachments_execution_log_psot) ──

if FSR_ATTACHMENT_EXECUTION_TABLE:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {FSR_ATTACHMENT_EXECUTION_TABLE} (
            {FSR_ATTACHMENT_EXECUTION_TABLE_DDL_COLS}
        )
        USING DELTA
        COMMENT 'The table stores execution logs for user attachments, including details about uploaded files, such as PDF names and upload dates, as well as information about the processing stages and status. This data can be used to track the progress of attachment processing, identify potential issues, and analyze the performance of different stages.'
        TBLPROPERTIES (
            'delta.enableDeletionVectors'      = 'true',
            'delta.columnMapping.mode'         = 'name',
            'delta.minReaderVersion'           = '3',
            'delta.minWriterVersion'           = '7',
            'delta.parquet.compression.codec' = 'zstd'
        )
    """)
    log.info(f"FSR attachment execution table ready: {FSR_ATTACHMENT_EXECUTION_TABLE}")
else:
    log.info("FSR_ATTACHMENT_EXECUTION_TABLE not configured — skipping FSR attachment execution table creation")

# COMMAND ----------

# ── Create VS index (fsr_vs_index_v2) ─────────────────────────────────────────
# Uses REST API (same pattern as ER/MND DDL) — no SDK dependency.
# Idempotent: skips creation if the index already exists.

import json
import os as _os
import ssl
import urllib.request
import urllib.error

def _get_dbr_auth():
    try:
        from pyspark.sql import SparkSession as _SS
        _host = _SS.builder.getOrCreate().conf.get("spark.databricks.workspaceUrl")
        _ws = f"https://{_host}"
    except Exception:
        _ws = _os.getenv("DATABRICKS_HOST", "")
    try:
        _tok = (dbutils.notebook.entry_point  # noqa: F821
                .getDbutils().notebook().getContext().apiToken().get())
    except Exception:
        _tok = _os.getenv("DATABRICKS_TOKEN", "")
    return _ws, _tok or ""

def _check_vs_index(_ws_url, _token, _index_name, _ctx):
    _url = f"{_ws_url}/api/2.0/vector-search/indexes/{_index_name}"
    _req = urllib.request.Request(_url, headers={"Authorization": f"Bearer {_token}"})
    with urllib.request.urlopen(_req, context=_ctx, timeout=30) as _r:  # noqa: S310
        return json.loads(_r.read())

if VS_INDEX_V2 and VS_ENDPOINT_V2:
    _ws_url, _token = _get_dbr_auth()
    _ctx = ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = ssl.CERT_NONE

    # 1. Check endpoint state
    try:
        _ep_url = f"{_ws_url}/api/2.0/vector-search/endpoints/{VS_ENDPOINT_V2}"
        _ep_req = urllib.request.Request(_ep_url, headers={"Authorization": f"Bearer {_token}"})
        with urllib.request.urlopen(_ep_req, context=_ctx, timeout=30) as _resp:  # noqa: S310
            _ep_info = json.loads(_resp.read())
        _ep_state = _ep_info.get("endpoint_status", {}).get("state", "UNKNOWN")
        log.info(f"VS endpoint '{VS_ENDPOINT_V2}' state: {_ep_state}")
        if _ep_state != "ONLINE":
            log.warning(f"VS endpoint is NOT ONLINE (state={_ep_state}) — index creation may fail")
    except Exception as _e:
        log.warning(f"VS endpoint check failed (non-blocking): {_e}")

    # 2. Check / create index
    _index_exists = False
    if RESET_FSR_V2:
        _delete_url = f"{_ws_url}/api/2.0/vector-search/indexes/{VS_INDEX_V2}"
        _delete_req = urllib.request.Request(
            _delete_url,
            headers={"Authorization": f"Bearer {_token}"},
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(_delete_req, context=_ctx, timeout=30):  # noqa: S310
                log.warning(f"Dropped VS index: {VS_INDEX_V2}")
        except urllib.error.HTTPError as _e:
            if _e.code == 404:
                log.info(f"VS index not found (already absent): {VS_INDEX_V2}")
            else:
                _body = _e.read().decode(errors="replace")[:500]
                raise RuntimeError(
                    f"VS index deletion failed: HTTP {_e.code} — {_body}"
                ) from _e

    try:
        _idx_status = _check_vs_index(_ws_url, _token, VS_INDEX_V2, _ctx)
        log.info(f"VS index '{VS_INDEX_V2}' already exists — status: "
                 f"{_idx_status.get('status', 'unknown')}")
        _index_exists = True
    except urllib.error.HTTPError as _e:
        if _e.code == 404:
            log.info(f"VS index '{VS_INDEX_V2}' does not exist — will create")
        else:
            _body = _e.read().decode(errors="replace")[:500]
            log.error(f"VS index check failed: HTTP {_e.code} — {_body}")

    if not _index_exists:
        _create_payload = {
            "name": VS_INDEX_V2,
            "endpoint_name": VS_ENDPOINT_V2,
            "primary_key": "chunk_id",
            "index_type": "DELTA_SYNC",
            "delta_sync_index_spec": {
                "source_table": CHUNK_TABLE_V2,
                "pipeline_type": "TRIGGERED",
                "embedding_vector_columns": [
                    {"name": "chunk_embedding", "embedding_dimension": 3072}
                ],
                "columns_to_sync": [
                    "chunk_id", "chunk_index", "document_id", "pdf_name",
                    "page_number", "chunk_text",
                    "region_primary_esn", "region_primary_equip_type", "active_esns",
                    "report_date", "outage_start_date", "metadata", "created_at",
                ],
            },
        }
        log.info(f"Creating VS index: {json.dumps(_create_payload)}")
        try:
            _create_url = f"{_ws_url}/api/2.0/vector-search/indexes"
            _req = urllib.request.Request(
                _create_url,
                data=json.dumps(_create_payload).encode(),
                headers={"Authorization": f"Bearer {_token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(_req, context=_ctx, timeout=60) as _resp:  # noqa: S310
                _resp_body = json.loads(_resp.read())
            log.info(f"VS index created: {_resp_body}")
        except urllib.error.HTTPError as _e:
            _body = _e.read().decode(errors="replace")[:500]
            log.error(f"VS index creation failed: HTTP {_e.code} — {_body}")
            log.error(f"  Source table : {CHUNK_TABLE_V2}")
            log.error(f"  Endpoint     : {VS_ENDPOINT_V2}")
else:
    log.info("VS_INDEX_V2 or VS_ENDPOINT_V2 not configured — skipping VS index creation")

# COMMAND ----------

# ── Create parsed-doc volume directory ───────────────────────────────────────
if FSR_PARSED_DOC_VOLUME_ROOT:
    volume_match = re.fullmatch(
        r"/Volumes/([^/]+)/([^/]+)/([^/]+)(?:/.*)?",
        FSR_PARSED_DOC_VOLUME_ROOT,
    )
    if not volume_match:
        raise ValueError(
            "FSR_PARSED_DOC_VOLUME_ROOT must use /Volumes/<catalog>/<schema>/<volume>"
        )
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", FSR_V2_PARSER_VERSION):
        raise ValueError("FSR_V2_PARSER_VERSION contains unsupported path characters")

    volume_catalog, volume_schema, volume_name = volume_match.groups()
    if RESET_FSR_V2:
        log.warning(
            f"RESET_FSR_V2=true: dropping parsed-doc volume "
            f"{volume_catalog}.{volume_schema}.{volume_name}"
        )
        spark.sql(
            f"DROP VOLUME IF EXISTS `{volume_catalog}`.`{volume_schema}`.`{volume_name}`"
        )
    spark.sql(
        f"CREATE VOLUME IF NOT EXISTS `{volume_catalog}`.`{volume_schema}`.`{volume_name}`"
    )
    log.info(
        f"Parsed doc volume ready: {volume_catalog}.{volume_schema}.{volume_name}"
    )
    dbutils.fs.mkdirs(FSR_PARSED_DOC_VOLUME_ROOT)  # noqa: F821
    versioned_path = f"{FSR_PARSED_DOC_VOLUME_ROOT.rstrip('/')}/{FSR_V2_PARSER_VERSION}"
    dbutils.fs.mkdirs(versioned_path)  # noqa: F821
    log.info(f"Parsed doc directories ready: {FSR_PARSED_DOC_VOLUME_ROOT}, {versioned_path}")
else:
    log.info("FSR_PARSED_DOC_VOLUME_ROOT not set — skipping volume dir creation")

# COMMAND ----------

# ── Verify ────────────────────────────────────────────────────────────────────

_tables_to_verify = [METADATA_TABLE_V2, DOC_EQUIPMENT_MAP_TABLE_V2, CHUNK_TABLE_V2]
if RUN_LOG_TABLE_V2:
    _tables_to_verify.append(RUN_LOG_TABLE_V2)
if DQ_LOG_TABLE_V2:
    _tables_to_verify.append(DQ_LOG_TABLE_V2)
if FSR_ATTACHMENT_EXECUTION_TABLE:
    _tables_to_verify.append(FSR_ATTACHMENT_EXECUTION_TABLE)

for table_name in _tables_to_verify:
    count = spark.sql(f"SELECT COUNT(*) AS n FROM {table_name}").first().n
    cols  = len(spark.table(table_name).columns)
    log.info(f"  {table_name}: {count} rows, {cols} columns")
