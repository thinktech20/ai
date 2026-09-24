#!/usr/bin/env python3
"""Raw extraction signal comparator for fast triage before full profile mismatch review.

This script compares extraction-level signals from our metadata export against
DS extracted-document artifacts. It helps separate parser/extraction gaps from
LLM/prompt shaping gaps so iteration cycles are shorter.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_DS_ROOT = Path(
    "/home/u560060992/dbx/1-TILs/analysis/ds-team-til-profile-results/"
    "til_profile_pilot_20260609_110447/til_profile_pilot_20260609_110447"
)
DEFAULT_OUR_METADATA_CSV = Path(
    "/home/u560060992/dbx/1-TILs/compare-til-profile/metadata-table-results/til-metadata-2.csv"
)
DEFAULT_SAMPLE_PDF_DIR = Path("/home/u560060992/dbx/1-TILs/analysis/sample-pdfs")
PART_NUMBER_PATTERN = re.compile(r"\b\d{3}[A-Z]\d{4}\b")


def normalize_til_id(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().upper()
    s = re.sub(r"^TIL\s+", "", s)
    return re.sub(r"\s+", "", s)


def load_our_rows(metadata_csv: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with metadata_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = normalize_til_id(row.get("matched_til_number"))
            if not key:
                continue
            out[key] = row
    return out


def load_ds_extracted_docs(ds_root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in ds_root.rglob("extracted_document.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        key = normalize_til_id(payload.get("matched_til_number"))
        if not key:
            # Fallback to folder name for DS artifacts like 1502-R1
            key = normalize_til_id(path.parent.name)
        if key:
            out[key] = payload
    return out


def parse_json_maybe(value: Any) -> Any:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def count_part_numbers_in_text(text: str) -> int:
    if not text:
        return 0
    return len(set(PART_NUMBER_PATTERN.findall(text.upper())))


def load_sample_pdf_index(sample_pdf_dir: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not sample_pdf_dir.exists():
        return out

    for path in sorted(sample_pdf_dir.glob("*.pdf")):
        stem = path.stem
        match = re.match(r"^\s*TIL\s+([0-9]+(?:-[0-9]+)?(?:-?R[0-9]+)?)", stem, re.IGNORECASE)
        if match:
            key = normalize_til_id(match.group(1))
        else:
            key = normalize_til_id(stem)
        if not key:
            continue
        out.setdefault(key, []).append(path.name)
    return out


def summarize(
    til: str,
    ds_doc: dict[str, Any],
    our_row: dict[str, Any],
    sample_pdf_index: dict[str, list[str]],
) -> dict[str, Any]:
    ds_text = str(ds_doc.get("text_content") or "")
    ds_tables = ds_doc.get("labeled_tables") or []
    ds_table_text = "\n".join(str((t or {}).get("content") or "") for t in ds_tables)

    parsed_profile = parse_json_maybe(our_row.get("parsed_profile_json")) or {}
    parts = parsed_profile.get("parts_referenced") if isinstance(parsed_profile, dict) else []
    parts_count = len(parts) if isinstance(parts, list) else 0

    return {
        "til": til,
        "ds_text_len": len(ds_text),
        "ds_table_count": len(ds_tables),
        "ds_table_part_numbers": count_part_numbers_in_text(ds_table_text),
        "our_text_len": int(our_row.get("extracted_text_char_count") or 0),
        "our_table_count": int(our_row.get("extracted_table_count") or 0),
        "our_status": our_row.get("metadata_status") or "",
        "our_profile_parts_count": parts_count,
        "sample_pdf_count": len(sample_pdf_index.get(til, [])),
        "sample_pdf_names": " | ".join(sample_pdf_index.get(til, [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare raw extraction signals")
    parser.add_argument("--tils", nargs="*", default=None, help="Optional explicit TIL ids")
    parser.add_argument("--ds-root", type=Path, default=DEFAULT_DS_ROOT)
    parser.add_argument("--our-metadata-csv", type=Path, default=DEFAULT_OUR_METADATA_CSV)
    parser.add_argument("--sample-pdf-dir", type=Path, default=DEFAULT_SAMPLE_PDF_DIR)
    args = parser.parse_args()

    ds_docs = load_ds_extracted_docs(args.ds_root)
    our_rows = load_our_rows(args.our_metadata_csv)
    sample_pdf_index = load_sample_pdf_index(args.sample_pdf_dir)

    common = sorted(set(ds_docs.keys()) & set(our_rows.keys()))
    if args.tils:
        wanted = {normalize_til_id(v) for v in args.tils}
        common = [k for k in common if k in wanted]

    if not common:
        raise SystemExit("No overlapping TILs for raw extraction signal comparison")

    print(
        "til,ds_text_len,our_text_len,ds_table_count,our_table_count,"
        "ds_table_part_numbers,our_profile_parts_count,our_status,"
        "sample_pdf_count,sample_pdf_names"
    )
    for til in common:
        row = summarize(til, ds_docs[til], our_rows[til], sample_pdf_index)
        print(
            f"{row['til']},{row['ds_text_len']},{row['our_text_len']},"
            f"{row['ds_table_count']},{row['our_table_count']},"
            f"{row['ds_table_part_numbers']},{row['our_profile_parts_count']},{row['our_status']},"
            f"{row['sample_pdf_count']},{json.dumps(row['sample_pdf_names'])}"
        )


if __name__ == "__main__":
    main()
