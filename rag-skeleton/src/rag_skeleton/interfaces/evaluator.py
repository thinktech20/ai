"""Evaluator contract — method-comparison metrics over a gold dataset."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, runtime_checkable


@dataclass(frozen=True)
class EvaluationCase:
    """One evaluation example: input + expected output."""

    case_id: str
    inputs: dict[str, Any]
    expected: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationResult:
    """One row written to the evaluation results table."""

    evaluation_run_id: str
    case_id: str
    method_name: str
    method_version: str
    metrics: dict[str, float]
    detail: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Evaluator(Protocol):
    """Score a candidate method against a gold dataset.

    Implementations: judge-based scorers (RetrievalGroundedness, RelevanceToQuery,
    Safety, Guidelines), exact-match metric scorers, custom domain scorers.
    """

    def evaluate(
        self,
        cases: Iterable[EvaluationCase],
        method_name: str,
        method_version: str,
    ) -> Iterable[EvaluationResult]: ...
