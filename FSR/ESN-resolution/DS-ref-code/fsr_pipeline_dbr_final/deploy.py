#!/usr/bin/env python
"""
Deploy fsr_pipeline_dbr to Databricks DEV workspace via REST API.

Usage:
    python deploy.py                                          # auto-detects workspace path
    python deploy.py --workspace-path /Users/you@ge.com/fsr_pipeline

Reads the Databricks Personal Access Token from DATABRICKS_TOKEN or an
optional token file. The token file should contain only the token string
(dapi...).
"""
import argparse
import base64
import os
import ssl
import sys
from pathlib import Path

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

urllib3.disable_warnings()

PROJECT_ROOT = Path(__file__).resolve().parent
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)

# ── Workspace ────────────────────────────────────────────────────────────────
DATABRICKS_HOST = "https://gevernova-ai-dev-dbr.cloud.databricks.com"

# Files to upload from src/ (recursive_chunking_v3.py included)
# .env.example is informational only – not uploaded
SKIP_SRC = {"__init__"}


# ── No-verify session (Python 3.14 Windows cert store hang workaround) ───────
class _NoVerifyAdapter(HTTPAdapter):
    def send(self, request, **kwargs):
        kwargs['verify'] = False
        return super().send(request, **kwargs)
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        super().init_poolmanager(*args, **kwargs)

_session = requests.Session()
_session.mount('https://', _NoVerifyAdapter())


# ── REST helpers ──────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def api(method: str, endpoint: str, token: str, **kwargs) -> dict:
    url  = f"{DATABRICKS_HOST}/api/2.0/{endpoint}"
    resp = _session.request(method, url, headers=_headers(token), **kwargs)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"API {method.upper()} /{endpoint} → HTTP {resp.status_code}\n{resp.text[:600]}"
        )
    return resp.json() if resp.text.strip() else {}


def mkdirs(path: str, token: str):
    try:
        api("POST", "workspace/mkdirs", token, json={"path": path})
    except Exception as e:
        print(f"  [WARN] mkdirs({path}): {e}")


def upload(local: Path, ws_path: str, token: str, as_notebook: bool = False):
    """Base64-encode and POST a file to the Databricks workspace."""
    content = local.read_bytes()
    b64     = base64.b64encode(content).decode()

    payload = {
        "path":      ws_path,
        "content":   b64,
        "overwrite": True,
    }
    if as_notebook:
        # run_pipeline.py has the '# Databricks notebook source' header
        payload["format"]   = "SOURCE"
        payload["language"] = "PYTHON"
    else:
        # Plain Python module – stored as a workspace file, importable via sys.path
        payload["format"] = "AUTO"

    api("POST", "workspace/import", token, json=payload)
    print(f"  [OK] {local.name:<40} -> {ws_path}")


def get_current_user(token: str) -> str:
    try:
        result = api("GET", "preview/scim/v2/Me", token)
        return result.get("userName", "")
    except Exception as e:
        print(f"  [WARN] Could not resolve current user: {e}")
        return ""


def read_token(token_file: Path | None) -> str:
    env_token = os.getenv("DATABRICKS_TOKEN", "").strip().strip("'\"")
    if env_token:
        return env_token
    if token_file and token_file.exists():
        return token_file.read_text().strip().strip("'\"")
    return ""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Deploy fsr_pipeline to Databricks DEV workspace"
    )
    parser.add_argument(
        "--workspace-path", default="",
        help="Databricks workspace destination, e.g. /Users/you@ge.com/fsr_pipeline",
    )
    parser.add_argument(
        "--token-file", default="dbr_token.txt",
        help="Optional PAT token file (default: dbr_token.txt). DATABRICKS_TOKEN takes precedence.",
    )
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    token_file   = project_root / args.token_file if args.token_file else None
    token = read_token(token_file)
    if not token:
        if token_file is not None and token_file.exists():
            sys.exit(f"[ERROR] Token file is empty: {token_file}")
        sys.exit(
            "[ERROR] Databricks token not found. Set DATABRICKS_TOKEN or provide --token-file."
        )

    print(f"Connecting to {DATABRICKS_HOST} …")

    user = get_current_user(token)
    if not user:
        sys.exit(
            "[ERROR] Authentication failed. Check DATABRICKS_TOKEN or your token file."
        )
    print(f"[OK] Authenticated as: {user}")

    ws_root = args.workspace_path or f"/Users/{user}/fsr_pipeline"
    print(f"Deploying to workspace path: {ws_root}\n")

    # ── Create directories ────────────────────────────────────────────────────
    for sub in ("", "/src"):
        mkdirs(ws_root + sub, token)

    # ── Upload run_pipeline.py as a notebook ─────────────────────────────────
    nb = project_root / "run_pipeline.py"
    if nb.exists():
        upload(nb, f"{ws_root}/run_pipeline", token, as_notebook=True)
    else:
        print(f"  [WARN] run_pipeline.py not found – skipping notebook upload")

    # ── Upload src/*.py as plain workspace files ──────────────────────────────
    src_dir = project_root / "src"
    for py in sorted(src_dir.glob("*.py")):
        stem = py.stem
        if stem.startswith("_") or stem in SKIP_SRC:
            continue
        upload(py, f"{ws_root}/src/{py.name}", token, as_notebook=False)

    # ── Upload run_evaluation.py as a notebook ─────────────────────────────────
    eval_nb = project_root / "run_evaluation.py"
    if eval_nb.exists():
        upload(eval_nb, f"{ws_root}/run_evaluation", token, as_notebook=True)

    # ── Upload SSL cert if present ────────────────────────────────────────────
    cert = project_root / "GE_Enterprise_Root_CA_2_1.crt"
    if cert.exists():
        upload(cert, f"{ws_root}/GE_Enterprise_Root_CA_2_1.crt", token)

    # ── Upload Excel data files for evaluation ────────────────────────────────
    for xlsx_name in (
        "Heat Map - Unified Structure v0.1.xlsx",
        "FSR_citations_processed_20260305_135321.xlsx",
    ):
        xlsx = project_root / xlsx_name
        if xlsx.exists():
            upload(xlsx, f"{ws_root}/{xlsx_name}", token)
        else:
            print(f"  [WARN] {xlsx_name} not found - evaluation may not work")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Deployment complete")
    print(f"{'='*60}")
    print(f"Open notebooks:")
    print(f"  Pipeline:   {DATABRICKS_HOST}/#workspace{ws_root}/run_pipeline")
    print(f"  Evaluation: {DATABRICKS_HOST}/#workspace{ws_root}/run_evaluation")
    print()
    print(f"Next steps:")
    print(f"  1. Open the notebook and attach cluster: ai-pw-ser-ds-dev-apc")
    print(f"  2. (First time) Create secret scope with your API key:")
    print(f"       databricks secrets create-scope fsr-pipeline")
    print(f"       databricks secrets put-secret fsr-pipeline LITELLM_API_KEY --string-value <key>")
    print(f"  3. Confirm VS_ENDPOINT_NAME with the platform team and set it")
    print(f"     in the notebook's VS_ENDPOINT_OVERRIDE cell if needed")
    print(f"  4. Run all cells")


if __name__ == "__main__":
    main()
