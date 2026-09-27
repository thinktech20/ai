"""FSR v2 mapping eval runner (starter).

Phase D starter utility:
- Loads a gold-set CSV.
- Validates required columns and basic row constraints.
- Prints a compact summary so data quality issues are caught early.

No Databricks queries or model outputs are used in this starter.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

REQUIRED_COLUMNS = [
    "record_id",
    "document_id",
    "pdf_name",
    "region_start_char",
    "region_end_char",
    "true_primary_esn",
    "true_primary_equip_type",
    "true_active_esns",
    "label_status",
    "notes",
]

OPTIONAL_PREDICTION_COLUMNS = [
    "predicted_primary_esn",
    "predicted_primary_equip_type",
]

PREDICTIONS_REQUIRED_COLUMNS = [
    "record_id",
    "predicted_primary_esn",
    "predicted_primary_equip_type",
]


def _normalize_text(value: str) -> str:
    return (value or "").strip()


def _normalize_esn(value: str) -> str:
    return _normalize_text(value).upper()


def _parse_optional_int(value: str, field_name: str, row_idx: int) -> int | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"row {row_idx}: {field_name} must be integer or empty (got '{text}')") from exc


def _split_pipe(value: str) -> list[str]:
    text = _normalize_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def load_gold_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV header is missing")

        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        rows = [dict(r) for r in reader]

    if not rows:
        raise ValueError("CSV has no data rows")

    return rows


def load_prediction_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Predictions CSV header is missing")

        missing = [c for c in PREDICTIONS_REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Missing required prediction columns: {missing}")

        rows = [dict(r) for r in reader]

    if not rows:
        raise ValueError("Predictions CSV has no data rows")

    return rows


def merge_prediction_rows(
    gold_rows: list[dict[str, str]], prediction_rows: list[dict[str, str]]
) -> tuple[list[dict[str, str]], dict[str, object]]:
    errors: list[str] = []
    prediction_map: dict[str, dict[str, str]] = {}

    for idx, row in enumerate(prediction_rows, start=2):
        record_id = _normalize_text(row.get("record_id", ""))
        if not record_id:
            errors.append(f"prediction row {idx}: record_id is required")
            continue
        if record_id in prediction_map:
            errors.append(f"prediction row {idx}: duplicate record_id '{record_id}'")
            continue
        prediction_map[record_id] = row

    gold_record_ids = {_normalize_text(row.get("record_id", "")) for row in gold_rows}
    unknown_prediction_ids = sorted(record_id for record_id in prediction_map if record_id not in gold_record_ids)
    for record_id in unknown_prediction_ids:
        errors.append(f"prediction row has unknown record_id '{record_id}'")

    merged_rows: list[dict[str, str]] = []
    matched_prediction_count = 0

    for row in gold_rows:
        merged_row = dict(row)
        record_id = _normalize_text(row.get("record_id", ""))
        prediction = prediction_map.get(record_id)
        if prediction:
            matched_prediction_count += 1
            for column in OPTIONAL_PREDICTION_COLUMNS:
                merged_row[column] = prediction.get(column, "")
        merged_rows.append(merged_row)

    merge_summary = {
        "prediction_row_count": len(prediction_rows),
        "matched_prediction_count": matched_prediction_count,
        "unmatched_gold_count": len(gold_rows) - matched_prediction_count,
        "unknown_prediction_id_count": len(unknown_prediction_ids),
        "merge_error_count": len(errors),
        "merge_errors": errors,
    }
    return merged_rows, merge_summary


def validate_rows(rows: list[dict[str, str]]) -> dict:
    errors: list[str] = []
    label_status_counts: Counter[str] = Counter()
    equip_type_counts: Counter[str] = Counter()
    docs_seen: set[str] = set()

    for idx, row in enumerate(rows, start=2):
        record_id = _normalize_text(row.get("record_id", ""))
        document_id = _normalize_text(row.get("document_id", ""))
        pdf_name = _normalize_text(row.get("pdf_name", ""))
        esn = _normalize_esn(row.get("true_primary_esn", ""))
        equip_type = _normalize_text(row.get("true_primary_equip_type", ""))
        active_esns = [_normalize_esn(v) for v in _split_pipe(row.get("true_active_esns", ""))]
        label_status = _normalize_text(row.get("label_status", "")).lower()

        start_char = _parse_optional_int(row.get("region_start_char", ""), "region_start_char", idx)
        end_char = _parse_optional_int(row.get("region_end_char", ""), "region_end_char", idx)

        if not record_id:
            errors.append(f"row {idx}: record_id is required")
        if not document_id:
            errors.append(f"row {idx}: document_id is required")
        if not pdf_name:
            errors.append(f"row {idx}: pdf_name is required")
        if not esn:
            errors.append(f"row {idx}: true_primary_esn is required")
        if not equip_type:
            errors.append(f"row {idx}: true_primary_equip_type is required")
        if not label_status:
            errors.append(f"row {idx}: label_status is required")

        if start_char is not None and end_char is not None and end_char < start_char:
            errors.append(f"row {idx}: region_end_char must be >= region_start_char")

        if active_esns and esn and esn not in active_esns:
            errors.append(
                f"row {idx}: true_primary_esn '{esn}' not present in true_active_esns '{row.get('true_active_esns', '')}'"
            )

        if document_id:
            docs_seen.add(document_id)
        if label_status:
            label_status_counts[label_status] += 1
        if equip_type:
            equip_type_counts[equip_type] += 1

    summary = {
        "row_count": len(rows),
        "unique_document_count": len(docs_seen),
        "label_status_counts": dict(label_status_counts),
        "equip_type_counts": dict(equip_type_counts),
        "error_count": len(errors),
        "errors": errors,
    }
    return summary


def build_row_results(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    row_results: list[dict[str, str]] = []

    for row in rows:
        true_esn = _normalize_esn(row.get("true_primary_esn", ""))
        true_equip_type = _normalize_text(row.get("true_primary_equip_type", ""))
        predicted_esn = _normalize_esn(row.get("predicted_primary_esn", ""))
        predicted_equip_type = _normalize_text(row.get("predicted_primary_equip_type", ""))

        has_prediction = bool(predicted_esn or predicted_equip_type)
        equip_type_match = bool(predicted_equip_type) and predicted_equip_type == true_equip_type
        esn_match = bool(predicted_esn) and predicted_esn == true_esn

        if not has_prediction:
            score_status = "pending_prediction"
        elif equip_type_match and esn_match:
            score_status = "exact_match"
        elif equip_type_match:
            score_status = "equip_type_only_match"
        elif esn_match:
            score_status = "esn_only_match"
        else:
            score_status = "mismatch"

        row_results.append(
            {
                "record_id": _normalize_text(row.get("record_id", "")),
                "document_id": _normalize_text(row.get("document_id", "")),
                "pdf_name": _normalize_text(row.get("pdf_name", "")),
                "true_primary_esn": true_esn,
                "predicted_primary_esn": predicted_esn,
                "esn_match": str(esn_match).lower(),
                "true_primary_equip_type": true_equip_type,
                "predicted_primary_equip_type": predicted_equip_type,
                "equip_type_match": str(equip_type_match).lower(),
                "score_status": score_status,
            }
        )

    return row_results


def score_rows(rows: list[dict[str, str]]) -> dict:
    scored_row_count = 0
    pending_prediction_count = 0
    equip_type_exact_match_count = 0
    esn_exact_match_count = 0
    both_exact_match_count = 0
    equip_type_mismatches: Counter[str] = Counter()
    per_true_equip_type: dict[str, dict[str, int]] = {}

    for row in rows:
        true_esn = _normalize_esn(row.get("true_primary_esn", ""))
        true_equip_type = _normalize_text(row.get("true_primary_equip_type", ""))

        predicted_esn = _normalize_esn(row.get("predicted_primary_esn", ""))
        predicted_equip_type = _normalize_text(row.get("predicted_primary_equip_type", ""))

        if not predicted_esn and not predicted_equip_type:
            pending_prediction_count += 1
            continue

        scored_row_count += 1

        type_bucket = per_true_equip_type.setdefault(
            true_equip_type or "UNKNOWN",
            {
                "scored_row_count": 0,
                "equip_type_exact_match_count": 0,
                "esn_exact_match_count": 0,
                "both_exact_match_count": 0,
            },
        )
        type_bucket["scored_row_count"] += 1

        equip_type_match = bool(predicted_equip_type) and predicted_equip_type == true_equip_type
        esn_match = bool(predicted_esn) and predicted_esn == true_esn

        if equip_type_match:
            equip_type_exact_match_count += 1
            type_bucket["equip_type_exact_match_count"] += 1
        elif predicted_equip_type and true_equip_type:
            equip_type_mismatches[f"{true_equip_type} -> {predicted_equip_type}"] += 1

        if esn_match:
            esn_exact_match_count += 1
            type_bucket["esn_exact_match_count"] += 1

        if equip_type_match and esn_match:
            both_exact_match_count += 1
            type_bucket["both_exact_match_count"] += 1

    equip_type_accuracy = (
        equip_type_exact_match_count / scored_row_count if scored_row_count else None
    )
    esn_accuracy = esn_exact_match_count / scored_row_count if scored_row_count else None
    joint_accuracy = both_exact_match_count / scored_row_count if scored_row_count else None

    per_true_equip_type_summary: dict[str, dict[str, float | int | None]] = {}
    for equip_type, bucket in per_true_equip_type.items():
        type_scored_row_count = bucket["scored_row_count"]
        per_true_equip_type_summary[equip_type] = {
            **bucket,
            "equip_type_accuracy": (
                bucket["equip_type_exact_match_count"] / type_scored_row_count if type_scored_row_count else None
            ),
            "esn_accuracy": (
                bucket["esn_exact_match_count"] / type_scored_row_count if type_scored_row_count else None
            ),
            "joint_accuracy": (
                bucket["both_exact_match_count"] / type_scored_row_count if type_scored_row_count else None
            ),
        }

    return {
        "scored_row_count": scored_row_count,
        "pending_prediction_count": pending_prediction_count,
        "equip_type_exact_match_count": equip_type_exact_match_count,
        "esn_exact_match_count": esn_exact_match_count,
        "both_exact_match_count": both_exact_match_count,
        "equip_type_accuracy": equip_type_accuracy,
        "esn_accuracy": esn_accuracy,
        "joint_accuracy": joint_accuracy,
        "top_equip_type_mismatches": dict(equip_type_mismatches.most_common(10)),
        "per_true_equip_type": per_true_equip_type_summary,
        "prediction_columns_present": [
            column for column in OPTIONAL_PREDICTION_COLUMNS if any(_normalize_text(row.get(column, "")) for row in rows)
        ],
    }


def write_row_results_csv(csv_path: Path, row_results: list[dict[str, str]]) -> None:
    fieldnames = [
        "record_id",
        "document_id",
        "pdf_name",
        "true_primary_esn",
        "predicted_primary_esn",
        "esn_match",
        "true_primary_equip_type",
        "predicted_primary_equip_type",
        "equip_type_match",
        "score_status",
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(row_results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate FSR v2 mapping gold-set CSV")
    parser.add_argument(
        "--gold-csv",
        type=Path,
        default=Path(__file__).resolve().parent / "gold-set-template.csv",
        help="Path to gold-set CSV",
    )
    parser.add_argument(
        "--predictions-csv",
        type=Path,
        help="Optional predictions CSV keyed by record_id",
    )
    parser.add_argument(
        "--row-results-csv",
        type=Path,
        help="Optional output CSV path for row-level scoring results",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when validation errors are found",
    )
    args = parser.parse_args()

    rows = load_gold_rows(args.gold_csv)
    summary = validate_rows(rows)

    if args.predictions_csv:
        prediction_rows = load_prediction_rows(args.predictions_csv)
        rows, merge_summary = merge_prediction_rows(rows, prediction_rows)
        summary["prediction_merge"] = merge_summary
        summary["error_count"] += merge_summary["merge_error_count"]
        summary["errors"] = list(summary["errors"]) + list(merge_summary["merge_errors"])

    summary["scoring"] = score_rows(rows)

    if args.row_results_csv:
        row_results = build_row_results(rows)
        write_row_results_csv(args.row_results_csv, row_results)
        summary["row_results_csv"] = str(args.row_results_csv)
        summary["row_results_count"] = len(row_results)

    print(json.dumps(summary, indent=2))

    if args.strict and summary["error_count"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
