# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_repair_vistra_xtrain_verify — Read-only verification of a Vistra
# cross-train repair run.
#
# Run after nb_sdg_fsr_repair_vistra_xtrain (any env). Pass the same
# REPAIR_RUN_ID + JB_ENV used by the repair. No writes.
#
# Checks (all scoped to REPAIR_RUN_ID):
#   C1 staging done count       matches audit metadata-row count
#   C2 every audited document_id is present in METADATA_TABLE
#   C3 every audited chunk_id   is present in CHUNK_TABLE
#   C4 every inserted metadata row has the expected ESN + equipment_type
#   C5 per (pdf_name, esn) chunk distribution looks sane
#       (new ESN row count > 0, equal-or-close to base row count)
#   C6 sample VS search round-trip for one inserted ESN (best-effort)
#
# Exits non-zero summary string if any of C1..C4 fail. C5 + C6 are reports,
# not gates.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../../common/fsr_config

# COMMAND ----------

import logging

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.repair.vistra.verify")

# COMMAND ----------

_sot_prefix = METADATA_TABLE.rsplit(".", 1)[0]
_std_prefix = CHUNK_TABLE.rsplit(".", 1)[0]

STAGING_TABLE = get_runtime_param("STAGING_TABLE", f"{_sot_prefix}.staging_vistra_gap")
AUDIT_CHUNK_TABLE = get_runtime_param(
    "AUDIT_CHUNK_TABLE", f"{_std_prefix}.fsr_repair_vistra_chunk_inserts"
)
AUDIT_META_TABLE = get_runtime_param(
    "AUDIT_META_TABLE", f"{_sot_prefix}.fsr_repair_vistra_metadata_updates"
)

REPAIR_RUN_ID = get_runtime_param("REPAIR_RUN_ID", "").strip()
JB_ENV = get_runtime_param("jb_env", "").strip().lower()

if JB_ENV not in ("dev", "prod"):
    raise ValueError("JB_ENV must be 'dev' or 'prod'.")

RUN_ID_COL = f"{JB_ENV}_run_id"
STATUS_COL = f"{JB_ENV}_status"


