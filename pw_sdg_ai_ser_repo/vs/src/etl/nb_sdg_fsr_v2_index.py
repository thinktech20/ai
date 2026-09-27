# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_v2_index — P3: Vector Index Management (VS)
#
# Orchestrates stage 6 of the FSR V2 pipeline:
#   Stage 6 — Vector index: create, refresh, or sync fsr_vs_index_v2
#
# Runs independently from P1/P2 — can be triggered separately for:
#   - Initial index creation
#   - Metadata-only refresh (no re-embedding)
#   - Full sync after P2 writes new chunks
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../../common/fsr_v2/config

# COMMAND ----------

import logging
import os
import sys
import uuid

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.p3")

_VS_ETL = os.path.normpath(os.path.join(os.getcwd(), "../../../vs/src/etl"))
if _VS_ETL not in sys.path:
	sys.path.insert(0, _VS_ETL)

from fsr_v2 import vector_index


def _parse_verify_ssl(name: str, default: str = "false"):
	raw = get_runtime_param(name, default).strip()
	if raw.lower() in ("0", "false", "f", "no", "n", "off"):
		return False
	if os.path.exists(raw):
		return raw
	return True


def _get_dbr_auth():
	host = spark.conf.get("spark.databricks.workspaceUrl")
	ws_url = f"https://{host}"
	token = (dbutils.notebook.entry_point  # noqa: F821
			 .getDbutils().notebook().getContext().apiToken().get())
	return ws_url, token


CHUNK_TABLE = get_runtime_param("CHUNK_TABLE_V2", CHUNK_TABLE_V2).strip()
VS_INDEX = get_runtime_param("VS_INDEX_V2", VS_INDEX_V2).strip()
VS_ENDPOINT = get_runtime_param("VS_ENDPOINT_V2", VS_ENDPOINT_V2).strip()
MODE = get_runtime_param("INDEX_MODE", INDEX_MODE or "sync").strip().lower()
VERIFY_SSL = _parse_verify_ssl("FSR_DATABRICKS_VERIFY_SSL", "false")
EMBED_DIM = int(get_runtime_param("FSR_EMBEDDING_DIMENSION", "3072"))
RUN_MODE = get_runtime_param("FSR_V2_RUN_MODE", "incremental").strip().lower()
REPAIR_SCOPE_TABLE = get_runtime_param("FSR_V2_REPAIR_SCOPE_TABLE", "").strip()
REPAIR_RUN_ID = get_runtime_param("FSR_V2_REPAIR_RUN_ID", "").strip()
REPAIR_DRY_RUN = get_runtime_param("FSR_V2_REPAIR_DRY_RUN", "false").strip().lower() == "true"
P3_RUN_ID = uuid.uuid4().hex

if not CHUNK_TABLE or not VS_INDEX or not VS_ENDPOINT:
	raise ValueError("CHUNK_TABLE_V2, VS_INDEX_V2, and VS_ENDPOINT_V2 are required")
if RUN_MODE not in {"incremental", "targeted", "repair"}:
	raise ValueError(f"Unsupported FSR_V2_RUN_MODE={RUN_MODE!r}")
if RUN_MODE == "repair":
	if not REPAIR_SCOPE_TABLE or not REPAIR_RUN_ID:
		raise ValueError(
			"FSR_V2_RUN_MODE=repair requires FSR_V2_REPAIR_SCOPE_TABLE and "
			"FSR_V2_REPAIR_RUN_ID"
		)
	if REPAIR_DRY_RUN:
		dbutils.notebook.exit("Repair dry run: P3 did not synchronize the vector index")  # noqa: F821

# COMMAND ----------

# ── STAGE 6: VECTOR INDEX ─────────────────────────────────────────────────────
# Create or sync fsr_vs_index_v2 over fsr_chunks_v2.
# INDEX_MODE controls behaviour: create | sync

log.info("=== FSR V2 P3 (Vector Index) ===")
log.info(f"Chunk table  : {CHUNK_TABLE}")
log.info(f"VS index     : {VS_INDEX}")
log.info(f"VS endpoint  : {VS_ENDPOINT}")
log.info(f"Mode         : {MODE}")

if RUN_MODE == "repair":
	spark.sql(f"""
		UPDATE {REPAIR_SCOPE_TABLE}
		SET p3_status = 'in_progress', p3_run_id = '{P3_RUN_ID}'
		WHERE run_id = '{REPAIR_RUN_ID.replace("'", "''")}'
		  AND p2_status = 'completed'
		  AND p3_status IN ('pending', 'failed')
	""")

ws_url, token = _get_dbr_auth()

try:
	vector_index.run(
		chunk_table=CHUNK_TABLE,
		index_name=VS_INDEX,
		endpoint_name=VS_ENDPOINT,
		mode=MODE,
		workspace_url=ws_url,
		token=token,
		verify_ssl=VERIFY_SSL,
		embedding_dimension=EMBED_DIM,
	)
except Exception as exc:
	if RUN_MODE == "repair":
		spark.sql(f"""
			UPDATE {REPAIR_SCOPE_TABLE}
			SET p3_status = 'failed', error_message = '{str(exc)[:1000].replace("'", "''")}'
			WHERE run_id = '{REPAIR_RUN_ID.replace("'", "''")}'
			  AND p3_status = 'in_progress'
		""")
	raise

if RUN_MODE == "repair":
	spark.sql(f"""
		UPDATE {REPAIR_SCOPE_TABLE}
		SET p3_status = 'completed', p3_run_id = '{P3_RUN_ID}',
			completed_at = current_timestamp(), error_message = NULL
		WHERE run_id = '{REPAIR_RUN_ID.replace("'", "''")}'
		  AND p3_status = 'in_progress'
	""")

log.info("=== FSR V2 P3 complete ===")
