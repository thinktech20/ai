# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_fsr_v2_dev_ingest — FSR v2 targeted dev ingest orchestrator
#
# Drops and recreates all FSR v2 dev tables and VS index, then runs the full
# P1 → P2 → P3 pipeline for a targeted set of PDFs.
#
# Purpose: dev/QA validation cycle — clean slate ingest for specific documents.
#
# Steps:
#   1. Drop existing fsr_v2 tables (metadata, chunks, doc_equipment_map)
#   2. Drop existing VS index via REST API
#   3. Recreate tables via DDL notebook
#   4. Run P1 (metadata extraction) for targeted PDFs
#   5. Run P2 (chunking + embedding)
#   6. Run P3 (vector index create + sync)
#
# Inputs (widgets):
#   TARGET_PDF_NAMES          — comma-separated PDF names to ingest (required)
#   METADATA_TABLE_V2         — fsr_metadata_v2 table
#   CHUNK_TABLE_V2            — fsr_chunks_v2 table
#   DOC_EQUIPMENT_MAP_TABLE_V2 — fsr_document_equipment_map_v2 table
#   VS_INDEX_V2               — VS index name
#   VS_ENDPOINT_V2            — VS endpoint name
#   FSR_SOURCE_VOLUME_PATHS   — comma-separated source volume paths
#   LITELLM_BASE_URL          — LiteLLM gateway base URL
#   LITELLM_API_KEY           — LiteLLM API key
#   DROP_TABLES_AND_INDEX     — true: drop tables + VS index and recreate (default: true)
#                               false: skip drop, run P1/P2/P3 only
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../../common/fsr_v2/config

# COMMAND ----------

import logging
import os
import re
import requests
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.dev.ingest")

# ── Resolve repo root from current notebook path ──────────────────────────────
# Databricks notebookPath() returns paths WITHOUT /Workspace prefix.
# Two derived paths:
#   REPO_ROOT    — no /Workspace prefix  → used for dbutils.notebook.run()
#   _WS_USER_DIR — with /Workspace prefix → used for filesystem access (open/os)
_nb_path_raw = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()  # noqa: F821
_nb_path_dbr = _nb_path_raw if not _nb_path_raw.startswith("/Workspace") else _nb_path_raw[len("/Workspace"):]
_nb_path_fs  = _nb_path_raw if _nb_path_raw.startswith("/Workspace") else f"/Workspace{_nb_path_raw}"
_REPO_NAME   = "pw_sdg_ai_ser_repo"
REPO_ROOT    = _nb_path_dbr[:_nb_path_dbr.index(_REPO_NAME) + len(_REPO_NAME)]  # no /Workspace
_WS_USER_DIR = _nb_path_fs[:_nb_path_fs.index(_REPO_NAME) - 1]                  # with /Workspace
log.info(f"Resolved repo root : {REPO_ROOT}")
log.info(f"Workspace user dir : {_WS_USER_DIR}")

# COMMAND ----------

