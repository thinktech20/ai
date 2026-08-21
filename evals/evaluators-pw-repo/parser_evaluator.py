"""Generic Process 1 parser evaluator.

Runs a DocumentParser over a set of EvaluationCases and produces
EvaluationResult rows compatible with Delta table schemas.

Metrics computed (proxy — no gold labels required):
  - char_count           : total characters extracted
  - word_count           : total words extracted
  - required_field_hits  : count of required field name/label occurrences (configurable regex)
  - table_count          : number of tables extracted
  - formula_hits         : count of formula/numeric expression occurrences (configurable regex)
  - noise_ratio          : duplicate line ratio (boilerplate indicator)
  - latency_s            : parse time in seconds

When gold labels are supplied in EvaluationCase.expected, additional
exact-match metrics are computed:
  - field_exact_match    : fraction of expected fields matched exactly

Usage:
    from common.evaluators import ParserEvaluator
    from contracts.interfaces.parsers import DocumentParser

    parser = DocumentParser()  # your concrete parser
    evaluator = ParserEvaluator(
        parser=parser,
        evaluation_run_id="eval_run_001",
        required_fields_re=your_required_fields_pattern,  # optional
        formula_re=your_formula_pattern,  # optional
    )
    results = evaluator.evaluate(cases, method_name="foundation", method_version="v0")
"""
from __future__ import annotations

import re
import time
from typing import Any, Iterable

from common.constants import METRIC_GROUP_EXTRACTION, PROCESS_1
from contracts.interfaces.evaluators import EvaluationCase, EvaluationResult, Evaluator
from contracts.interfaces.parsers import DocumentParser
from contracts.types.entities import DocumentReference


# Default patterns — can be overridden by caller or domain-specific subclass
_DEFAULT_REQUIRED_FIELDS_RE = re.compile(r"\b(title|section|field|value)\b", re.IGNORECASE)
# Counts formula and numeric expressions found in extracted text as a signal of extraction quality
_DEFAULT_FORMULA_RE = re.compile(
    r"[=><±]\s*[\d\.]+|[\d\.]+\s*[×x\*/]\s*[\d\.]+|\d+\s*%|[\d\.]+\s*/\s*[\d\.]+",
    re.IGNORECASE,
)


def _to_searchable_text(value: Any) -> str:
    """Flatten nested parser output into plain text for regex scoring."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_to_searchable_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_to_searchable_text(v) for v in value)
    return str(value)


class ParserEvaluator(Evaluator):
    """Generic evaluator for Process 1: wraps a DocumentParser and measures extraction quality.
    
    Metrics are proxy signals useful for relative parser comparison. Regex patterns
    are configurable to support any document type (TILs, manuals, specifications, etc.).
    """

    STAGE_NAME = PROCESS_1
    METRIC_GROUP = METRIC_GROUP_EXTRACTION

    @staticmethod
    def _build_formula_corpus(text: str, profile: Any) -> str:
        """Build a parser-agnostic text corpus for formula counting.

        We include structured table/element content so parsers that return tables
        as HTML/JSON are not unfairly penalized versus plain-text parsers.
        """
        parts: list[str] = [text]

        fields = getattr(profile, "fields", {}) or {}
        raw_tables = fields.get("raw_tables")
        if raw_tables:
            parts.append(_to_searchable_text(raw_tables))

        elements = getattr(profile, "elements", []) or []
        if elements:
            parts.append(_to_searchable_text(elements))

        # Normalize whitespace so line-wrapped expressions match more consistently.
        return re.sub(r"\s+", " ", "\n".join(p for p in parts if p).strip())

    def __init__(
        self,
        parser: DocumentParser,
        evaluation_run_id: str,
        required_fields_re: re.Pattern | None = None,
        formula_re: re.Pattern | None = None,
    ) -> None:
        """Initialize the parser evaluator.
        
        Args:
            parser: DocumentParser instance to evaluate.
            evaluation_run_id: Unique identifier for this evaluation run.
            required_fields_re: Compiled regex to count required field mentions.
                                If None, uses sensible defaults.
            formula_re: Compiled regex to count formula/numeric expressions.
                        If None, uses sensible defaults.
        """
        self.parser = parser
        self.evaluation_run_id = evaluation_run_id
        self.required_fields_re = required_fields_re or _DEFAULT_REQUIRED_FIELDS_RE
        self.formula_re = formula_re or _DEFAULT_FORMULA_RE

    def evaluate(
        self,
        cases: Iterable[EvaluationCase],
        method_name: str,
        method_version: str,
    ) -> Iterable[EvaluationResult]:
        """Evaluate a parser over a set of evaluation cases.
        
        Args:
            cases: Iterable of EvaluationCase (each with case_id, inputs, expected).
            method_name: Parser method name (e.g., "foundation", "pdfplumber").
            method_version: Parser version string (e.g., "v0").
            
        Yields:
            EvaluationResult rows (one per metric per case).
        """
        results: list[EvaluationResult] = []
        for case in cases:
            doc_ref = DocumentReference(
                document_id=case.case_id,
                source_path=case.inputs.get("source_path", ""),
                source_hash=case.inputs.get("source_hash", ""),
            )
            payload: bytes = case.inputs.get("pdf_bytes", b"")

            t0 = time.time()
            try:
                profile = self.parser.parse(doc_ref, payload)
                status = "success"
                error = ""
            except Exception as exc:
                profile = None
                status = "error"
                error = str(exc)
            latency_s = round(time.time() - t0, 3)

            text = ""
            formula_corpus = ""
            table_count = 0
            if profile is not None:
                text = str(profile.fields.get("raw_text") or "")
                formula_corpus = self._build_formula_corpus(text=text, profile=profile)
                explicit_table_count = profile.fields.get("table_count")
                raw_tables = profile.fields.get("raw_tables")

                if isinstance(explicit_table_count, (int, float)):
                    table_count = int(explicit_table_count)
                elif isinstance(raw_tables, list):
                    table_count = len(raw_tables)
                else:
                    table_count = len(profile.elements or [])

            lines = [l.strip() for l in text.splitlines() if l.strip()]
            dup_lines = len(lines) - len(set(lines))

            proxy_metrics = {
                "char_count":          float(len(text)),
                "word_count":          float(len(text.split())),
                "required_field_hits": float(len(self.required_fields_re.findall(text))),
                "table_count":         float(table_count),
                "formula_hits":        float(len(self.formula_re.findall(formula_corpus))),
                "noise_ratio":         round(dup_lines / max(len(lines), 1), 4),
                "latency_s":           latency_s,
                "parse_success":       1.0 if status == "success" else 0.0,
            }

            # Gold-label metrics when expected fields are supplied.
            expected_fields: dict = case.expected.get("fields", {})
            if expected_fields and profile is not None:
                extracted_fields = profile.fields or {}
                matched = sum(
                    1 for k, v in expected_fields.items()
                    if str(extracted_fields.get(k, "")).strip().lower()
                    == str(v).strip().lower()
                )
                proxy_metrics["field_exact_match"] = round(
                    matched / len(expected_fields), 4
                )

            detail_base = {"status": status, "error": error}
            for metric_name, metric_value in proxy_metrics.items():
                results.append(
                    EvaluationResult(
                        evaluation_run_id=self.evaluation_run_id,
                        case_id=case.case_id,
                        stage_name=self.STAGE_NAME,
                        method_name=method_name,
                        method_version=method_version,
                        metric_group=self.METRIC_GROUP,
                        metric_name=metric_name,
                        metric_value=metric_value,
                        detail=detail_base,
                    )
                )
        return results
