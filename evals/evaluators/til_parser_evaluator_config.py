"""TIL-specific parser evaluator configuration.

Defines regex patterns and field labels for TIL extraction evaluation.
Used by ParserEvaluator to measure extraction quality specific to TIL documents.
"""
from __future__ import annotations

import re

# Proxy signal only: counts mentions of common required TIL field labels in
# extracted text. This is not a semantic validator; it is used for relative
# parser comparison in Process 1 (P1).
TIL_REQUIRED_FIELDS_RE = re.compile(
    r"\b(TIL\s*[\d\-R]+|revision|compliance|timing.?code|issue.?date|"
    r"title|scope|recommendation|applicable)\b",
    re.IGNORECASE,
)

# Proxy signal only: counts simple numeric/formula-like expressions that should
# survive extraction (comparators, multiplications, percentages).
TIL_FORMULA_RE = re.compile(
    r"[=><±]\s*[\d\.]+|[\d\.]+\s*[×x\*]\s*[\d\.]+|\d+\s*%",
    re.IGNORECASE,
)
