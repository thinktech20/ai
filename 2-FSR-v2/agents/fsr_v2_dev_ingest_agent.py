#!/usr/bin/env python3
"""FSR v2 dev ingest agent wrapper.

This script is the agent-side control plane for running the Databricks
orchestrator notebook with concrete, profile-resolved object names.

Key rule: table/index profile resolution stays in the agent layer, not inside
nb_fsr_v2_dev_ingest.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentRequest:
    env: str
    profile: str
    mode: str
    file_names: list[str]


BASE_DEV_OBJECTS = {
    "METADATA_TABLE_V2": "vaid.ai_sot_field_service_report.fsr_metadata_v2",
    "CHUNK_TABLE_V2": "vaid.ai_std_con_field_service_report.fsr_chunks_v2",
    "DOC_EQUIPMENT_MAP_TABLE_V2": "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2",
    "RUN_LOG_TABLE_V2": "vaid.ai_sot_field_service_report.fsr_run_log_v2",
    "DQ_LOG_TABLE_V2": "vaid.ai_sot_field_service_report.fsr_data_quality_log_v2",
    "VS_INDEX_V2": "vaid.ai_std_con_field_service_report.fsr_vs_index_v2",
    "VS_ENDPOINT_V2": "pw-ser-sdg-vector-search",
}

ALLOWED_PROFILES = {"ms_test", "ds_test", "dev"}


def _normalize_doc_name(value: str) -> str:
    item = (value or "").strip().strip('"\'')
    if not item:
        return ""
    if item.lower().endswith(".pdf"):
        return item
    return item


def _parse_file_names(raw: str) -> list[str]:
    docs = [_normalize_doc_name(part) for part in re.split(r"[,;\n]", raw) if part.strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for doc in docs:
        key = doc.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(doc)
    return deduped


def _prefix_object_name(qualified_name: str, profile: str) -> str:
    if profile == "dev":
        return qualified_name

    if profile not in ALLOWED_PROFILES:
        raise ValueError("profile must be one of: ms_test, ds_test, dev")

    parts = qualified_name.split(".")
    if len(parts) < 3:
        raise ValueError(f"Expected fully qualified name (catalog.schema.object), got: {qualified_name}")

    object_name = parts[-1]
    object_name = re.sub(r"^(ms_test_|ds_test_)", "", object_name)
    object_name = f"{profile}_{object_name}"
    return ".".join(parts[:-1] + [object_name])


def resolve_profile_objects(profile: str) -> dict[str, str]:
    if profile not in ALLOWED_PROFILES:
        raise ValueError("profile must be one of: ms_test, ds_test, dev")

    resolved = dict(BASE_DEV_OBJECTS)
    if profile == "dev":
        return resolved

    for key in (
        "METADATA_TABLE_V2",
        "CHUNK_TABLE_V2",
        "DOC_EQUIPMENT_MAP_TABLE_V2",
        "RUN_LOG_TABLE_V2",
        "DQ_LOG_TABLE_V2",
        "VS_INDEX_V2",
    ):
        resolved[key] = _prefix_object_name(resolved[key], profile)

    return resolved


def parse_agent_request(nl_command: str) -> AgentRequest:
    # Canonical shape expected:
    # Ingest and validate these docs <file_names> in dev using <ms_test|ds_test|dev> with <drop|no-drop>
    # using <profile> is optional and defaults to ms_test for first rollout pass.

    command = " ".join((nl_command or "").strip().split())
    if not command:
        raise ValueError("Empty command")

    pattern = re.compile(
        r"ingest\s*(?:and|&)\s*validate\s*these\s*docs\s+(.+?)\s+in\s+(dev)"
        r"(?:\s+using\s+(ms_test|ds_test|dev))?\s+with\s+(drop|no-drop)\s*$",
        re.IGNORECASE,
    )
    match = pattern.search(command)
    if not match:
        raise ValueError(
            "Command format not recognized. Use: "
            "Ingest and validate these docs <file_names> in dev using <ms_test|ds_test|dev> with <drop|no-drop>"
        )

    file_names_raw = match.group(1)
    env = match.group(2).lower()
    profile = (match.group(3) or "ms_test").lower()
    mode = match.group(4).lower()

    file_names = _parse_file_names(file_names_raw)
    if not file_names:
        raise ValueError("No document names found in command")

    return AgentRequest(env=env, profile=profile, mode=mode, file_names=file_names)


def build_notebook_params(req: AgentRequest) -> dict[str, str]:
    resolved = resolve_profile_objects(req.profile)
    params: dict[str, str] = {
        "jb_env": req.env,
        "TARGET_PDF_NAMES": ",".join(req.file_names),
        "DROP_TABLES_AND_INDEX": "true" if req.mode == "drop" else "false",
        "RUN_ALL_FROM_VOLUMES": "false",
        "FSR_CHUNKING_STRATEGY": "section",
    }
    params.update(resolved)
    return params


def build_runs_submit_payload(notebook_path: str, params: dict[str, str]) -> dict[str, Any]:
    return {
        "run_name": f"fsr-v2-agent-dev-{params['TARGET_PDF_NAMES'][:60]}",
        "tasks": [
            {
                "task_key": "fsr_v2_dev_ingest_agent_task",
                "notebook_task": {
                    "notebook_path": notebook_path,
                    "base_parameters": params,
                },
            }
        ],
    }


def submit_run(host: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = host.rstrip("/") + "/api/2.1/jobs/runs/submit"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Databricks API error {exc.code}: {error_body}") from exc


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FSR v2 dev ingest agent wrapper")
    p.add_argument(
        "--command",
        required=True,
        help=(
            "Natural language command. Example: "
            "Ingest and validate these docs 12345,67890 in dev using ms_test with drop"
        ),
    )
    p.add_argument(
        "--notebook-path",
        default="/Repos/<repo-path>/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest",
        help="Workspace path to notebook for runs/submit payload",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Submit to Databricks API instead of only printing resolved payload",
    )
    p.add_argument(
        "--host",
        default=os.getenv("DATABRICKS_HOST", ""),
        help="Databricks workspace host (or set DATABRICKS_HOST)",
    )
    p.add_argument(
        "--token",
        default=os.getenv("DATABRICKS_TOKEN", ""),
        help="Databricks PAT (or set DATABRICKS_TOKEN)",
    )
    return p


def main() -> int:
    args = _parser().parse_args()
    request = parse_agent_request(args.command)
    notebook_params = build_notebook_params(request)
    payload = build_runs_submit_payload(args.notebook_path, notebook_params)

    result: dict[str, Any] = {
        "parsed_request": {
            "env": request.env,
            "profile": request.profile,
            "mode": request.mode,
            "file_names": request.file_names,
        },
        "notebook_parameters": notebook_params,
        "runs_submit_payload": payload,
    }

    if not args.execute:
        print(json.dumps(result, indent=2))
        return 0

    if not args.host or not args.token:
        raise ValueError("--execute requires --host and --token (or DATABRICKS_HOST/DATABRICKS_TOKEN)")

    submit_response = submit_run(args.host, args.token, payload)
    result["submit_response"] = submit_response
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
