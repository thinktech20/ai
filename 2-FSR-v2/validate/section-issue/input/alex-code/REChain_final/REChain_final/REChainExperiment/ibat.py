"""Step 3: Query IBAT equipment metadata from Databricks for a given serial number."""

from __future__ import annotations

from typing import Dict, List

from .config import (
    get_db_connection,
    IBAT_EQUIPMENT_VIEW,
    IBAT_PLANT_VIEW,
    IBAT_TRAIN_VIEW,
)


IBAT_EQUIPMENT_COLUMNS = (
    "equipment_type", "equipment_name", "sales_channel", "equipment_sys_id",
    "contract_type", "equipment_code", "equipment_class", "block_sys_id_fk",
    "plant_sys_id_fk", "train_sys_id_fk", "actualized_flag", "duty_cycle",
    "equip_serial_number", "rotor_rewind", "stator_rewind", "cooling_system",
)
IBAT_PLANT_COLUMNS = (
    "site_customer_name", "plant_name", "site_country", "site_state",
    "hyp_sub_region", "ps_pole", "cust_gegul_name", "industry",
)
IBAT_TRAIN_COLUMNS = ("fuel_type",)


def query_ibat(serial_number: str) -> List[Dict]:
    """
    Query IBAT equipment + plant + train tables joined by serial number.

    Args:
        serial_number: e.g. "290T658"

    Returns:
        List of dicts with equipment, plant, and train metadata
    """
    try:
        rows = _query_ibat_live(serial_number)
    except Exception as exc:
        raise RuntimeError(
            f"IBAT lookup failed for serial '{serial_number}' from Databricks."
        ) from exc

    if rows:
        print(f"[IBAT] Found {len(rows)} live row(s) for serial_number='{serial_number}'")
        return rows

    raise LookupError(f"IBAT lookup returned no rows for serial '{serial_number}'")


def _query_ibat_live(serial_number: str) -> List[Dict]:
    e_cols = ", ".join(f"e.{c}" for c in IBAT_EQUIPMENT_COLUMNS)
    p_cols = ", ".join(f"p.{c}" for c in IBAT_PLANT_COLUMNS)
    t_cols = ", ".join(f"t.{c}" for c in IBAT_TRAIN_COLUMNS)

    query = f"""
        SELECT DISTINCT {e_cols}, {p_cols}, {t_cols}
        FROM {IBAT_EQUIPMENT_VIEW} e
        LEFT JOIN {IBAT_PLANT_VIEW} p ON e.plant_sys_id_fk = p.plant_sys_id
        LEFT JOIN {IBAT_TRAIN_VIEW} t ON e.train_sys_id_fk = t.train_sys_id
        WHERE e.equip_serial_number = '{_escape(serial_number)}'
        LIMIT 50
    """

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _escape(val: str) -> str:
    return str(val).replace("'", "''")
