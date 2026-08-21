from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import normalize_issue_name


RISK_TO_PRIORITY = {
    "Not Mentioned": 0,
    "Light": 1,
    "Med": 2,
    "Heavy": 3,
    "IMMEDIATE ACTION": 4,
}

_RISK_ALIASES = {
    "not mentioned": "Not Mentioned",
    "no data": "Not Mentioned",
    "light": "Light",
    "medium": "Med",
    "med": "Med",
    "heavy": "Heavy",
    "immediate": "IMMEDIATE ACTION",
    "immediate action": "IMMEDIATE ACTION",
}


def _normalize_risk_label(value: object) -> str:
    text = str(value).strip()
    if not text:
        return ""
    return _RISK_ALIASES.get(text.lower(), text)


def build_condensed_matrix(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"serial_number", "issue_name", "risk", "status"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    working = df.copy()
    working["issue_label"] = working["issue_name"].map(normalize_issue_name)
    working["status_label"] = working["status"].fillna("").astype(str).str.strip()

    success = working[working["status_label"].eq("success")].copy()
    if success.empty:
        raise ValueError("Input contains no success rows to condense.")

    non_success = working[working["status_label"].ne("success")].copy()
    unresolved_count = len(non_success.merge(
        success[["serial_number", "issue_label"]].drop_duplicates(),
        on=["serial_number", "issue_label"],
        how="left",
        indicator=True,
    ).query("_merge == 'left_only'"))
    if unresolved_count:
        print(f"[Condense] Skipping {unresolved_count} non-success rows with no successful counterpart")

    working = success
    working["risk_label"] = working["risk"].fillna("").map(_normalize_risk_label)
    working["risk_label"] = working["risk_label"].replace("", "Not Mentioned")
    working["risk_priority"] = working["risk_label"].map(RISK_TO_PRIORITY)

    unknown_risks = working[working["risk_priority"].isna()]["risk_label"].unique().tolist()
    if unknown_risks:
        raise ValueError(f"Unknown risk values encountered: {sorted(unknown_risks)}")

    serial_order = working["serial_number"].drop_duplicates().tolist()
    issue_order = working["issue_label"].drop_duplicates().tolist()

    strongest = (
        working.groupby(["issue_label", "serial_number"], as_index=False)["risk_priority"]
        .max()
    )

    risk_lookup = working[
        ["issue_label", "serial_number", "risk_priority", "risk_label"]
    ].drop_duplicates()

    strongest = strongest.merge(
        risk_lookup,
        on=["issue_label", "serial_number", "risk_priority"],
        how="left",
    )

    matrix = strongest.pivot(
        index="issue_label",
        columns="serial_number",
        values="risk_label",
    )

    matrix = matrix.reindex(index=issue_order, columns=serial_order)
    matrix.index.name = "issue_name"
    return matrix.fillna("")


def write_condensed_csv(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    input_csv = Path(input_path)
    output_csv = Path(output_path)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv)
    matrix = build_condensed_matrix(df)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(output_csv, encoding="utf-8")
    return matrix