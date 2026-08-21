#!/usr/bin/env python3
"""Deploy FSR v2 Mosaic AI Agent to Databricks workspace.

This script registers the agent with Databricks Agents API and returns
the agent endpoint URL for testing and production use.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr_v2_agent_deploy")


def deploy_agent_via_sdk(
    host: str,
    token: str,
    agent_name: str = "fsr-v2-dev-ingest-agent",
    agent_description: str | None = None,
    model: str = "claude-3-5-sonnet",
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """
    Deploy agent via Databricks SDK (Agent Framework API).
    
    Requires: databricks-sdk Python package
    Install: pip install databricks-sdk
    
    Args:
        host: Databricks workspace host (https://...)
        token: Databricks personal access token
        agent_name: Agent name (must be unique in workspace)
        agent_description: Agent description
        model: LLM model (e.g., claude-3-5-sonnet)
        system_prompt: System prompt/instructions for agent
    
    Returns:
        dict with agent metadata and deployment status
    """
    
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.agents import (
            Agent,
            Tool,
            ToolParameterType,
        )
    except ImportError:
        return {
            "status": "error",
            "message": "databricks-sdk not installed. Install with: pip install databricks-sdk",
        }
    
    log.info(f"Connecting to Databricks workspace: {host}")
    ws = WorkspaceClient(host=host, token=token)
    
    # Define tools for the agent
    tools = [
        Tool(
            name="fsr_v2_orchestrator_run",
            description=(
                "Execute FSR v2 dev ingest pipeline with profile-based table routing. "
                "Accepts target PDFs, table profile (ms_test/ds_test/dev), and mode (drop/no-drop)."
            ),
            input_params=[
                {
                    "name": "target_pdf_names",
                    "type": ToolParameterType.STRING,
                    "required": True,
                    "description": "Comma-separated PDF file names to ingest",
                },
                {
                    "name": "table_profile",
                    "type": ToolParameterType.STRING,
                    "required": False,
                    "description": "Profile: ms_test (personal test), ds_test (team), dev (production). Default: ms_test",
                },
                {
                    "name": "mode",
                    "type": ToolParameterType.STRING,
                    "required": False,
                    "description": "Mode: drop (recreate tables/index) or no-drop (reprocess). Default: no-drop",
                },
            ],
        ),
    ]
    
    # Create agent
    log.info(f"Creating agent: {agent_name}")
    
    agent = Agent(
        name=agent_name,
        description=agent_description or "FSR v2 dev ingest orchestrator agent",
        model=model,
        system_prompt=system_prompt or (
            "You are the FSR v2 Dev Ingest Agent. Parse user requests to ingest FSR documents "
            "and execute the pipeline with correct table profiles. "
            "Format: 'Ingest and validate these docs <files> in dev using <profile> with <mode>' "
            "Default profile: ms_test (for safety). Profiles: ms_test, ds_test, dev."
        ),
        tools=tools,
    )
    
    # Note: The actual SDK deployment would use agent creation API
    # This is a placeholder showing the structure
    log.info(f"Agent definition prepared: {agent_name}")
    log.info("To deploy via Databricks UI:")
    log.info("  1. Go to Workspace → Agents → Create Agent")
    log.info("  2. Paste agent YAML config from fsr_v2_dev_ingest_agent_config.yaml")
    log.info("  3. Configure compute and authorization")
    log.info("  4. Deploy and test")
    
    return {
        "status": "prepared",
        "agent_name": agent_name,
        "model": model,
        "message": "Agent definition prepared. Deploy via Databricks UI or use agent creation SDK call.",
        "agent_object": agent,
    }


def deploy_via_ui_instructions() -> dict[str, str]:
    """Return step-by-step instructions for deploying via Databricks UI."""
    
    return {
        "title": "Deploy FSR v2 Agent via Databricks UI",
        "steps": [
            "1. Go to https://gevernova-ai-dev-dbr.cloud.databricks.com → Agents tab",
            "2. Click 'Create Agent' button (top right)",
            "3. Fill in agent details:",
            "   Name: fsr-v2-dev-ingest-agent",
            "   Description: FSR v2 targeted dev ingest agent with profile routing",
            "   Model: Claude 3.5 Sonnet (or latest)",
            "4. Paste system prompt from fsr_v2_dev_ingest_agent_config.yaml",
            "5. Add tool: fsr_v2_orchestrator_run (see databricks_agent_tools.py for parameters)",
            "6. Set deployment settings:",
            "   Environment: dev",
            "   Max turns: 10",
            "   Timeout: 3600 seconds",
            "7. Configure RBAC:",
            "   Admin: @GE Vernova Databricks Operations Team",
            "   Service account: service.globalopsfsso@gevernova.com",
            "8. Click Deploy",
            "9. Test via chat UI or REST API",
        ],
        "next": "Once deployed, interact via REST API or Databricks chat UI",
    }


def generate_agent_interaction_curl() -> str:
    """Generate example curl command to interact with deployed agent."""
    
    return """
# Example: Interact with agent via Databricks Agents REST API
# After agent is deployed, you'll get an agent_id from Databricks

AGENT_ID="<your-agent-id-from-deployment>"
WORKSPACE_HOST="https://gevernova-ai-dev-dbr.cloud.databricks.com"
TOKEN="<your-databricks-pat>"

curl -X POST "$WORKSPACE_HOST/api/2.0/agents/requests" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent_id": "'$AGENT_ID'",
    "request": "Ingest and validate these docs 12345,67890 in dev using ms_test with drop"
  }'

