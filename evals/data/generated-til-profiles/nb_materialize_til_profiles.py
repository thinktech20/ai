# Databricks notebook source
"""Databricks notebook entry point for exporting TIL metadata rows to JSON."""

# COMMAND ----------

import json
import re
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession
from pyspark.sql.functions import coalesce, col, upper


def _safe_name(value: object) -> str:
    text = str(value or "unknown").strip()
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    return text.strip("_") or "unknown"


def _parse_json_value(value: object) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


# COMMAND ----------

try:
    TIL_METADATA_TABLE
except NameError:
    TIL_METADATA_TABLE = "vaid.ai_sot_field_service_report.til_metadata"



try:
    ONLY_COMPLETED
except NameError:
    ONLY_COMPLETED = True


dbutils.widgets.text("table", TIL_METADATA_TABLE, "Source table")
dbutils.widgets.text(
    "output_dir",
    "/Workspace/Users/madhurima.saxena@gevernova.com/sdg-evals-git/til/generated-til-profiles/til_p1_20260704_235852_30f3ba3a",
    "Output dir",
)
dbutils.widgets.dropdown("only_completed", "true", ["true", "false"], "Only completed")
dbutils.widgets.text("run_id", "til_p1_20260704_235852_30f3ba3a", "Filter run_id (optional)")
dbutils.widgets.text("tils", "1502-2R1,1509-R4,1562-R1,1584-R1,1603-R2,1615-R1,1638-R3,1769,1850-R3,1870-R2,1907-R1,1937-R2,1945-R2,1972-R2,2045-R2,2069,2167-R1,2212-R3,2284,2297,2322-R2,2342-R1,2467,2511,2558", "Filter TILs (optional, comma-separated)")

table_name = dbutils.widgets.get("table")
output_dir = dbutils.widgets.get("output_dir")
only_completed = dbutils.widgets.get("only_completed").lower() == "true"
run_id_filter = dbutils.widgets.get("run_id").strip()
tils_raw = dbutils.widgets.get("tils").strip()
til_filters = [t.strip().upper() for t in tils_raw.split(",") if t.strip()]

spark = SparkSession.getActiveSession() or spark
df = spark.table(table_name)
if only_completed:
    df = df.filter((df.metadata_status == "completed") & df.parsed_profile_json.isNotNull())
if run_id_filter:
    df = df.filter(df.run_id == run_id_filter)
if til_filters:
    df = df.filter(
        upper(coalesce(col("matched_til_number"), col("requested_til_number"))).isin(til_filters)
    )

if output_dir.startswith("dbfs:/"):
    local_output_dir = "/dbfs/" + output_dir[len("dbfs:/"):].lstrip("/")
else:
    local_output_dir = output_dir

output_root = Path(local_output_dir)
output_root.mkdir(parents=True, exist_ok=True)

exported = []
for row in df.toLocalIterator():
    record = row.asDict(recursive=True)
    til_id = (
        record.get("matched_til_number")
        or record.get("requested_til_number")
        or record.get("document_id")
        or "unknown"
    )
    til_dir = output_root / _safe_name(til_id)
    til_dir.mkdir(parents=True, exist_ok=True)

    parsed_profile = _parse_json_value(record.get("parsed_profile_json"))
    raw_profile = _parse_json_value(record.get("raw_profile_json"))

    metadata_payload = dict(record)
    metadata_payload["parsed_profile_json"] = parsed_profile
    metadata_payload["raw_profile_json"] = raw_profile

    _write_json(til_dir / "metadata_row.json", metadata_payload)
    if parsed_profile is not None:
        _write_json(til_dir / "profile_response.json", parsed_profile)

    exported.append(
        {
            "til_id": til_id,
            "folder": str(til_dir),
            "metadata_file": str(til_dir / "metadata_row.json"),
            "profile_file": str(til_dir / "profile_response.json") if parsed_profile is not None else None,
        }
    )

manifest = {
    "table_name": table_name,
    "output_dir": output_dir,
    "only_completed": only_completed,
    "run_id_filter": run_id_filter or None,
    "tils_filter": til_filters,
    "exported_count": len(exported),
    "exports": exported,
}

_write_json(output_root / "manifest.json", manifest)
print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))

# COMMAND ----------

from pathlib import Path

root = Path("/Workspace/Users/madhurima.saxena@gevernova.com/sdg-evals-git/til/generated-til-profiles/til_p1_20260704_235852_30f3ba3a")
print("exists:", root.exists(), "is_dir:", root.is_dir())

profiles = list(root.rglob("profile_response.json"))
print("profile_response.json count:", len(profiles))
print("sample:")
for p in profiles[:5]:
    print(" ", p)