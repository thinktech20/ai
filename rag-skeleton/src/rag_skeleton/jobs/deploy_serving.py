"""Job H: Deploy/Update serving endpoint shell.

Skeleton for packaging and deploying the retrieval+generation runtime to a
serving surface (for example, PyFunc + UC + Databricks Model Serving).

No deployment logic is implemented here; this module only defines the contract.
"""
from __future__ import annotations

from ..config import PipelineConfig


def run(config: PipelineConfig, deployment_run_id: str) -> None:
    """Deploy or update the serving endpoint.

    Steps (to be implemented by adapters):
      1. Open audit row (job_til_deploy_serving) and MLflow run.
      2. Package serving artifacts (retriever+generator composition contract).
      3. Register/update model version and endpoint configuration.
      4. Run smoke tests and rollback-on-failure checks.
      5. Record deployed version, endpoint URL/ID, and close audit row.
    """
    raise NotImplementedError
