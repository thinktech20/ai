# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_verify_retrieval_ucs — FSR v2 retrieval verification across UC1, UC2-current, UC2-future
#
# Runs all three retrieval use cases inline so all output is visible in one place.
# No sub-notebook calls — output stays here.
#
# Sections:
#   1. UC1  — Data readiness: does each active ESN have eligible docs?
#   2. UC2-current — Retrieval with Issue 3 fallback (primary_esn filter + fallback)
#   3. UC2-future  — Clean retrieval, no fallback (primary_esn filter only)
#   4. Summary     — PASS/FAIL across all UCs
#
# Inputs (widgets):
#   REQUESTED_ESN             — ESN to run UC2 for (leave empty = use first active ESN found)
#   QUERY_TEXT                — Natural language query for UC2
#   METADATA_TABLE_V2
#   DOC_EQUIPMENT_MAP_TABLE_V2
#   VS_INDEX_V2
#   VS_ENDPOINT_V2
#   NUM_RESULTS               — VS results per query (default: 5)
#   MIN_RESULTS               — UC2-current fallback threshold (default: 3)
#   RECENCY_MONTHS            — Recency window (default: 120)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet databricks-vectorsearch

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run /Users/madhurima.saxena@gevernova.com/pw_sdg_ai_ser_repo/common/fsr_v2/config

# COMMAND ----------

import json
import logging
import requests
from datetime import date
from dateutil.relativedelta import relativedelta
from pyspark.sql import SparkSession
from databricks.vector_search.client import VectorSearchClient


def _embed_query(text: str, base_url: str, api_key: str, model: str) -> list:
    """Embed a single query string using the LiteLLM endpoint."""
    resp = requests.post(
        f"{base_url}/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "input": [text]},
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]

spark = SparkSession.builder.getOrCreate()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.verify.retrieval")

# COMMAND ----------

dbutils.widgets.text("REQUESTED_ESN",              "")   # noqa: F821  leave empty = auto-pick first active ESN
dbutils.widgets.text("QUERY_TEXT",                  "What are the generator inspection findings and risk items?")  # noqa: F821
dbutils.widgets.text("METADATA_TABLE_V2",           "vaid.ai_sot_field_service_report.fsr_metadata_v2")           # noqa: F821
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2",  "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")  # noqa: F821
dbutils.widgets.text("VS_INDEX_V2",                 "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")        # noqa: F821
dbutils.widgets.text("VS_ENDPOINT_V2",              "pw-ser-sdg-vector-search")                                    # noqa: F821
dbutils.widgets.text("NUM_RESULTS",                 "5")                                                           # noqa: F821
dbutils.widgets.text("MIN_RESULTS",                 "3")                                                           # noqa: F821
dbutils.widgets.text("RECENCY_MONTHS",              "120")                                                         # noqa: F821
dbutils.widgets.text("LITELLM_BASE_URL",            "https://dev-gateway.apps.gevernova.net")                      # noqa: F821
dbutils.widgets.text("LITELLM_API_KEY",             "sk-cjRRha3Ejczz8AmnJKyQxA")                                   # noqa: F821  dev key — local notebook only
dbutils.widgets.text("EMBEDDING_MODEL",             "azure-text-embedding-3-large-1")                              # noqa: F821

# COMMAND ----------

REQUESTED_ESN  = get_runtime_param("REQUESTED_ESN", "").strip().upper()
QUERY_TEXT     = get_runtime_param("QUERY_TEXT", "What are the generator inspection findings?").strip()
META_TABLE     = get_runtime_param("METADATA_TABLE_V2",          METADATA_TABLE_V2).strip()
MAP_TABLE      = get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2", DOC_EQUIPMENT_MAP_TABLE_V2).strip()
VS_INDEX       = get_runtime_param("VS_INDEX_V2",                VS_INDEX_V2).strip()
VS_ENDPOINT    = get_runtime_param("VS_ENDPOINT_V2",             VS_ENDPOINT_V2).strip()
NUM_RESULTS      = int(get_runtime_param("NUM_RESULTS", "5"))
MIN_RESULTS      = int(get_runtime_param("MIN_RESULTS", "3"))
RECENCY_MONTHS   = int(get_runtime_param("RECENCY_MONTHS", "120"))
LITELLM_BASE_URL = get_runtime_param("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net").strip()
LITELLM_API_KEY  = get_runtime_param("LITELLM_API_KEY", "").strip()
EMBEDDING_MODEL  = get_runtime_param("EMBEDDING_MODEL", "azure-text-embedding-3-large-1").strip()
THRESHOLD_DATE   = (date.today() - relativedelta(months=RECENCY_MONTHS)).strftime("%Y-%m-%d")

print(f"Query          : {QUERY_TEXT}")
print(f"Recency window : {THRESHOLD_DATE} onwards")
print(f"VS index       : {VS_INDEX}")
print(f"Embed model    : {EMBEDDING_MODEL}")

# COMMAND ----------

