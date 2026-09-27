# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_fsr_v2_dev_debug_single_doc — Run P1 + P2 for a single doc and surface all debug info
#
# Purpose: targeted debugging; lets you inspect exactly what P1 writes to the
#          metadata table (especially parsed_volume_path) and what P2 does with it.
#
# Steps:
#   1. Run P1 (nb_sdg_fsr_v2_metadata) for a single doc
#   2. Dump full metadata row: metadata_status, parsed_volume_path, preprocessor_regions, errors
#   3. Run P2 (nb_sdg_fsr_v2_chunks) for that doc
#   4. Dump chunk results: chunk_status, chunk_error, chunk count + sample chunks
#   5. Trigger VS index sync (P3) so the new chunk is queryable
#
# Widgets:
#   DEBUG_DOC_ID              — single document_id / PDF stem to debug (required)
#   FSR_PARSED_DOC_VOLUME_ROOT — volume path where P1 saves parsed JSONs (required for P2 to work)
#   METADATA_TABLE_V2         — fsr_metadata_v2 table
#   CHUNK_TABLE_V2            — fsr_chunks_v2 table
#   DOC_EQUIPMENT_MAP_TABLE_V2 — fsr_document_equipment_map_v2 table
#   VS_INDEX_V2               — VS index name
#   VS_ENDPOINT_V2            — VS endpoint name
#   FSR_SOURCE_VOLUME_PATHS   — comma-separated source volume paths
#   LITELLM_BASE_URL          — LiteLLM gateway base URL
#   LITELLM_API_KEY           — LiteLLM API key
#   SKIP_P1                   — true: skip P1 and only (re-)run P2 on existing metadata row
#   SKIP_P3                   — true: skip VS index sync (useful when debugging P1/P2 only)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../../common/fsr_v2/config

# COMMAND ----------

import logging
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.getOrCreate()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.debug.single")

# COMMAND ----------

# ── Resolve repo root ─────────────────────────────────────────────────────────
_nb_path_raw = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()  # noqa: F821
_nb_path_dbr = _nb_path_raw if not _nb_path_raw.startswith("/Workspace") else _nb_path_raw[len("/Workspace"):]
_nb_path_fs  = _nb_path_raw if _nb_path_raw.startswith("/Workspace") else f"/Workspace{_nb_path_raw}"
_REPO_NAME   = "pw_sdg_ai_ser_repo"
REPO_ROOT    = _nb_path_dbr[:_nb_path_dbr.index(_REPO_NAME) + len(_REPO_NAME)]
log.info(f"Repo root: {REPO_ROOT}")

# COMMAND ----------

dbutils.widgets.text("DEBUG_DOC_ID",               "65f6535e-e26a-4e7a-bd41-6cdf4eaf1efa")           # noqa: F821
dbutils.widgets.text("FSR_PARSED_DOC_VOLUME_ROOT", "/Volumes/vaid/ai_sot_field_service_report/ms_test_fsr_parsed_docs")  # noqa: F821
dbutils.widgets.text("FSR_SOURCE_VOLUME_PATHS",    "/Volumes/viud/ing_ud_fieldvision/fv_field_service_report,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/FSR_manual,/Volumes/vaid/ai_std_con_field_service_report/fsr_v2_test")  # noqa: F821
dbutils.widgets.text("METADATA_TABLE_V2",          "vaid.ai_sot_field_service_report.ms_test_fsr_metadata_v2")                    # noqa: F821
dbutils.widgets.text("CHUNK_TABLE_V2",             "vaid.ai_std_con_field_service_report.ms_test_fsr_chunks_v2")                  # noqa: F821
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2", "vaid.ai_sot_field_service_report.ms_test_fsr_document_equipment_map_v2")  # noqa: F821
dbutils.widgets.text("LITELLM_BASE_URL",           "https://dev-gateway.apps.gevernova.net")                     # noqa: F821
dbutils.widgets.text("LITELLM_API_KEY",            "")                                                           # noqa: F821
dbutils.widgets.text("VS_INDEX_V2",                "vaid.ai_std_con_field_service_report.ms_test_fsr_vs_index_v2")  # noqa: F821
dbutils.widgets.text("VS_ENDPOINT_V2",             "pw-ser-sdg-vector-search")                                   # noqa: F821
dbutils.widgets.text("SKIP_P1",                    "false")                                                      # noqa: F821
dbutils.widgets.text("SKIP_P3",                    "false")                                                      # noqa: F821
# P1 enrichment dependencies. Without these P1 falls back to empty resolvers
# (blank Generator ESN, blank event/technology fields).
dbutils.widgets.text("FSR_IBAT_TABLE",             "vgpd.prm_std_views.ibat_equipment_mst")                      # noqa: F821
dbutils.widgets.text("FSR_EVENT_VISION_TABLE",     "vgpd.fsr_std_views.eventmgmt_event_vision_sot")              # noqa: F821
dbutils.widgets.text("FSR_PSOT_TABLE",             "vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot")  # noqa: F821
dbutils.widgets.text("FSR_PDF_REF_VIEW",           "vgpp.fsr_std_views.fsr_pdf_ref")                             # noqa: F821

