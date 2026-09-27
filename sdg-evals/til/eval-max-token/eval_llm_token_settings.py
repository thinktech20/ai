# Databricks notebook source
# MAGIC %md
# MAGIC # TIL LLM Token Settings Eval
# MAGIC
# MAGIC Runs one MLflow experiment with multiple token-setting variants (for example low, medium, gateway_default)
# MAGIC against a selected TIL subset and DS/SME-reviewed gold profiles.
# MAGIC
# MAGIC This notebook is read-only for data sources:
# MAGIC - Reads from metadata table
# MAGIC - Reads gold profiles from workspace files
# MAGIC - Logs metrics to MLflow
# MAGIC - Does not create or update Delta tables

# COMMAND ----------

# MAGIC %pip install --quiet mlflow-skinny

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Inputs

# COMMAND ----------

import datetime as dt
import importlib.util
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mlflow


RUN_SPECS_TEMPLATE = (
    "t1024=run_id:<run_id_for_1024>;"
    "t2048=run_id:<run_id_for_2048>;"
    "t3072=run_id:<run_id_for_3072>;"
    "t4096=run_id:<run_id_for_4096>;"
    "gateway=run_id:<run_id_for_gateway_default>"
)


dbutils.widgets.text("METADATA_TABLE", "vaid.ai_sot_field_service_report.til_metadata")
dbutils.widgets.text("RUN_SPECS", RUN_SPECS_TEMPLATE)
dbutils.widgets.text("TILS", "1502-2R1,1937-R2,1945-R2,2284")
dbutils.widgets.text("GOLD_ROOT", "/Workspace/Users/madhurima.saxena@gevernova.com/sdg-evals/til/til-profile-gold-set")
dbutils.widgets.text("MLFLOW_EXPERIMENT", "/Shared/til-token-setting-eval")
dbutils.widgets.text("RUN_NAME_PREFIX", "til_token_eval")
dbutils.widgets.text("MLFLOW_TRACKING_URI", "databricks")

METADATA_TABLE = dbutils.widgets.get("METADATA_TABLE").strip()
RUN_SPECS = dbutils.widgets.get("RUN_SPECS").strip()
TILS_RAW = dbutils.widgets.get("TILS").strip()
GOLD_ROOT = dbutils.widgets.get("GOLD_ROOT").strip()
MLFLOW_EXPERIMENT = dbutils.widgets.get("MLFLOW_EXPERIMENT").strip()
RUN_NAME_PREFIX = dbutils.widgets.get("RUN_NAME_PREFIX").strip() or "til_token_eval"
MLFLOW_TRACKING_URI = dbutils.widgets.get("MLFLOW_TRACKING_URI").strip() or "databricks"

if not METADATA_TABLE:
    raise ValueError("METADATA_TABLE is required")
if not RUN_SPECS:
    RUN_SPECS = "latest=where:1=1"
    print(
        "RUN_SPECS not provided. Using default: latest=where:1=1\n"
        "Recommended RUN_SPECS format: "
        "t1024=run_id:<id>;t2048=run_id:<id>;t3072=run_id:<id>;t4096=run_id:<id>;gateway=run_id:<id>"
    )
if not TILS_RAW:
    raise ValueError("TILS is required")