# Batch A (27 docs). Comment out and swap with Batch B below for the second run.
dbutils.widgets.text("TARGET_PDF_NAMES",             "a1f6ca9b-f5db-4f22-b6ca-9bf5db7f227a,dd49968b-f9f3-4190-8996-8bf9f3b190a4,a7d1eb20-01c4-4d3a-91eb-2001c4bd3a42,7bd46ac1-a114-45df-bbd1-9232920f34a6,4638f199-976b-4b59-b8f1-99976beb5920,5a80e76a-3286-45bb-80e7-6a328655bba8,2e99bef9-224d-4980-99be-f9224d698022,2e985aa3-4262-4a92-985a-a34262ca9215,d633b55c-0a89-4448-b945-4d5c3e5ecedc,c067602d-4b8f-4dd9-99e4-670db03c6d06,09aee7cd-b42f-40c5-aee7-cdb42f60c5ec,5f1ac3d0-eed1-4135-9ac3-d0eed11135f7,90d2b6a7-0f1e-4b2c-98c1-d7d9f254a5c7,5a82aa03-e7dd-45c4-b226-460c508a4889,a9d4cff6-3586-4d8c-a26b-09754468d833_605013480-50051-298340-final_master_report,d82afaae-8979-436c-bb4e-92aaa8b48f62_605012157-52123-298340-final_master_report,be53e9a9-a3be-457b-a04f-2ed5d0387a1e,d1348ae1-b54c-418f-9833-b0ce99bcc899_605012157-52122-298339-final_master_report,2b66a60e-8501-4560-adf8-192af8d7a04d,0208ea9c-327a-40fc-88ea-9c327a90fc5c,f93401b3-da8a-4e45-b401-b3da8a5e4552,7a977117-fe94-4387-bac0-de48a2e45f5c,bab97474-e2af-4f40-8251-346a69bb5619_605012901-526-298006-final_master_report,8675f3cf-c109-461b-b7b2-70d5f45adf87,cc9fe3d7-87cc-4687-9fe3-d787cc3687b3,0be4a3ad-7395-41ea-8ec2-e7669c9c15aa,bdd56c7a-ebe5-4bf7-904a-5bb63091ba20")  # noqa: F821
# Batch B (26 docs). Swap active line with Batch A above for the second run.
# dbutils.widgets.text("TARGET_PDF_NAMES",           "4597a853-5ffb-40bb-b0be-bd6307b0acdc,27314604-ed52-402f-921f-34737a048841,4a56cb21-fd6b-4300-ac1b-62cf53b868a0,11338269-9d7c-4865-bfcf-1a4db9014acf,af693a98-1e5c-499d-aa10-cccc54885c64,b775cf29-8b42-4a83-af21-53075fef0802,9e279e5a-a24e-4ebd-a79e-5aa24efebd04,cdd0cca4-93ba-43b0-98e5-3d1ea2312c19,69dfe261-34b0-4740-ab89-498e7d0072df,d9b6c08b-d098-4939-a549-d113964e3150,796f4d53-a8ad-42e1-af4d-53a8add2e1a4,5b688732-39f2-48d2-a887-3239f258d28b,fcb1511e-596a-4a56-b151-1e596afa569c,b7b347fd-0b59-4c67-b609-9ad2c35105cc,35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report,806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report,3e91b865-2aaa-4233-ae4a-3e15ba641f96_605007134-180498-270t483-final_master_report,b1cdbc80-364f-4240-8dbc-80364f1240fa,3f5a1ea8-8f35-4e97-9a1e-a88f358e9768,32689520-afed-4dd4-a895-20afed7dd4d2,b25c94da-d954-4283-9c94-dad954a28307,d3b1da8a-03b4-4ea6-aa7b-0482edb532ce,111adf26-dcec-4b33-9adf-26dcec6b334e,unit_10b_borescope_inspection_spring_2026_,3d156a24-2bb9-4ccd-a81e-c122c39aa3ac,65f6535e-e26a-4e7a-bd41-6cdf4eaf1efa")  # noqa: F821
dbutils.widgets.text("FSR_SOURCE_VOLUME_PATHS",       "/Volumes/viud/ing_ud_fieldvision/fv_field_service_report,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/FSR_manual,/Volumes/vaid/ai_std_con_field_service_report/fsr_v2_test")  # noqa: F821
dbutils.widgets.text("METADATA_TABLE_V2",             "vaid.ai_sot_field_service_report.fsr_metadata_v2")     # noqa: F821
dbutils.widgets.text("CHUNK_TABLE_V2",                "vaid.ai_std_con_field_service_report.fsr_chunks_v2")   # noqa: F821
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2",    "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")  # noqa: F821
dbutils.widgets.text("RUN_LOG_TABLE_V2",              "vaid.ai_sot_field_service_report.fsr_run_log_v2")      # noqa: F821
dbutils.widgets.text("DQ_LOG_TABLE_V2",               "vaid.ai_sot_field_service_report.fsr_data_quality_log_v2")  # noqa: F821
dbutils.widgets.text("VS_INDEX_V2",                   "vaid.ai_std_con_field_service_report.fsr_vs_index_v2") # noqa: F821
dbutils.widgets.text("VS_ENDPOINT_V2",                "pw-ser-sdg-vector-search")                             # noqa: F821
dbutils.widgets.text("LITELLM_BASE_URL",              "https://dev-gateway.apps.gevernova.net")               # noqa: F821
dbutils.widgets.text("LITELLM_API_KEY",               "")                                                     # noqa: F821
dbutils.widgets.text("DROP_TABLES_AND_INDEX",          "true")                                                 # noqa: F821
dbutils.widgets.text("RUN_ALL_FROM_VOLUMES",           "false")                                                # noqa: F821
dbutils.widgets.text("FSR_PARSED_DOC_VOLUME_ROOT",    "/Volumes/vaid/ai_sot_field_service_report/fsr_parsed_docs")  # noqa: F821
# P1 enrichment dependencies. Without these P1 falls back to empty resolvers
# (blank Generator ESN, blank event/technology fields).
dbutils.widgets.text("FSR_IBAT_TABLE",                 "vgpd.prm_std_views.ibat_equipment_mst")                # noqa: F821
dbutils.widgets.text("FSR_EVENT_VISION_TABLE",         "vgpd.fsr_std_views.eventmgmt_event_vision_sot")        # noqa: F821
dbutils.widgets.text("FSR_PSOT_TABLE",                 "vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot")  # noqa: F821
dbutils.widgets.text("FSR_PDF_REF_VIEW",               "vgpp.fsr_std_views.fsr_pdf_ref")                       # noqa: F821

