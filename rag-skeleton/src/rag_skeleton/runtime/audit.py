"""Pipeline run audit write contract.

Every job opens and closes an audit row tied to a pipeline_run_id so operators
can see one row per (run, job) with timing, counts, and outcome.

First-iteration scope: most of what this layer captures is also captured by
MLflow runs (see runtime/tracking.py). This contract is kept so the team has a
SQL-joinable audit table alongside Silver/Gold/validation tables; once MLflow
coverage is validated in production, this layer can be dropped or replaced
with a Delta view over MLflow runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class AuditOpen:
    pipeline_run_id: str
    job_name: str
    run_mode: str
    input_scope: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditClose:
    pipeline_run_id: str
    job_name: str
    status: str  # success | partial_success | failed
    counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class AuditWriter(Protocol):
    def open(self, audit: AuditOpen) -> None: ...

    def close(self, audit: AuditClose) -> None: ...
