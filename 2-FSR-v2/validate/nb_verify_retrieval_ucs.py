# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_verify_retrieval_ucs — FSR v2 retrieval verification orchestrator
#
# Calls the canonical retrieval notebooks in pw_sdg_ai_ser_repo/validation/fsr_v2/retrieval/
# and prints a consolidated PASS/FAIL summary.
#
# Sub-notebooks called (via dbutils.notebook.run):
#   nb_fsr_v2_retrieval_uc1         — data readiness (SQL, one ESN at a time)
#   nb_fsr_v2_retrieval_uc2_current — retrieval with Issue 3 fallback
#   nb_fsr_v2_retrieval_uc2_future  — retrieval without fallback (post-Issue 3 fix)
#
# Inputs (widgets):
#   REQUESTED_ESN             — ESN to run UC2 for (leave empty = auto-pick first active ESN)
#   QUERY_TEXT                — Natural language query for UC2
#   METADATA_TABLE_V2
#   DOC_EQUIPMENT_MAP_TABLE_V2
#   VS_INDEX_V2
#   VS_ENDPOINT_V2
#   TOP_K                     — Final top-K chunks to return per query (default: 5)
#   MIN_RESULTS               — UC2-current fallback threshold (default: 3)
#   RECENCY_MONTHS            — Recency window in months (default: 120)
#   LITELLM_BASE_URL
#   LITELLM_API_KEY
#   EMBEDDING_MODEL
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run /Users/madhurima.saxena@gevernova.com/pw_sdg_ai_ser_repo/common/fsr_v2/config

# COMMAND ----------

import json
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.verify.orchestrator")

# ── Resolve repo root for dbutils.notebook.run (no /Workspace prefix) ─────────
_nb_path_raw = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()  # noqa: F821
_nb_path_dbr = _nb_path_raw if not _nb_path_raw.startswith("/Workspace") else _nb_path_raw[len("/Workspace"):]
# This notebook lives at .../2-FSR-v2/validate/... — derive user dir from that marker
_WS_USER_DIR_DBR = _nb_path_dbr[:_nb_path_dbr.index("/2-FSR-v2/")]
_RETRIEVAL_NB_DIR = f"{_WS_USER_DIR_DBR}/pw_sdg_ai_ser_repo/validation/fsr_v2/retrieval"
log.info(f"Retrieval notebook dir: {_RETRIEVAL_NB_DIR}")

# COMMAND ----------

dbutils.widgets.text("REQUESTED_ESN",              "")   # noqa: F821  leave empty = auto-pick first active ESN
dbutils.widgets.text("QUERY_TEXT",                  "What are the generator inspection findings and risk items?")  # noqa: F821
dbutils.widgets.text("METADATA_TABLE_V2",           "vaid.ai_sot_field_service_report.fsr_metadata_v2")           # noqa: F821
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2",  "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")  # noqa: F821
dbutils.widgets.text("VS_INDEX_V2",                 "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")        # noqa: F821
dbutils.widgets.text("VS_ENDPOINT_V2",              "pw-ser-sdg-vector-search")                                    # noqa: F821
dbutils.widgets.text("TOP_K",                       "5")                                                           # noqa: F821
dbutils.widgets.text("MIN_RESULTS",                 "3")                                                           # noqa: F821
dbutils.widgets.text("RECENCY_MONTHS",              "120")                                                         # noqa: F821
dbutils.widgets.text("LITELLM_BASE_URL",            "https://dev-gateway.apps.gevernova.net")                      # noqa: F821
dbutils.widgets.text("LITELLM_API_KEY",             "sk-cjRRha3Ejczz8AmnJKyQxA")                                   # noqa: F821  dev key — local notebook only
dbutils.widgets.text("EMBEDDING_MODEL",             "azure-text-embedding-3-large-1")                              # noqa: F821

# COMMAND ----------

