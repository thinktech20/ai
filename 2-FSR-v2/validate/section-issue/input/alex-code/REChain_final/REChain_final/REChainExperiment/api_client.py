"""
API client for the FastAPI data service (ibat&heatmap, port 8001).

Uncomment and use these functions when the data service is available,
instead of querying Databricks directly via heatmap.py / ibat.py.

Endpoints:
  GET /api/v1/heatmap/load?equipment_type={GEN|GT}&persona={REL|OE}&component={}
  GET /api/v1/ibat/equipment?equip_serial_number={esn}
"""

# import requests
# from typing import Any, Dict, List
#
#
# DATA_SERVICE_URL = "http://localhost:8001"
#
#
# def query_heatmap_api(
#     equipment_type: str,
#     component: str = "",
#     persona: str = "REL",
# ) -> List[Dict[str, Any]]:
#     """
#     Call the heatmap API to get risk matrix rows.
#
#     Args:
#         equipment_type: "GEN" or "GT"
#         component: e.g. "Rotor", "Stator"
#         persona: "REL" or "OE"
#
#     Returns:
#         List of heatmap row dicts with issue_prompt, severity_criteria, etc.
#     """
#     params = {
#         "equipment_type": equipment_type,
#         "persona": persona,
#     }
#     if component:
#         params["component"] = component
#
#     resp = requests.get(
#         f"{DATA_SERVICE_URL}/api/v1/heatmap/load",
#         params=params,
#         timeout=30,
#     )
#     resp.raise_for_status()
#     payload = resp.json()
#
#     rows = payload.get("data", [])
#     print(f"[Heatmap API] {len(rows)} rows for equipment_type={equipment_type}, component={component}")
#     return rows
#
#
# def query_ibat_api(serial_number: str) -> List[Dict[str, Any]]:
#     """
#     Call the IBAT API to get equipment metadata.
#
#     Args:
#         serial_number: e.g. "290T658"
#
#     Returns:
#         List of equipment row dicts with plant, train, cooling info.
#     """
#     resp = requests.get(
#         f"{DATA_SERVICE_URL}/api/v1/ibat/equipment",
#         params={"equip_serial_number": serial_number},
#         timeout=30,
#     )
#     resp.raise_for_status()
#     payload = resp.json()
#
#     rows = payload.get("data", [])
#     print(f"[IBAT API] {len(rows)} rows for serial_number={serial_number}")
#     return rows
#
#
# def filter_heatmap_by_issue(rows: List[Dict], issue_name: str) -> List[Dict]:
#     """Filter heatmap API rows to match a specific issue_name."""
#     target = issue_name.strip().upper()
#     return [r for r in rows if str(r.get("issue_name", "")).strip().upper() == target]
