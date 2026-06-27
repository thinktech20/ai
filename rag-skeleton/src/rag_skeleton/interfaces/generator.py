"""Generator contract — query + retrieved context -> answer.

The LLM call layer of a RAG flow. Like the retriever, this is a serving-side
component, not used by batch pipeline jobs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..types import GenerationResult, RetrievedChunk


@dataclass(frozen=True)
class GeneratorConfig:
    model: str
    model_version: str
    options: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Generator(Protocol):
    """Produce an answer grounded in retrieved context.

    Implementations: Databricks-hosted foundation models, external LLM clients,
    fine-tuned domain models, etc.
    """

    config: GeneratorConfig

    def generate(
        self, query: str, context: list[RetrievedChunk]
    ) -> GenerationResult: ...
