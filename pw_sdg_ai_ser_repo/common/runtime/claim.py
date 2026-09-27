"""Status-driven row-claim contract for batch processing stages."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ClaimRequest:
    table_name: str
    status_column: str
    eligible_status: str
    claim_status: str
    batch_size: int
    run_id: str


@dataclass(frozen=True)
class ClaimedRow:
    document_id: str
    unique_key: str
    payload: dict


@runtime_checkable
class WorkClaim(Protocol):
    def claim(self, request: ClaimRequest) -> list[ClaimedRow]: ...

    def mark_completed(self, table_name: str, status_column: str, document_ids: list[str]) -> None: ...

    def mark_failed(
        self,
        table_name: str,
        status_column: str,
        document_ids: list[str],
        error_code: str,
        error_message: str,
    ) -> None: ...
