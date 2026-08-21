# Agent Customization Guide for agent-fsr-v2-dev-ingest

This guide shows the exact changes needed in `agent.py` to integrate the FSR v2 tool and system prompt.

## Step 1: Update agent.py (in the deployed app)

In your Databricks Apps, click **View source** → `/Workspaces/agent-openai-agents-sdk/agent_server/agent.py`

### A. Add imports at top

```python
from typing import Any
from openai_agents_sdk import agent, function_tool

# Import FSR tool config
from dataclasses import dataclass

@dataclass(frozen=True)
class ProfileConfig:
    metadata_table: str
    chunk_table: str
    doc_equipment_map_table: str
    run_log_table: str
    dq_log_table: str
    vs_index: str
    vs_endpoint: str
```

### B. Add ProfileConfig and PROFILE_CONFIGS (copy from databricks_agent_tools.py)

After the ProfileConfig dataclass, add:

```python
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
```

### C. Add the FSR tool function (with @function_tool decorator)

```python
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
    
    # Submit job to Databricks
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        
        dbx_cluster_id = "0825-191656-xzk24shw"  # Update with your cluster ID
        
        run_response = w.jobs.submit(
            tasks=[
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
            run_name=f"fsr_v2_ingest_{table_profile}_{mode}_{target_pdf_names.replace(',', '_')[:30]}",
        )
        
        job_run_id = run_response.run_id
        workspace_url = w.config.host or "https://gevernova-ai-dev-dbr.cloud.databricks.com"
        run_url = f"{workspace_url}/#job/{run_response.job_id}/run/{job_run_id}"
        
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
```

### D. Replace system prompt

Find the `SYSTEM_PROMPT` or `system_prompt` variable in agent.py and replace with:

```python
SYSTEM_PROMPT = """You are the FSR v2 Dev Ingest Agent for Databricks Field Service Report processing.

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
```

### E. Register tool with agent

In the `create_agent()` or agent initialization, ensure `fsr_v2_orchestrator_run` is in the tools list:

```python
# In the Agent() constructor or create_agent() function:
my_agent = agent.Agent(
    name="fsr-v2-dev-ingest-agent",
    model="gpt-4-turbo",
    system_prompt=SYSTEM_PROMPT,
    tools=[fsr_v2_orchestrator_run],  # ← Add tool here
)
```

## Step 2: Update requirements.txt

Ensure `databricks-sdk` is included:

```
databricks-sdk>=0.20.0
openai-agents-sdk
# ... other dependencies
```

## Step 3: Deploy

After making changes, commit and deploy:

```bash
cd /Workspaces/agent-openai-agents-sdk

# Validate configuration
databricks bundle validate

# Deploy
databricks bundle deploy

# Optional: Run the agent
databricks bundle run agent-fsr-v2-dev-ingest
```

## Step 4: Test

Once deployed, open the agent chat UI and test:

```
"Ingest and validate these docs 12345,67890 in dev using ms_test with drop"
```

Expected response: Agent confirms parameters, calls tool, returns job ID and monitoring URL.

---

**Notes:**
- Replace `"0825-191656-xzk24shw"` with your actual cluster ID
- If running on serverless (recommended), use `new_cluster` spec instead of `existing_cluster_id`
- System prompt can be tuned based on actual usage patterns
- Tool will be called automatically by the agent based on natural language understanding
