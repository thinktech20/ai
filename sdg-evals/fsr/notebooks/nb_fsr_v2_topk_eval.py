# Databricks notebook source
# MAGIC %md
# MAGIC # FSR v2 Top-k Retrieval Eval
# MAGIC
# MAGIC Runs probe-based retrieval eval across multiple `k` values and retriever
# MAGIC strategies (`ura_current`, `ura_with_shared_impl`).

# COMMAND ----------

# MAGIC %pip install --quiet mlflow-skinny databricks-vectorsearch

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import json
import os
import sys
import csv
import io
import tempfile
from collections import defaultdict

# Make repo importable from /Workspace/Repos/... notebook context
# Notebook lives at <repo>/fsr/notebooks, so two levels up is repo root.
REPO_ROOT = os.path.abspath(os.path.join(os.getcwd(), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from fsr.retrieval.embedder import EmbedderConfig, LiteLLMEmbedder
from fsr.retrieval_eval.harness import run_eval_detailed
from fsr.retrieval_eval.probe_set import load_probe_set_csv
from fsr.retrieval.retriever import (
    DatabricksSqlEligibilityProvider,
    DatabricksVectorSearchProvider,
    RetrieverConfig,
    create_retriever,
)
from databricks.vector_search.client import VectorSearchClient

# COMMAND ----------

dbutils.widgets.text("FSR_VS_ENDPOINT", "pw-ser-sdg-vector-search")
dbutils.widgets.text("FSR_VS_INDEX", "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")
dbutils.widgets.text("FSR_LEGACY_INDEX", "vaid.ai_std_con_field_service_report.vs_vec_field_service_report")
dbutils.widgets.text("FSR_V2_MAPPING_TABLE", "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")
dbutils.widgets.text("FSR_V2_METADATA_TABLE", "vaid.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("FSR_LEGACY_METADATA_TABLE", "vaid.ai_sot_field_service_report.fsr_metadata")
dbutils.widgets.text("FSR_LEGACY_CHUNKS_TABLE", "vaid.ai_sot_field_service_report.fsr_chunks")
dbutils.widgets.text(
    "PROBE_CSV_PATH",
    os.path.join(REPO_ROOT, "fsr", "probe-sets", "probe-set.csv"),
)
dbutils.widgets.text("PROBE_SET_VERSION", "v1")
dbutils.widgets.text("STRATEGIES", "ura_current,ura_with_shared_impl")
dbutils.widgets.text("TOP_K_VALUES", "5,10,20,40")
dbutils.widgets.text("OVERFETCH_K", "")
dbutils.widgets.text("RECENCY_WINDOW_MONTHS", "120")
dbutils.widgets.text("QUERY_TYPE", "HYBRID")
dbutils.widgets.text("RESULT_ESN_COLUMN", "region_primary_esn")
dbutils.widgets.text("RESULT_EQUIP_TYPE_COLUMN", "region_primary_equip_type")
dbutils.widgets.text("RESULT_CHUNK_TEXT_COLUMN", "chunk_text")
dbutils.widgets.text("MLFLOW_EXPERIMENT", "/Users/madhurima.saxena@gevernova.com/fsr_v2_topk_eval")
dbutils.widgets.text("RUN_NAME_PREFIX", "fsr_v2_topk")
dbutils.widgets.text("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
dbutils.widgets.text("LITELLM_API_KEY", "")
dbutils.widgets.text("EMBEDDING_MODEL", "azure-text-embedding-3-large-1")
dbutils.widgets.text("LLM_VERIFY_SSL", "false")

ENDPOINT = dbutils.widgets.get("FSR_VS_ENDPOINT").strip()
INDEX = dbutils.widgets.get("FSR_VS_INDEX").strip()
LEGACY_INDEX = dbutils.widgets.get("FSR_LEGACY_INDEX").strip()
V2_MAPPING_TABLE = dbutils.widgets.get("FSR_V2_MAPPING_TABLE").strip()
V2_METADATA_TABLE = dbutils.widgets.get("FSR_V2_METADATA_TABLE").strip()
LEGACY_METADATA_TABLE = dbutils.widgets.get("FSR_LEGACY_METADATA_TABLE").strip()
LEGACY_CHUNKS_TABLE = dbutils.widgets.get("FSR_LEGACY_CHUNKS_TABLE").strip()
DEFAULT_PROBE_CSV_PATH = os.path.join(REPO_ROOT, "fsr", "probe-sets", "probe-set.csv")
PROBE_CSV_PATH = dbutils.widgets.get("PROBE_CSV_PATH").strip() or DEFAULT_PROBE_CSV_PATH
PROBE_SET_VERSION = dbutils.widgets.get("PROBE_SET_VERSION").strip() or "v1"
STRATEGIES = [s.strip() for s in dbutils.widgets.get("STRATEGIES").split(",") if s.strip()]
TOP_K_VALUES = [int(v.strip()) for v in dbutils.widgets.get("TOP_K_VALUES").split(",") if v.strip()]
OVERFETCH_K = int(dbutils.widgets.get("OVERFETCH_K")) if dbutils.widgets.get("OVERFETCH_K").strip() else None
RECENCY_WINDOW_MONTHS = int(dbutils.widgets.get("RECENCY_WINDOW_MONTHS"))
QUERY_TYPE = dbutils.widgets.get("QUERY_TYPE").strip().upper() or "HYBRID"
RESULT_ESN_COLUMN = dbutils.widgets.get("RESULT_ESN_COLUMN").strip() or "region_primary_esn"
RESULT_EQUIP_TYPE_COLUMN = dbutils.widgets.get("RESULT_EQUIP_TYPE_COLUMN").strip() or "region_primary_equip_type"
RESULT_CHUNK_TEXT_COLUMN = dbutils.widgets.get("RESULT_CHUNK_TEXT_COLUMN").strip() or "chunk_text"
EXPERIMENT = dbutils.widgets.get("MLFLOW_EXPERIMENT").strip()
RUN_NAME_PREFIX = dbutils.widgets.get("RUN_NAME_PREFIX").strip() or "fsr_v2_topk"
LITELLM_URL = dbutils.widgets.get("LITELLM_BASE_URL").strip()
LITELLM_KEY = dbutils.widgets.get("LITELLM_API_KEY").strip()
EMBED_MODEL = dbutils.widgets.get("EMBEDDING_MODEL").strip() or "azure-text-embedding-3-large-1"
VERIFY_SSL = dbutils.widgets.get("LLM_VERIFY_SSL").strip().lower() != "false"

if not STRATEGIES:
    raise ValueError("STRATEGIES must include at least one strategy")
invalid_strategies = [s for s in STRATEGIES if s not in {"ura_current", "ura_with_shared_impl"}]
if invalid_strategies:
    raise ValueError(f"Unsupported STRATEGIES: {invalid_strategies}")
if not TOP_K_VALUES:
    raise ValueError("TOP_K_VALUES must include at least one integer")
if QUERY_TYPE not in {"HYBRID", "ANN"}:
    raise ValueError("QUERY_TYPE must be HYBRID or ANN")
if RECENCY_WINDOW_MONTHS < 0:
    raise ValueError("RECENCY_WINDOW_MONTHS must not be negative")


def _python_path(path: str) -> str:
    """Convert a DBFS URI to a local driver path for Python file access."""
    return "/dbfs/" + path.removeprefix("dbfs:/").lstrip("/") if path.startswith("dbfs:/") else path


def _validate_probe_csv_path(path: str) -> str:
    """Validate the resolved probe CSV before starting embedding or search work."""
    python_path = _python_path(path.strip())
    if not python_path:
        raise ValueError(
            "PROBE_CSV_PATH is empty. Set it to the reviewed resolved probe CSV "
            f"(default: {DEFAULT_PROBE_CSV_PATH})."
        )
    if not os.path.isfile(python_path):
        raise FileNotFoundError(
            f"Resolved probe CSV was not found: {path}. "
            "Use a Workspace, DBFS, or Volume path accessible to the driver."
        )

    with open(python_path, "r", encoding="utf-8", newline="") as f:
        csv_text = "".join(
            line for line in f
            if line.strip() and not line.lstrip().startswith("#")
        )
        reader = csv.DictReader(io.StringIO(csv_text))
        fieldnames = reader.fieldnames or []
        required = {"probe_id", "esn", "expected_document_ids"}
        missing = sorted(required - set(fieldnames))
        if missing:
            raise ValueError(
                f"Resolved probe CSV is missing required columns: {missing}. "
                "Regenerate it from the probe template and reviewed labels."
            )
        row_count = sum(1 for _ in reader)

    if row_count == 0:
        template_path = os.path.join(os.path.dirname(python_path), "probe-set.csv")
        if os.path.isfile(template_path):
            with open(template_path, "r", encoding="utf-8", newline="") as template_file:
                template_lines = [
                    line for line in template_file
                    if line.strip() and not line.lstrip().startswith("#")
                ]
            template_reader = csv.DictReader(io.StringIO("".join(template_lines)))
            template_rows = sum(1 for _ in template_reader)
            if template_rows:
                print(
                    f"Resolved probe CSV has no data rows; using populated template instead: "
                    f"{template_path} ({template_rows} probes)."
                )
                return template_path
        raise ValueError(
            f"Resolved probe CSV has no data rows: {path}. "
            "Populate it with reviewed probes, or provide a populated sibling "
            "probe-set.csv."
        )
    return python_path


def _normalize_probe_csv_for_loader(csv_path: str) -> str:
    """Backfill optional columns so simplified probe templates still load.

    The loader accepts simplified probe files when chunk-level labels are not
    available, so add empty compatibility columns when needed.
    """
    python_path = _python_path(csv_path)
    with open(python_path, "r", encoding="utf-8", newline="") as f:
        raw_lines = f.readlines()
        data_lines = [
            line for line in raw_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
        reader = csv.DictReader(io.StringIO("".join(data_lines)))
        if reader.fieldnames is None:
            raise ValueError("Probe CSV header is missing")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    ignored_prefix_lines = len(raw_lines) != len(data_lines)
    if (
        not ignored_prefix_lines
        and "expected_chunk_ids" in fieldnames
        and "chunk_table_version" in fieldnames
    ):
        return python_path

    missing = [c for c in ("expected_chunk_ids", "chunk_table_version") if c not in fieldnames]
    out_fields = fieldnames + missing
    for row in rows:
        row.pop(None, None)
        for col in missing:
            row[col] = ""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows)
        normalized_path = fh.name

    print(
        "Probe CSV normalized for loader compatibility. Added columns: "
        f"{missing}. Using temp file: {normalized_path}"
    )
    return normalized_path

# COMMAND ----------

embedder = LiteLLMEmbedder(
    EmbedderConfig(
        base_url=LITELLM_URL,
        api_key=LITELLM_KEY,
        model=EMBED_MODEL,
        verify_ssl=VERIFY_SSL,
    )
)
PROBE_CSV_PATH = _validate_probe_csv_path(PROBE_CSV_PATH)
normalized_probe_csv_path = _normalize_probe_csv_for_loader(PROBE_CSV_PATH)
probes = load_probe_set_csv(normalized_probe_csv_path)
print(f"Loaded {len(probes)} probes from: {normalized_probe_csv_path}")


class SparkQueryClient:
    def query(self, query: str, params: dict[str, str]):
        escaped_esn = params["esn"].replace("'", "''")
        return [row.asDict() for row in spark.sql(query.replace(":esn", f"'{escaped_esn}'")).collect()]


vector_client = VectorSearchClient(disable_notice=True)
search_provider = DatabricksVectorSearchProvider(
    vector_client,
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


class V2OnlyEligibilityProvider:
    """Wrap the real provider and fail if the legacy fallback would be used."""

    def __init__(self, inner):
        self._inner = inner

    def v2_document_ids(self, esn: str, recency_window_months: int):
        return self._inner.v2_document_ids(esn, recency_window_months)

    def legacy_document_ids(self, esn: str, recency_window_months: int):
        raise RuntimeError(
            f"Legacy fallback disabled for this eval: esn={esn} has no eligible v2 documents "
            "within the recency window. Add it to the v2 mapping/metadata tables or remove "
            "the probe."
        )


eligibility_provider = V2OnlyEligibilityProvider(eligibility_provider)


# COMMAND ----------

run_rows = []
for strategy in STRATEGIES:
    for k in TOP_K_VALUES:
        cfg = RetrieverConfig(
            v2_index_name=INDEX,
            legacy_index_name=LEGACY_INDEX,
            columns=[
                "chunk_id",
                "document_id",
                "pdf_name",
                "page_number",
                "chunk_text",
                RESULT_ESN_COLUMN,
                RESULT_EQUIP_TYPE_COLUMN,
                "outage_start_date",
                "metadata",
            ],
            top_k=k,
            overfetch_k=OVERFETCH_K,
            recency_window_months=RECENCY_WINDOW_MONTHS,
            query_type=QUERY_TYPE,
        )
        retriever = create_retriever(
            strategy=strategy,
            config=cfg,
            embedder=embedder,
            eligibility=eligibility_provider,
            search=search_provider,
        )

        result = run_eval_detailed(
            retriever=retriever,
            probe_set=probes,
            experiment_name=EXPERIMENT,
            run_name_prefix=f"{RUN_NAME_PREFIX}_{strategy}_k{k}",
            extra_tags={
                "eval_suite": "fsr_v2",
                "eval_stage": "phase_c_topk",
                "strategy": strategy,
                "top_k": str(k),
                "probe_set_version": PROBE_SET_VERSION,
            },
            probe_set_params={
                "probe_set_version": PROBE_SET_VERSION,
                "probe_csv_path": PROBE_CSV_PATH,
                "probe_csv_path_effective": normalized_probe_csv_path,
            },
        )

        row = {
            "strategy": strategy,
            "k": k,
            "run_id": result["run_id"],
            "probes_succeeded": result["probes_succeeded"],
            "probes_failed": result["probes_failed"],
            **result["aggregate"],
        }
        row.pop("retrieval_filter_match_rate_at_k", None)
        run_rows.append(row)
        print(f"Finished strategy={strategy} k={k} run_id={result['run_id']}")

# COMMAND ----------

display(spark.createDataFrame(run_rows))

by_k = defaultdict(dict)
for row in run_rows:
    by_k[row["k"]][row["strategy"]] = row

deltas = []
for k in sorted(by_k.keys()):
    if "ura_current" not in by_k[k] or "ura_with_shared_impl" not in by_k[k]:
        continue
    h = by_k[k]["ura_with_shared_impl"]
    v = by_k[k]["ura_current"]
    deltas.append(
        {
            "k": k,
            "shared_impl_run_id": h["run_id"],
            "current_run_id": v["run_id"],
            "delta_doc_recall": float(h.get("doc_recall_at_k", 0.0)) - float(v.get("doc_recall_at_k", 0.0)),
            "delta_doc_ids_not_same_flag": float(h.get("doc_ids_not_same_flag", 0.0)) - float(v.get("doc_ids_not_same_flag", 0.0)),
            "delta_cited_doc_page_hit_rate": float(h.get("cited_doc_page_hit_rate", 0.0)) - float(v.get("cited_doc_page_hit_rate", 0.0)),
            "delta_latency_ms": float(h.get("latency_ms", 0.0)) - float(v.get("latency_ms", 0.0)),
            "shared_impl_avg_latency_ms": float(h.get("latency_ms", 0.0)),
            "current_avg_latency_ms": float(v.get("latency_ms", 0.0)),
        }
    )

if deltas:
    print("URA shared implementation vs current URA delta summary")
    print(json.dumps(deltas, indent=2))
    display(spark.createDataFrame(deltas))
else:
    print("Delta summary skipped: both retriever strategies were not present for at least one k")