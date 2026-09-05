#!/usr/bin/env python
"""
Deploy the FSR scraping pipeline notebook to the Databricks DEV workspace.

Usage:
    python deploy_scraping.py
    python deploy_scraping.py --workspace-path /Users/you@ge.com/fsr_scraping

Uploads:
  - run_scraping_pipeline.py  (the original DS-team notebook)
  - run_scraping_interactive.py  (the safe dev wrapper)
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
REPO_ROOT = PROJECT_ROOT.parent.parent  # dbx/
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)

DATABRICKS_HOST = "https://gevernova-ai-dev-dbr.cloud.databricks.com"


class _NoVerifyAdapter(HTTPAdapter):
    def send(self, request, **kwargs):
        kwargs["verify"] = False
        return super().send(request, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)


_session = requests.Session()
_session.mount("https://", _NoVerifyAdapter())


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def api(method: str, endpoint: str, token: str, **kwargs) -> dict:
    url = f"{DATABRICKS_HOST}/api/2.0/{endpoint}"
    resp = _session.request(method, url, headers=_headers(token), **kwargs)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"API {method.upper()} /{endpoint} → HTTP {resp.status_code}\n{resp.text[:600]}")
    return resp.json() if resp.text.strip() else {}


def mkdirs(path: str, token: str):
    try:
        api("POST", "workspace/mkdirs", token, json={"path": path})
    except Exception as e:
        print(f"  [WARN] mkdirs({path}): {e}")


def upload_notebook(local_path: Path, ws_path: str, token: str):
    content = local_path.read_bytes()
    b64 = base64.b64encode(content).decode()
    api(
        "POST",
        "workspace/import",
        token,
        json={
            "path": ws_path,
            "format": "SOURCE",
            "language": "PYTHON",
            "content": b64,
            "overwrite": True,
        },
    )
    print(f"  ✓ {local_path.name} → {ws_path}")


def get_token() -> str:
    token = os.getenv("DATABRICKS_TOKEN", "").strip()
    if token:
        return token
    token_file = Path.home() / ".databricks_token"
    if token_file.exists():
        return token_file.read_text().strip()
    print("ERROR: Set DATABRICKS_TOKEN or create ~/.databricks_token", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-path",
        default=None,
        help="Workspace folder, e.g. /Users/you@ge.com/fsr_scraping",
    )
    args = parser.parse_args()

    token = get_token()

    if args.workspace_path:
        ws_dir = args.workspace_path.rstrip("/")
    else:
        me = api("GET", "preview/scim/v2/Me", token)
        email = me.get("userName", me.get("emails", [{}])[0].get("value", "unknown"))
        ws_dir = f"/Users/{email}/fsr_scraping"

    print(f"Target: {ws_dir}")
    mkdirs(ws_dir, token)

    # Upload original pipeline notebook
    original = REPO_ROOT / "poc" / "ds-experimentation-code" / "fsr_scraping" / "run_scraping_pipeline.py"
    if original.exists():
        upload_notebook(original, f"{ws_dir}/run_scraping_pipeline", token)
    else:
        print(f"  [WARN] Not found: {original}")

    # Upload the interactive wrapper
    interactive = PROJECT_ROOT / "run_scraping_interactive.py"
    if interactive.exists():
        upload_notebook(interactive, f"{ws_dir}/run_scraping_interactive", token)
    else:
        print(f"  [WARN] Not found: {interactive}")

    print("\nDone. Open in Databricks:")
    print(f"  {DATABRICKS_HOST}/#workspace{ws_dir}")


if __name__ == "__main__":
    main()
