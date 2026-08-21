"""Step 1: Query heatmap risk matrix — reads from local xlsx file.

Fallback: Databricks SQL queries are commented out below.
"""

import os
import pandas as pd
from typing import Dict, List

# from .config import get_db_connection, HEATMAP_VIEW

# Local xlsx file (same schema as fsr_unit_risk_matrix_view)
HEATMAP_XLSX = os.path.join(os.path.dirname(__file__), "fsr_unit_risk_matrix_view.xlsx")


HEATMAP_COLUMNS = (
    "equipment_type",
    "technology_group",
    "technology",
    "component",
    "persona",
    "issue_grouping",
    "issue_name",
    "issue_prompt",
    "severity_criteria_0_no_data",
    "severity_criteria_1_light",
    "severity_criteria_2_medium",
    "severity_criteria_3_heavy",
    "severity_criteria_4_immediate",
    "applicable_data_objects",
)

HEATMAP_EQUIPMENT_TYPE_FILTER = os.getenv("RE_CHAIN_HEATMAP_EQUIPMENT_TYPE", "GEN").strip().upper()
HEATMAP_PERSONA_FILTER = os.getenv("RE_CHAIN_HEATMAP_PERSONA", "REL").strip().upper()


def _load_xlsx() -> pd.DataFrame:
    """Load heatmap xlsx and normalise column names."""
    df = pd.read_excel(HEATMAP_XLSX)
    df.columns = df.columns.str.strip().str.lower()
    return df


def _apply_heatmap_scope(df: pd.DataFrame) -> pd.DataFrame:
    equipment_type = df["equipment_type"].astype(str).str.strip().str.upper()
    persona = df["persona"].astype(str).str.strip().str.upper()
    return df[
        equipment_type.eq(HEATMAP_EQUIPMENT_TYPE_FILTER)
        & persona.eq(HEATMAP_PERSONA_FILTER)
    ]


def query_heatmap(issue_name: str, component: str) -> List[Dict]:
    """
    Query heatmap for rows matching issue_name and component.
    Reads from local xlsx file.

    Args:
        issue_name: e.g. "Vibration", "Flux probe"
        component: e.g. "Rotor", "Stator"

    Returns:
        List of dicts with heatmap columns including issue_prompt and severity_criteria_0..4
    """
    df = _apply_heatmap_scope(_load_xlsx())
    mask = (
        df["issue_name"].str.strip().str.upper() == issue_name.strip().upper()
    ) & (
        df["component"].str.strip().str.lower().str.contains(component.strip().lower(), na=False)
    )
    filtered = df[mask].sort_values("issue_name")
    avail = [c for c in HEATMAP_COLUMNS if c in filtered.columns]
    rows = filtered[avail].to_dict(orient="records")

    print(
        f"[Heatmap] Found {len(rows)} rows for issue_name='{issue_name}', component='{component}' "
        f"within equipment_type={HEATMAP_EQUIPMENT_TYPE_FILTER}, persona={HEATMAP_PERSONA_FILTER}"
    )
    return rows


# ── Databricks SQL version (commented out — data deleted from DB) ──
# def query_heatmap(issue_name: str, component: str) -> List[Dict]:
#     col_list = ", ".join(HEATMAP_COLUMNS)
#     query = f"""
#         SELECT {col_list}
#         FROM {HEATMAP_VIEW}
#         WHERE UPPER(issue_name) = UPPER('{_escape(issue_name)}')
#           AND component ILIKE '%{_escape(component)}%'
#         ORDER BY issue_name
#         LIMIT 50
#     """
#     with get_db_connection() as conn:
#         with conn.cursor() as cursor:
#             cursor.execute(query)
#             columns = [desc[0] for desc in cursor.description]
#             rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
#     print(f"[Heatmap] Found {len(rows)} rows for issue_name='{issue_name}', component='{component}'")
#     return rows


def build_query_from_heatmap(heatmap_row: Dict) -> str:
    """
    Build a retrieval query string from a heatmap row.
    Combines issue_prompt + severity criteria into a single search query.
    """
    issue_prompt = str(heatmap_row.get("issue_prompt") or "").strip()

    severity_parts = []
    sev_map = {
        "severity_criteria_0_no_data": "No Data",
        "severity_criteria_1_light": "Light",
        "severity_criteria_2_medium": "Medium",
        "severity_criteria_3_heavy": "Heavy",
        "severity_criteria_4_immediate": "Immediate",
    }
    for col, label in sev_map.items():
        val = heatmap_row.get(col)
        if val and str(val).strip():
            severity_parts.append(f"{label}: {str(val).strip()}")

    severity_text = " | ".join(severity_parts)
    query = f"{issue_prompt} {severity_text}".strip()
    return query


def query_all_issues() -> List[Dict]:
    """Fetch all issue rows from the heatmap xlsx."""
    df = _apply_heatmap_scope(_load_xlsx())
    df = df.sort_values(["component", "issue_name"])
    avail = [c for c in HEATMAP_COLUMNS if c in df.columns]
    rows = df[avail].to_dict(orient="records")
    print(
        f"[Heatmap] Loaded {len(rows)} total issue rows "
        f"for equipment_type={HEATMAP_EQUIPMENT_TYPE_FILTER}, persona={HEATMAP_PERSONA_FILTER}"
    )
    return rows


# ── Databricks SQL version (commented out — data deleted from DB) ──
# def query_all_issues() -> List[Dict]:
#     col_list = ", ".join(HEATMAP_COLUMNS)
#     query = f"SELECT {col_list} FROM {HEATMAP_VIEW} ORDER BY component, issue_name"
#     with get_db_connection() as conn:
#         with conn.cursor() as cursor:
#             cursor.execute(query)
#             columns = [desc[0] for desc in cursor.description]
#             rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
#     print(f"[Heatmap] Loaded {len(rows)} total issue rows")
#     return rows


def _escape(val: str) -> str:
    return str(val).replace("'", "''")