REQUESTED_ESN    = get_runtime_param("REQUESTED_ESN", "").strip().upper()
QUERY_TEXT       = get_runtime_param("QUERY_TEXT", "What are the generator inspection findings?").strip()
META_TABLE       = get_runtime_param("METADATA_TABLE_V2",          METADATA_TABLE_V2).strip()
MAP_TABLE        = get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2", DOC_EQUIPMENT_MAP_TABLE_V2).strip()
VS_INDEX         = get_runtime_param("VS_INDEX_V2",                VS_INDEX_V2).strip()
VS_ENDPOINT      = get_runtime_param("VS_ENDPOINT_V2",             VS_ENDPOINT_V2).strip()
TOP_K            = get_runtime_param("TOP_K", "5")
MIN_RESULTS      = get_runtime_param("MIN_RESULTS", "3")
RECENCY_MONTHS   = get_runtime_param("RECENCY_MONTHS", "120")
LITELLM_BASE_URL = get_runtime_param("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net").strip()
LITELLM_API_KEY  = get_runtime_param("LITELLM_API_KEY", "").strip()
EMBEDDING_MODEL  = get_runtime_param("EMBEDDING_MODEL", "azure-text-embedding-3-large-1").strip()
THRESHOLD_DATE   = (date.today() - relativedelta(months=int(RECENCY_MONTHS))).strftime("%Y-%m-%d")

print(f"Query          : {QUERY_TEXT}")
print(f"Recency window : {THRESHOLD_DATE} onwards")
print(f"VS index       : {VS_INDEX}")

# ── Shared args passed to every sub-notebook ──────────────────────────────────
_COMMON_ARGS = {
    "METADATA_TABLE_V2":           META_TABLE,
    "DOC_EQUIPMENT_MAP_TABLE_V2":  MAP_TABLE,
    "VS_INDEX_V2":                 VS_INDEX,
    "VS_ENDPOINT_V2":              VS_ENDPOINT,
    "TOP_K":                       TOP_K,
    "MIN_RESULTS":                 MIN_RESULTS,
    "RECENCY_MONTHS":              RECENCY_MONTHS,
    "LITELLM_BASE_URL":            LITELLM_BASE_URL,
    "LITELLM_API_KEY":             LITELLM_API_KEY,
    "EMBEDDING_MODEL":             EMBEDDING_MODEL,
}

# COMMAND ----------

# ── Collect all active ESNs with eligible docs ────────────────────────────────
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
        raise ValueError("No active ESNs found — check tables and recency window")
    REQUESTED_ESN = ALL_ACTIVE_ESNS[0]
    print(f"REQUESTED_ESN not set — auto-selected: {REQUESTED_ESN}")
else:
    print(f"REQUESTED_ESN  : {REQUESTED_ESN}")