# COMMAND ----------

TARGET_PDF_NAMES    = get_runtime_param("TARGET_PDF_NAMES", "").strip()
SOURCE_VOLUMES      = get_runtime_param("FSR_SOURCE_VOLUME_PATHS", "").strip()
META_TABLE          = get_runtime_param("METADATA_TABLE_V2",            METADATA_TABLE_V2).strip()
CHUNK_TABLE         = get_runtime_param("CHUNK_TABLE_V2",               CHUNK_TABLE_V2).strip()
MAP_TABLE           = get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2",   DOC_EQUIPMENT_MAP_TABLE_V2).strip()
RUN_LOG_TABLE       = get_runtime_param("RUN_LOG_TABLE_V2",             "").strip()
DQ_LOG_TABLE        = get_runtime_param("DQ_LOG_TABLE_V2",              "").strip()
VS_INDEX            = get_runtime_param("VS_INDEX_V2",                  VS_INDEX_V2).strip()
VS_ENDPOINT         = get_runtime_param("VS_ENDPOINT_V2",               VS_ENDPOINT_V2).strip()
LITELLM_BASE_URL    = get_runtime_param("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net").strip()
LITELLM_API_KEY     = get_runtime_param("LITELLM_API_KEY", "").strip()
DROP_TABLES_AND_INDEX = get_runtime_param("DROP_TABLES_AND_INDEX", "true").strip().lower() == "true"
RUN_ALL_FROM_VOLUMES = get_runtime_param("RUN_ALL_FROM_VOLUMES", "false").strip().lower() == "true"
PARSED_DOC_VOLUME_ROOT = get_runtime_param("FSR_PARSED_DOC_VOLUME_ROOT", "").strip()
FSR_IBAT_TABLE = get_runtime_param("FSR_IBAT_TABLE", "").strip()
FSR_EVENT_VISION_TABLE = get_runtime_param("FSR_EVENT_VISION_TABLE", "").strip()
FSR_PSOT_TABLE = get_runtime_param("FSR_PSOT_TABLE", "").strip()
FSR_PDF_REF_VIEW = get_runtime_param("FSR_PDF_REF_VIEW", "").strip()

if not FSR_IBAT_TABLE:
    log.warning(
        "FSR_IBAT_TABLE is empty — IBAT train-scoped Generator/Steam Turbine "
        "ESN resolution will be disabled in P1. Set the widget explicitly to "
        "restore fallback behaviour."
    )


def _normalize_doc_id(value: str) -> str:
    # Cleanup/status helper only. P1 input resolution is handled in fsr_v2/input.py.
    v = (value or "").strip().strip("\"'")
    if v.lower().endswith(".pdf"):
        v = v[:-4]
    return v.lower()


def _parse_target_ids(raw: str) -> list[str]:
    if not raw:
        return []
    ids = [_normalize_doc_id(part) for part in re.split(r"[,;\n]", raw) if part.strip()]
    # Stable dedupe
    return list(dict.fromkeys(ids))


