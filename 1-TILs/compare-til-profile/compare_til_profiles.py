#!/usr/bin/env python3
"""Lightweight TIL profile comparison: DS baseline vs current pipeline output.

Usage examples:
  python3 compare_til_profiles.py --phase 1 --offset 0
  python3 compare_til_profiles.py --phase 5 --offset 1
  python3 compare_til_profiles.py --phase 10 --offset 6
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_DS_ROOT = Path(
    "/home/u560060992/dbx/1-TILs/analysis/ds-team-til-profile-results/"
    "til_profile_pilot_20260609_110447/til_profile_pilot_20260609_110447"
)
DEFAULT_OUR_METADATA_CSV = Path(
    "/home/u560060992/dbx/1-TILs/compare-til-profile/metadata-table-results/til-profile-results.csv"
)
DEFAULT_BASE_DIR = Path("/home/u560060992/dbx/1-TILs/compare-til-profile")

CRITICAL_FIELDS = ["til_number", "revision", "title"]
COMPARE_FIELDS = [
    "til_number",
    "revision",
    "title",
    "publish_date",
    "compliance_category_code",
    "coarse_outage_type",
    "scope_of_work",
    "service_recommendation_line_items",
    "parts_referenced",
    "extraction_confidence",
]


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


def parse_json_maybe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def load_ds_profiles(ds_root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in ds_root.rglob("profile_response.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        key = normalize_til_id(payload.get("requested_til"))
        profile = payload.get("parsed_profile")
        if key and isinstance(profile, dict):
            out[key] = profile
    return out


def load_our_profiles(metadata_csv: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with metadata_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = normalize_til_id(row.get("matched_til_number"))
            profile = parse_json_maybe(row.get("parsed_profile_json"))
            if key and isinstance(profile, dict):
                out[key] = profile
    return out


def compare_profiles(
    ds_profiles: dict[str, dict[str, Any]],
    our_profiles: dict[str, dict[str, Any]],
    selected: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for til in selected:
        ds = ds_profiles[til]
        ours = our_profiles[til]
        exact = 0
        mismatch = 0
        critical_ok = True

        for field in COMPARE_FIELDS:
            ds_norm = normalize_for_compare(ds.get(field))
            our_norm = normalize_for_compare(ours.get(field))
            if ds_norm == our_norm:
                exact += 1
                continue
            mismatch += 1
            if field in CRITICAL_FIELDS:
                critical_ok = False
            mismatches.append(
                {
                    "til": til,
                    "field": field,
                    "ds_value": ds.get(field),
                    "our_value": ours.get(field),
                }
            )

        summary.append(
            {
                "til": til,
                "exact_fields": exact,
                "mismatch_fields": mismatch,
                "critical_identity_pass": critical_ok,
                "overall_pass": critical_ok and mismatch <= 1,
            }
        )

    return summary, mismatches


def write_outputs(base_dir: Path, selected: list[str], summary: list[dict[str, Any]], mismatches: list[dict[str, Any]]) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = base_dir / "outputs" / f"compare_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["til", "exact_fields", "mismatch_fields", "critical_identity_pass", "overall_pass"],
        )
        writer.writeheader()
        writer.writerows(summary)

    with (out_dir / "mismatch_details.jsonl").open("w", encoding="utf-8") as f:
        for row in mismatches:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    run_info = {
        "selected_tils": selected,
        "selection_count": len(selected),
    }
    (out_dir / "run_info.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight TIL profile comparison")
    parser.add_argument("--phase", type=int, choices=[1, 5, 10], default=1)
    parser.add_argument("--offset", type=int, default=0, help="Start index in sorted overlap set")
    parser.add_argument("--tils", nargs="*", default=None, help="Optional explicit TIL ids")
    parser.add_argument("--ds-root", type=Path, default=DEFAULT_DS_ROOT)
    parser.add_argument("--our-metadata-csv", type=Path, default=DEFAULT_OUR_METADATA_CSV)
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    args = parser.parse_args()

    ds_profiles = load_ds_profiles(args.ds_root)
    our_profiles = load_our_profiles(args.our_metadata_csv)

    common = sorted(set(ds_profiles.keys()) & set(our_profiles.keys()))
    if not common:
        raise SystemExit("No overlapping TILs found between DS and current outputs")

    print(f"Overlap count: {len(common)}")
    if len(common) <= 20:
        print(f"Overlap TILs: {', '.join(common)}")

    if args.tils:
        selected = [normalize_til_id(v) for v in args.tils]
        selected = [v for v in selected if v in common]
    else:
        selected = common[args.offset : args.offset + args.phase]

    if not selected:
        raise SystemExit("No TILs selected. Check --offset or --tils.")

    summary, mismatches = compare_profiles(ds_profiles, our_profiles, selected)
    out_dir = write_outputs(args.base_dir, selected, summary, mismatches)

    total_exact = sum(row["exact_fields"] for row in summary)
    total_mismatch = sum(row["mismatch_fields"] for row in summary)

    print(f"Compared TILs: {', '.join(selected)}")
    print(f"Summary: exact={total_exact}, mismatch={total_mismatch}")
    print(f"Output folder: {out_dir}")
    if not args.tils:
        print(f"Next batch suggestion: --phase {args.phase} --offset {args.offset + args.phase}")


if __name__ == "__main__":
    main()
