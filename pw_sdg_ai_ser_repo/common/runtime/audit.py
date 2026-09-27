"""Run-audit contract for SQL-joinable job outcomes."""
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
    status: str
    counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class AuditWriter(Protocol):
    def open(self, audit: AuditOpen) -> None: ...

    def close(self, audit: AuditClose) -> None: ...
