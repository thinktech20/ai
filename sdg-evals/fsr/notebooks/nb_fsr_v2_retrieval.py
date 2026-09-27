# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_fsr_v2_retrieval — FSR v2 retrieval validation notebook
#
# Purpose:
# - Keep the simple one-off FSR v2 retrieval validation flow inside sdg-evals.
# - Keep data-readiness and retrieval checks in one place.
#
# Modes:
#     1) data_readiness -> SQL document lookup by ESN
#     2) retrieval      -> vector/hybrid retrieval by ESN + query text
#
# Scope:
# - Uses the current V2 metadata/map/index tables.
# - Keeps logic self-contained so it does not depend on pw_sdg_ai_ser_repo.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

import json
import logging
import re
from datetime import date

import requests
from dateutil.relativedelta import relativedelta
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.validation.retrieval")


def get_runtime_param(name: str, default: str = "") -> str:
    try:
        value = dbutils.widgets.get(name)  # noqa: F821
    except Exception:
        value = default
    return value if value is not None else default


# COMMAND ----------

dbutils.widgets.dropdown("MODE", "retrieval", ["retrieval", "data_readiness"])
dbutils.widgets.dropdown("QUERY_MODE", "hybrid", ["hybrid", "vector"])
dbutils.widgets.text("REQUESTED_ESN", "")
dbutils.widgets.text("QUERY_TEXT", "")
dbutils.widgets.text("TOP_K", "5")
dbutils.widgets.text("RECENCY_MONTHS", "120")

dbutils.widgets.text("METADATA_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")
dbutils.widgets.text("VS_INDEX_V2", "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")