TARGET_DOC_IDS = _parse_target_ids(TARGET_PDF_NAMES)

# COMMAND ----------

# ── Target selection mode ────────────────────────────────────────────────────
# Default mode is explicit target list.
# Set RUN_ALL_FROM_VOLUMES=true to process all eligible docs discovered in FSR_SOURCE_VOLUME_PATHS.

if not LITELLM_API_KEY:
    raise ValueError(
        "LITELLM_API_KEY is required. Set it in the LITELLM_API_KEY widget before running."
    )

if RUN_ALL_FROM_VOLUMES:
    if TARGET_PDF_NAMES:
        log.warning(
            "RUN_ALL_FROM_VOLUMES=true with non-empty TARGET_PDF_NAMES. "
            "Ignoring TARGET_PDF_NAMES and running all eligible docs from volumes."
        )
        TARGET_PDF_NAMES = ""
    log.info("Target mode      : all eligible docs from provided volumes")
else:
    if not TARGET_PDF_NAMES:
        raise ValueError(
            "TARGET_PDF_NAMES is required when RUN_ALL_FROM_VOLUMES=false. "
            "Either provide a comma-separated target list, or set RUN_ALL_FROM_VOLUMES=true."
        )
    log.info("Target mode      : explicit target list")
    log.info(f"Target PDF names : {TARGET_PDF_NAMES}")

log.info("=== FSR v2 Dev Ingest ===")
log.info(f"  Targets         : {TARGET_PDF_NAMES if TARGET_PDF_NAMES else 'all eligible from volumes'}")
log.info(f"  Metadata table  : {META_TABLE}")
log.info(f"  Chunk table     : {CHUNK_TABLE}")
log.info(f"  Map table       : {MAP_TABLE}")
log.info(f"  Run log table   : {RUN_LOG_TABLE or '(disabled)'}")
log.info(f"  DQ log table    : {DQ_LOG_TABLE or '(disabled)'}")
log.info(f"  VS index        : {VS_INDEX}")
log.info(f"  Drop tables     : {DROP_TABLES_AND_INDEX}")
log.info(f"  Run all volumes : {RUN_ALL_FROM_VOLUMES}")
log.info(f"  Parsed doc root : {PARSED_DOC_VOLUME_ROOT or '(not set — P2 will fail!)'}")
if not PARSED_DOC_VOLUME_ROOT:
    log.warning("FSR_PARSED_DOC_VOLUME_ROOT is not set. P1 will not persist parsed JSONs → P2 will fail with 'Missing parsed_volume_path'. Set this widget before running.")
if TARGET_DOC_IDS:
    log.info(f"  Target doc IDs  : {', '.join(TARGET_DOC_IDS)}")

# COMMAND ----------

# ── Helper: get Databricks workspace URL + token ──────────────────────────────
def _get_dbr_auth():
    host = spark.conf.get("spark.databricks.workspaceUrl")
    ws_url = f"https://{host}"
    token = (dbutils.notebook.entry_point  # noqa: F821
             .getDbutils().notebook().getContext().apiToken().get())
    return ws_url, token

WS_URL, WS_TOKEN = _get_dbr_auth()

# COMMAND ----------

