# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_fsr_v2_verify — FSR v2 post-ingest and retrieval verification
#
# Reads from existing fsr_v2 tables and VS index only — no new tables created.
#
# Sections:
#   A. P1 status     — metadata extraction completeness for ingested docs
#   B. P2 status     — chunking completeness + attribution quality
#   C. Map table     — ESN coverage across documents
#   D. VS index      — index sync state check
#   E. UC1 spot-check — data readiness query for each unique active ESN
#   F. UC2 spot-check — retrieval query for a sample ESN + query text
#   G. ESN precision metric — % chunks attributed to requested ESN
#
# Inputs (widgets):
#   METADATA_TABLE_V2          — fsr_metadata_v2
#   CHUNK_TABLE_V2             — fsr_chunks_v2
#   DOC_EQUIPMENT_MAP_TABLE_V2 — fsr_document_equipment_map_v2
#   VS_INDEX_V2                — VS index name
#   VS_ENDPOINT_V2             — VS endpoint name
#   SAMPLE_QUERY               — natural language query for UC2 spot-check
#   RECENCY_MONTHS             — recency window (default: 120)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../pw_sdg_ai_ser_repo/common/fsr_v2/config

# COMMAND ----------

import json
import logging
import requests
from datetime import date
from dateutil.relativedelta import relativedelta
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.verify")

# COMMAND ----------

dbutils.widgets.text("METADATA_TABLE_V2",            "vaid.ai_sot_field_service_report.fsr_metadata_v2")        # noqa: F821
dbutils.widgets.text("CHUNK_TABLE_V2",               "vaid.ai_std_con_field_service_report.fsr_chunks_v2")      # noqa: F821
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2",   "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")  # noqa: F821
dbutils.widgets.text("VS_INDEX_V2",                  "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")    # noqa: F821
dbutils.widgets.text("VS_ENDPOINT_V2",               "pw-ser-sdg-vector-search")                                # noqa: F821
dbutils.widgets.text("SAMPLE_QUERY",                 "What are the generator inspection findings and risk items?")  # noqa: F821
dbutils.widgets.text("RECENCY_MONTHS",               "120")                                                      # noqa: F821
dbutils.widgets.text("LITELLM_BASE_URL",              "https://dev-gateway.apps.gevernova.net")                  # noqa: F821
dbutils.widgets.text("LITELLM_API_KEY",               "sk-cjRRha3Ejczz8AmnJKyQxA")                              # noqa: F821  dev key
dbutils.widgets.text("EMBEDDING_MODEL",               "azure-text-embedding-3-large-1")                         # noqa: F821

# COMMAND ----------

META_TABLE     = get_runtime_param("METADATA_TABLE_V2",            METADATA_TABLE_V2).strip()
CHUNK_TABLE    = get_runtime_param("CHUNK_TABLE_V2",               CHUNK_TABLE_V2).strip()
MAP_TABLE      = get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2",   DOC_EQUIPMENT_MAP_TABLE_V2).strip()
VS_INDEX       = get_runtime_param("VS_INDEX_V2",                  VS_INDEX_V2).strip()
VS_ENDPOINT    = get_runtime_param("VS_ENDPOINT_V2",               VS_ENDPOINT_V2).strip()
SAMPLE_QUERY   = get_runtime_param("SAMPLE_QUERY", "What are the generator inspection findings?").strip()
RECENCY_MONTHS = int(get_runtime_param("RECENCY_MONTHS", "120"))
THRESHOLD_DATE = (date.today() - relativedelta(months=RECENCY_MONTHS)).strftime("%Y-%m-%d")
LITELLM_BASE_URL = get_runtime_param("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net").strip()
LITELLM_API_KEY  = get_runtime_param("LITELLM_API_KEY", "").strip()
EMBEDDING_MODEL  = get_runtime_param("EMBEDDING_MODEL", "azure-text-embedding-3-large-1").strip()

def _get_dbr_auth():
    host = spark.conf.get("spark.databricks.workspaceUrl")
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()  # noqa: F821
    return f"https://{host}", token

