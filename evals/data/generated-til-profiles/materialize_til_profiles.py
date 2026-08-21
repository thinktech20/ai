"""Materialize TIL metadata rows into shareable JSON files.

The TIL metadata pipeline stores the extracted profile in Delta as
`parsed_profile_json` and the original LLM payload in `raw_profile_json`.
This utility exports those rows into a folder layout that is easy to share
with the DS team:

  <output_dir>/<til_id>/metadata_row.json
  <output_dir>/<til_id>/profile_response.json

The script is intended to run in a Databricks notebook or any environment
with Spark access to the TIL metadata table.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from contracts.table_specs.tils.til_tables import TIL_METADATA_TABLE


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


def export_til_profiles(
    spark: SparkSession,
    output_dir: str,
    table_name: str = TIL_METADATA_TABLE,
    only_completed: bool = True,
) -> dict[str, Any]:
    df = spark.table(table_name)
    if only_completed:
        df = df.filter((df.metadata_status == "completed") & df.parsed_profile_json.isNotNull())

    output_root = Path(output_dir)
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
        "output_dir": str(output_root),
        "only_completed": only_completed,
        "exported_count": len(exported),
        "exports": exported,
    }
    _write_json(output_root / "manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize TIL metadata rows into JSON files")
    parser.add_argument("--table", default=TIL_METADATA_TABLE, help="Source Delta table name")
    parser.add_argument("--output-dir", default="data/generated-til-profiles", help="Folder to write JSON files")
    parser.add_argument("--all-rows", action="store_true", help="Export every row instead of only completed profiles")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    manifest = export_til_profiles(
        spark=spark,
        output_dir=args.output_dir,
        table_name=args.table,
        only_completed=not args.all_rows,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()