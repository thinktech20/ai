# Databricks notebook source
# MAGIC %md
# MAGIC # TIL Profile Quality Eval
# MAGIC
# MAGIC Measures field-level data quality of extracted TIL profiles against DS/SME gold profiles.
# MAGIC
# MAGIC This notebook is read-only for data sources:
# MAGIC - Reads extracted profiles from the metadata table
# MAGIC - Reads DS gold profiles from workspace files
# MAGIC - Logs per-field accuracy metrics to MLflow
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
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mlflow


dbutils.widgets.text("METADATA_TABLE", "vaid.ai_sot_field_service_report.til_metadata")
dbutils.widgets.text("RUN_SPEC", "run_id:til_p1_20260704_235852_30f3ba3a")
dbutils.widgets.text("TILS", "1502-2R1,1509-R4,1562-R1,1584-R1,1603-R2,1615-R1,1638-R3,1769,1850-R3,1870-R2,1907-R1,1937-R2,1945-R2,1972-R2,2045-R2,2069,2167-R1,2212-R3,2284,2297,2322-R2,2342-R1,2467,2511,2558")
dbutils.widgets.text("DS_GOLD_ROOT", "/Workspace/Users/madhurima.saxena@gevernova.com/sdg-evals-git/til/til-profile-gold-set/data")
dbutils.widgets.text("MLFLOW_EXPERIMENT", "/Shared/til-profile-quality-eval")
dbutils.widgets.text("RUN_NAME_PREFIX", "til_quality_eval")
dbutils.widgets.text("MLFLOW_TRACKING_URI", "databricks")

METADATA_TABLE = dbutils.widgets.get("METADATA_TABLE").strip()
RUN_SPEC = dbutils.widgets.get("RUN_SPEC").strip()
TILS_RAW = dbutils.widgets.get("TILS").strip()
DS_GOLD_ROOT = dbutils.widgets.get("DS_GOLD_ROOT").strip()
MLFLOW_EXPERIMENT = dbutils.widgets.get("MLFLOW_EXPERIMENT").strip()
RUN_NAME_PREFIX = dbutils.widgets.get("RUN_NAME_PREFIX").strip() or "til_quality_eval"
MLFLOW_TRACKING_URI = dbutils.widgets.get("MLFLOW_TRACKING_URI").strip() or "databricks"

if not METADATA_TABLE:
    raise ValueError("METADATA_TABLE is required")
if not RUN_SPEC or "<pipeline_run_id>" in RUN_SPEC:
    raise ValueError("RUN_SPEC is required. Set it to run_id:<your_til_p1_run_id> or where:<sql_expr>")
if not TILS_RAW:
    raise ValueError("TILS is required")

print(f"METADATA_TABLE={METADATA_TABLE}")
print(f"RUN_SPEC={RUN_SPEC}")
print(f"MLFLOW_EXPERIMENT={MLFLOW_EXPERIMENT}")
print(f"DS_GOLD_ROOT={DS_GOLD_ROOT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Field Definitions

# COMMAND ----------

# All fields from DS gold profiles — used for full-coverage comparison.
ALL_FIELDS = [
    "til_number",
    "revision",
    "title",
    "publish_date",
    "reason_for_revision",
    "purpose",
    "compliance_category_code",
    "compliance_category_text",
    "recurring_indicator_if_found",
    "coarse_outage_type",
    "scope_of_work",
    "service_recommendation_line_items",
    "completion_criteria_text",
    "maintenance_trigger_text",
    "recommended_interval_or_trigger",
    "usage_counters_to_check_or_consider",
    "usage_counter_requirements_text",
    "frame_or_model_applicability_text",
    "combustion_or_fuel_configuration_text",
    "hardware_or_part_configuration_text",
    "serial_or_unit_applicability_text",
    "exclusions_or_non_applicable_conditions_text",
    "required_prior_modifications_text",
    "prerequisite_outage_or_inspection_context_text",
    "sbom_dependency_flag",
    "sbom_trigger_reason",
    "mli_numbers",
    "parts_referenced",
    "reference_documents",
    "configuration_dependent",
    "configuration_variables",
    "configuration_summary",
    "severity_signals",
    "failure_consequences",
    "risk_summary",
    "safety_or_damage_language_found",
    "tables_found_summary",
    "missing_information_flags",
    "source_snippets",
    "extraction_confidence",
]

# Identity fields: must match for the row to be a valid comparison.
IDENTITY_FIELDS = ["til_number", "revision", "title"]

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


def normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in {"", "n/a", "na", "none", "null"}:
        return ""
    return " ".join(s.split()).lower()


def normalize_for_compare(value: Any) -> str:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict):
                items.append(normalize_scalar(json.dumps(item, sort_keys=True)))
            else:
                items.append(normalize_scalar(item))
        return "\n".join(sorted(v for v in items if v))
    if isinstance(value, dict):
        return normalize_scalar(json.dumps(value, sort_keys=True))
    return normalize_scalar(value)


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
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def parse_run_spec(spec: str) -> str:
    """Convert run_id:<id> or where:<expr> to a SQL WHERE clause."""
    spec = spec.strip()
    if spec.startswith("where:"):
        return spec[len("where:"):].strip()
    if spec.startswith("run_id:"):
        run_id = spec[len("run_id:"):].strip()
        return f"run_id = '{run_id.replace(chr(39), chr(39)*2)}'"
    # Shorthand: treat as plain run_id value
    return f"run_id = '{spec.replace(chr(39), chr(39)*2)}'"


