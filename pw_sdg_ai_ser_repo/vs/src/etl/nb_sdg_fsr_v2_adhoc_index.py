# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_v2_adhoc_index — Adhoc vector_index_sync_v2 task
#
# Third task of PW_SDG_FSR_V2_Ingestion_Adhoc. Invokes the UNMODIFIED main P3
# notebook (vs/src/etl/nb_sdg_fsr_v2_index.py) via dbutils.notebook.run() —
# same pattern as P1/P2 — then records completion in the SDG execution-state
# table, keyed on (pdf_name, dag_run_id) passed in from the triggering DAG
# (esn is looked up from that row instead of being passed separately).
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_v2/config

# COMMAND ----------

import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.adhoc_p3")

if "get_runtime_param" not in globals():
	def get_runtime_param(name: str, default: str = "") -> str:  # type: ignore[no-redef]
		return os.getenv(name, default)

# Make fsr_v2 package importable — needed for the document_id normalization
# helper used by the per-document stage-update check below.
_SILVER_ETL = os.path.normpath(os.path.join(os.getcwd(), "../../../silver/src/etl"))
if _SILVER_ETL not in sys.path:
	sys.path.insert(0, _SILVER_ETL)
_BUNDLE_ROOT = str(Path(_SILVER_ETL).parents[2])
if _BUNDLE_ROOT not in sys.path:
	sys.path.insert(0, _BUNDLE_ROOT)

from fsr_v2 import input as inp  # noqa: E402 — unmodified: same doc_id normalization as P1/P2

METADATA_TABLE = get_runtime_param("METADATA_TABLE_V2", "").strip()

# ============================================================
# SDG EXECUTION STATE - DISCOVERED ROWS
# pdf_name/dag_run_id pairs come from chunking_v2's task value — the
# triggering DAG passes no identifying parameters at all.
# ============================================================

import json  # noqa: E402

dbutils.widgets.text(  # noqa: F821
	"execution_table",
	get_runtime_param("FSR_SDG_EXECUTION_TABLE", "viud.ing_ud_fieldvision.sdg_user_attachments_execution_log_psot")
)
execution_table = dbutils.widgets.get("execution_table").strip()  # noqa: F821

if not execution_table:
	raise ValueError("execution_table parameter is missing")
if "{{" in execution_table or "}}" in execution_table:
	raise ValueError(
		f"execution_table still contains an un-templated placeholder ('{execution_table}') — "
		"the triggering caller must override this job parameter with a real value"
	)

_ready_pairs_raw = get_runtime_param("FSR_ADHOC_READY_PAIRS", "[]").strip()
try:
	READY_PAIRS = json.loads(_ready_pairs_raw) if _ready_pairs_raw else []
except ValueError:
	log.warning(f"FSR_ADHOC_READY_PAIRS was not valid JSON ({_ready_pairs_raw!r}) — treating as empty")
	READY_PAIRS = []

log.info(f"SDG state table   : {execution_table}")
log.info(f"Discovered {len(READY_PAIRS)} row(s) ready for P3: {[p['pdf_name'] for p in READY_PAIRS]}")

_p3_timeout_raw = get_runtime_param("FSR_ADHOC_P3_TIMEOUT_SECONDS", "3600").strip()
P3_TIMEOUT_SECONDS = int(_p3_timeout_raw) if _p3_timeout_raw else 3600

# COMMAND ----------

# ── Invoke the unmodified main P3 notebook ───────────────────────────────────
# Raises on child failure/timeout — the SYNCED update below never runs if this does.

_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()  # noqa: F821
_this_notebook_path = _ctx.notebookPath().get()
_p3_notebook_path = "/".join(_this_notebook_path.split("/")[:-1]) + "/nb_sdg_fsr_v2_index"
log.info(f"P3 notebook path: {_p3_notebook_path}")

p3_args = {
	"CHUNK_TABLE_V2": get_runtime_param("CHUNK_TABLE_V2", ""),
	"VS_INDEX_V2": get_runtime_param("VS_INDEX_V2", ""),
	"VS_ENDPOINT_V2": get_runtime_param("VS_ENDPOINT_V2", ""),
	"INDEX_MODE": get_runtime_param("INDEX_MODE", "sync"),
	"FSR_DATABRICKS_VERIFY_SSL": get_runtime_param("FSR_DATABRICKS_VERIFY_SSL", "false"),
	"FSR_EMBEDDING_DIMENSION": get_runtime_param("FSR_EMBEDDING_DIMENSION", "3072"),
}

_p3_run_id = dbutils.notebook.run(_p3_notebook_path, P3_TIMEOUT_SECONDS, p3_args)  # noqa: F821
log.info(f"P3 child notebook run complete: run_id={_p3_run_id}")

# COMMAND ----------

# ============================================================
# SDG STAGE UPDATE - SYNCED (per discovered row)
# The P3 sync itself is table-wide (not scoped to any one pdf_name), so a
# successful call above only proves the index sync ran — it doesn't prove any
# given document's chunks were ever produced. Re-check chunk_status per row.
# ============================================================

for _pair in READY_PAIRS:
	_pdf_name = _pair["pdf_name"]
	_dag_run_id = _pair["dag_run_id"]
	_doc_id = inp._target_document_id(_pdf_name)  # noqa: F821
	_doc_id_sql = _doc_id.replace("'", "''")

	_post_rows = spark.sql(f"""
		SELECT chunk_status
		FROM {METADATA_TABLE}
		WHERE document_id = '{_doc_id_sql}'
	""").collect()  # noqa: F821

	if _post_rows and _post_rows[0]["chunk_status"] == "completed":
		stage_value, status_value, event_status = "SYNCED", "COMPLETED", "SUCCESS"
	else:
		stage_value, status_value, event_status = "SKIPPED", "SKIPPED", "SKIPPED"

	log.info(f"Per-document P3 outcome: pdf_name={_pdf_name} document_id={_doc_id} -> stage={stage_value}")

	sync_update_sql = f"""
	UPDATE {execution_table}
	SET
	    last_stage_processed_at = current_timestamp(),
	    current_stage = '{stage_value}',
	    status = '{status_value}',
	    timeline_metadata = to_json(
	        concat(
	            from_json(
	                COALESCE(timeline_metadata, '[]'),
	                'array<struct<event:string,event_time:string,status:string>>'
	            ),
	            array(
	                named_struct(
	                    'event', '{stage_value}',
	                    'event_time', CAST(current_timestamp() AS STRING),
	                    'status', '{event_status}'
	                )
	            )
	        )
	    )
	WHERE pdf_name = :pdf_name
	  AND dag_run_id = :dag_run_id
	"""
	spark.sql(sync_update_sql, args={"pdf_name": _pdf_name, "dag_run_id": _dag_run_id})  # noqa: F821

log.info(f"SDG state updated for {len(READY_PAIRS)} row(s)")
