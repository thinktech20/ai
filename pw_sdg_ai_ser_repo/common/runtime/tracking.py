"""MLflow run tracking contract for pipeline stages."""
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


class RunHandle:
    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        raise NotImplementedError

    def log_metrics(self, metrics: dict[str, float]) -> None:
        raise NotImplementedError

    def set_tag(self, key: str, value: str) -> None:
        raise NotImplementedError


@contextmanager
def track_job_run(_ctx: JobRunContext) -> Iterator[RunHandle]:
    """Open an MLflow run and yield a run handle.

    Left as a contract in this scaffold; concrete implementation can be added
    once job wiring starts.
    """
    raise NotImplementedError