def load_ds_gold(ds_gold_root: str, tils: list[str]) -> dict[str, dict[str, Any]]:
    """Load DS gold profiles from workspace path.

    Supports both:
    - sdg-evals gold-set layout: <root>/data/<til>/profile_response.json
    - DS pilot exports:          <root>/<til>/profile_response.json
      (and nested run folders that contain those <til>/ directories)

    Supports both JSON shapes:
    - {"parsed_profile": {...}}
    - {...}  # profile object directly
    """
    root = Path(ds_gold_root)
    out: dict[str, dict[str, Any]] = {}

    print(f"  [gold] root={root}")
    print(f"  [gold] root_exists={root.exists()} root_is_dir={root.is_dir()}")

    # Index all profile_response.json files once so we can support nested run folders.
    indexed_by_til: dict[str, Path] = {}
    try:
        for candidate in root.rglob("profile_response.json"):
            til_key = normalize_til_id(candidate.parent.name)
            if til_key and til_key not in indexed_by_til:
                indexed_by_til[til_key] = candidate
    except Exception as exc:
        print(f"  [gold] warning: recursive scan failed under {root}: {exc}")

    print(f"  [gold] discovered_profile_files={len(indexed_by_til)}")
    if len(indexed_by_til) == 0:
        print("  [gold] hint: path is visible but no profile_response.json found from this runtime")
        print("  [gold] hint: for repo files, use /Workspace/Repos/.../sdg-evals/til/til-profile-gold-set")
        print("  [gold] hint: for workspace files, use /Workspace/Users/.../til-profile-gold-set")

    for til in tils:
        direct_candidates = [
            root / "data" / til / "profile_response.json",
            root / til / "profile_response.json",
        ]

        candidate = None
        for path in direct_candidates:
            if path.exists():
                candidate = path
                break

        if candidate is None:
            candidate = indexed_by_til.get(normalize_til_id(til))

        if candidate is None or not candidate.exists():
            print(f"  [gold] not found for {til} under: {root}")
            continue

        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            parsed = None
            if isinstance(payload, dict):
                nested = payload.get("parsed_profile")
                parsed = nested if isinstance(nested, dict) else payload
            if isinstance(parsed, dict):
                out[til] = parsed
            else:
                print(f"  [gold] invalid payload shape for {til}: {candidate}")
        except Exception as exc:
            print(f"  [gold] load error for {til}: {exc}")

    return out


# match_type values:
#   exact_match       - normalized values are identical
#   both_empty        - both DS and pipeline are empty
#   coverage_gap      - DS has value, pipeline is empty (FLAG: we are missing content)
#   pred_only         - pipeline has value, DS is empty (not a flag; we may extract more)
#   content_differs   - both have content but normalized values differ
@dataclass
class FieldResult:
    til: str
    field: str
    match: bool
    match_type: str
    ds_value: Any
    pred_value: Any


@dataclass
class TILResult:
    til: str
    status: str
    run_id: str
    identity_pass: bool
    fields_matched: int
    fields_total: int
    match_rate: float
    field_results: list[FieldResult] = field(default_factory=list)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load Data

# COMMAND ----------

tils = [normalize_til_id(t) for t in TILS_RAW.split(",") if normalize_til_id(t)]
selector_sql = parse_run_spec(RUN_SPEC)