if DROP_TABLES_AND_INDEX:
    # ── Step 1: Drop existing fsr_v2 tables ──────────────────────────────────
    log.info("=== Step 1: Dropping fsr_v2 tables ===")

    for table in [CHUNK_TABLE, MAP_TABLE, META_TABLE, RUN_LOG_TABLE, DQ_LOG_TABLE]:
        if not table:
            continue
        spark.sql(f"DROP TABLE IF EXISTS {table}")
        log.info(f"  Dropped: {table}")

    # ── Step 2: Drop existing VS index ───────────────────────────────────────
    log.info("=== Step 2: Dropping VS index ===")
    headers = {"Authorization": f"Bearer {WS_TOKEN}", "Content-Type": "application/json"}
    resp = requests.delete(
        f"{WS_URL}/api/2.0/vector-search/indexes/{VS_INDEX}",
        headers=headers,
        timeout=30,
        verify=True,
    )
    if resp.status_code == 404:
        log.info(f"  VS index not found (already absent): {VS_INDEX}")
    elif resp.ok:
        log.info(f"  Dropped VS index: {VS_INDEX}")
    else:
        log.warning(f"  VS index delete returned HTTP {resp.status_code}: {resp.text[:200]}")

    # ── Step 3: Recreate tables via DDL notebook ──────────────────────────────
    log.info("=== Step 3: Recreating tables via DDL notebook ===")
    dbutils.notebook.run(  # noqa: F821
        f"{REPO_ROOT}/ddls/fsr_v2/nb_sdg_fsr_v2_ddl",
        timeout_seconds=300,
        arguments={
            "METADATA_TABLE_V2":           META_TABLE,
            "CHUNK_TABLE_V2":              CHUNK_TABLE,
            "DOC_EQUIPMENT_MAP_TABLE_V2":  MAP_TABLE,
            "RUN_LOG_TABLE_V2":            RUN_LOG_TABLE,
            "DQ_LOG_TABLE_V2":             DQ_LOG_TABLE,
            "VS_INDEX_V2":                 VS_INDEX,
            "VS_ENDPOINT_V2":              VS_ENDPOINT,
        },
    )
    log.info("  Tables recreated.")
else:
    log.info("=== Steps 1-3 skipped (DROP_TABLES_AND_INDEX=false) ===")
    if TARGET_DOC_IDS:
        # no-drop semantics: remove target docs from v2 tables so ingest acts as reinsert.
        ids_sql = ", ".join("'" + doc_id.replace("'", "''") + "'" for doc_id in TARGET_DOC_IDS)
        for table_name in [CHUNK_TABLE, MAP_TABLE, META_TABLE]:
            deleted_df = spark.sql(
                f"DELETE FROM {table_name} WHERE LOWER(document_id) IN ({ids_sql})"
            )
            deleted_rows = None
            try:
                deleted_rows = deleted_df.first()[0] if deleted_df is not None else None
            except Exception:
                deleted_rows = None
            if deleted_rows is None:
                log.info(f"  no-drop cleanup on {table_name}: done")
            else:
                log.info(f"  no-drop cleanup on {table_name}: {deleted_rows} row(s) deleted")
        log.info(
            "  no-drop cleanup complete for target docs; final P3 sync will reconcile VS index state"
        )
    else:
        log.info("  no-drop cleanup skipped (no explicit TARGET_PDF_NAMES provided)")

# COMMAND ----------

# ── Helper: run a sub-notebook and print a clickable link to its run history ──
def _run_notebook(label, path, timeout_seconds, arguments):
    """Wraps dbutils.notebook.run and surfaces the sub-notebook link + any failure inline."""
    _host = spark.conf.get("spark.databricks.workspaceUrl")
    _nb_url = f"https://{_host}/#workspace{path}"
    _safe_args = {k: ("<redacted>" if "key" in k.lower() or "token" in k.lower() else v) for k, v in arguments.items()}
    log.info(f"  [{label}] calling with args: {_safe_args}")
    displayHTML(  # noqa: F821
        f'<b>{label}</b> — '
        f'<a href="{_nb_url}" target="_blank">open notebook ↗</a> '
        f'(run logs: right-click the notebook in the workspace file browser → <b>View run history</b>)'
    )
    try:
        result = dbutils.notebook.run(path, timeout_seconds=timeout_seconds, arguments=arguments)  # noqa: F821
        log.info(f"  {label} completed: {result}")
        return True, result, None
    except Exception as _e:
        err = str(_e)
        log.error(f"  {label} FAILED:\n{err}")
        displayHTML(  # noqa: F821
            f'<div style="background:#fff0f0;border:1px solid #c00;padding:10px;margin-top:8px;'
            f'font-family:monospace;white-space:pre-wrap;font-size:0.9em;">'
            f'<b style="color:#c00">✗ {label} FAILED</b><br>'
            f'To see cell-level traceback: <a href="{_nb_url}" target="_blank">open notebook ↗</a> '
            f'then right-click it in the workspace file browser → <b>View run history</b>.<br><br>'
            f'{err[:3000]}'
            f'</div>'
        )
        return False, None, err

