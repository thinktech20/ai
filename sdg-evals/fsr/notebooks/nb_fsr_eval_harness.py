# Databricks notebook source
# MAGIC %md
# MAGIC # FSR Retrieval Eval Harness
# MAGIC
# MAGIC Runs the probe set through the FSR vector-search index and logs a lightweight MLflow run.
# MAGIC The headline metric is `avg_retrieved_vs_exists_ratio`.
# MAGIC Flip `TOP_K` or `MAX_PER_DOC` and re-run to A/B.

# COMMAND ----------

# MAGIC %pip install --quiet mlflow-skinny databricks-vectorsearch

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import sys, os
# Make the repo importable when running this notebook from /Workspace/Repos/...
REPO_ROOT = os.path.abspath(os.path.join(os.getcwd(), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from fsr.retrieval.embedder import EmbedderConfig, LiteLLMEmbedder
from fsr.retrieval_eval.harness import run_eval
from fsr.retrieval_eval.probe_set import build_probe_set_in_memory, load_probe_set
from fsr.retrieval.retriever import (
    DatabricksSqlEligibilityProvider,
    DatabricksVectorSearchProvider,
    RetrieverConfig,
    create_retriever,
)
from databricks.vector_search.client import VectorSearchClient

# COMMAND ----------

dbutils.widgets.text("FSR_VS_ENDPOINT", "pw-ser-sdg-vector-search")
dbutils.widgets.text("FSR_VS_INDEX",    "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")
dbutils.widgets.text("FSR_LEGACY_INDEX", "vaid.ai_std_con_field_service_report.vs_vec_field_service_report")
dbutils.widgets.text("FSR_V2_MAPPING_TABLE", "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")
dbutils.widgets.text("FSR_V2_METADATA_TABLE", "vaid.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("FSR_LEGACY_METADATA_TABLE", "vaid.ai_sot_field_service_report.fsr_metadata")
dbutils.widgets.text("FSR_LEGACY_CHUNKS_TABLE", "vaid.ai_sot_field_service_report.fsr_chunks")
dbutils.widgets.text("FSR_METADATA_TABLE", "vaid.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("PROBE_SET_TABLE",    "")
dbutils.widgets.text("METADATA_VERSION",   "")     # blank = latest Delta version (pinned and logged either way)
dbutils.widgets.text("PROBE_SET_VERSION",  "v1")   # opaque label for the probe definition; bump when template/rules change
dbutils.widgets.text("PROBE_QUERY_TEMPLATE", "field service report findings for unit {esn}")
dbutils.widgets.text("PROBE_PER_BUCKET",   "15")
dbutils.widgets.text("PROBE_SEED",         "7")
dbutils.widgets.text("MLFLOW_EXPERIMENT",  "/Users/madhurima.saxena@gevernova.com/fsr_retrieval_eval")
dbutils.widgets.text("RUN_NAME_PREFIX",    "fsr_retrieval")
dbutils.widgets.text("TOP_K",              "10")
dbutils.widgets.text("STRATEGY",           "ura_current")
dbutils.widgets.text("MAX_PER_DOC",        "")     # blank = off
# FSR index is direct-access — we must embed the query ourselves with the same
# model the pipeline used. Defaults match common/fsr_config.py / databricks.yaml.
dbutils.widgets.text("LITELLM_BASE_URL",   "https://dev-gateway.apps.gevernova.net")
dbutils.widgets.text("LITELLM_API_KEY",    "")  # paste at runtime; not stored
dbutils.widgets.text("EMBEDDING_MODEL",    "azure-text-embedding-3-large-1")

ENDPOINT  = dbutils.widgets.get("FSR_VS_ENDPOINT")
INDEX     = dbutils.widgets.get("FSR_VS_INDEX")
LEGACY_INDEX = dbutils.widgets.get("FSR_LEGACY_INDEX")
V2_MAPPING_TABLE = dbutils.widgets.get("FSR_V2_MAPPING_TABLE")
V2_METADATA_TABLE = dbutils.widgets.get("FSR_V2_METADATA_TABLE")
LEGACY_METADATA_TABLE = dbutils.widgets.get("FSR_LEGACY_METADATA_TABLE")
LEGACY_CHUNKS_TABLE = dbutils.widgets.get("FSR_LEGACY_CHUNKS_TABLE")
META      = dbutils.widgets.get("FSR_METADATA_TABLE")
PROBE_SET_TABLE = dbutils.widgets.get("PROBE_SET_TABLE").strip()
META_VER  = int(dbutils.widgets.get("METADATA_VERSION")) if dbutils.widgets.get("METADATA_VERSION") else None
PROBE_VER = dbutils.widgets.get("PROBE_SET_VERSION")
QUERY_TMPL = dbutils.widgets.get("PROBE_QUERY_TEMPLATE")
PER_BUCKET = int(dbutils.widgets.get("PROBE_PER_BUCKET"))
SEED      = int(dbutils.widgets.get("PROBE_SEED"))
EXPERIMENT = dbutils.widgets.get("MLFLOW_EXPERIMENT")
RUN_NAME_PREFIX = dbutils.widgets.get("RUN_NAME_PREFIX").strip() or "fsr_retrieval_eval"
TOP_K     = int(dbutils.widgets.get("TOP_K"))
STRATEGY = dbutils.widgets.get("STRATEGY").strip()
MAX_PER_DOC = int(dbutils.widgets.get("MAX_PER_DOC")) if dbutils.widgets.get("MAX_PER_DOC") else None
LITELLM_URL = dbutils.widgets.get("LITELLM_BASE_URL")
LITELLM_KEY = dbutils.widgets.get("LITELLM_API_KEY")
EMBED_MODEL = dbutils.widgets.get("EMBEDDING_MODEL")

# COMMAND ----------

# Prefer a fixed probe table when provided so baseline and candidate use the
# exact same ESN/query set across runs. Fall back to in-memory sampling only
# when a saved probe table is not supplied.
if PROBE_SET_TABLE:
    probes = load_probe_set(spark, PROBE_SET_TABLE)
    used_meta_version = META_VER
    print(f"Loaded {len(probes)} probes from table {PROBE_SET_TABLE!r} (probe_set={PROBE_VER})")
else:
    # Read-only, version-pinned probe set. No tables are written.
    # These values travel into MLflow so the run is reproducible end-to-end:
    #   metadata_version    -> which snapshot of the metadata table we sampled from
    #   probe_set_version   -> opaque label for the probe definition
    #   query_template      -> exact text used to build each probe's query
    probes, used_meta_version = build_probe_set_in_memory(
        spark,
        metadata_table=META,
        per_bucket=PER_BUCKET,
        seed=SEED,
        metadata_version=META_VER,
        query_template=QUERY_TMPL,
        probe_set_version=PROBE_VER,
    )
    print(f"Loaded {len(probes)} probes  (probe_set={PROBE_VER}, metadata version {used_meta_version})")
print(f"Sample query: {probes[0].query!r}")

# COMMAND ----------

embedder = LiteLLMEmbedder(EmbedderConfig(
    base_url=LITELLM_URL,
    api_key=LITELLM_KEY,
    model=EMBED_MODEL,
))


class SparkQueryClient:
    def query(self, query: str, params: dict[str, str]):
        escaped_esn = params["esn"].replace("'", "''")
        return [row.asDict() for row in spark.sql(query.replace(":esn", f"'{escaped_esn}'")).collect()]


search_provider = DatabricksVectorSearchProvider(
    VectorSearchClient(disable_notice=True),
    ENDPOINT,
    {"v2": INDEX, "legacy": LEGACY_INDEX},
)
eligibility_provider = DatabricksSqlEligibilityProvider(
    SparkQueryClient(),
    v2_mapping_table=V2_MAPPING_TABLE,
    v2_metadata_table=V2_METADATA_TABLE,
    legacy_metadata_table=LEGACY_METADATA_TABLE,
    legacy_chunks_table=LEGACY_CHUNKS_TABLE,
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Smoke test — time a single embedding call
# MAGIC
# MAGIC Run this before the full harness. Expected: 3072-dim vector in 1–4 s.
# MAGIC * < 5 s → healthy, continue.
# MAGIC * 5–30 s → gateway slow but reachable; harness will work but be slow.
# MAGIC * Times out → gateway problem, not our code. Stop and investigate before the full run.

# COMMAND ----------

import time
_t0 = time.perf_counter()
_v = embedder.embed("field service report findings for unit ESN-TEST")
print(f"Got {len(_v)}-dim vector in {(time.perf_counter() - _t0):.2f}s")

# COMMAND ----------

cfg = RetrieverConfig(
    v2_index_name=INDEX,
    legacy_index_name=LEGACY_INDEX,
    top_k=TOP_K,
)
retriever = create_retriever(
    strategy=STRATEGY,
    config=cfg,
    embedder=embedder,
    eligibility=eligibility_provider,
    search=search_provider,
)
run_id = run_eval(
    retriever, probes, experiment_name=EXPERIMENT,
    run_name_prefix=RUN_NAME_PREFIX,
    extra_tags={
        "variant": f"k{TOP_K}_capPerDoc{MAX_PER_DOC}",
        "metric": "avg_retrieved_vs_exists_ratio",
        "probe_set_version": PROBE_VER,
        "probe_source": "table" if PROBE_SET_TABLE else "sampled_in_memory",
    },
    probe_set_params={
        "probe_set_table":   PROBE_SET_TABLE,
        "metadata_table":     META,
        "metadata_version":   used_meta_version,
        "set_version":        PROBE_VER,
        "query_template":     QUERY_TMPL,
        "per_bucket":         PER_BUCKET,
        "seed":               SEED,
    },
)
print(f"MLflow run id: {run_id}")
