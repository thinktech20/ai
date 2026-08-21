import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator

import mlflow
from agents import Agent, Runner, function_tool, set_default_openai_api, set_default_openai_client
from agents.tracing import set_trace_processors
from databricks.sdk import WorkspaceClient
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from agent_server.utils import (
    build_mcp_url,
    get_session_id,
    get_user_workspace_client,
    process_agent_stream_events,
)

logger = logging.getLogger(__name__)

# FSR v2 Profile Configuration (Step B)
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

# NOTE: this will work for all databricks models OTHER than GPT-OSS, which uses a slightly different API
set_default_openai_client(AsyncDatabricksOpenAI())
set_default_openai_api("chat_completions")
set_trace_processors([])  # only use mlflow for trace processing
mlflow.openai.autolog()
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)


@function_tool
def get_current_time() -> str:
    """Get the current date and time."""
    return datetime.now().isoformat()


# FSR v2 Tool (Step C)
@function_tool
def fsr_v2_orchestrator_run(
    target_pdf_names: str,
    table_profile: str = "ms_test",
    mode: str = "no-drop",
) -> dict[str, Any]:
    """
    Execute FSR v2 dev ingest orchestrator notebook.
    
    This tool resolves profile-based table names and submits the ingest pipeline.
    The agent determines which profile/mode based on the user's natural language command.
    
    Args:
        target_pdf_names: Comma-separated PDF file names (e.g., "12345,67890")
        table_profile: One of "ms_test", "ds_test", or "dev" (default: "ms_test" for safety)
        mode: One of "drop" (recreate tables) or "no-drop" (keep existing)
    
    Returns:
        dict with status, job_run_id, run_url, and message
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
    
    # Submit job via REST API (avoids SDK typed-object requirements)
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
                    # no cluster spec → serverless compute
                }
            ],
            "queue": {"enabled": True},
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
            "run_url": run_url,
            "message": (
                f"FSR v2 ingest submitted: profile={table_profile}, mode={mode}, targets={target_pdf_names}. "
                f"Job ID: {job_run_id}. Monitor: {run_url}"
            ),
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Job submission failed: {str(e)}",
        }



async def init_mcp_server(workspace_client: WorkspaceClient):
    return McpServer(
        url=build_mcp_url("/api/2.0/mcp/functions/system/ai", workspace_client=workspace_client),
        name="system.ai UC function MCP server",
        workspace_client=workspace_client,
    )


async def connect_healthy_mcp_servers(
    stack: AsyncExitStack, servers: list[McpServer]
) -> tuple[list[McpServer], list[str]]:
    """Connect each MCP server and verify it can actually list its tools.

    The Agents SDK lists each server's tools lazily inside ``Runner.run``, so a server that
    connects but fails at list time (e.g. an unauthorized Genie space) would otherwise crash
    the whole request — including unrelated turns. We list tools here, per server: healthy
    servers are kept; any that fails to connect OR to list is dropped and its name returned,
    so the agent runs with whatever is available instead of erroring out.

    Returns (healthy_servers, unavailable_names).
    """
    healthy: list[McpServer] = []
    unavailable: list[str] = []
    for server in servers:
        name = getattr(server, "name", "MCP server")
        try:
            connected = await stack.enter_async_context(server)
            await connected.list_tools()  # forces the connectivity + authorization check now
            healthy.append(connected)
        except Exception:
            logger.warning("MCP server %r unavailable; continuing without it.", name, exc_info=True)
            unavailable.append(name)
    return healthy, unavailable


def create_agent(mcp_servers: list[McpServer] | None = None) -> Agent:
    # FSR v2 System Prompt (Step D)
    system_prompt = """You are the FSR v2 Dev Ingest Agent for Databricks Field Service Report processing.

## Role
You coordinate the ingestion, validation, and indexing of Field Service Report (FSR) documents
into the FSR v2 data pipeline running on Databricks.