print(f"All active ESNs: {ALL_ACTIVE_ESNS}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# UC1 — DATA READINESS: call nb_fsr_v2_retrieval_uc1 for each active ESN
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("UC1 — DATA READINESS")
print("=" * 70)

_UC1_NB = f"{_RETRIEVAL_NB_DIR}/nb_fsr_v2_retrieval_uc1"
_uc1_results = []

for _esn in ALL_ACTIVE_ESNS:
    _raw = dbutils.notebook.run(  # noqa: F821
        _UC1_NB,
        timeout_seconds=300,
        arguments={**_COMMON_ARGS, "REQUESTED_ESN": _esn},
    )
    _r = json.loads(_raw) if _raw and _raw.strip().startswith("{") else {"status": "ERROR", "eligible_docs": 0, "esn": _esn}
    _uc1_results.append(_r)
    print(f"  [{_r['status']}] ESN={_esn:20s}  eligible_docs={_r.get('eligible_docs', '?')}")

_uc1_pass = all(r["status"] == "PASS" for r in _uc1_results)
print(f"\nUC1 overall: {'PASS — all ESNs have eligible docs' if _uc1_pass else 'WARN — some ESNs have no eligible docs'}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# UC2-current — RETRIEVAL WITH FALLBACK  (all active ESNs)
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("UC2-current — RETRIEVAL WITH FALLBACK  (all active ESNs)")
print("=" * 70)

_UC2C_NB = f"{_RETRIEVAL_NB_DIR}/nb_fsr_v2_retrieval_uc2_current"
_host = spark.conf.get("spark.databricks.workspaceUrl")
displayHTML(f'<b>UC2-current</b> — <a href="https://{_host}/#workspace{_UC2C_NB}" target="_blank">open notebook ↗</a>')  # noqa: F821

_uc2c_results = []
for _esn in ALL_ACTIVE_ESNS:
    _uc2c_raw = dbutils.notebook.run(  # noqa: F821
        _UC2C_NB,
        timeout_seconds=600,
        arguments={**_COMMON_ARGS, "REQUESTED_ESN": _esn, "QUERY_TEXT": QUERY_TEXT},
    )
    _r = json.loads(_uc2c_raw) if _uc2c_raw and _uc2c_raw.strip().startswith("{") else {"status": "ERROR", "chunk_count": 0, "fallback_used": False, "esn": _esn}
    _uc2c_results.append(_r)
    _fb = " fallback" if _r.get("fallback_used") else ""
    print(f"  [{_r['status']}] ESN={_esn:20s}  chunks={_r.get('chunk_count', '?')}{_fb}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# UC2-future — CLEAN RETRIEVAL  (all active ESNs)
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("UC2-future — CLEAN RETRIEVAL  (all active ESNs)")
print("=" * 70)

_UC2F_NB = f"{_RETRIEVAL_NB_DIR}/nb_fsr_v2_retrieval_uc2_future"
displayHTML(f'<b>UC2-future</b> — <a href="https://{_host}/#workspace{_UC2F_NB}" target="_blank">open notebook ↗</a>')  # noqa: F821

_uc2f_results = []
for _esn in ALL_ACTIVE_ESNS:
    _uc2f_raw = dbutils.notebook.run(  # noqa: F821
        _UC2F_NB,
        timeout_seconds=600,
        arguments={**_COMMON_ARGS, "REQUESTED_ESN": _esn, "QUERY_TEXT": QUERY_TEXT},
    )
    _r = json.loads(_uc2f_raw) if _uc2f_raw and _uc2f_raw.strip().startswith("{") else {"status": "ERROR", "chunk_count": 0, "esn": _esn}
    _uc2f_results.append(_r)
    print(f"  [{_r['status']}] ESN={_esn:20s}  chunks={_r.get('chunk_count', '?')}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  Query          : {QUERY_TEXT}")
print(f"  Recency window : {THRESHOLD_DATE} onwards")
print(f"  ESNs tested    : {len(ALL_ACTIVE_ESNS)}")
print()
print(f"  UC1  (data readiness) : {'PASS' if _uc1_pass else 'WARN'}")
for r in _uc1_results:
    print(f"       [{r['status']}] {r['esn']:20s}  docs={r.get('eligible_docs', '?')}")
print()

print(f"  UC2-current (with fallback):")
_uc2c_all_pass = True
for r in _uc2c_results:
    _fb = "  fallback" if r.get("fallback_used") else ""
    _ok = r.get("status") == "PASS"
    if not _ok:
        _uc2c_all_pass = False
    print(f"       [{r['status']}] {r.get('esn', '?'):20s}  chunks={r.get('chunk_count', '?')}{_fb}")
print()

print(f"  UC2-future  (no fallback):")
_uc2f_all_pass = True
for rc, rf in zip(_uc2c_results, _uc2f_results):
    _esn = rc.get("esn", rf.get("esn", "?"))
    _ok  = rf.get("status") == "PASS"
    if not _ok:
        _uc2f_all_pass = False
    _note = ""
    if rc.get("status") == "PASS" and not _ok:
        _note = "  ← Issue 3 impact (fallback needed)"
    print(f"       [{rf['status']}] {_esn:20s}  chunks={rf.get('chunk_count', '?')}{_note}")
print()

if _uc2c_all_pass and _uc2f_all_pass:
    print("  All ESNs PASS on both variants — retrieval is clean.")
elif _uc2c_all_pass and not _uc2f_all_pass:
    print("  DIAGNOSIS: Issue 3 is present — some ESNs need the fallback. Retrieval is working.")
elif not _uc2c_all_pass:
    print("  WARNING: Some ESNs failing even with fallback. Check VS index sync and chunk attribution.")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION D — DIAGNOSTIC CHECKS (data-level; does not call retrieval notebooks)
# ═══════════════════════════════════════════════════════════════════════════════
# These SQL queries run directly against the Delta tables to understand the
# dataset and identify edge cases for Sections E-H.

# Derive CHUNKS_TABLE from VS_INDEX catalog (same catalog, different schema/table)
_CHUNKS_TABLE = VS_INDEX.rsplit(".", 2)[0] + ".ai_std_con_field_service_report.fsr_chunks_v2"

print("=" * 70)
print("SECTION D — DIAGNOSTIC CHECKS")
print("=" * 70)

# D.1 — unattributed chunks (primary_esn = '')
_unattributed_count = spark.sql(f"""
    SELECT COUNT(*) AS cnt
    FROM {_CHUNKS_TABLE}
    WHERE primary_esn = ''
""").collect()[0].cnt
print(f"\nD.1  Unattributed chunks (primary_esn=''):  {_unattributed_count}")
if _unattributed_count > 0:
    _unattributed_sample = spark.sql(f"""
        SELECT DISTINCT document_id, primary_esn
        FROM {_CHUNKS_TABLE}
        WHERE primary_esn = ''
        LIMIT 5
    """).collect()
    print("     Sample document_ids with unattributed chunks:")
    for r in _unattributed_sample:
        print(f"       document_id={r.document_id}")
else:
    print("     No unattributed chunks in this dataset — Issue 3 not manifested.")

# D.2 — secondary ESN rows (is_primary_esn = false in map table)
_secondary_rows = spark.sql(f"""
    SELECT d.esn, d.document_id, d.is_primary_esn
    FROM {MAP_TABLE} d
    WHERE d.is_active = true
      AND d.is_primary_esn = false
    LIMIT 10
""").collect()
print(f"\nD.2  Secondary ESN entries (is_primary_esn=false):  {len(_secondary_rows)}")
if _secondary_rows:
    for r in _secondary_rows:
        print(f"       esn={r.esn}  document_id={r.document_id}")
    _SECONDARY_ESN_CANDIDATES = list({r.esn for r in _secondary_rows})
else:
    print("     No secondary ESN entries in this dataset.")
    _SECONDARY_ESN_CANDIDATES = []

# D.3 — multi-doc ESNs (more than one eligible document)
_multidoc_rows = spark.sql(f"""
    SELECT d.esn, COUNT(DISTINCT d.document_id) AS doc_count
    FROM {MAP_TABLE} d
    INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
    WHERE d.is_active = true
      AND m.metadata_status = 'completed'
      AND m.chunk_status = 'completed'
      AND m.outage_start_date >= '{THRESHOLD_DATE}'
    GROUP BY d.esn
    HAVING doc_count > 1
    ORDER BY doc_count DESC
""").collect()
print(f"\nD.3  Multi-doc ESNs (>=2 eligible docs):  {len(_multidoc_rows)}")
if _multidoc_rows:
    for r in _multidoc_rows:
        print(f"       esn={r.esn}  eligible_docs={r.doc_count}")
    _MULTIDOC_ESN = _multidoc_rows[0].esn
else:
    print("     No multi-doc ESNs in dataset.")
    _MULTIDOC_ESN = None

# D.4 — oldest eligible doc per ESN (for recency boundary test)
_oldest_rows = spark.sql(f"""
    SELECT d.esn, d.document_id, m.outage_start_date
    FROM {MAP_TABLE} d
    INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
    WHERE d.is_active = true
      AND m.metadata_status = 'completed'
      AND m.chunk_status = 'completed'
    ORDER BY m.outage_start_date ASC
    LIMIT 3
""").collect()
print(f"\nD.4  Oldest eligible docs (recency boundary context):")
for r in _oldest_rows:
    print(f"       esn={r.esn}  document_id={r.document_id}  outage_start_date={r.outage_start_date}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION E — RECENCY FILTER GATE TEST
# ═══════════════════════════════════════════════════════════════════════════════
# Verifies that the outage_start_date filter in Step 2a actually excludes docs
# outside the recency window (not just accepted without error).
#
# Strategy: take the oldest doc's outage_start_date, set recency_months so that
# date falls just outside the window (1 day after threshold), then verify UC2
# returns zero results for that ESN+doc combination.
#
# Simpler approach used here: run UC2-current for REQUESTED_ESN with
# RECENCY_MONTHS = 1 (1 month). All dev docs are from 2018+, so this should
# exclude everything. Expect chunk_count = 0.

print("=" * 70)
print("SECTION E — RECENCY FILTER GATE TEST  (RECENCY_MONTHS=1 → expect 0 chunks)")
print("=" * 70)

_e_raw = dbutils.notebook.run(  # noqa: F821
    _UC2C_NB,
    timeout_seconds=600,
    arguments={**_COMMON_ARGS, "REQUESTED_ESN": REQUESTED_ESN, "QUERY_TEXT": QUERY_TEXT, "RECENCY_MONTHS": "1"},
)
_e = json.loads(_e_raw) if _e_raw and _e_raw.strip().startswith("{") else {"status": "ERROR", "chunk_count": -1}
print(f"  Result: status={_e['status']}  chunks={_e.get('chunk_count', '?')}")

if _e.get("chunk_count", -1) == 0 and _e.get("status") == "MISS":
    print("  PASS — recency filter is working correctly (excluded all docs with 1-month window)")
elif _e.get("chunk_count", -1) > 0:
    print("  FAIL — recency filter did NOT exclude docs: chunks still returned with 1-month window")
    print("         Check outage_start_date values in index and filter logic in UC2-current.")
else:
    print(f"  INCONCLUSIVE — unexpected result: {_e}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION F — SECONDARY ESN RETRIEVAL TEST
# ═══════════════════════════════════════════════════════════════════════════════
# Verifies that UC2 returns chunks for an ESN that appears as secondary
# (is_primary_esn = false) in the map table.
# If no secondary ESNs exist in the dataset, this section is skipped.

print("=" * 70)
print("SECTION F — SECONDARY ESN RETRIEVAL TEST")
print("=" * 70)

if not _SECONDARY_ESN_CANDIDATES:
    print("  SKIP — no secondary ESN entries in this dataset (is_primary_esn=false rows = 0)")
else:
    _sec_esn = _SECONDARY_ESN_CANDIDATES[0]
    print(f"  Testing secondary ESN: {_sec_esn}")
    _f_raw = dbutils.notebook.run(  # noqa: F821
        _UC2C_NB,
        timeout_seconds=600,
        arguments={**_COMMON_ARGS, "REQUESTED_ESN": _sec_esn, "QUERY_TEXT": QUERY_TEXT},
    )
    _f = json.loads(_f_raw) if _f_raw and _f_raw.strip().startswith("{") else {"status": "ERROR", "chunk_count": 0}
    print(f"  Result: status={_f['status']}  chunks={_f.get('chunk_count', '?')}  fallback_used={_f.get('fallback_used', '?')}")

    if _f.get("status") == "PASS":
        print(f"  PASS — secondary ESN {_sec_esn} retrieval working")
    elif _f.get("status") == "MISS":
        print(f"  WARN — secondary ESN {_sec_esn} returned MISS: no eligible docs in UC1 gate or no chunks in VS")
        print("         Verify this ESN has docs in the VS index with primary_esn matching it at chunk level.")
    else:
        print(f"  FAIL — unexpected result for secondary ESN {_sec_esn}: {_f}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION G — MULTI-DOC ESN TEST
# ═══════════════════════════════════════════════════════════════════════════════
# Verifies that UC2 returns chunks from multiple documents when the ESN has
# more than one eligible document. Tests whether the VS query with
# outage_start_date filter doesn't collapse to a single doc's chunks.

print("=" * 70)
print("SECTION G — MULTI-DOC ESN TEST")
print("=" * 70)

if _MULTIDOC_ESN is None:
    print("  SKIP — no multi-doc ESNs in this dataset")
else:
    print(f"  Testing multi-doc ESN: {_MULTIDOC_ESN}")
    # Use large TOP_K to increase chance of getting chunks from multiple docs
    _g_args = {**_COMMON_ARGS, "REQUESTED_ESN": _MULTIDOC_ESN, "QUERY_TEXT": QUERY_TEXT, "TOP_K": "20"}
    _g_raw = dbutils.notebook.run(_UC2C_NB, timeout_seconds=600, arguments=_g_args)  # noqa: F821
    _g = json.loads(_g_raw) if _g_raw and _g_raw.strip().startswith("{") else {"status": "ERROR", "chunk_count": 0}
    print(f"  Result: status={_g['status']}  chunks={_g.get('chunk_count', '?')}  fallback_used={_g.get('fallback_used', '?')}")

    # UC2-current exits with chunk_count but not document_id breakdown.
    # We check the chunks table directly to understand how many unique docs are eligible.
    _g_eligible_docs = spark.sql(f"""
        SELECT d.document_id
        FROM {MAP_TABLE} d
        INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
        WHERE d.esn = '{_MULTIDOC_ESN}'
          AND d.is_active = true
          AND m.metadata_status = 'completed'
          AND m.chunk_status = 'completed'
          AND m.outage_start_date >= '{THRESHOLD_DATE}'
    """).collect()
    _g_doc_ids = [r.document_id for r in _g_eligible_docs]
    print(f"  Eligible document_ids for {_MULTIDOC_ESN}: {_g_doc_ids}")

    # Count chunks per doc in the VS-backed chunks table
    _g_chunk_counts = spark.sql(f"""
        SELECT document_id, COUNT(*) AS chunk_count
        FROM {_CHUNKS_TABLE}
        WHERE primary_esn = '{_MULTIDOC_ESN}'
          AND document_id IN ({', '.join(repr(d) for d in _g_doc_ids)})
        GROUP BY document_id
        ORDER BY document_id
    """).collect()
    print(f"  Chunks per doc in {_CHUNKS_TABLE}:")
    for r in _g_chunk_counts:
        print(f"       document_id={r.document_id}  chunks={r.chunk_count}")
    if len(_g_chunk_counts) >= 2:
        print(f"  PASS — both docs have chunks indexed; VS returned {_g.get('chunk_count', '?')} chunks total")
        print("         Note: VS result may not include both docs due to similarity ranking — expected.")
    elif len(_g_chunk_counts) == 1:
        print("  WARN — only one document has indexed chunks for this ESN (other doc may not be in index)")
    else:
        print("  WARN — no chunks found in chunks table for this multi-doc ESN")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION H — STEP 2B FALLBACK END-TO-END TEST
# ═══════════════════════════════════════════════════════════════════════════════
# Verifies that Step 2b (unattributed chunk fallback) actually fires and returns
# results when unattributed chunks exist in eligible documents.
#
# Prerequisites:
#   1. Some chunks must have primary_esn = '' in the chunks table (D.1 > 0)
#   2. Those chunks must belong to docs that pass the UC1 gate for some ESN
#
# If no unattributed chunks exist, this section is skipped.

print("=" * 70)
print("SECTION H — STEP 2B FALLBACK END-TO-END TEST")
print("=" * 70)

if _unattributed_count == 0:
    print("  SKIP — no unattributed chunks in this dataset (primary_esn='' count = 0)")
    print("         Issue 3 has not manifested in this dev dataset.")
else:
    print(f"  Found {_unattributed_count} unattributed chunks — finding an ESN to trigger Step 2b")

    # Find an ESN whose eligible docs contain unattributed chunks
    _h_candidate = spark.sql(f"""
        SELECT DISTINCT d.esn
        FROM {MAP_TABLE} d
        INNER JOIN {META_TABLE} m ON d.document_id = m.document_id
        INNER JOIN {_CHUNKS_TABLE} c ON c.document_id = d.document_id
        WHERE d.is_active = true
          AND m.metadata_status = 'completed'
          AND m.chunk_status = 'completed'
          AND m.outage_start_date >= '{THRESHOLD_DATE}'
          AND c.primary_esn = ''
        LIMIT 1
    """).collect()

    if not _h_candidate:
        print("  SKIP — unattributed chunks exist but not in any ESN's eligible docs")
    else:
        _h_esn = _h_candidate[0].esn
        print(f"  Using ESN {_h_esn} — has eligible docs with unattributed chunks")
        # Set MIN_RESULTS very high to guarantee Step 2b triggers even if Step 2a returns some results
        _h_args = {**_COMMON_ARGS, "REQUESTED_ESN": _h_esn, "QUERY_TEXT": QUERY_TEXT,
                   "MIN_RESULTS": "999", "TOP_K": "10"}
        _h_raw = dbutils.notebook.run(_UC2C_NB, timeout_seconds=600, arguments=_h_args)  # noqa: F821
        _h = json.loads(_h_raw) if _h_raw and _h_raw.strip().startswith("{") else {"status": "ERROR", "chunk_count": 0}
        print(f"  Result: status={_h['status']}  chunks={_h.get('chunk_count', '?')}  fallback_used={_h.get('fallback_used', '?')}")

        if _h.get("fallback_used"):
            print("  PASS — Step 2b triggered and returned results")
        elif _h.get("status") == "PASS" and not _h.get("fallback_used"):
            print("  WARN — Step 2b did not trigger (Step 2a may have already returned enough results)")
            print("         Increase MIN_RESULTS further or use an ESN where primary_esn attribution is entirely missing.")
        else:
            print(f"  FAIL or INCONCLUSIVE — check fallback logic: {_h}")
