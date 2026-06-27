"""Job 7: Evaluation (on-demand).

Runs configured Evaluator(s) over a gold dataset for method comparison and
persists results to til_evaluation_results plus MLflow.
"""
from __future__ import annotations

from ..config import PipelineConfig


def run(config: PipelineConfig, evaluation_run_id: str) -> None:
    """Score a candidate method on the gold dataset.

    Steps:
      1. Open audit row (job_evaluation).
      2. Open MLflow run with method_name and method_version as parameters.
      3. Load gold cases for the configured dataset_slice.
      4. Call Evaluator.evaluate(...) and persist EvaluationResult rows to
         til_evaluation_results.
      5. Log aggregate metrics (per metric group) to MLflow.
      6. Close audit row.
    """
    raise NotImplementedError