print(f"METADATA_TABLE={METADATA_TABLE}")
print(f"MLFLOW_EXPERIMENT={MLFLOW_EXPERIMENT}")
print(f"GOLD_ROOT={GOLD_ROOT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Helpers

# COMMAND ----------

def normalize_til_id(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().upper()
    s = re.sub(r"^TIL\s+", "", s)
    return re.sub(r"\s+", "", s)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def parse_json_maybe(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def normalize_recommendations(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    normalized: set[str] = set()
    for item in value:
        if isinstance(item, dict):
            normalized.add(normalize_text(json.dumps(item, sort_keys=True)))
        else:
            normalized.add(normalize_text(item))
    return {v for v in normalized if v}


def classify_failure(status: str, error_message: str) -> str:
    s = (status or "").strip().lower()
    e = (error_message or "").strip().lower()

    if s == "completed":
        return "none"
    if s == "llm_content_filtered" or "content_filter" in e:
        return "content_filter"
    if s == "llm_parse_failed" and "unterminated" in e:
        return "truncated_json"
    if s == "llm_parse_failed":
        return "parse_failed_other"
    if "timeout" in e or "read timed out" in e:
        return "timeout"
    return "other"


def quality_checks(profile: dict[str, Any] | None) -> tuple[int, dict[str, bool]]:
    checks = {
        "has_til_number": False,
        "has_title": False,
        "has_recommendations": False,
    }
    if not isinstance(profile, dict):
        return 0, checks

    til_number = str(profile.get("til_number") or "").strip()
    title = str(profile.get("title") or "").strip()
    recos = profile.get("service_recommendation_line_items")

    checks["has_til_number"] = bool(til_number)
    checks["has_title"] = bool(title)
    checks["has_recommendations"] = isinstance(recos, list) and len(recos) > 0

    return sum(1 for ok in checks.values() if ok), checks


def quality_checks_against_gold(
    predicted: dict[str, Any] | None,
    gold: dict[str, Any] | None,
) -> tuple[int, dict[str, bool], str]:
    if not isinstance(gold, dict):
        score, checks = quality_checks(predicted)
        return score, checks, "fallback_presence"

    checks = {
        "has_til_number": False,
        "has_title": False,
        "has_recommendations": False,
    }

    if not isinstance(predicted, dict):
        return 0, checks, "gold_compare"

    pred_til = normalize_til_id(predicted.get("til_number"))
    gold_til = normalize_til_id(gold.get("til_number"))
    checks["has_til_number"] = bool(pred_til) and bool(gold_til) and pred_til == gold_til

    pred_title = normalize_text(predicted.get("title"))
    gold_title = normalize_text(gold.get("title"))
    checks["has_title"] = bool(pred_title) and bool(gold_title) and pred_title == gold_title

    pred_recos = normalize_recommendations(predicted.get("service_recommendation_line_items"))
    gold_recos = normalize_recommendations(gold.get("service_recommendation_line_items"))
    checks["has_recommendations"] = bool(pred_recos) and bool(gold_recos)

    return sum(1 for ok in checks.values() if ok), checks, "gold_compare"


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parse_run_specs(specs_text: str) -> list[tuple[str, str]]:
    """
    Parse RUN_SPECS in format:
      low=run_id:abc123;medium=run_id:def456;gateway=where:run_id LIKE 'til_p1_%'
    """
    out: list[tuple[str, str]] = []
    for item in [x.strip() for x in specs_text.split(";") if x.strip()]:
        if "=" not in item:
            raise ValueError(
                f"Invalid run spec: {item}. Expected label=run_id:<id> or label=where:<sql_expr>"
            )
        label, selector_raw = item.split("=", 1)
        label = label.strip()
        selector_raw = selector_raw.strip()
        if not label:
            raise ValueError(f"Invalid run label in: {item}")
        if selector_raw.startswith("where:"):
            selector_sql = selector_raw[len("where:") :].strip()
            if not selector_sql:
                raise ValueError(f"Invalid where selector in: {item}")
        elif selector_raw.startswith("run_id:"):
            run_id = selector_raw[len("run_id:") :].strip()
            if not run_id:
                raise ValueError(f"Invalid run_id selector in: {item}")
            selector_sql = f"run_id = {_sql_quote(run_id)}"
        else:
            # shorthand: treat raw selector as run_id
            selector_sql = f"run_id = {_sql_quote(selector_raw)}"
        out.append((label, selector_sql))
    if not out:
        raise ValueError("No valid run specs parsed from RUN_SPECS")
    return out


def load_gold_loader(gold_root: str):
    loader_file = Path(gold_root) / "gold_loader.py"
    if not loader_file.exists():
        raise FileNotFoundError(f"gold_loader.py not found under GOLD_ROOT: {loader_file}")

    spec = importlib.util.spec_from_file_location("til_gold_loader", str(loader_file))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load import spec from: {loader_file}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "load_gold_profiles"):
        raise AttributeError("gold_loader.py must expose function load_gold_profiles(gold_root, tils)")
    return module.load_gold_profiles


@dataclass
class RunResult:
    run_label: str
    til: str
    status: str
    failure_type: str
    quality_score: int
    has_til_number: bool
    has_title: bool
    has_recommendations: bool
    llm_model: str
    run_id: str
    timestamp: str
    error_message: str
    quality_mode: str


def best_timestamp(row: dict[str, str]) -> str:
    return (
        row.get("metadata_processed_ts")
        or row.get("ingest_ts")
        or row.get("chunk_processed_ts")
        or ""
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load Gold Profiles and Run Specs

# COMMAND ----------

tils = [normalize_til_id(x) for x in TILS_RAW.split(",") if normalize_til_id(x)]
run_specs = parse_run_specs(RUN_SPECS)

load_gold_profiles = load_gold_loader(GOLD_ROOT)
gold_profiles = load_gold_profiles(Path(GOLD_ROOT), tils)

print(f"Target TIL count: {len(tils)}")
print(f"Gold profiles loaded: {len(gold_profiles)}")
print(f"Run variants: {[label for label, _ in run_specs]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Evaluate Per Run Variant (table-based, no temp CSV)

# COMMAND ----------

def load_latest_rows_for_run(metadata_table: str, run_selector_sql: str, target_tils: list[str]) -> dict[str, dict[str, str]]:
    wanted = set(target_tils)
    latest: dict[str, dict[str, str]] = {}

    query = f"""
        SELECT
            requested_til_number,
            matched_til_number,
            metadata_status,
            error_message,
            parsed_profile_json,
            llm_model,
            run_id,
            metadata_processed_ts,
            ingest_ts,
            chunk_processed_ts
        FROM {metadata_table}
        WHERE {run_selector_sql}
    """

    for row_obj in spark.sql(query).collect():
        row = {k: ("" if v is None else str(v)) for k, v in row_obj.asDict().items()}
        til = normalize_til_id(row.get("requested_til_number") or row.get("matched_til_number"))
        if not til or til not in wanted:
            continue

        prev = latest.get(til)
        if prev is None or best_timestamp(row) >= best_timestamp(prev):
            latest[til] = row

    return latest


def evaluate_run(run_label: str, run_selector_sql: str, target_tils: list[str]) -> list[RunResult]:
    rows = load_latest_rows_for_run(METADATA_TABLE, run_selector_sql, target_tils)
    results: list[RunResult] = []

    for til in target_tils:
        row = rows.get(til)
        if row is None:
            results.append(
                RunResult(
                    run_label=run_label,
                    til=til,
                    status="missing",
                    failure_type="missing",
                    quality_score=0,
                    has_til_number=False,
                    has_title=False,
                    has_recommendations=False,
                    llm_model="",
                    run_id="",
                    timestamp="",
                    error_message="No row found for requested TIL in selected run",
                    quality_mode="missing",
                )
            )
            continue

        status = (row.get("metadata_status") or "").strip()
        error_message = (row.get("error_message") or "").strip()
        profile = parse_json_maybe(row.get("parsed_profile_json"))
        gold = gold_profiles.get(til)
        score, checks, quality_mode = quality_checks_against_gold(profile, gold)

        results.append(
            RunResult(
                run_label=run_label,
                til=til,
                status=status,
                failure_type=classify_failure(status, error_message),
                quality_score=score,
                has_til_number=checks["has_til_number"],
                has_title=checks["has_title"],
                has_recommendations=checks["has_recommendations"],
                llm_model=(row.get("llm_model") or "").strip(),
                run_id=(row.get("run_id") or "").strip(),
                timestamp=best_timestamp(row),
                error_message=error_message,
                quality_mode=quality_mode,
            )
        )

    return results


def run_summary(run_label: str, rows: list[RunResult]) -> dict[str, Any]:
    total = len(rows)
    completed = sum(1 for r in rows if r.status == "completed")
    content_filtered = sum(1 for r in rows if r.failure_type == "content_filter")
    parse_failed = sum(1 for r in rows if r.failure_type in {"truncated_json", "parse_failed_other"})
    missing = sum(1 for r in rows if r.failure_type == "missing")
    quality_pass = sum(1 for r in rows if r.quality_score == 3)
    gold_compared = sum(1 for r in rows if r.quality_mode == "gold_compare")
    avg_quality = round(sum(r.quality_score for r in rows) / total, 3) if total else 0.0

    return {
        "run_label": run_label,
        "total_tils": total,
        "completed": completed,
        "completed_rate": round(completed / total, 3) if total else 0.0,
        "content_filtered": content_filtered,
        "parse_failed": parse_failed,
        "missing": missing,
        "quality_pass": quality_pass,
        "quality_pass_rate": round(quality_pass / total, 3) if total else 0.0,
        "gold_compared": gold_compared,
        "gold_coverage_rate": round(gold_compared / total, 3) if total else 0.0,
        "avg_quality_score": avg_quality,
    }


def choose_recommendation(summaries: list[dict[str, Any]]) -> str:
    if not summaries:
        return ""

    ranked = sorted(
        summaries,
        key=lambda s: (
            s["completed_rate"],
            s["quality_pass_rate"],
            -s["parse_failed"],
            -s["content_filtered"],
            s["avg_quality_score"],
        ),
        reverse=True,
    )
    return ranked[0]["run_label"]


detail_rows: list[RunResult] = []
summary_rows: list[dict[str, Any]] = []

for label, selector_sql in run_specs:
    per_run = evaluate_run(label, selector_sql, tils)
    detail_rows.extend(per_run)
    summary_rows.append(run_summary(label, per_run))

recommendation = choose_recommendation(summary_rows)
print(f"Recommended run: {recommendation or 'none'}")

summary_df = spark.createDataFrame(summary_rows)
detail_df = spark.createDataFrame([r.__dict__ for r in detail_rows])

print("Summary:")
display(summary_df)
print("Detail rows:")
display(detail_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log to MLflow

# COMMAND ----------

def _metric_safe_label(label: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", (label or "").strip().lower())
    return cleaned.strip("_") or "run"

if MLFLOW_TRACKING_URI:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
if MLFLOW_EXPERIMENT:
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

run_name = f"{RUN_NAME_PREFIX}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"

with mlflow.start_run(run_name=run_name) as run:
    mlflow.log_param("metadata_table", METADATA_TABLE)
    mlflow.log_param("recommendation", recommendation or "none")
    mlflow.log_param("target_tils", ",".join(tils))
    mlflow.log_param("run_labels", ",".join(label for label, _ in run_specs))
    mlflow.log_param("run_count", len(run_specs))
    mlflow.log_param("gold_root", GOLD_ROOT)

    for label, selector_sql in run_specs:
        key = _metric_safe_label(label)
        mlflow.log_param(f"run_selector_{key}", selector_sql)

    for summary in summary_rows:
        key = _metric_safe_label(str(summary.get("run_label") or "run"))
        mlflow.log_metric(f"{key}_completed_rate", float(summary.get("completed_rate") or 0.0))
        mlflow.log_metric(f"{key}_quality_pass_rate", float(summary.get("quality_pass_rate") or 0.0))
        mlflow.log_metric(f"{key}_avg_quality_score", float(summary.get("avg_quality_score") or 0.0))
        mlflow.log_metric(f"{key}_parse_failed", float(summary.get("parse_failed") or 0.0))
        mlflow.log_metric(f"{key}_content_filtered", float(summary.get("content_filtered") or 0.0))
        mlflow.log_metric(f"{key}_missing", float(summary.get("missing") or 0.0))
        mlflow.log_metric(f"{key}_gold_coverage_rate", float(summary.get("gold_coverage_rate") or 0.0))

    total_details = len(detail_rows)
    completed = sum(1 for d in detail_rows if d.status == "completed")
    parse_failed = sum(1 for d in detail_rows if d.failure_type in {"truncated_json", "parse_failed_other"})
    content_filtered = sum(1 for d in detail_rows if d.failure_type == "content_filter")
    if total_details > 0:
        mlflow.log_metric("overall_completed_rate", completed / total_details)
        mlflow.log_metric("overall_parse_failed_rate", parse_failed / total_details)
        mlflow.log_metric("overall_content_filtered_rate", content_filtered / total_details)

    # Persist downloadable run artifacts (for sharing outside the notebook UI).
    with tempfile.TemporaryDirectory(prefix="til_token_eval_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        summary_csv = tmp_root / "summary.csv"
        detail_csv = tmp_root / "detail.csv"
        config_json = tmp_root / "run_config.json"

        summary_df.toPandas().to_csv(summary_csv, index=False)
        detail_df.toPandas().to_csv(detail_csv, index=False)
        config_json.write_text(
            json.dumps(
                {
                    "metadata_table": METADATA_TABLE,
                    "run_specs": RUN_SPECS,
                    "target_tils": tils,
                    "gold_root": GOLD_ROOT,
                    "recommendation": recommendation or "none",
                    "run_labels": [label for label, _ in run_specs],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        mlflow.log_artifact(str(summary_csv), artifact_path="reports")
        mlflow.log_artifact(str(detail_csv), artifact_path="reports")
        mlflow.log_artifact(str(config_json), artifact_path="reports")

    run_id = run.info.run_id

print(f"MLflow run id: {run_id}")
