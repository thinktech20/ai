"""Reusable helpers for Process 1 (P1) parser evaluation runs.

This module keeps notebook code thin by centralizing:
- EvaluationCase construction from PDF bytes
- Parser method comparison execution and result flattening
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from common.evaluators import ParserEvaluator
from common.parsers.factory import build_parser
from contracts.interfaces.evaluators import EvaluationCase
from silver.src.tils.evaluators.til_parser_evaluator_config import (
    TIL_FORMULA_RE,
    TIL_REQUIRED_FIELDS_RE,
)


def make_evaluation_run_id(prefix: str = "parser_eval") -> str:
    """Create a stable UTC run id for evaluation tracking."""
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def load_pdf_bytes(
    til_number: str,
    volume_path: str,
    local_sample_dir: str = "",
    dbutils: Any | None = None,
) -> tuple[bytes | None, str, str]:
    """Load a TIL PDF by number from volume or local sample directory.

    Returns:
        (pdf_bytes_or_none, source_label, message)
        source_label is one of: volume, local_sample, missing
    """
    til = (til_number or "").strip()
    if not til:
        return None, "missing", "empty til_number"

    # Common filename prefixes used in TIL documents.
    candidate_prefixes = [
        f"TIL {til}",
        f"TIL_{til}",
        f"TIL-{til}",
    ]

    # 1) Try direct filesystem reads from volume path.
    if volume_path:
        for prefix in candidate_prefixes:
            candidate_path = f"{volume_path.rstrip('/')}/{prefix}.pdf"
            try:
                return Path(candidate_path).read_bytes(), "volume", f"{candidate_path}"
            except Exception:
                pass

        # 2) If dbutils is available, list + copy matching file from volume.
        if dbutils is not None:
            try:
                entries = dbutils.fs.ls(volume_path)
                matched = None
                lower_prefixes = tuple(p.lower() for p in candidate_prefixes)
                for entry in entries:
                    name = entry.name.lower()
                    if name.endswith(".pdf") and name.startswith(lower_prefixes):
                        matched = entry.path
                        break
                if matched:
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp_path = tmp.name
                    try:
                        dbutils.fs.cp(matched, f"file:{tmp_path}", True)
                        return Path(tmp_path).read_bytes(), "volume", matched
                    finally:
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
            except Exception:
                pass

    # 3) Local sample directory fallback.
    if local_sample_dir:
        local_dir = Path(local_sample_dir)
        if local_dir.exists():
            matched_file = None
            lower_prefixes = tuple(p.lower() for p in candidate_prefixes)
            for file_path in local_dir.glob("*.pdf"):
                name = file_path.name.lower()
                if name.startswith(lower_prefixes):
                    matched_file = file_path
                    break
            if matched_file is not None:
                return matched_file.read_bytes(), "local_sample", str(matched_file)

    return None, "missing", f"No PDF found for TIL {til}"


def build_evaluation_cases(
    til_pdf_pairs: list[tuple[str, bytes]] | None = None,
    volume_path_prefix: str = "",
    *,
    til_numbers: list[str] | None = None,
    volume_path: str = "",
    local_sample_dir: str = "",
    dbutils: Any | None = None,
) -> list[EvaluationCase] | tuple[list[EvaluationCase], list[str]]:
    """Build EvaluationCase objects.

    Args:
        til_pdf_pairs: Optional list of (til_number, pdf_bytes) tuples
        volume_path_prefix: Optional prefix for source_path (e.g., volume path for documentation)
        til_numbers: Optional list of TIL numbers to resolve via load_pdf_bytes
        volume_path: Volume path used when til_numbers is provided
        local_sample_dir: Local fallback directory used when til_numbers is provided
        dbutils: Optional Databricks dbutils handle for volume access

    Returns:
        - If til_pdf_pairs is provided: List[EvaluationCase]
        - If til_numbers is provided: Tuple[List[EvaluationCase], List[str]] where
          second item is a list of skip messages for unresolved TILs.
    """
    # Backward-compatible notebook mode: resolve bytes from TIL numbers.
    if til_numbers is not None:
        resolved_pairs: list[tuple[str, bytes]] = []
        skips: list[str] = []
        for til in til_numbers:
            pdf_bytes, _, msg = load_pdf_bytes(
                til_number=til,
                volume_path=volume_path,
                local_sample_dir=local_sample_dir,
                dbutils=dbutils,
            )
            if pdf_bytes is None:
                skips.append(msg)
                continue
            resolved_pairs.append((til, pdf_bytes))

        cases = build_evaluation_cases(
            til_pdf_pairs=resolved_pairs,
            volume_path_prefix=volume_path or volume_path_prefix,
        )
        return cases, skips

    cases: list[EvaluationCase] = []
    for til_number, pdf_bytes in til_pdf_pairs or []:
        source_path = f"{volume_path_prefix.rstrip('/')}/TIL {til_number}.pdf" if volume_path_prefix else f"TIL {til_number}.pdf"

        cases.append(
            EvaluationCase(
                case_id=til_number,
                inputs={
                    "pdf_bytes": pdf_bytes,
                    "source_path": source_path,
                    "source": "volume" if volume_path_prefix else "provided",
                    "source_hash": hashlib.sha1(pdf_bytes).hexdigest(),
                },
                expected={},
            )
        )

    return cases


def run_method_comparison(
    cases: Iterable[EvaluationCase],
    parser_methods: Iterable[str],
    evaluation_run_id: str,
) -> list[dict[str, Any]]:
    """Run configured parser methods and return flattened result rows."""
    rows: list[dict[str, Any]] = []

    for method in parser_methods:
        parser = build_parser(method)
        evaluator = ParserEvaluator(
            parser=parser,
            evaluation_run_id=evaluation_run_id,
            required_fields_re=TIL_REQUIRED_FIELDS_RE,
            formula_re=TIL_FORMULA_RE,
        )
        results = list(
            evaluator.evaluate(
                cases=cases,
                method_name=method,
                method_version=parser.version,
            )
        )
        rows.extend(
            {
                "evaluation_run_id": result.evaluation_run_id,
                "til_number": result.case_id,
                "stage_name": result.stage_name,
                "method_name": result.method_name,
                "method_version": result.method_version,
                "metric_group": result.metric_group,
                "metric_name": result.metric_name,
                "metric_value": result.metric_value,
                "status": result.detail.get("status"),
                "error": result.detail.get("error"),
            }
            for result in results
        )

    return rows
