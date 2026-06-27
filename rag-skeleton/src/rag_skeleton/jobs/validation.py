"""Job E: Validation and quality gates.

Reads Silver + Gold for documents that have completed chunking, runs the
configured Validator, and writes findings to the validation results table.
"""
from __future__ import annotations

from ..config import PipelineConfig


def run(config: PipelineConfig, pipeline_run_id: str) -> None:
    """Validate eligible documents and persist findings.

    Steps:
      1. Select documents where chunk_status='completed' and not yet validated
         for this run.
      2. For each document:
         - load ExtractedMetadata + ChunkWithEmbedding rows
         - call Validator.validate(...)
         - persist findings to til_validation_results
      3. Log pass/review/fail counts to MLflow.
      4. Close audit row.
    """
    raise NotImplementedError
