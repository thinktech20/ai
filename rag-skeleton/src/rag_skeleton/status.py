"""Per-stage status enum used by the FSR-style queuing pattern.

Each row in the Silver registry carries a status column per downstream stage.
Jobs claim work by querying these statuses; transitions are guarded.

Vector index sync is intentionally NOT a per-row stage. The sync job triggers
a table-wide Delta Sync against the configured Vector Search index (one API
call per run); validation gating happens before chunks land in the source
table. See jobs/vector_sync.py.
"""
from __future__ import annotations

from enum import Enum


class StageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# Status column names used across the registry table.
# Adapters/jobs reference these constants instead of string literals.
METADATA_STATUS = "metadata_status"
CHUNK_STATUS = "chunk_status"
