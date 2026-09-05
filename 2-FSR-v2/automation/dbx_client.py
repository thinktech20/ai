"""Thin Databricks REST client for the FSR v2 verification driver.

Stdlib only, so this runs anywhere without a venv. Reads host/token from
~/.databrickscfg so no secrets live in this folder.
"""

import configparser
import json
import os
import time
import urllib.error
import urllib.request


class DbxClient:
    def __init__(self, profile="dev-dbr-profile", warehouse_id=None):
        cfg = configparser.ConfigParser()
        cfg.read(os.path.expanduser("~/.databrickscfg"))
        if profile not in cfg:
            raise SystemExit(f"profile '{profile}' not found in ~/.databrickscfg")
        self.host = cfg[profile]["host"].rstrip("/")
        self.token = cfg[profile]["token"]
        self.warehouse_id = warehouse_id

    def _call(self, method, path, payload=None):
        url = f"{self.host}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise SystemExit(f"{method} {path} -> {e.code}: {e.read().decode()[:500]}")

    # --- SQL -------------------------------------------------------------

    def sql(self, statement):
        """Run a statement, return list of row-lists (strings). Polls until done."""
        if not self.warehouse_id:
            raise SystemExit("warehouse_id required for SQL")
        r = self._call(
            "POST",
            "/api/2.0/sql/statements",
            {
                "warehouse_id": self.warehouse_id,
                "statement": statement,
                "wait_timeout": "30s",
            },
        )
        sid = r["statement_id"]
        while r["status"]["state"] in ("PENDING", "RUNNING"):
            time.sleep(2)
            r = self._call("GET", f"/api/2.0/sql/statements/{sid}")
        state = r["status"]["state"]
        if state != "SUCCEEDED":
            msg = r["status"].get("error", {}).get("message", state)
            raise RuntimeError(f"SQL failed: {msg}\n  statement: {statement[:300]}")
        return r.get("result", {}).get("data_array", []) or []

    def scalar(self, statement):
        rows = self.sql(statement)
        return rows[0][0] if rows and rows[0] else None

    # --- Jobs ------------------------------------------------------------

    def job_parameter_names(self, job_id):
        """Parameter names the job declares. Anything else is rejected by run-now."""
        r = self._call("GET", f"/api/2.1/jobs/get?job_id={int(job_id)}")
        return [p["name"] for p in r.get("settings", {}).get("parameters", [])]

    def run_job(self, job_id, params):
        r = self._call(
            "POST",
            "/api/2.1/jobs/run-now",
            {"job_id": int(job_id), "job_parameters": params},
        )
        return r["run_id"]

    def submit_notebook(self, run_name, notebook_path, params):
        """One-off serverless run of a notebook by path.

        Used for sandbox mode. These have no job-level parameters, so widgets are
        fed via base_parameters rather than job_parameters.
        """
        r = self._call(
            "POST",
            "/api/2.1/jobs/runs/submit",
            {
                "run_name": run_name,
                "tasks": [{
                    "task_key": "main",
                    "notebook_task": {
                        "notebook_path": notebook_path,
                        "base_parameters": params,
                    },
                }],
            },
        )
        return r["run_id"]

    def wait_for_run(self, run_id, poll=30, timeout=14400):
        """Block until the run reaches a terminal state. Returns the run object."""
        deadline = time.time() + timeout
        while True:
            r = self._call("GET", f"/api/2.1/jobs/runs/get?run_id={run_id}")
            state = r["state"]
            life = state.get("life_cycle_state")
            if life in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
                return r
            if time.time() > deadline:
                raise SystemExit(f"run {run_id} still {life} after {timeout}s")
            time.sleep(poll)

    def run_output(self, run_id):
        """Driver log text for a run. Descends into the first task of a multi-task run."""
        r = self._call("GET", f"/api/2.1/jobs/runs/get?run_id={run_id}")
        target = r.get("tasks", [{}])[0].get("run_id", run_id) if r.get("tasks") else run_id
        out = self._call("GET", f"/api/2.1/jobs/runs/get-output?run_id={target}")
        return out.get("logs") or out.get("error") or ""

    def run_url(self, run_id):
        return f"{self.host}/#job/run/{run_id}"