print(f"Target TILs: {tils}")
print(f"Run selector: {selector_sql}")

# Load DS gold profiles
ds_gold = load_ds_gold(DS_GOLD_ROOT, tils)
print(f"\nDS gold profiles loaded: {list(ds_gold.keys())}")

# Load pipeline output from metadata table
query = f"""
    SELECT
        requested_til_number,
        matched_til_number,
        metadata_status,
        parsed_profile_json,
        run_id,
        metadata_processed_ts
    FROM {METADATA_TABLE}
    WHERE {selector_sql}
"""

raw_rows = spark.sql(query).collect()
pipeline_profiles: dict[str, dict[str, Any]] = {}
pipeline_run_ids: dict[str, str] = {}
pipeline_statuses: dict[str, str] = {}

for row_obj in raw_rows:
    row = {k: ("" if v is None else str(v)) for k, v in row_obj.asDict().items()}
    til = normalize_til_id(row.get("requested_til_number") or row.get("matched_til_number"))
    if not til or til not in set(tils):
        continue
    profile = parse_json_maybe(row.get("parsed_profile_json"))
    if profile:
        pipeline_profiles[til] = profile
        pipeline_run_ids[til] = row.get("run_id", "")
        pipeline_statuses[til] = row.get("metadata_status", "")

print(f"Pipeline profiles loaded: {list(pipeline_profiles.keys())}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Field-Level Comparison

# COMMAND ----------

til_results: list[TILResult] = []

for til in tils:
    gold = ds_gold.get(til)
    pred = pipeline_profiles.get(til)
    run_id = pipeline_run_ids.get(til, "")
    status = pipeline_statuses.get(til, "missing")

    if gold is None:
        print(f"  [{til}] no gold profile — skipping")
        continue

    if pred is None:
        til_results.append(TILResult(
            til=til,
            status=status or "missing",
            run_id=run_id,
            identity_pass=False,
            fields_matched=0,
            fields_total=len(ALL_FIELDS),
            match_rate=0.0,
        ))
        continue

    field_results: list[FieldResult] = []
    identity_pass = True

    for f_name in ALL_FIELDS:
        # til_number: normalize both sides with normalize_til_id to strip
        # "TIL " prefix so "TIL 2284" and "2284" compare as equal.
        if f_name == "til_number":
            gold_val = normalize_til_id(gold.get(f_name))
            pred_val = normalize_til_id(pred.get(f_name))
        else:
            gold_val = normalize_for_compare(gold.get(f_name))
            pred_val = normalize_for_compare(pred.get(f_name))
        match = gold_val == pred_val
        if not match and f_name in IDENTITY_FIELDS:
            identity_pass = False

        if match:
            match_type = "exact_match" if gold_val else "both_empty"
        elif not gold_val and pred_val:
            match_type = "pred_only"
        elif gold_val and not pred_val:
            match_type = "coverage_gap"
        else:
            match_type = "content_differs"

        field_results.append(FieldResult(
            til=til,
            field=f_name,
            match=match,
            match_type=match_type,
            ds_value=gold.get(f_name),
            pred_value=pred.get(f_name),
        ))

    matched = sum(1 for fr in field_results if fr.match)
    til_results.append(TILResult(
        til=til,
        status=status,
        run_id=run_id,
        identity_pass=identity_pass,
        fields_matched=matched,
        fields_total=len(ALL_FIELDS),
        match_rate=round(matched / len(ALL_FIELDS), 3),
        field_results=field_results,
    ))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Display Results

# COMMAND ----------

# Per-TIL summary
summary_rows = [
    {
        "til": r.til,
        "status": r.status,
        "identity_pass": r.identity_pass,
        "fields_matched": r.fields_matched,
        "fields_total": r.fields_total,
        "match_rate": r.match_rate,
        "run_id": r.run_id,
    }
    for r in til_results
]
summary_df = spark.createDataFrame(summary_rows)
print("=== Per-TIL Summary ===")
display(summary_df)

# Per-field pass rate across all TILs
field_counts: dict[str, int] = {f: 0 for f in ALL_FIELDS}
field_totals: dict[str, int] = {f: 0 for f in ALL_FIELDS}
for r in til_results:
    for fr in r.field_results:
        field_totals[fr.field] = field_totals.get(fr.field, 0) + 1
        if fr.match:
            field_counts[fr.field] = field_counts.get(fr.field, 0) + 1

# Per-field coverage gap counts (DS has value, pipeline is empty)
field_coverage_gaps: dict[str, int] = {f: 0 for f in ALL_FIELDS}
for r in til_results:
    for fr in r.field_results:
        if fr.match_type == "coverage_gap":
            field_coverage_gaps[fr.field] = field_coverage_gaps.get(fr.field, 0) + 1

field_rows = [
    {
        "field": f,
        "match_count": field_counts.get(f, 0),
        "total": field_totals.get(f, 0),
        "pass_rate": round(field_counts.get(f, 0) / field_totals[f], 3) if field_totals.get(f, 0) > 0 else 0.0,
        "coverage_gaps": field_coverage_gaps.get(f, 0),
        "is_identity_field": f in IDENTITY_FIELDS,
    }
    for f in ALL_FIELDS
    if field_totals.get(f, 0) > 0
]
field_df = spark.createDataFrame(field_rows)
print("=== Per-Field Pass Rate ===")
display(field_df.orderBy("pass_rate"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log to MLflow

# COMMAND ----------

def _metric_key(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_") or "field"


if MLFLOW_TRACKING_URI:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
if MLFLOW_EXPERIMENT:
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

run_name = f"{RUN_NAME_PREFIX}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"

with mlflow.start_run(run_name=run_name) as run:
    mlflow.log_param("metadata_table", METADATA_TABLE)
    mlflow.log_param("run_spec", RUN_SPEC)
    mlflow.log_param("target_tils", ",".join(tils))
    mlflow.log_param("ds_gold_root", DS_GOLD_ROOT)
    mlflow.log_param("fields_evaluated", len(ALL_FIELDS))

    # Overall metrics
    total = len(til_results)
    if total > 0:
        mlflow.log_metric("tils_evaluated", total)
        mlflow.log_metric("identity_pass_rate", sum(1 for r in til_results if r.identity_pass) / total)
        mlflow.log_metric("avg_field_match_rate", sum(r.match_rate for r in til_results) / total)
        mlflow.log_metric("tils_completed", sum(1 for r in til_results if r.status == "completed"))

    # Per-field pass rates and coverage gaps
    for row in field_rows:
        mlflow.log_metric(f"field_{_metric_key(row['field'])}_pass_rate", row["pass_rate"])
        if row["coverage_gaps"] > 0:
            mlflow.log_metric(f"field_{_metric_key(row['field'])}_coverage_gaps", float(row["coverage_gaps"]))

    total_coverage_gaps = sum(r["coverage_gaps"] for r in field_rows)
    mlflow.log_metric("total_coverage_gaps", float(total_coverage_gaps))

    # Per-TIL match rates
    for r in til_results:
        mlflow.log_metric(f"til_{_metric_key(r.til)}_match_rate", r.match_rate)

    # Artifacts
    with tempfile.TemporaryDirectory(prefix="til_quality_eval_") as tmp_dir:
        tmp = Path(tmp_dir)
        import pandas as pd
        pd.DataFrame(summary_rows).to_csv(tmp / "summary.csv", index=False)
        pd.DataFrame(field_rows).to_csv(tmp / "field_pass_rates.csv", index=False)

        # Mismatch details
        mismatch_rows = [
            {
                "til": fr.til,
                "field": fr.field,
                "match_type": fr.match_type,
                "ds_value": str(fr.ds_value) if fr.ds_value is not None else "",
                "pred_value": str(fr.pred_value) if fr.pred_value is not None else "",
            }
            for r in til_results
            for fr in r.field_results
            if not fr.match
        ]
        pd.DataFrame(mismatch_rows).to_csv(tmp / "mismatches.csv", index=False)

        mlflow.log_artifact(str(tmp / "summary.csv"), artifact_path="reports")
        mlflow.log_artifact(str(tmp / "field_pass_rates.csv"), artifact_path="reports")
        mlflow.log_artifact(str(tmp / "mismatches.csv"), artifact_path="reports")

    run_id = run.info.run_id

print(f"MLflow run id: {run_id}")

# COMMAND ----------

from pathlib import Path
root = Path("/Workspace/Users/madhurima.saxena@gevernova.com/sdg-evals-git/til/til-profile-gold-set/data")
files = list(root.rglob("profile_response.json"))
print("exists:", root.exists(), "count:", len(files))
print("sample:", [str(p) for p in files[:5]])
