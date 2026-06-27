"""MLflow tracking wrapper used by every job.

Goal: every job execution becomes one MLflow run with a stable tag scheme so
runs can be linked back to the pipeline_run_audit row.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class JobRunContext:
    job_name: str
    pipeline_run_id: str
    environment: str
    parameters: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)


@contextmanager
def track_job_run(ctx: JobRunContext) -> Iterator["RunHandle"]:
    """Open an MLflow run for this job execution.

    Concrete implementation calls `mlflow.start_run`, sets standard tags
    (job_name, pipeline_run_id, environment), and logs `ctx.parameters`.
    """
    raise NotImplementedError


class RunHandle:
    """Handle returned inside the `track_job_run` context."""

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        raise NotImplementedError

    def log_metrics(self, metrics: dict[str, float]) -> None:
        raise NotImplementedError

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        raise NotImplementedError

    def set_tag(self, key: str, value: str) -> None:
        raise NotImplementedError