# ── Step 4: Run P1 — metadata extraction for targeted PDFs ───────────────────
stage_logs: list[dict] = []

log.info("=== Step 4: P1 — Metadata extraction ===")
log.info(f"  Targets: {TARGET_PDF_NAMES}")

p1_ok, p1_result, p1_err = _run_notebook(
    "P1 — Metadata extraction",
    f"{REPO_ROOT}/silver/src/etl/nb_sdg_fsr_v2_metadata",
    timeout_seconds=7200,
    arguments={
        "jb_env":                       get_runtime_param("jb_env", "dev"),
        "METADATA_TABLE_V2":            META_TABLE,
        "DOC_EQUIPMENT_MAP_TABLE_V2":   MAP_TABLE,
        "RUN_LOG_TABLE_V2":             RUN_LOG_TABLE,
        "DQ_LOG_TABLE_V2":              DQ_LOG_TABLE,
        "INPUT_MODE":                   "volume_list",
        "FSR_TARGET_PDF_NAMES":         TARGET_PDF_NAMES,
        "FSR_SOURCE_VOLUME_PATHS":      SOURCE_VOLUMES,
        "LITELLM_BASE_URL":             LITELLM_BASE_URL,
        "LITELLM_API_KEY":              LITELLM_API_KEY,
        "FSR_PARSED_DOC_VOLUME_ROOT":   PARSED_DOC_VOLUME_ROOT,
        "FSR_IBAT_TABLE":               FSR_IBAT_TABLE,
        "FSR_EVENT_VISION_TABLE":       FSR_EVENT_VISION_TABLE,
        "FSR_PSOT_TABLE":               FSR_PSOT_TABLE,
        "FSR_PDF_REF_VIEW":             FSR_PDF_REF_VIEW,
    },
)
stage_logs.append({"stage": "P1", "status": "success" if p1_ok else "failed", "error": p1_err})

if not p1_ok:
    log.error("P1 failed — checking metadata table for partial failure rows and config issues")
    log.error(f"  PARSED_DOC_VOLUME_ROOT passed to P1 : {PARSED_DOC_VOLUME_ROOT!r}")
    log.error(f"  META_TABLE                          : {META_TABLE}")
    log.error(f"  SOURCE_VOLUMES                      : {SOURCE_VOLUMES}")
    log.error(f"  TARGET_PDF_NAMES (first 200 chars)  : {TARGET_PDF_NAMES[:200]}")
    try:
        _fail_df = spark.sql(f"""
            SELECT document_id, metadata_status, metadata_error, chunk_status
            FROM {META_TABLE}
            WHERE metadata_status = 'failed' OR metadata_error IS NOT NULL
            ORDER BY metadata_status
        """)
        _fail_count = _fail_df.count()
        log.error(f"  Rows with metadata failures in table: {_fail_count}")
        if _fail_count > 0:
            print("=== P1 Failure: metadata rows with errors ===")
            display(_fail_df)
    except Exception as _de:
        log.error(f"  Could not query metadata table after P1 failure: {_de}")

# COMMAND ----------

# ── P1 debug snapshot: verify parsed_volume_path was persisted ───────────────
try:
    p1_debug_df = spark.sql(f"""
        SELECT
            document_id,
            metadata_status,
            chunk_status,
            CASE WHEN parsed_volume_path IS NOT NULL AND parsed_volume_path <> '' THEN 'SET' ELSE 'MISSING' END AS parsed_path_present,
            parsed_volume_path,
            metadata_error,
            chunk_error
        FROM {META_TABLE}
        ORDER BY metadata_status, chunk_status
    """)
    _p1_total = p1_debug_df.count()
    _p1_parsed_ok = p1_debug_df.filter("parsed_path_present = 'SET'").count()
    log.info(f"P1 debug: {_p1_total} docs in metadata table; {_p1_parsed_ok} have parsed_volume_path set, {_p1_total - _p1_parsed_ok} missing")
    if _p1_total - _p1_parsed_ok > 0:
        log.warning("parsed_volume_path is MISSING for some docs — P2 will fail. Check FSR_PARSED_DOC_VOLUME_ROOT widget.")
    print("=== P1 Debug: parsed_volume_path + status per doc ===")
    display(p1_debug_df)
