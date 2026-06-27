"""Validator contract — quality gates over Silver and Gold outputs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..types import ChunkWithEmbedding, ExtractedMetadata


@dataclass(frozen=True)
class ValidationFinding:
    document_id: str
    rule: str
    status: str  # pass | review | fail
    detail: dict[str, Any]


@runtime_checkable
class Validator(Protocol):
    """Validate extracted metadata and chunks against rules and thresholds.

    Implementations are expected to be additive — new rules slot in without
    changing the validator surface.
    """

    def validate(
        self,
        metadata: ExtractedMetadata,
        chunks: list[ChunkWithEmbedding],
    ) -> list[ValidationFinding]: ...
