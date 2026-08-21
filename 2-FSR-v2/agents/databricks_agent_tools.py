#!/usr/bin/env python3
"""Databricks Agent tool definitions for FSR v2 dev ingest.

Tools are Python functions that Databricks Agents can call during reasoning.
Each tool is wrapped with proper typing and documentation for the LLM.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

try:
    from databricks.sdk import WorkspaceClient
    DATABRICKS_SDK_AVAILABLE = True
except ImportError:
    DATABRICKS_SDK_AVAILABLE = False


@dataclass(frozen=True)
class ProfileConfig:
    metadata_table: str
    chunk_table: str
    doc_equipment_map_table: str
    run_log_table: str
    dq_log_table: str
    vs_index: str
    vs_endpoint: str


PROFILE_CONFIGS = {
    "dev": ProfileConfig(
        metadata_table="vaid.ai_sot_field_service_report.fsr_metadata_v2",
        chunk_table="vaid.ai_std_con_field_service_report.fsr_chunks_v2",
        doc_equipment_map_table="vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2",
        run_log_table="vaid.ai_sot_field_service_report.fsr_run_log_v2",
        dq_log_table="vaid.ai_sot_field_service_report.fsr_data_quality_log_v2",
        vs_index="vaid.ai_std_con_field_service_report.fsr_vs_index_v2",
        vs_endpoint="pw-ser-sdg-vector-search",
    ),
    "ds_test": ProfileConfig(
        metadata_table="vaid.ai_sot_field_service_report.ds_test_fsr_metadata_v2",
        chunk_table="vaid.ai_std_con_field_service_report.ds_test_fsr_chunks_v2",
        doc_equipment_map_table="vaid.ai_sot_field_service_report.ds_test_fsr_document_equipment_map_v2",
        run_log_table="vaid.ai_sot_field_service_report.ds_test_fsr_run_log_v2",
        dq_log_table="vaid.ai_sot_field_service_report.ds_test_fsr_data_quality_log_v2",
        vs_index="vaid.ai_std_con_field_service_report.ds_test_fsr_vs_index_v2",
        vs_endpoint="pw-ser-sdg-vector-search",
    ),
    "ms_test": ProfileConfig(
        metadata_table="vaid.ai_sot_field_service_report.ms_test_fsr_metadata_v2",
        chunk_table="vaid.ai_std_con_field_service_report.ms_test_fsr_chunks_v2",
        doc_equipment_map_table="vaid.ai_sot_field_service_report.ms_test_fsr_document_equipment_map_v2",
        run_log_table="vaid.ai_sot_field_service_report.ms_test_fsr_run_log_v2",
        dq_log_table="vaid.ai_sot_field_service_report.ms_test_fsr_data_quality_log_v2",
        vs_index="vaid.ai_std_con_field_service_report.ms_test_fsr_vs_index_v2",
        vs_endpoint="pw-ser-sdg-vector-search",
    ),
}


def fsr_v2_orchestrator_run(
    target_pdf_names: str,
    table_profile: str = "ms_test",
    mode: str = "no-drop",
) -> dict[str, Any]:
    """
    Execute FSR v2 dev ingest orchestrator notebook.
    
    This tool is the bridge between the agent's reasoning layer and the Databricks
    notebook pipeline execution. The agent calls this tool with validated parameters,
    and the tool:
    1. Resolves concrete table/index names based on profile
    2. Builds Databricks Jobs API payload
    3. Submits the job and monitors execution
    4. Returns structured results
    
    Args:
        target_pdf_names: Comma-separated PDF file names (e.g., "12345,67890" or "report.pdf")
        table_profile: One of "ms_test", "ds_test", or "dev" (default: "ms_test")
        mode: One of "drop" or "no-drop" (default: "no-drop")
    
    Returns:
        dict with keys:
            - job_run_id: Databricks job run ID
            - status: "submitted" or error details
            - notebook_path: Full path to executed notebook
            - parameters: Resolved parameters sent to notebook
            - profile: Resolved profile (ms_test/ds_test/dev)
    
    Example:
        >>> result = fsr_v2_orchestrator_run(
        ...     target_pdf_names="12345,67890",
        ...     table_profile="ms_test",
        ...     mode="drop"
        ... )
        >>> print(result["job_run_id"])
    """
    
    # Validate inputs
    if not target_pdf_names or not target_pdf_names.strip():
        return {
            "status": "error",
            "message": "target_pdf_names cannot be empty",
        }
    
    if table_profile not in PROFILE_CONFIGS:
        return {
            "status": "error",
            "message": f"Invalid profile '{table_profile}'. Must be one of: {', '.join(PROFILE_CONFIGS.keys())}",
        }
    
    if mode not in {"drop", "no-drop"}:
        return {
            "status": "error",
            "message": f"Invalid mode '{mode}'. Must be 'drop' or 'no-drop'",
        }
    
    # Resolve profile-specific config
    profile_config = PROFILE_CONFIGS[table_profile]
    
    # Build notebook parameters
    notebook_params = {
        "jb_env": "dev",
        "TARGET_PDF_NAMES": target_pdf_names.strip(),
        "METADATA_TABLE_V2": profile_config.metadata_table,
        "CHUNK_TABLE_V2": profile_config.chunk_table,
        "DOC_EQUIPMENT_MAP_TABLE_V2": profile_config.doc_equipment_map_table,
        "RUN_LOG_TABLE_V2": profile_config.run_log_table,
        "DQ_LOG_TABLE_V2": profile_config.dq_log_table,
        "VS_INDEX_V2": profile_config.vs_index,
        "VS_ENDPOINT_V2": profile_config.vs_endpoint,
        "DROP_TABLES_AND_INDEX": "true" if mode == "drop" else "false",
        "RUN_ALL_FROM_VOLUMES": "false",
        "FSR_CHUNKING_STRATEGY": "section",
        "FSR_SOURCE_VOLUME_PATHS": (
            "/Volumes/viud/ing_ud_fieldvision/fv_field_service_report,"
            "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports,"
            "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/FSR_manual"
        ),
        "LITELLM_BASE_URL": "https://dev-gateway.apps.gevernova.net",
    }
    
    notebook_path = "/Repos/pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest"
    
    # Submit job to Databricks via REST API (avoids SDK typed-object requirements)
    try:
        import requests as _requests

        w = WorkspaceClient()
        workspace_url = (w.config.host or "https://gevernova-ai-dev-dbr.cloud.databricks.com").rstrip("/")
        token = w.config.token or os.environ.get("DATABRICKS_TOKEN", "")
        dbx_cluster_id = os.environ.get("DBX_CLUSTER_ID", "0825-191656-xzk24shw")

        payload = {
            "run_name": f"fsr_v2_ingest_{table_profile}_{mode}_{target_pdf_names.replace(',', '_')[:30]}",
            "tasks": [
                {
                    "task_key": "fsr_v2_ingest",
                    "notebook_task": {
                        "notebook_path": notebook_path,
                        "base_parameters": notebook_params,
                    },
                    "existing_cluster_id": dbx_cluster_id,
                    "timeout_seconds": 3600,
                }
            ],
        }

        resp = _requests.post(
            f"{workspace_url}/api/2.1/jobs/runs/submit",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        run_data = resp.json()
        job_run_id = run_data.get("run_id")
        run_url = f"{workspace_url}/#job/0/run/{job_run_id}"
        
        return {
            "status": "submitted",
            "job_run_id": str(job_run_id),
            "job_id": str(run_response.job_id),
            "run_url": run_url,
            "notebook_path": notebook_path,
            "profile": table_profile,
            "mode": mode,
            "target_pdf_names": target_pdf_names,
            "parameters": notebook_params,
            "message": (
                f"FSR v2 dev ingest job submitted successfully. "
                f"Profile={table_profile}, Mode={mode}, Targets={target_pdf_names}. "
                f"Job run ID: {job_run_id}. Monitor at: {run_url}"
            ),
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to submit FSR v2 ingest job: {str(e)}",
            "error_type": type(e).__name__,
        }


# NOTE: NL parsing is handled by Databricks Agent framework itself during reasoning.
# The agent reads the user's command, system prompt, and tool signatures,
# then automatically determines which tool to call and with what parameters.
# parse_ingest_command() below is retained for local testing/debugging only,
# not exposed as an agent tool.

def parse_ingest_command(command: str) -> dict[str, Any]:
    """
    Parse user natural language command into structured parameters.
    
    NOTE: This function is for LOCAL TESTING/DEBUGGING only.
    Databricks Agents does this parsing automatically via LLM reasoning.
    
    Expected format:
    "Ingest and validate these docs <file_names> in dev using <profile> with <mode>"
    
    Where:
    - file_names: comma-separated PDF names
    - profile: ms_test, ds_test, or dev (optional, defaults to ms_test)
    - mode: drop or no-drop
    
    Args:
        command: Natural language command string
    
    Returns:
        dict with keys: target_pdf_names, table_profile, mode
        If parsing fails, returns dict with "error" key
    
    Example:
        >>> parse_ingest_command("Ingest and validate these docs 12345,67890 in dev using ms_test with drop")
        {
            "target_pdf_names": "12345,67890",
            "table_profile": "ms_test",
            "mode": "drop"
        }
    """
    
    pattern = re.compile(
        r"ingest\s*(?:and|&)\s*validate\s*these\s*docs\s+(.+?)\s+in\s+(dev)"
        r"(?:\s+using\s+(ms_test|ds_test|dev))?\s+with\s+(drop|no-drop)\s*$",
        re.IGNORECASE,
    )
    
    match = pattern.search(command.strip())
    if not match:
        return {
            "error": (
                "Could not parse command. Expected format: "
                "Ingest and validate these docs <files> in dev using <profile> with <mode>"
            )
        }
    
    file_names = match.group(1).strip()
    profile = (match.group(3) or "ms_test").lower()
    mode = match.group(4).lower()
    
    if not file_names:
        return {"error": "No document names provided"}
    
    return {
        "target_pdf_names": file_names,
        "table_profile": profile,
        "mode": mode,
    }


# Agent tool registry for Databricks Agents
# Only include the main orchestrator tool.
# NL parsing is handled automatically by the agent framework during reasoning.
AGENT_TOOLS = [
    {
        "name": "fsr_v2_orchestrator_run",
        "description": (
            "Execute FSR v2 dev ingest pipeline with profile-based table routing. "
            "Takes target PDFs, profile (ms_test/ds_test/dev), and reset mode (drop/no-drop)."
        ),
        "python_function": fsr_v2_orchestrator_run,
    },
]


if __name__ == "__main__":
    # Demo: Parse and execute
    cmd = "Ingest and validate these docs 12345,67890 in dev using ms_test with drop"
    print(f"Command: {cmd}\n")
    
    parsed = parse_ingest_command(cmd)
    print(f"Parsed: {json.dumps(parsed, indent=2)}\n")
    
    if "error" not in parsed:
        result = fsr_v2_orchestrator_run(**parsed)
        print(f"Execution: {json.dumps(result, indent=2)}")