# COMMAND ----------

DEBUG_DOC_ID           = get_runtime_param("DEBUG_DOC_ID", "").strip().strip("'\"")
PARSED_DOC_VOLUME_ROOT = get_runtime_param("FSR_PARSED_DOC_VOLUME_ROOT", "").strip()
SOURCE_VOLUMES         = get_runtime_param("FSR_SOURCE_VOLUME_PATHS", "").strip()
META_TABLE             = get_runtime_param("METADATA_TABLE_V2", METADATA_TABLE_V2).strip()
CHUNK_TABLE            = get_runtime_param("CHUNK_TABLE_V2", CHUNK_TABLE_V2).strip()
MAP_TABLE              = get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2", DOC_EQUIPMENT_MAP_TABLE_V2).strip()
LITELLM_BASE_URL       = get_runtime_param("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net").strip()
LITELLM_API_KEY        = get_runtime_param("LITELLM_API_KEY", "").strip()
VS_INDEX               = get_runtime_param("VS_INDEX_V2", VS_INDEX_V2).strip()
VS_ENDPOINT            = get_runtime_param("VS_ENDPOINT_V2", VS_ENDPOINT_V2).strip()
SKIP_P1                = get_runtime_param("SKIP_P1", "false").strip().lower() == "true"
SKIP_P3                = get_runtime_param("SKIP_P3", "false").strip().lower() == "true"
FSR_IBAT_TABLE         = get_runtime_param("FSR_IBAT_TABLE", "").strip()
FSR_EVENT_VISION_TABLE = get_runtime_param("FSR_EVENT_VISION_TABLE", "").strip()
FSR_PSOT_TABLE         = get_runtime_param("FSR_PSOT_TABLE", "").strip()
FSR_PDF_REF_VIEW       = get_runtime_param("FSR_PDF_REF_VIEW", "").strip()

if not DEBUG_DOC_ID:
    raise ValueError("DEBUG_DOC_ID is required. Set it to the document_id / PDF stem you want to debug.")
if not LITELLM_API_KEY:
    raise ValueError("LITELLM_API_KEY is required.")
if not PARSED_DOC_VOLUME_ROOT:
    log.warning("FSR_PARSED_DOC_VOLUME_ROOT is empty — P1 will not persist parsed JSON, and P2 WILL FAIL with 'Missing parsed_volume_path'. Set this widget.")

log.info("=== FSR v2 Single-Doc Debug ===")
log.info(f"  Doc ID              : {DEBUG_DOC_ID}")
log.info(f"  Parsed doc root     : {PARSED_DOC_VOLUME_ROOT or '(NOT SET)'}")
log.info(f"  Metadata table      : {META_TABLE}")
log.info(f"  Chunk table         : {CHUNK_TABLE}")
log.info(f"  Map table           : {MAP_TABLE}")
log.info(f"  VS index            : {VS_INDEX}")
log.info(f"  Skip P1             : {SKIP_P1}")
log.info(f"  Skip P3             : {SKIP_P3}")

