"""Simple MLflow logging wrapper for FSR v2 experiments.

Logs experiment tracking params (strategy, model, etc.) and basic metrics
(chunks written, success/failure rates, timing).

Can be extended later with more detailed metrics and nested runs.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger("fsr.v2.mlflow_logger")


def _resolve_experiment_path(env_var: str, fallback_name: str) -> str:
    """Return a valid Databricks MLflow experiment path.

    Databricks requires an absolute workspace path (e.g. /Shared/...).
    """
    configured = os.getenv(env_var, "").strip()
    if configured:
        return configured if configured.startswith("/") else f"/Shared/{configured}"
    return f"/Shared/{fallback_name}"


def log_p1_experiment_start(
    llm_model: str,
    llm_prompt_version: str,
    pipeline_version: str,
    run_id: str | None = None,
    extractor_method: str = "pypdf2_v1.0",
    preprocess_method: str = "preprocessor_v2_final",
) -> dict:
    """Log P1 (metadata extraction) experiment parameters.

    Args:
        llm_model: LLM model name (e.g. gpt-4-turbo, claude-3-sonnet)
        llm_prompt_version: Prompt template version (v1, v2_with_hints, etc.)
        pipeline_version: Overall pipeline version
        run_id: Unique run identifier for grouping
        extractor_method: Text extraction method
        preprocess_method: Preprocessor version

    Returns:
        dict with run start time (for duration calculation later)
    """
    try:
        import mlflow  # noqa: PLC0415
    except ImportError:
        log.warning("MLflow not available; skipping experiment logging")
        return {"start_time": time.time()}

    try:
        mlflow.set_experiment(
            _resolve_experiment_path("FSR_MLFLOW_EXPERIMENT_P1", "fsr_v2_p1_metadata_extraction")
        )
        mlflow.start_run(run_name=f"p1_{run_id}" if run_id else None)
        mlflow.log_params({
            "extractor_method": extractor_method,
            "preprocess_method": preprocess_method,
            "llm_model": llm_model,
            "llm_prompt_version": llm_prompt_version,
            "pipeline_version": pipeline_version,
            "run_id": run_id or "unset",
        })
        log.info(f"MLflow P1 run started: {llm_model} + {llm_prompt_version}")
    except Exception as e:
        log.warning(f"MLflow P1 logging failed: {e}")

    return {"start_time": time.time()}


def log_p1_experiment_end(
    start_context: dict,
    docs_processed: int = 0,
    docs_succeeded: int = 0,
    docs_failed: int = 0,
    errors: dict | None = None,
) -> None:
    """Log P1 experiment results.

    Args:
        start_context: dict returned from log_p1_experiment_start
        docs_processed: total documents processed
        docs_succeeded: documents with successful metadata extraction
        docs_failed: documents that failed
        errors: dict of {doc_id: error_message} for failed docs
    """
    try:
        import mlflow  # noqa: PLC0415
    except ImportError:
        return

    try:
        elapsed = time.time() - start_context.get("start_time", time.time())
        success_rate = docs_succeeded / max(docs_processed, 1)

        mlflow.log_metrics({
            "docs_processed": docs_processed,
            "docs_succeeded": docs_succeeded,
            "docs_failed": docs_failed,
            "success_rate": success_rate,
            "duration_seconds": elapsed,
        })

        if errors:
            # Log sample of error messages as artifact
            error_summary = "\n".join([f"{did}: {msg[:100]}" for did, msg in list(errors.items())[:10]])
            mlflow.log_text(error_summary, "error_samples.txt")

        mlflow.end_run()
        log.info(f"MLflow P1 run ended: {docs_succeeded}/{docs_processed} succeeded ({100*success_rate:.1f}%) in {elapsed:.1f}s")
    except Exception as e:
        log.warning(f"MLflow P1 end logging failed: {e}")


def log_p2_experiment_start(
    chunking_strategy: str,
    embedding_model: str,
    merge_strategy: str,
    region_attribution_method: str,
    pipeline_version: str,
    run_id: str | None = None,
    chunk_size: int = 0,
    chunk_overlap: int = 0,
) -> dict:
    """Log P2 (chunking & embedding) experiment parameters.

    Args:
        chunking_strategy: Strategy used (recursive, markdown, section, etc.)
        embedding_model: Embedding model (text-embedding-3-large, etc.)
        merge_strategy: Merge logic version
        region_attribution_method: Region matching method
        pipeline_version: Overall pipeline version
        run_id: Unique run identifier
        chunk_size: Target chunk size
        chunk_overlap: Chunk overlap in characters

    Returns:
        dict with run start time
    """
    try:
        import mlflow  # noqa: PLC0415
    except ImportError:
        log.warning("MLflow not available; skipping experiment logging")
        return {"start_time": time.time()}

    try:
        mlflow.set_experiment(
            _resolve_experiment_path("FSR_MLFLOW_EXPERIMENT_P2", "fsr_v2_p2_chunking_embedding")
        )
        mlflow.start_run(run_name=f"p2_{chunking_strategy}_{run_id}" if run_id else None)
        mlflow.log_params({
            "chunking_strategy": chunking_strategy,
            "embedding_model": embedding_model,
            "merge_strategy": merge_strategy,
            "region_attribution_method": region_attribution_method,
            "pipeline_version": pipeline_version,
            "run_id": run_id or "unset",
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        })
        log.info(f"MLflow P2 run started: {chunking_strategy} + {embedding_model}")
    except Exception as e:
        log.warning(f"MLflow P2 logging failed: {e}")

    return {"start_time": time.time()}


def log_p2_experiment_end(
    start_context: dict,
    docs_succeeded: int = 0,
    docs_failed: int = 0,
    chunks_written: int = 0,
    embedding_dimension: int = 0,
    embed_failures: int = 0,
) -> None:
    """Log P2 experiment results.

    Args:
        start_context: dict returned from log_p2_experiment_start
        docs_succeeded: documents with successful chunking
        docs_failed: documents that failed
        chunks_written: total chunks written to table
        embedding_dimension: actual embedding vector dimension
        embed_failures: number of chunks that failed embedding
    """
    try:
        import mlflow  # noqa: PLC0415
    except ImportError:
        return

    try:
        elapsed = time.time() - start_context.get("start_time", time.time())
        docs_total = docs_succeeded + docs_failed
        success_rate = docs_succeeded / max(docs_total, 1)
        embed_success_rate = 1.0 if embed_failures == 0 else (chunks_written / max(chunks_written + embed_failures, 1))

        mlflow.log_metrics({
            "docs_succeeded": docs_succeeded,
            "docs_failed": docs_failed,
            "docs_total": docs_total,
            "success_rate": success_rate,
            "chunks_written": chunks_written,
            "embedding_dimension": embedding_dimension,
            "embed_failures": embed_failures,
            "embed_success_rate": embed_success_rate,
            "duration_seconds": elapsed,
        })

        mlflow.end_run()
        log.info(f"MLflow P2 run ended: {docs_succeeded}/{docs_total} docs ({100*success_rate:.1f}%), "
                 f"{chunks_written} chunks, {embedding_dimension}D embeddings in {elapsed:.1f}s")
    except Exception as e:
        log.warning(f"MLflow P2 end logging failed: {e}")