except Exception as _e:
    log.warning(f"P1 debug snapshot unavailable: {_e}")

# COMMAND ----------

# ── Step 5: Run P2 — chunking + embedding ────────────────────────────────────
if p1_ok:
    log.info("=== Step 5: P2 — Chunking ===")

    p2_ok, p2_result, p2_err = _run_notebook(
        "P2 — Chunking",
        f"{REPO_ROOT}/gold/src/etl/nb_sdg_fsr_v2_chunks",
        timeout_seconds=7200,
        arguments={
            "jb_env":                   get_runtime_param("jb_env", "dev"),
            "METADATA_TABLE_V2":        META_TABLE,
            "CHUNK_TABLE_V2":           CHUNK_TABLE,
            "RUN_LOG_TABLE_V2":         RUN_LOG_TABLE,
            "LITELLM_BASE_URL":         LITELLM_BASE_URL,
            "LITELLM_API_KEY":          LITELLM_API_KEY,
            "FSR_LLM_VERIFY_SSL":       "false",
        },
    )
    stage_logs.append({"stage": "P2", "status": "success" if p2_ok else "failed", "error": p2_err})
else:
    p2_ok, p2_result, p2_err = False, None, "Skipped because P1 failed"
    stage_logs.append({"stage": "P2", "status": "skipped", "error": p2_err})
    log.warning("=== Step 5 skipped because Step 4 (P1) failed ===")

# COMMAND ----------

# ── Step 6: Run P3 — vector index create + sync ───────────────────────────────
if p2_ok:
    log.info("=== Step 6: P3 — Vector index create + sync ===")

    p3_ok, p3_result, p3_err = _run_notebook(
        "P3 — VS index",
        f"{REPO_ROOT}/vs/src/etl/nb_sdg_fsr_v2_index",
        timeout_seconds=1800,
        arguments={
            "jb_env":               get_runtime_param("jb_env", "dev"),
            "CHUNK_TABLE_V2":       CHUNK_TABLE,
            "VS_INDEX_V2":          VS_INDEX,
            "VS_ENDPOINT_V2":       VS_ENDPOINT,
            "INDEX_MODE":           "create",
            "FSR_DATABRICKS_VERIFY_SSL": "false",
            "FSR_EMBEDDING_DIMENSION":   "3072",
        },
    )
    stage_logs.append({"stage": "P3", "status": "success" if p3_ok else "failed", "error": p3_err})
else:
    p3_ok, p3_result, p3_err = False, None, "Skipped because P2 failed or was skipped"
    stage_logs.append({"stage": "P3", "status": "skipped", "error": p3_err})
    log.warning("=== Step 6 skipped because Step 5 (P2) failed or was skipped ===")

# COMMAND ----------

# ── Lightweight progress snapshot (non-blocking) ───────────────────────────
# Keep orchestrator simple: run P1 -> P2 -> P3 and report statuses.
try:
    progress_df = spark.sql(f"""
        SELECT
            metadata_status,
            chunk_status,
            COUNT(*) AS doc_count
        FROM {META_TABLE}
        GROUP BY metadata_status, chunk_status
        ORDER BY metadata_status, chunk_status
    """)

    print("=== Progress Snapshot After P3 ===")
    display(progress_df)
except Exception as _e:
    log.warning(f"Progress snapshot unavailable: {_e}")

# COMMAND ----------

# ── Summary ───────────────────────────────────────────────────────────────────
log.info("=== Dev ingest complete ===")

print("=== Stage Execution Log ===")
_log_schema = "stage STRING, status STRING, error STRING"
display(spark.createDataFrame(
    [{"stage": r["stage"], "status": r["status"], "error": r.get("error") or ""} for r in stage_logs],
    schema=_log_schema,
))

summary_df = spark.sql(f"""
    SELECT
        m.metadata_status,
        m.chunk_status,
        COUNT(*) AS doc_count,
        SUM(c.chunk_count) AS total_chunks
    FROM {META_TABLE} m
    LEFT JOIN (
        SELECT document_id, COUNT(*) AS chunk_count
        FROM {CHUNK_TABLE}
        GROUP BY document_id
    ) c ON m.document_id = c.document_id
    GROUP BY m.metadata_status, m.chunk_status
    ORDER BY m.metadata_status, m.chunk_status
""")

