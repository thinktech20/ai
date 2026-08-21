# FSR v2 Databricks Mosaic AI Agent — Migration & Deployment Guide

## Overview

This guide walks you through migrating from the custom Python agent (`fsr_v2_dev_ingest_agent.py`) to a managed **Databricks Mosaic AI Agent**.

**Why migrate?**
- Managed scaling and availability (Databricks handles infrastructure)
- Built-in chat UI in Databricks Workspace
- REST API for programmatic access
- Automatic tool discovery and parameter validation
- Integrated monitoring and audit logging

---

## Architecture

### Custom Python Agent (Phase 1)
```
Your VS Code / CLI
    ↓
fsr_v2_dev_ingest_agent.py (NL parsing + parameter mapping)
    ↓
Databricks Jobs API (/api/2.1/jobs/runs/submit)
    ↓
nb_fsr_v2_dev_ingest.py (orchestrator notebook)
```

### Databricks Mosaic AI Agent (Phase 2 — This Guide)
```
Databricks Workspace UI / REST API
    ↓
Databricks Agent Framework (reasoning + tool orchestration)
    ↓
fsr_v2_orchestrator_run tool (parameter resolution)
    ↓
Databricks Jobs API (/api/2.1/jobs/runs/submit)
    ↓
nb_fsr_v2_dev_ingest.py (orchestrator notebook)
```

Key difference: **Databricks Agent Framework** manages the reasoning loop, NL parsing, and tool calling. You define **what** the agent should do; Databricks handles **how** to do it.

---

## Quick Start: Deploy via Databricks UI (5 minutes)

### Step 1: Prepare
1. Have access to https://gevernova-ai-dev-dbr.cloud.databricks.com
2. Have admin or agent-creator role
3. Ensure this repo is synced to Databricks Repos

### Step 2: Go to Agents
1. In Databricks Workspace, click **Agents** (left sidebar)
2. Click **Create Agent** (top right, blue button)

### Step 3: Fill In Agent Details

**Basic Info:**
- **Name:** `fsr-v2-dev-ingest-agent`
- **Description:** `FSR v2 targeted document ingest agent with ms_test/ds_test/dev profile routing`
- **Model:** `Claude 3.5 Sonnet` (or latest available)

**System Prompt (copy from `fsr_v2_dev_ingest_agent_config.yaml` → `agent.system_prompt`):**
```
You are the FSR v2 Dev Ingest Agent for Databricks Field Service Report processing.

Your role: Parse user requests to ingest and validate FSR documents, then execute
the Databricks orchestrator pipeline with correct table/index profiles.

Command Format:
"Ingest and validate these docs <file_names> in dev using <profile> with <mode>"

Where:
- file_names: comma-separated PDF names (e.g., "12345", "report_abc.pdf")
- profile: ms_test (first validation), ds_test (team validation), or dev (production)
- mode: drop (recreate tables/index) or no-drop (keep and reprocess)

If profile is omitted, default to ms_test for safety.

Your responsibilities:
1. Parse and validate the user request
2. Extract: file_names, profile, mode
3. Call the fsr_v2_orchestrator_run tool with correct parameters
4. Report results: overall status, per-doc table, failure summary

Important rules:
- Profile routing is YOUR decision (agent layer) — tables are concrete by submission time
- Never modify notebook or pipeline behavior — only parameter routing
- Report partial failures clearly (some docs may pass, others fail)
- If user provides invalid profile, suggest ms_test, ds_test, or dev
- If drop mode is requested, remind user it's destructive but proceed (dev only)
```

### Step 4: Add Tools

Click **Add Tool** and select **Notebook Tool**:

**Tool Name:** `fsr_v2_orchestrator_run`

**Notebook Path:** `/Repos/pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest`

**Tool Description:**
```
Execute FSR v2 dev ingest orchestrator with profile-based table routing.
Ingests targeted PDFs, routes to ms_test/ds_test/dev tables, and returns per-doc status.
```

**Parameters** (add each as a parameter):

1. **jb_env**
   - Type: String
   - Required: Yes
   - Default: `dev`
   - Description: Databricks environment (dev only for agent v1)

2. **TARGET_PDF_NAMES**
   - Type: String
   - Required: Yes
   - Description: Comma-separated PDF file names to ingest

3. **DROP_TABLES_AND_INDEX**
   - Type: String
   - Required: No
   - Default: `false`
   - Description: Set to 'true' to drop/recreate tables and index

4. **METADATA_TABLE_V2**, **CHUNK_TABLE_V2**, **DOC_EQUIPMENT_MAP_TABLE_V2**, **RUN_LOG_TABLE_V2**, **DQ_LOG_TABLE_V2**, **VS_INDEX_V2**
   - Type: String
   - Required: No (can be overridden by agent)
   - Description: Profile-specific table names (agent sets these)

### Step 5: Set Compute & Deployment