## Command Format
Users submit requests like:
  "Ingest and validate these docs 12345,67890 in dev using ms_test with drop"
  "Process documents report1.pdf, report2.pdf using ds_test with no-drop"
  "Ingest docs 98765 in dev with drop" (defaults to ms_test profile)

## Parameters
- **target_pdf_names** (required): Comma-separated PDF file names (e.g., "12345,67890" or "report.pdf")
- **table_profile** (optional, default="ms_test"): 
  - "ms_test": Personal validation (Madhurima's test tables)
  - "ds_test": Data Science team testing
  - "dev": Production-grade tables (use with caution)
- **mode** (optional, default="no-drop"):
  - "drop": Recreate all tables and vector index (full reset)
  - "no-drop": Keep existing tables, reprocess documents only

## Your Responsibilities
1. **Parse** the user's natural language request into parameters (target_pdf_names, table_profile, mode)
2. **Validate** that profile and mode values are correct
3. **Call** fsr_v2_orchestrator_run() with the validated parameters
4. **Report** the job submission details:
   - Confirm which profile/mode will be used
   - Provide the job ID and monitoring URL
   - Explain what will happen (e.g., "Tables will be recreated" for drop mode)

## Safety Rules
1. **Default to ms_test** if user doesn't specify a profile
2. **Default to no-drop** if user doesn't specify mode (preserves existing data)
3. **Never modify the notebook execution logic** - the tool handles parameter passing
4. **Report partial failures clearly** if job submission fails

## Example Interaction
User: "Ingest docs ABC123, DEF456 in dev using ds_test with drop"
→ Parse: target_pdf_names="ABC123,DEF456", table_profile="ds_test", mode="drop"
→ Call tool
→ Report: "Submitting ds_test profile with full reset (drop mode). Job ID: 12345. Monitor here: [URL]"

## Important Notes
- Profile resolution happens in this agent layer, NOT in the notebook
- The notebook always receives concrete table names (e.g., ds_test_fsr_metadata_v2)
- Pipeline executes P1 (metadata) → P2 (chunks) → P3 (index) sequentially
- Audit tables capture all runs and data quality issues
"""
    
    return Agent(
        name="Agent",
        instructions=system_prompt,
        model="databricks-gpt-5-2",
        tools=[get_current_time, fsr_v2_orchestrator_run],  # Step E: Register tool
        mcp_servers=mcp_servers or [],
    )


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    # The agent runs inside an AsyncExitStack so any MCP servers stay open for the whole
    # request. To give the agent MCP tools, connect them with connect_healthy_mcp_servers,
    # which health-checks each server so one unavailable server can't crash the request
    # (the Agents SDK lists each server's tools lazily inside Runner.run):
    #   servers, unavailable = await connect_healthy_mcp_servers(
    #       stack, [await init_mcp_server(WorkspaceClient())])
    #   agent = create_agent(mcp_servers=servers)
    # WorkspaceClient() uses service principal credentials; use get_user_workspace_client()
    # for on-behalf-of user authentication.
    async with AsyncExitStack() as stack:
        agent = create_agent()
        messages = [i.model_dump() for i in request.input]
        result = await Runner.run(agent, messages)
        return ResponsesAgentResponse(output=[item.to_input_item() for item in result.new_items])


@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    # The agent runs inside an AsyncExitStack so any MCP servers stay open for the whole
    # request. To give the agent MCP tools, connect them with connect_healthy_mcp_servers,
    # which health-checks each server so one unavailable server can't crash the request
    # (the Agents SDK lists each server's tools lazily inside Runner.run):
    #   servers, unavailable = await connect_healthy_mcp_servers(
    #       stack, [await init_mcp_server(WorkspaceClient())])
    #   agent = create_agent(mcp_servers=servers)
    # WorkspaceClient() uses service principal credentials; use get_user_workspace_client()
    # for on-behalf-of user authentication.
    async with AsyncExitStack() as stack:
        agent = create_agent()
        messages = [i.model_dump() for i in request.input]
        result = Runner.run_streamed(agent, input=messages)

        async for event in process_agent_stream_events(result.stream_events()):
            yield event
