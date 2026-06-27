"""Status-driven row-claim contract (FSR-style queue, Delta-backed).

Concrete adapters use a guarded MERGE/UPDATE to flip rows from `pending` to
`in_progress` atomically. The skeleton only defines the surface so jobs can be
written against it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..status import StageStatus


@dataclass(frozen=True)
class ClaimRequest:
    table: str
    status_column: str
    eligible_status: StageStatus
    batch_size: int
    run_id: str
    max_retries: int
    retry_count_column: str | None = None


@dataclass(frozen=True)
class ClaimedRow:
    document_id: str
    unique_key: str
    payload: dict


@runtime_checkable
class WorkClaim(Protocol):
    """Claim and release rows for a downstream stage."""

    def claim(self, request: ClaimRequest) -> list[ClaimedRow]: ...

    def mark_completed(self, table: str, status_column: str, document_ids: list[str]) -> None: ...

    def mark_failed(
        self,
        table: str,
        status_column: str,
        document_ids: list[str],
        error_code: str,
        error_message: str,
    ) -> None: ...

    def reset_stale_in_progress(
        self, table: str, status_column: str, stale_minutes: int
    ) -> int: ...