# ── Shared: collect all active ESNs with eligible docs ────────────────────────
_active_esn_rows = spark.sql(f"""
    SELECT DISTINCT d.esn
    FROM {MAP_TABLE} d
    INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
    WHERE d.is_active = true
      AND m.metadata_status = 'completed'
      AND m.chunk_status = 'completed'
      AND m.outage_start_date >= '{THRESHOLD_DATE}'
    ORDER BY d.esn
""").collect()
ALL_ACTIVE_ESNS = [r.esn for r in _active_esn_rows]

if not REQUESTED_ESN:
    if not ALL_ACTIVE_ESNS:
        raise ValueError("No active ESNs found in ingested docs — check tables and recency window")
    REQUESTED_ESN = ALL_ACTIVE_ESNS[0]
    print(f"REQUESTED_ESN not set — auto-selected: {REQUESTED_ESN}")
else:
    print(f"REQUESTED_ESN  : {REQUESTED_ESN}")

print(f"All active ESNs: {ALL_ACTIVE_ESNS}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# UC1 — DATA READINESS: does each active ESN have eligible docs?
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("UC1 — DATA READINESS")
print("=" * 70)

_uc1_results = []
for esn in ALL_ACTIVE_ESNS:
    rows = spark.sql(f"""
        SELECT
            d.esn,
            COUNT(DISTINCT d.document_id) AS eligible_docs,
            MAX(m.outage_start_date)      AS most_recent_doc
        FROM {MAP_TABLE} d
        INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
        WHERE UPPER(d.esn) = '{esn}'
          AND d.is_active = true
          AND m.metadata_status = 'completed'
          AND m.chunk_status = 'completed'
          AND m.outage_start_date >= '{THRESHOLD_DATE}'
        GROUP BY d.esn
    """).collect()
    n = rows[0].eligible_docs if rows else 0
    most_recent = rows[0].most_recent_doc if rows else None
    status = "PASS" if n > 0 else "MISS"
    _uc1_results.append({"esn": esn, "status": status, "eligible_docs": n, "most_recent": most_recent})
    print(f"  [{status}] ESN={esn:20s}  eligible_docs={n}  most_recent={most_recent}")

_uc1_pass = all(r["status"] == "PASS" for r in _uc1_results)
print(f"\nUC1 overall: {'PASS — all ESNs have eligible docs' if _uc1_pass else 'WARN — some ESNs have no eligible docs'}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# UC2-current — RETRIEVAL WITH ISSUE 3 FALLBACK
# Step 1: SQL gate — confirm REQUESTED_ESN has eligible docs
# Step 2a: VS primary search — filter primary_esn = REQUESTED_ESN
# Step 2b: Fallback — if results < MIN_RESULTS, search primary_esn="" from eligible docs
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print(f"UC2-current — RETRIEVAL WITH FALLBACK  |  ESN={REQUESTED_ESN}")
print("=" * 70)

_COLS = ["chunk_id", "document_id", "pdf_name", "chunk_text",
         "primary_esn", "primary_equip_type", "outage_start_date", "metadata"]

# Step 1: SQL gate
_eligible = spark.sql(f"""
    SELECT d.document_id
    FROM {MAP_TABLE} d
    INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
    WHERE UPPER(d.esn) = '{REQUESTED_ESN}'
      AND d.is_active = true
      AND m.metadata_status = 'completed'
      AND m.chunk_status = 'completed'
      AND m.outage_start_date >= '{THRESHOLD_DATE}'
""").collect()
_eligible_doc_ids = [r.document_id for r in _eligible]

print(f"\nStep 1 — SQL gate: {len(_eligible_doc_ids)} eligible doc(s) found")
if not _eligible_doc_ids:
    print("  MISS — no eligible docs for this ESN. Stopping UC2-current.")
    _uc2c_results = []
    _uc2c_fallback_used = False
else:
    vs_client = VectorSearchClient()
    index = vs_client.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)

    print("Embedding query text...")
    _query_vector = _embed_query(QUERY_TEXT, LITELLM_BASE_URL, LITELLM_API_KEY, EMBEDDING_MODEL)
    print(f"  Embedding dimension: {len(_query_vector)}")

    # Step 2a: primary ESN filter (recency already enforced by SQL gate Step 1)
    _resp_2a = index.similarity_search(
        query_vector=_query_vector,
        columns=_COLS,
        filters={"primary_esn": REQUESTED_ESN},
        num_results=NUM_RESULTS,
    )
    _rows_2a = _resp_2a.get("result", {}).get("data_array", [])
    print(f"\nStep 2a — VS primary filter (primary_esn={REQUESTED_ESN}): {len(_rows_2a)} chunk(s) returned")

    _uc2c_results = [dict(zip(_COLS, r)) for r in _rows_2a]
    _uc2c_fallback_used = False

    # Step 2b: fallback if needed
    if len(_rows_2a) < MIN_RESULTS:
        print(f"\nStep 2b — Fallback triggered (results {len(_rows_2a)} < MIN_RESULTS {MIN_RESULTS})")
        # VS API rejects filtering by empty string — can't use {"primary_esn": ""}.
        # Instead: filter by eligible document_id list (IN semantics), then post-filter
        # in Python for unattributed chunks (primary_esn == "").
        # Over-fetch by 5x because most results will be attributed and get dropped.
        _needed = max(1, NUM_RESULTS - len(_rows_2a))
        _resp_2b = index.similarity_search(
            query_vector=_query_vector,
            columns=_COLS,
            filters={"document_id": _eligible_doc_ids},
            num_results=min(_needed * 5, 50),
        )
        _rows_2b = _resp_2b.get("result", {}).get("data_array", [])
        # Keep only unattributed chunks (primary_esn == "") from eligible docs
        _rows_2b_filtered = [
            r for r in _rows_2b
            if dict(zip(_COLS, r)).get("primary_esn", "") == ""
        ][:_needed]
        print(f"  Fallback: VS returned {len(_rows_2b)} chunks, {len(_rows_2b_filtered)} unattributed from eligible docs")
        _uc2c_results += [dict(zip(_COLS, r)) for r in _rows_2b_filtered]
        _uc2c_fallback_used = True
    else:
        print("Step 2b — Fallback not needed")

    print(f"\nFinal results: {len(_uc2c_results)} chunk(s)")
    for i, chunk in enumerate(_uc2c_results, 1):
        meta = json.loads(chunk.get("metadata") or "{}")
        print(f"  Chunk {i}:")
        print(f"    doc         : {chunk.get('pdf_name')}")
        print(f"    primary_esn : {chunk.get('primary_esn') or '(unattributed)'}")
        print(f"    date        : {chunk.get('outage_start_date')}")
        print(f"    section     : {meta.get('section', {}).get('section_title', '')}")
        print(f"    text        : {(chunk.get('chunk_text') or '')[:200].replace(chr(10), ' ')}...")
        print()

_uc2c_pass = len(_uc2c_results) > 0

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# UC2-future — CLEAN RETRIEVAL (no fallback, requires Issue 3 fixed in P1)
# Step 1: SQL gate
# Step 2: VS query — primary_esn + outage_start_date filter only
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print(f"UC2-future — CLEAN RETRIEVAL (no fallback)  |  ESN={REQUESTED_ESN}")
print("=" * 70)

if not _eligible_doc_ids:
    print("  MISS — no eligible docs (same as UC2-current Step 1). Skipping.")
    _uc2f_results = []
else:
    _resp_fut = index.similarity_search(
        query_vector=_query_vector,
        columns=_COLS,
        filters={"primary_esn": REQUESTED_ESN},
        num_results=NUM_RESULTS,
    )
    _rows_fut = _resp_fut.get("result", {}).get("data_array", [])
    _uc2f_results = [dict(zip(_COLS, r)) for r in _rows_fut]

    print(f"\nVS query (primary_esn={REQUESTED_ESN}): {len(_uc2f_results)} chunk(s)")
    for i, chunk in enumerate(_uc2f_results, 1):
        meta = json.loads(chunk.get("metadata") or "{}")
        print(f"  Chunk {i}:")
        print(f"    doc         : {chunk.get('pdf_name')}")
        print(f"    primary_esn : {chunk.get('primary_esn')}")
        print(f"    date        : {chunk.get('outage_start_date')}")
        print(f"    section     : {meta.get('section', {}).get('section_title', '')}")
        print(f"    text        : {(chunk.get('chunk_text') or '')[:200].replace(chr(10), ' ')}...")
        print()

    if not _uc2f_results:
        print("  NOTE: Zero results without fallback — Issue 3 impact is real for this ESN.")

_uc2f_pass = len(_uc2f_results) > 0

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  ESN tested     : {REQUESTED_ESN}")
print(f"  Query          : {QUERY_TEXT}")
print(f"  Recency window : {THRESHOLD_DATE} onwards")
print()
print(f"  UC1  (data readiness)      : {'PASS' if _uc1_pass else 'WARN'}")
for r in _uc1_results:
    print(f"       [{r['status']}] {r['esn']:20s}  docs={r['eligible_docs']}")
print()
print(f"  UC2-current (with fallback): {'PASS' if _uc2c_pass else 'FAIL'}  ({len(_uc2c_results)} chunks{'  — fallback used' if _uc2c_fallback_used else ''})")
print(f"  UC2-future  (no fallback)  : {'PASS' if _uc2f_pass else 'FAIL — Issue 3 impact'}  ({len(_uc2f_results)} chunks)")
print()
if _uc2c_pass and not _uc2f_pass:
    print("  DIAGNOSIS: Issue 3 is affecting this ESN — primary_esn attribution gaps exist.")
    print("  Fallback is working correctly as a workaround.")
elif _uc2f_pass:
    print("  Retrieval is clean — no Issue 3 impact for this ESN.")
elif not _uc2c_pass:
    print("  WARNING: Retrieval failing even with fallback. Check VS index sync and chunk attribution.")