# COMMAND ----------

# ── Pre-run: delete existing rows for this doc so each run is a clean insert ──
_safe_id = DEBUG_DOC_ID.replace("'", "''")
for _tbl in [CHUNK_TABLE, MAP_TABLE, META_TABLE]:
    spark.sql(f"DELETE FROM {_tbl} WHERE LOWER(document_id) = LOWER('{_safe_id}')")
    log.info(f"  Cleaned {_tbl}")

# COMMAND ----------

# ── Step 1: Run P1 ────────────────────────────────────────────────────────────

if not SKIP_P1:
    log.info("=== Running P1 (metadata extraction) ===")
    try:
        p1_result = dbutils.notebook.run(  # noqa: F821
            f"{REPO_ROOT}/silver/src/etl/nb_sdg_fsr_v2_metadata",
            timeout_seconds=3600,
            arguments={
                "jb_env":                    get_runtime_param("jb_env", "dev"),
                "METADATA_TABLE_V2":          META_TABLE,
                "DOC_EQUIPMENT_MAP_TABLE_V2":  MAP_TABLE,
                "INPUT_MODE":                 "volume_list",
                "FSR_TARGET_PDF_NAMES":      DEBUG_DOC_ID,
                "FSR_SOURCE_VOLUME_PATHS":   SOURCE_VOLUMES,
                "LITELLM_BASE_URL":          LITELLM_BASE_URL,
                "LITELLM_API_KEY":           LITELLM_API_KEY,
                "FSR_PARSED_DOC_VOLUME_ROOT": PARSED_DOC_VOLUME_ROOT,
                "FSR_IBAT_TABLE":            FSR_IBAT_TABLE,
                "FSR_EVENT_VISION_TABLE":    FSR_EVENT_VISION_TABLE,
                "FSR_PSOT_TABLE":            FSR_PSOT_TABLE,
                "FSR_PDF_REF_VIEW":          FSR_PDF_REF_VIEW,
            },
        )
        log.info(f"P1 completed: {p1_result}")
        p1_ok = True
    except Exception as _e:
        log.error(f"P1 FAILED: {_e}")
        p1_ok = False
else:
    log.info("=== SKIP_P1=true — skipping P1, using existing metadata row ===")
    p1_ok = True

# COMMAND ----------

# ── Step 2: Inspect metadata row after P1 ─────────────────────────────────────
print("=== Metadata row after P1 ===")
meta_row_df = spark.sql(f"""
    SELECT
        document_id,
        pdf_name,
        volume_path,
        metadata_status,
        metadata_error,
        chunk_status,
        chunk_error,
        CASE WHEN parsed_volume_path IS NOT NULL AND parsed_volume_path <> '' THEN 'SET' ELSE 'MISSING ⚠' END AS parsed_path_present,
        parsed_volume_path,
        parsed_parser_version,
        primary_esn,
        primary_equip_type,
        page_count,
        CASE WHEN preprocessor_regions IS NOT NULL THEN 'present' ELSE 'NULL' END AS preprocessor_regions_present,
        CASE WHEN inactive_esns IS NOT NULL THEN 'present' ELSE 'NULL' END AS inactive_esns_present,
        pipeline_version,
        run_id
    FROM {META_TABLE}
    WHERE LOWER(document_id) = LOWER('{_safe_id}')
""")
display(meta_row_df)

# COMMAND ----------

# ── Step 2b: Check if parsed JSON file actually exists on volume ──────────────
try:
    _path_row = spark.sql(f"""
        SELECT parsed_volume_path FROM {META_TABLE}
        WHERE LOWER(document_id) = LOWER('{_safe_id}')
          AND parsed_volume_path IS NOT NULL AND parsed_volume_path <> ''
        LIMIT 1
    """).first()
    if _path_row:
        _parsed_path = _path_row["parsed_volume_path"]
        try:
            dbutils.fs.ls(_parsed_path)  # noqa: F821
            log.info(f"parsed JSON exists on volume: {_parsed_path}")
        except Exception:
            log.error(f"parsed JSON path is in metadata but file NOT FOUND on volume: {_parsed_path}")
    else:
        log.warning("parsed_volume_path is NULL/empty in metadata row — P2 will fail.")