**Compute:**
- Select an existing Databricks cluster or job cluster
- Recommend: shared cluster with 4+ workers, 2+ DBUs each

**Timeout:** 3600 seconds (1 hour)

**Max Turns:** 10 (agent reasoning loops)

### Step 6: Configure Access

**RBAC:**
- **Admins:** Add `@GE Vernova Databricks Operations Team`
- **Service Account:** `service.globalopsfsso@gevernova.com`

### Step 7: Deploy

Click **Deploy**. Databricks will create the agent and show you the **Agent ID**.

### Step 8: Test

Once deployed:

**Via Chat UI:**
1. Open the agent
2. Type: `Ingest and validate these docs 12345,67890 in dev using ms_test with drop`
3. Agent will parse, confirm parameters, and execute

**Via REST API:**
```bash
AGENT_ID="<your-agent-id>"
WORKSPACE_HOST="https://gevernova-ai-dev-dbr.cloud.databricks.com"
TOKEN="<your-pat>"

curl -X POST "$WORKSPACE_HOST/api/2.0/agents/requests" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "'$AGENT_ID'",
    "request": "Ingest and validate these docs 12345,67890 in dev using ms_test with drop"
  }'
```

---

## Learning Resources

### Databricks Agent Framework

**Official Docs:**
- https://docs.databricks.com/en/generative-ai/agents/index.html
- https://docs.databricks.com/en/generative-ai/agents/tools.html

**Key Concepts:**
- **Agents:** Autonomous reasoning systems that use tools to solve problems
- **Tools:** Functions agents can call (SQL queries, notebooks, APIs, retrieval, etc.)
- **ReAct Pattern:** Reasoning loop (Thought → Action → Observation → Repeat)

**Mosaic AI Framework:**
- https://docs.databricks.com/en/generative-ai/mosaic-ai-training/index.html

### Best Practices for FSR v2 Agent

1. **Profile Routing in Agent, Not Notebook**
   - Agent resolves `ms_test` → concrete table names
   - Notebook receives ready-to-use parameters
   - Keeps notebook logic clean and reusable

2. **Error Handling**
   - Agent reports partial failures clearly
   - Notebook audit tables capture detailed telemetry
   - Users always get per-doc status

3. **Safety Rules (Dev Only)**
   - Drop mode is destructive; only in dev workspace
   - No-drop mode deletes per-doc rows; intended for reprocessing
   - Agent enforces these rules via system prompt

4. **Monitoring & Audit**
   - FSR v2 run-log and DQ-log tables capture all executions
   - Databricks Agents REST API includes execution history
   - Query audit tables for compliance/debugging

---

## File Structure

```
2-FSR-v2/agents/
├── fsr_v2_dev_ingest_agent_config.yaml      # Agent definition (Databricks native format)
├── databricks_agent_tools.py                 # Tool implementations (Python)
├── deploy_agent.py                           # Deployment script
├── fsr_v2_dev_ingest_agent.py                # (Optional) Keep for backwards compatibility
└── README.md                                 # This file
```

---

## Advanced: Deploy via SDK

If you prefer infrastructure-as-code, use `databricks-sdk`:

```bash
pip install databricks-sdk
export DATABRICKS_HOST="https://gevernova-ai-dev-dbr.cloud.databricks.com"
export DATABRICKS_TOKEN="<your-pat>"

python deploy_agent.py --deploy
```

See [deploy_agent.py](deploy_agent.py) for details.

---

## Troubleshooting

### Agent doesn't parse my command
- Ensure you use exact format: `Ingest and validate these docs <files> in dev using <profile> with <mode>`
- Profile and mode are optional (defaults: `ms_test`, `no-drop`)
- Example: `Ingest and validate these docs 12345 in dev with drop` ✓

### Tool call fails with "notebook not found"
- Check notebook path in tool config matches actual Databricks Repos path
- Verify repo is synced to workspace

### Job timeout
- Increase agent timeout (default: 3600s = 1 hour)
- Check notebook execution logs in Databricks jobs UI

### Profile objects don't exist
- For `ds_test` and `ms_test`, ensure tables are pre-created
- Use existing DDL in `pw_sdg_ai_ser_repo/ddls/fsr_v2/nb_sdg_fsr_v2_ddl.py`

---

## Next Steps

1. **Deploy agent** (follow Quick Start above)
2. **Test with ms_test profile** (personal validation)
3. **Coordinate with DS team** for ds_test table setup
4. **Move to dev profile** once team validates
5. **(Future) Extend to qa and prod** with similar agents but stricter safety rules

---

## Support & Questions

- **Databricks Docs:** https://docs.databricks.com/en/generative-ai/agents/
- **Internal:** Reach out to @madhurima.saxena@gevernova.com or the FSR v2 team

---

**Version:** 1.0  
**Last Updated:** 2026-08-09  
**Agent Framework Version:** Databricks Mosaic AI (Claude 3.5 Sonnet)
