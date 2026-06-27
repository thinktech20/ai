"""Pipeline configuration dataclasses.

A real deployment loads these from YAML/JSON and passes them to job entry points.
The skeleton only defines the shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParserConfig:
    name: str
    version: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkerConfig:
    name: str
    version: str
    strategy: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbedderConfig:
    model: str
    model_version: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VectorStoreConfig:
    name: str
    index: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeConfig:
    """Run-mode and queue-claim controls shared across jobs."""

    run_mode: str = "incremental"  # incremental | backfill | reprocess
    batch_size: int = 100
    max_retries: int = 3
    stale_claim_minutes: int = 30


@dataclass(frozen=True)
class PipelineConfig:
    parser: ParserConfig
    chunker: ChunkerConfig
    embedder: EmbedderConfig
    vector_store: VectorStoreConfig
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    tables: dict[str, str] = field(default_factory=dict)