# Expected response structure:
# {
#   "request_id": "req_xyz123",
#   "status": "processing",
#   "agent_name": "fsr-v2-dev-ingest-agent",
#   "message": "FSR v2 dev ingest submitted with profile=ms_test, mode=drop..."
# }

# Poll for results:
curl -X GET "$WORKSPACE_HOST/api/2.0/agents/requests/<request_id>" \\
  -H "Authorization: Bearer $TOKEN"
"""


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deploy FSR v2 Databricks Agent")
    p.add_argument(
        "--host",
        default=os.getenv("DATABRICKS_HOST", "https://gevernova-ai-dev-dbr.cloud.databricks.com"),
        help="Databricks workspace host",
    )
    p.add_argument(
        "--token",
        default=os.getenv("DATABRICKS_TOKEN", ""),
        help="Databricks PAT (or set DATABRICKS_TOKEN env var)",
    )
    p.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy via SDK (requires databricks-sdk installed)",
    )
    p.add_argument(
        "--show-ui-steps",
        action="store_true",
        help="Show step-by-step UI deployment instructions",
    )
    p.add_argument(
        "--show-curl",
        action="store_true",
        help="Show example curl commands for interacting with agent",
    )
    p.add_argument(
        "--generate-config",
        action="store_true",
        help="Output agent YAML config ready for UI import",
    )
    return p


def main() -> int:
    args = _parser().parse_args()
    
    if args.show_ui_steps:
        instructions = deploy_via_ui_instructions()
        print("\n" + "="*60)
        print(instructions["title"])
        print("="*60)
        for step in instructions["steps"]:
            print(step)
        print("\n" + instructions["next"])
        return 0
    
    if args.show_curl:
        print(generate_agent_interaction_curl())
        return 0
    
    if args.generate_config:
        config_path = "./fsr_v2_dev_ingest_agent_config.yaml"
        try:
            with open(config_path) as f:
                config = f.read()
            print(config)
        except FileNotFoundError:
            print(f"Config file not found: {config_path}", file=sys.stderr)
            return 1
        return 0
    
    if args.deploy:
        if not args.token:
            log.error("--token required for SDK deployment (or set DATABRICKS_TOKEN)")
            return 1
        
        result = deploy_agent_via_sdk(host=args.host, token=args.token)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") != "error" else 1
    
    # Default: show quick start
    print("FSR v2 Databricks Agent Deployment Tool")
    print("\nQuick start:")
    print("  1. Show UI steps:  python deploy_agent.py --show-ui-steps")
    print("  2. Generate config: python deploy_agent.py --generate-config > agent.yaml")
    print("  3. Show curl examples: python deploy_agent.py --show-curl")
    print("  4. Deploy via SDK: python deploy_agent.py --deploy --token <your-pat>")
    print("\nOr see README for full instructions.")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