WS_URL, WS_TOKEN = _get_dbr_auth()

print(f"Tables : {META_TABLE}")
print(f"         {CHUNK_TABLE}")
print(f"         {MAP_TABLE}")
print(f"VS index: {VS_INDEX}")
print(f"Recency : {THRESHOLD_DATE} onwards")

# COMMAND ----------

# ── VS REST API helpers (used in sections F and G) ──────────────────────────────────────────────

_VS_COLS = ["chunk_id", "document_id", "pdf_name", "chunk_text",
            "region_primary_esn", "region_primary_equip_type", "outage_start_date", "metadata"]

def _embed(text):
    resp = requests.post(
        f"{LITELLM_BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {LITELLM_API_KEY}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "input": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]

def _vs_search(query_vector, filters, num_results=5):
    resp = requests.post(
        f"{WS_URL}/api/2.0/vector-search/indexes/{VS_INDEX}/query",
        headers={"Authorization": f"Bearer {WS_TOKEN}", "Content-Type": "application/json"},
        json={
            "dataframe_records": [{"query_vector": query_vector}],
            "columns":           _VS_COLS,
            "filters_json":      json.dumps(filters),
            "num_results":       num_results,
        },
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json().get("result", {}).get("data_array", [])

# COMMAND ----------

# ── A. P1 Status — metadata extraction completeness ───────────────────────────
print("=" * 60)
print("A. P1 STATUS — metadata extraction")
print("=" * 60)

display(spark.sql(f"""
    SELECT
        metadata_status,
        COUNT(*)                     AS doc_count,
        COUNT(primary_esn)           AS has_primary_esn,
        COUNT(outage_start_date)     AS has_outage_date,
        COUNT(preprocessor_regions)  AS has_regions
    FROM {META_TABLE}
    GROUP BY metadata_status
    ORDER BY metadata_status
"""))

# Failed docs detail
failed_p1 = spark.sql(f"""
    SELECT document_id, pdf_name, metadata_status, metadata_error
    FROM {META_TABLE}
    WHERE metadata_status = 'failed'
""")
if failed_p1.count():
    print("\nP1 failed documents:")
    display(failed_p1)
else:
    print("No P1 failures.")

# COMMAND ----------

# ── B. P2 Status — chunking completeness + attribution quality ────────────────
print("=" * 60)
print("B. P2 STATUS — chunking + attribution")
print("=" * 60)

display(spark.sql(f"""
    SELECT
        m.chunk_status,
        COUNT(DISTINCT m.document_id)           AS doc_count,
        SUM(c.chunk_count)                      AS total_chunks,
        SUM(c.attributed_chunks)                AS chunks_with_esn,
        SUM(c.unattributed_chunks)              AS chunks_no_esn,
        ROUND(
            100.0 * SUM(c.attributed_chunks) / NULLIF(SUM(c.chunk_count), 0), 1
        )                                       AS attribution_pct
    FROM {META_TABLE} m
    LEFT JOIN (
        SELECT
            document_id,
            COUNT(*)                                          AS chunk_count,
            COUNT(CASE WHEN region_primary_esn != '' THEN 1 END)    AS attributed_chunks,
            COUNT(CASE WHEN region_primary_esn = ''  THEN 1 END)    AS unattributed_chunks
        FROM {CHUNK_TABLE}
        GROUP BY document_id
    ) c ON m.document_id = c.document_id
    GROUP BY m.chunk_status
    ORDER BY m.chunk_status
"""))

# Per-document detail
print("\nPer-document chunk breakdown:")
display(spark.sql(f"""
    SELECT
        m.pdf_name,
        m.primary_esn         AS doc_primary_esn,
        m.primary_equip_type,
        m.outage_start_date,
        m.chunk_status,
        COUNT(c.chunk_id)     AS total_chunks,
          COUNT(CASE WHEN c.region_primary_esn != '' THEN 1 END) AS attributed,
          COUNT(CASE WHEN c.region_primary_esn = ''  THEN 1 END) AS unattributed,
          ROUND(100.0 * COUNT(CASE WHEN c.region_primary_esn != '' THEN 1 END)
              / NULLIF(COUNT(c.chunk_id), 0), 1)         AS attribution_pct
    FROM {META_TABLE} m
    LEFT JOIN {CHUNK_TABLE} c ON m.document_id = c.document_id
    GROUP BY m.document_id, m.pdf_name, m.primary_esn,
             m.primary_equip_type, m.outage_start_date, m.chunk_status
    ORDER BY m.pdf_name
"""))

# COMMAND ----------

# ── C. Map table — ESN coverage per document ──────────────────────────────────
print("=" * 60)
print("C. MAP TABLE — ESN coverage")
print("=" * 60)

display(spark.sql(f"""
    SELECT
        m.pdf_name,
        d.esn,
        d.equip_type,
        d.is_primary_esn,
        d.is_active,
        d.source_region_count,
        chunk_counts.chunks_for_esn
    FROM {MAP_TABLE} d
    INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
    LEFT JOIN (
        SELECT document_id, region_primary_esn, COUNT(*) AS chunks_for_esn
        FROM {CHUNK_TABLE}
        WHERE region_primary_esn != ''
        GROUP BY document_id, region_primary_esn
    ) chunk_counts
        ON d.document_id = chunk_counts.document_id
        AND d.esn = chunk_counts.region_primary_esn
    ORDER BY m.pdf_name, d.is_primary_esn DESC
"""))

# COMMAND ----------

# ── D. VS Index — sync state check ───────────────────────────────────────────
print("=" * 60)
print("D. VS INDEX — sync state")
print("=" * 60)

headers = {"Authorization": f"Bearer {WS_TOKEN}"}
resp = requests.get(
    f"{WS_URL}/api/2.0/vector-search/indexes/{VS_INDEX}",
    headers=headers, timeout=30, verify=False,
)

if resp.status_code == 404:
    print(f"VS index not found: {VS_INDEX}")
elif resp.ok:
    idx = resp.json()
    status = (idx.get("status") or {})
    print(f"Index name   : {VS_INDEX}")
    print(f"State        : {status.get('state') or status.get('detailed_state', 'UNKNOWN')}")
    print(f"Last sync    : {status.get('indexed_row_count', 'N/A')} rows indexed")
    print(f"Sync message : {status.get('message', '')}")
else:
    print(f"VS index check failed: HTTP {resp.status_code} — {resp.text[:300]}")

# COMMAND ----------

# ── E. UC1 Spot-check — data readiness per active ESN ────────────────────────
print("=" * 60)
print("E. UC1 SPOT-CHECK — data readiness per active ESN")
print("=" * 60)

active_esns = [
    r.esn for r in spark.sql(f"""
        SELECT DISTINCT d.esn
        FROM {MAP_TABLE} d
        INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
        WHERE d.is_active = true
          AND m.metadata_status = 'completed'
          AND m.chunk_status = 'completed'
          AND m.outage_start_date >= '{THRESHOLD_DATE}'
    """).collect()
]

print(f"Active ESNs in ingested docs: {active_esns}\n")

for esn in active_esns:
    count = spark.sql(f"""
        SELECT COUNT(DISTINCT d.document_id) AS n
        FROM {MAP_TABLE} d
        INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
        WHERE UPPER(d.esn) = '{esn}'
          AND d.is_active = true
          AND m.metadata_status = 'completed'
          AND m.chunk_status = 'completed'
          AND m.outage_start_date >= '{THRESHOLD_DATE}'
    """).first().n
    status = "OK" if count > 0 else "MISS"
    print(f"  [{status}] ESN={esn:15s}  eligible_docs={count}")

# COMMAND ----------

# ── F. UC2 Spot-check — retrieval for sample ESN + query ─────────────────────
print("=" * 60)
print("F. UC2 SPOT-CHECK — retrieval sample")
print("=" * 60)

if not active_esns:
    print("No active ESNs found — skipping UC2 spot-check.")
else:
    sample_esn = active_esns[0]
    print(f"Sample ESN : {sample_esn}")
    print(f"Query      : {SAMPLE_QUERY}\n")

    try:
        _qv = _embed(SAMPLE_QUERY)

        # Get eligible doc IDs for this ESN (for is_active filter)
        _eligible_docs = {r.document_id for r in spark.sql(f"""
            SELECT DISTINCT d.document_id
            FROM {MAP_TABLE} d INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
            WHERE UPPER(d.esn) = '{sample_esn}' AND d.is_active = true
              AND m.chunk_status = 'completed'
              AND m.outage_start_date >= '{THRESHOLD_DATE}'
        """).collect()}

        raw = _vs_search(
            query_vector=_qv,
            filters={"primary_esn": sample_esn},
            num_results=15,
        )
        results = [
            r for r in raw
            if dict(zip(_VS_COLS, r)).get("outage_start_date", "") >= THRESHOLD_DATE
            and dict(zip(_VS_COLS, r)).get("document_id") in _eligible_docs
        ][:5]

        print(f"Chunks returned: {len(results)}\n")
        for i, row in enumerate(results, 1):
            chunk = dict(zip(_VS_COLS, row))
            meta  = json.loads(chunk.get("metadata") or "{}")
            print(f"  Chunk {i}:")
            print(f"    doc         : {chunk.get('pdf_name')}")
            print(f"    primary_esn : {chunk.get('primary_esn')}")
            print(f"    equip_type  : {chunk.get('primary_equip_type')}")
            print(f"    section     : {meta.get('section', {}).get('section_title', '')}")
            print(f"    text        : {(chunk.get('chunk_text') or '')[:180]}...")
            print()
    except Exception as e:
        print(f"UC2 spot-check failed: {e}")

# COMMAND ----------

# ── G. Retrieval completeness check — zero-result gate ───────────────────────
# Goal: catch complete retrieval failures before going to evals.
# For each active ESN in the ingested set:
#   - Run a VS similarity search with the sample query
#   - FAIL if zero chunks returned (retrieval is completely broken for this ESN)
#   - Show top chunk text for a quick human sanity read
# Detailed relevance evaluation is handled separately in evals.
print("=" * 60)
print("G. RETRIEVAL COMPLETENESS — zero-result gate per active ESN")
print("=" * 60)

if not active_esns:
    print("No active ESNs found — skipping completeness check.")
else:
    try:
        _qv_g = _embed(SAMPLE_QUERY)
        _all_pass = True
        _columns = _VS_COLS  # reuse shared column list

        for esn in active_esns:
            # Get eligible doc IDs for this ESN
            _eligible_g = {r.document_id for r in spark.sql(f"""
                SELECT DISTINCT d.document_id
                FROM {MAP_TABLE} d INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
                WHERE UPPER(d.esn) = '{esn}' AND d.is_active = true
                  AND m.chunk_status = 'completed'
                  AND m.outage_start_date >= '{THRESHOLD_DATE}'
            """).collect()}

            raw_g = _vs_search(
                query_vector=_qv_g,
                filters={"primary_esn": esn},
                num_results=9,   # over-fetch for post-filter headroom
            )
            results = [
                r for r in raw_g
                if dict(zip(_columns, r)).get("outage_start_date", "") >= THRESHOLD_DATE
                and dict(zip(_columns, r)).get("document_id") in _eligible_g
            ][:3]

            if not results:
                print(f"  [FAIL] ESN={esn} — 0 chunks returned (retrieval will fail)")
                _all_pass = False
            else:
                top = dict(zip(_columns, results[0]))
                snippet = (top.get("chunk_text") or "")[:200].replace("\n", " ")
                print(f"  [PASS] ESN={esn} — {len(results)} chunk(s) returned")
                print(f"         doc  : {top.get('pdf_name')}")
                print(f"         date : {top.get('outage_start_date')}")
                print(f"         text : {snippet}...")
            print()

        if _all_pass:
            print("All ESNs returned at least one chunk — retrieval is functional.")
        else:
            print("WARNING: one or more ESNs returned zero results. Check VS index sync and primary_esn attribution.")
    except Exception as e:
        print(f"Retrieval completeness check failed: {e}")