dbutils.widgets.text("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
dbutils.widgets.text("LITELLM_API_KEY", "")
dbutils.widgets.text("EMBEDDING_MODEL", "azure-text-embedding-3-large-1")
dbutils.widgets.text("LLM_VERIFY_SSL", "true")

# COMMAND ----------

MODE = get_runtime_param("MODE", "retrieval").strip()
QUERY_MODE = get_runtime_param("QUERY_MODE", "hybrid").strip().lower()
REQUESTED_ESN = get_runtime_param("REQUESTED_ESN", "").strip().upper()
QUERY_TEXT = get_runtime_param("QUERY_TEXT", "").strip()
TOP_K = int(get_runtime_param("TOP_K", "5"))
RECENCY_MONTHS = int(get_runtime_param("RECENCY_MONTHS", "120"))

METADATA_TABLE = get_runtime_param(
    "METADATA_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_metadata_v2"
).strip()
MAP_TABLE = get_runtime_param(
    "DOC_EQUIPMENT_MAP_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2"
).strip()
VS_INDEX = get_runtime_param(
    "VS_INDEX_V2", "vaid.ai_std_con_field_service_report.fsr_vs_index_v2"
).strip()

LITELLM_BASE_URL = get_runtime_param("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net").strip()
LITELLM_API_KEY = get_runtime_param("LITELLM_API_KEY", "").strip()
EMBEDDING_MODEL = get_runtime_param("EMBEDDING_MODEL", "azure-text-embedding-3-large-1").strip()
_verify_ssl_raw = get_runtime_param("LLM_VERIFY_SSL", "true").strip().lower()
LLM_VERIFY_SSL = False if _verify_ssl_raw == "false" else True

if not REQUESTED_ESN:
    _active_esn_rows = spark.sql(f"""
        SELECT DISTINCT d.esn
        FROM {MAP_TABLE} d
        INNER JOIN {METADATA_TABLE} m ON d.document_id = m.document_id
        WHERE d.is_active = true
          AND m.metadata_status = 'completed'
          AND m.chunk_status = 'completed'
          AND m.outage_start_date >= DATE_FORMAT(ADD_MONTHS(CURRENT_DATE(), -{RECENCY_MONTHS}), 'yyyy-MM-dd')
        ORDER BY d.esn
        LIMIT 1
    """).collect()
    if _active_esn_rows:
        REQUESTED_ESN = _active_esn_rows[0].esn
        log.info(f"REQUESTED_ESN widget was empty — auto-selected active ESN: {REQUESTED_ESN}")
    else:
        raise ValueError("REQUESTED_ESN widget is required and no active ESNs were found in the database")

if not re.fullmatch(r"[A-Z0-9]{4,12}", REQUESTED_ESN):
    raise ValueError(f"REQUESTED_ESN must be 4-12 alphanumeric characters, got: {REQUESTED_ESN!r}")
if MODE == "retrieval" and not QUERY_TEXT:
    raise ValueError("QUERY_TEXT widget is required in retrieval mode")
if QUERY_MODE not in {"hybrid", "vector"}:
    raise ValueError("QUERY_MODE must be either 'hybrid' or 'vector'")
if TOP_K <= 0:
    raise ValueError("TOP_K must be > 0")

log.info("FSR v2 retrieval validation")
log.info(f"  Mode           : {MODE}")
log.info(f"  Query mode     : {QUERY_MODE}")
log.info(f"  ESN            : {REQUESTED_ESN}")
log.info(f"  Top-K          : {TOP_K}")
log.info(f"  Recency months : {RECENCY_MONTHS}")

# COMMAND ----------

candidate_rows = spark.sql(
    f"""
    SELECT DISTINCT d.document_id
    FROM {MAP_TABLE} d
    INNER JOIN {METADATA_TABLE} m ON d.document_id = m.document_id
    WHERE UPPER(d.esn) = '{REQUESTED_ESN}'
      AND d.is_active = true
      AND m.metadata_status = 'completed'
      AND m.chunk_status = 'completed'
      AND m.outage_start_date >= DATE_FORMAT(ADD_MONTHS(CURRENT_DATE(), -{RECENCY_MONTHS}), 'yyyy-MM-dd')
    """
).collect()

candidate_doc_ids = [r.document_id for r in candidate_rows]
candidate_doc_id_set = set(candidate_doc_ids)
log.info(f"Eligible docs for ESN: {len(candidate_doc_ids)}")

if MODE == "data_readiness":
    readiness_df = spark.sql(
        f"""
        SELECT
            m.document_id,
            m.pdf_name,
            m.primary_esn,
            m.primary_equip_type,
            d.esn AS matched_esn,
            d.equip_type AS matched_equip_type,
            d.is_primary_esn,
            m.report_issued_date,
            m.outage_start_date,
            m.outage_end_date,
            m.outage_type,
            m.customer,
            m.event_type,
            m.fsr_number,
            m.technology_type
        FROM {MAP_TABLE} d
        INNER JOIN {METADATA_TABLE} m ON d.document_id = m.document_id
        WHERE UPPER(d.esn) = '{REQUESTED_ESN}'
          AND d.is_active = true
          AND m.metadata_status = 'completed'
          AND m.chunk_status = 'completed'
          AND m.outage_start_date >= DATE_FORMAT(ADD_MONTHS(CURRENT_DATE(), -{RECENCY_MONTHS}), 'yyyy-MM-dd')
        ORDER BY m.report_issued_date DESC
        """
    )

    count = readiness_df.count()
    display(readiness_df)
    dbutils.notebook.exit(
        json.dumps(
            {
                "mode": MODE,
                "status": "PASS" if count > 0 else "MISS",
                "eligible_docs": count,
                "esn": REQUESTED_ESN,
            }
        )
    )

if not candidate_doc_ids:
    dbutils.notebook.exit(
        json.dumps(
            {
                "mode": MODE,
                "status": "MISS",
                "chunk_count": 0,
                "esn": REQUESTED_ESN,
            }
        )
    )

# COMMAND ----------


def embed_query(text: str) -> list[float]:
    resp = requests.post(
        f"{LITELLM_BASE_URL}/v1/embeddings",
        headers={"Authorization": f"Bearer {LITELLM_API_KEY}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "input": [text]},
        timeout=30,
        verify=LLM_VERIFY_SSL,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def vs_query(
    host: str,
    token: str,
    query_vector: list[float],
    query_text: str,
    query_mode: str,
    filters: dict,
    num_results: int,
) -> tuple[list[str], list[list]]:
    cols = [
        "chunk_id",
        "document_id",
        "pdf_name",
        "chunk_text",
        "region_primary_esn",
        "region_primary_equip_type",
        "outage_start_date",
        "metadata",
    ]
    payload = {
        "columns": cols,
        "num_results": num_results,
        "filters_json": json.dumps(filters),
    }
    if query_mode == "hybrid":
        payload.update(
            {
                "query_type": "HYBRID",
                "query_text": query_text,
                "query_vector": query_vector,
            }
        )
    else:
        payload.update({"query_vector": query_vector})

    resp = requests.post(
        f"https://{host}/api/2.0/vector-search/indexes/{VS_INDEX}/query",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    rows = resp.json().get("result", {}).get("data_array") or []
    return cols, rows


workspace_host = spark.conf.get("spark.databricks.workspaceUrl")
workspace_token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()  # noqa: F821
threshold_date = (date.today() - relativedelta(months=RECENCY_MONTHS)).strftime("%Y-%m-%d")

query_vector = embed_query(QUERY_TEXT)
log.info(f"Embedding dimension: {len(query_vector)}")

cols, raw_rows = vs_query(
    workspace_host,
    workspace_token,
    query_vector,
    QUERY_TEXT,
    QUERY_MODE,
    filters={"region_primary_esn": REQUESTED_ESN},
    num_results=TOP_K * 3,
)

results = [
    row
    for row in raw_rows
    if dict(zip(cols, row)).get("outage_start_date", "") >= threshold_date
    and dict(zip(cols, row)).get("document_id") in candidate_doc_id_set
][:TOP_K]

log.info(f"Retrieved chunks (post-filter): {len(results)}")

display(spark.createDataFrame([dict(zip(cols, r)) for r in results]))

dbutils.notebook.exit(
    json.dumps(
        {
            "mode": MODE,
            "query_mode": QUERY_MODE,
            "status": "PASS" if len(results) > 0 else "MISS",
            "chunk_count": len(results),
            "top_k": TOP_K,
            "esn": REQUESTED_ESN,
        }
    )
)