def _sql_quote(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


# If REPAIR_RUN_ID not provided, pick the latest one from chunk audit.
if not REPAIR_RUN_ID:
    _latest = spark.sql(
        f"""
        SELECT repair_run_id
        FROM {AUDIT_CHUNK_TABLE}
        WHERE repair_run_id IS NOT NULL
        ORDER BY inserted_at DESC
        LIMIT 1
        """
    ).first()
    if not _latest:
        dbutils.notebook.exit("NOOP: no audit rows found — nothing to verify")  # noqa: F821
    REPAIR_RUN_ID = _latest["repair_run_id"]

_RUN_PRED = f"repair_run_id = {_sql_quote(REPAIR_RUN_ID)}"
_RUN_PRED_A = f"a.repair_run_id = {_sql_quote(REPAIR_RUN_ID)}"

log.info("=== Vistra Cross-Train Repair VERIFY ===")
log.info(f"  REPAIR_RUN_ID     : {REPAIR_RUN_ID}")
log.info(f"  JB_ENV           : {JB_ENV}")
log.info(f"  STAGING_TABLE     : {STAGING_TABLE}")
log.info(f"  METADATA_TABLE    : {METADATA_TABLE}")
log.info(f"  CHUNK_TABLE       : {CHUNK_TABLE}")
log.info(f"  AUDIT_CHUNK_TABLE : {AUDIT_CHUNK_TABLE}")
log.info(f"  AUDIT_META_TABLE  : {AUDIT_META_TABLE}")

# COMMAND ----------

# ── Pre-flight counts ───────────────────────────────────────────────────────
audit_chunk_cnt = spark.sql(
    f"SELECT COUNT(*) AS cnt FROM {AUDIT_CHUNK_TABLE} WHERE {_RUN_PRED}"
).first().cnt
audit_meta_cnt = spark.sql(
    f"SELECT COUNT(*) AS cnt FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED}"
).first().cnt
staging_done_cnt = spark.sql(
    f"""
    SELECT COUNT(*) AS cnt FROM {STAGING_TABLE}
    WHERE {RUN_ID_COL} = {_sql_quote(REPAIR_RUN_ID)}
      AND LOWER({STATUS_COL}) = 'done'
    """
).first().cnt
staging_failed_cnt = spark.sql(
    f"""
    SELECT COUNT(*) AS cnt FROM {STAGING_TABLE}
    WHERE {RUN_ID_COL} = {_sql_quote(REPAIR_RUN_ID)}
      AND LOWER({STATUS_COL}) = 'failed'
    """
).first().cnt

log.info("")
log.info("Pre-flight counts:")
log.info(f"  audit_chunk_rows   : {audit_chunk_cnt:,}")
log.info(f"  audit_meta_rows    : {audit_meta_cnt:,}  (one per inserted doc)")
log.info(f"  staging_done       : {staging_done_cnt:,}")
log.info(f"  staging_failed     : {staging_failed_cnt:,}")

failures = []

# COMMAND ----------

# ── C1: staging done count == audit meta count ──────────────────────────────
if staging_done_cnt != audit_meta_cnt:
    failures.append(
        f"C1: staging done={staging_done_cnt} != audit_meta_rows={audit_meta_cnt}"
    )
    log.error(f"  [C1 FAIL] {failures[-1]}")
else:
    log.info(f"  [C1 OK]   staging done == audit meta rows ({staging_done_cnt})")

# COMMAND ----------

# ── C2: every audited document_id is present in METADATA_TABLE ──────────────
missing_meta = spark.sql(
    f"""
    SELECT a.document_id
    FROM {AUDIT_META_TABLE} a
    LEFT ANTI JOIN {METADATA_TABLE} m ON m.document_id = a.document_id
    WHERE {_RUN_PRED_A}
    """
).collect()

if missing_meta:
    failures.append(f"C2: {len(missing_meta)} audited metadata document_ids missing from {METADATA_TABLE}")
    log.error(f"  [C2 FAIL] {failures[-1]}")
    for r in missing_meta[:10]:
        log.error(f"           missing: {r['document_id']}")
else:
    log.info(f"  [C2 OK]   all {audit_meta_cnt} audited document_ids present in metadata")

# COMMAND ----------

# ── C3: every audited chunk_id is present in CHUNK_TABLE ────────────────────
missing_chunks_cnt = spark.sql(
    f"""
    SELECT COUNT(*) AS cnt
    FROM {AUDIT_CHUNK_TABLE} a
    LEFT ANTI JOIN {CHUNK_TABLE} c ON c.chunk_id = a.chunk_id
    WHERE {_RUN_PRED_A}
    """
).first().cnt

if missing_chunks_cnt > 0:
    failures.append(f"C3: {missing_chunks_cnt} audited chunk_ids missing from {CHUNK_TABLE}")
    log.error(f"  [C3 FAIL] {failures[-1]}")
else:
    log.info(f"  [C3 OK]   all {audit_chunk_cnt:,} audited chunk_ids present in chunks")

# COMMAND ----------

# ── C4: inserted metadata row carries the expected ESN + Generator type ─────
bad_meta_rows = spark.sql(
    f"""
    SELECT a.document_id, a.inserted_esn, m.esn, m.equipment_type
    FROM {AUDIT_META_TABLE} a
    JOIN {METADATA_TABLE} m ON m.document_id = a.document_id
    WHERE {_RUN_PRED_A}
      AND (
            COALESCE(TRIM(m.esn), '') != COALESCE(TRIM(a.inserted_esn), '')
         OR COALESCE(TRIM(m.equipment_type), '') != 'Generator'
      )
    """
).collect()

if bad_meta_rows:
    failures.append(f"C4: {len(bad_meta_rows)} inserted metadata rows have wrong esn/equipment_type")
    log.error(f"  [C4 FAIL] {failures[-1]}")
    for r in bad_meta_rows[:10]:
        log.error(
            f"           doc={r['document_id']} expected_esn={r['inserted_esn']} "
            f"actual_esn={r['esn']} equipment_type={r['equipment_type']}"
        )
else:
    log.info(f"  [C4 OK]   all {audit_meta_cnt} inserted metadata rows have expected esn + equipment_type")

# COMMAND ----------

# ── C5: chunk distribution per (pdf_name, esn) — report only ────────────────
log.info("")
log.info("C5: chunk distribution for processed docs (new + base):")
spark.sql(
    f"""
    WITH scope_docs AS (
        SELECT document_id      AS doc_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED}
        UNION
        SELECT base_document_id AS doc_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED}
    )
    SELECT c.pdf_name, c.esn, COUNT(*) AS chunk_rows
    FROM {CHUNK_TABLE} c
    JOIN scope_docs s ON c.document_id = s.doc_id
    GROUP BY c.pdf_name, c.esn
    ORDER BY c.pdf_name, c.esn
    """
).show(200, truncate=False)

log.info("Per-document new-vs-base chunk parity:")
spark.sql(
    f"""
    WITH new_cnt AS (
        SELECT a.base_document_id, a.document_id AS new_doc_id,
               COUNT(*) AS new_chunks
        FROM {AUDIT_CHUNK_TABLE} a
        WHERE {_RUN_PRED}
        GROUP BY a.base_document_id, a.document_id
    ),
    base_cnt AS (
        SELECT document_id AS base_document_id, COUNT(*) AS base_chunks
        FROM {CHUNK_TABLE}
        WHERE document_id IN (SELECT DISTINCT base_document_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED})
        GROUP BY document_id
    )
    SELECT n.base_document_id, n.new_doc_id, b.base_chunks, n.new_chunks,
           (b.base_chunks - n.new_chunks) AS diff
    FROM new_cnt n
    LEFT JOIN base_cnt b ON b.base_document_id = n.base_document_id
    ORDER BY ABS(COALESCE(b.base_chunks - n.new_chunks, 0)) DESC
    """
).show(200, truncate=False)

# COMMAND ----------

# ── C6: VS sample round-trip — best-effort, non-blocking ────────────────────
log.info("")
log.info("C6: VS sample round-trip (best-effort)...")

sample = spark.sql(
    f"""
    SELECT inserted_esn
    FROM {AUDIT_META_TABLE}
    WHERE {_RUN_PRED} AND inserted_esn IS NOT NULL
    LIMIT 1
    """
).first()

if sample is None:
    log.info("  No inserted_esn in audit — skipped")
else:
    sample_esn = sample["inserted_esn"]
    try:
        from databricks.vector_search.client import VectorSearchClient

        vsc = VectorSearchClient(disable_notice=True)
        idx = vsc.get_index(endpoint_name=VS_ENDPOINT_NAME, index_name=VS_INDEX_NAME)
        res = idx.similarity_search(
            query_text=f"generator inspection findings ESN {sample_esn}",
            columns=["chunk_id", "document_id", "esn", "pdf_name"],
            num_results=5,
            filters={"esn": sample_esn},
        )
        rows = (res.get("result") or {}).get("data_array") or []
        log.info(f"  VS hits for esn={sample_esn}: {len(rows)}")
        for row in rows[:5]:
            log.info(f"    {row}")
        if not rows:
            log.warning("  VS returned 0 hits — index may need a sync after the repair.")
    except Exception as e:  # noqa: BLE001
        log.warning(f"  VS round-trip skipped: {e}")

# COMMAND ----------

# ── Final result ────────────────────────────────────────────────────────────
log.info("")
log.info("=" * 70)
if failures:
    log.error("  VERIFY: FAIL")
    for f_ in failures:
        log.error(f"    - {f_}")
    log.info("=" * 70)
    raise RuntimeError(
        f"VERIFY FAIL (run_id={REPAIR_RUN_ID}, env={JB_ENV}): " + "; ".join(failures)
    )
else:
    log.info("  VERIFY: PASS")
    log.info("=" * 70)

dbutils.notebook.exit(  # noqa: F821
    f"VERIFY PASS (run_id={REPAIR_RUN_ID}, env={JB_ENV}): "
    f"docs={audit_meta_cnt}, chunks={audit_chunk_cnt}, "
    f"staging_done={staging_done_cnt}, staging_failed={staging_failed_cnt}"
)