except Exception as _e:
    log.warning(f"Could not check parsed JSON on volume: {_e}")

# COMMAND ----------

# ── Step 3: Run P2 (chunking) ─────────────────────────────────────────────────

if p1_ok:
    log.info("=== Running P2 (chunking) ===")
    try:
        p2_result = dbutils.notebook.run(  # noqa: F821
            f"{REPO_ROOT}/gold/src/etl/nb_sdg_fsr_v2_chunks",
            timeout_seconds=3600,
            arguments={
                "jb_env":                 get_runtime_param("jb_env", "dev"),
                "METADATA_TABLE_V2":      META_TABLE,
                "CHUNK_TABLE_V2":         CHUNK_TABLE,
                "LITELLM_BASE_URL":       LITELLM_BASE_URL,
                "LITELLM_API_KEY":        LITELLM_API_KEY,
                "FSR_LLM_VERIFY_SSL":     "false",
            },
        )
        log.info(f"P2 completed: {p2_result}")
        p2_ok = True
    except Exception as _e:
        log.error(f"P2 FAILED: {_e}")
        p2_ok = False
else:
    log.warning("=== P2 skipped because P1 failed ===")
    p2_ok = False

# COMMAND ----------

# ── Step 4: Inspect chunk_status + errors after P2 ────────────────────────────
print("=== Metadata row after P2 ===")
post_p2_meta_df = spark.sql(f"""
    SELECT
        document_id,
        metadata_status,
        chunk_status,
        chunk_error,
        CASE WHEN parsed_volume_path IS NOT NULL AND parsed_volume_path <> '' THEN 'SET' ELSE 'MISSING ⚠' END AS parsed_path_present
    FROM {META_TABLE}
    WHERE LOWER(document_id) = LOWER('{_safe_id}')
""")
display(post_p2_meta_df)

# COMMAND ----------

print("=== Chunks produced ===")
chunks_df = spark.sql(f"""
    SELECT
        document_id,
        chunk_index,
        page_number,
        region_primary_esn,
        region_primary_equip_type,
        chunk_strategy,
        LEFT(chunk_text, 300) AS chunk_text_preview,
        run_id
    FROM {CHUNK_TABLE}
    WHERE LOWER(document_id) = LOWER('{_safe_id}')
    ORDER BY chunk_index
""")
_chunk_count = chunks_df.count()
log.info(f"Chunks produced: {_chunk_count}")
display(chunks_df)

# COMMAND ----------

# ── Step 5: Trigger VS index sync (P3) ────────────────────────────────────────

if p2_ok and not SKIP_P3:
    log.info("=== Running P3 (VS index sync) ===")
    try:
        p3_result = dbutils.notebook.run(  # noqa: F821
            f"{REPO_ROOT}/vs/src/etl/nb_sdg_fsr_v2_index",
            timeout_seconds=1800,
            arguments={
                "jb_env":                      get_runtime_param("jb_env", "dev"),
                "CHUNK_TABLE_V2":              CHUNK_TABLE,
                "VS_INDEX_V2":                 VS_INDEX,
                "VS_ENDPOINT_V2":              VS_ENDPOINT,
                "INDEX_MODE":                  "sync",
                "FSR_DATABRICKS_VERIFY_SSL":   "false",
                "FSR_EMBEDDING_DIMENSION":     "3072",
            },
        )
        log.info(f"P3 completed: {p3_result}")
    except Exception as _e:
        log.error(f"P3 FAILED: {_e}")
elif SKIP_P3:
    log.info("=== P3 skipped (SKIP_P3=true) ===")
else:
    log.warning("=== P3 skipped because P2 failed ===")