print("=== Ingest Summary ===")
display(summary_df)

# COMMAND ----------

# ── Per-doc status table (target mode) ──────────────────────────────────────

if TARGET_DOC_IDS:
        _requested_rows = []
        for requested in [part.strip() for part in re.split(r"[,;\n]", TARGET_PDF_NAMES) if part.strip()]:
                _requested_rows.append({
                        "requested_file_name": requested,
                        "resolved_document_id": _normalize_doc_id(requested),
                })
        spark.createDataFrame(_requested_rows).createOrReplaceTempView("_fsr_v2_requested_docs")

        _index_status = "updated" if p3_ok else ("failed" if p2_ok else "not_run")
        _dq_counts_cte = (
            f"""
            dq_counts AS (
                SELECT document_id, COUNT(*) AS dq_count
                FROM {DQ_LOG_TABLE}
                GROUP BY document_id
            )
            """
            if DQ_LOG_TABLE else
            """
            dq_counts AS (
                SELECT CAST(NULL AS STRING) AS document_id, CAST(0 AS BIGINT) AS dq_count
                WHERE 1 = 0
            )
            """
        )

        per_doc_df = spark.sql(f"""
                WITH chunk_counts AS (
                        SELECT document_id, COUNT(*) AS chunk_count
                        FROM {CHUNK_TABLE}
                        GROUP BY document_id
                ),
                map_counts AS (
                        SELECT document_id, COUNT(*) AS map_count
                        FROM {MAP_TABLE}
                        GROUP BY document_id
            ),
            {_dq_counts_cte}
                SELECT
                        r.requested_file_name,
                        r.resolved_document_id,
                        CASE WHEN {str(DROP_TABLES_AND_INDEX).lower()} THEN 'drop' ELSE 'no-drop' END AS cleanup_mode,
                        CASE
                            WHEN {str(DROP_TABLES_AND_INDEX).lower()} THEN 'global_reset'
                            ELSE 'target_doc_cleanup'
                        END AS cleanup_status,
                        m.metadata_status,
                        m.chunk_status,
                        COALESCE(c.chunk_count, 0) AS chunk_count,
                        COALESCE(mp.map_count, 0) AS map_count,
                        '{_index_status}' AS index_status,
                        COALESCE(dq.dq_count, 0) AS dq_findings,
                        CASE
                            WHEN m.metadata_status = 'completed' AND m.chunk_status = 'completed' AND COALESCE(c.chunk_count, 0) > 0
                                THEN 'passed'
                            ELSE 'failed'
                        END AS validation_status,
                        CASE
                            WHEN m.metadata_status = 'completed' AND m.chunk_status = 'completed' AND COALESCE(c.chunk_count, 0) > 0
                                THEN 'passed'
                            ELSE 'failed'
                        END AS final_status,
                        CASE
                            WHEN m.metadata_error IS NOT NULL AND m.metadata_error <> '' THEN 'P1'
                            WHEN m.chunk_error IS NOT NULL AND m.chunk_error <> '' THEN 'P2'
                            ELSE NULL
                        END AS error_stage,
                        CASE
                            WHEN m.metadata_error IS NOT NULL AND m.metadata_error <> '' THEN m.metadata_error
                            WHEN m.chunk_error IS NOT NULL AND m.chunk_error <> '' THEN m.chunk_error
                            ELSE NULL
                        END AS error_message
                FROM _fsr_v2_requested_docs r
                LEFT JOIN {META_TABLE} m
                    ON LOWER(m.document_id) = r.resolved_document_id
                LEFT JOIN chunk_counts c
                    ON c.document_id = m.document_id
                LEFT JOIN map_counts mp
                    ON mp.document_id = m.document_id
                LEFT JOIN dq_counts dq
                    ON dq.document_id = m.document_id
                ORDER BY r.requested_file_name
        """)

        print("=== Per-doc Status ===")
        display(per_doc_df)
else:
        print("=== Per-doc Status ===")
        print("Skipped: explicit TARGET_PDF_NAMES were not provided.")
