"""Guardrail contracts and decision types.

Guardrails are pluggable input/output checks composed around a Generator at
serving time. They are not part of any batch pipeline job.

Split into two protocols so an implementation only takes on what it actually
checks (a PII redactor cares about output; a prompt-injection classifier cares
about input; some checks do both).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class GuardrailAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REWRITE = "rewrite"


@dataclass(frozen=True)
class GuardrailDecision:
    action: GuardrailAction
    reason: str = ""
    rewritten_text: str | None = None
    violated_rules: list[str] = field(default_factory=list)
    detail: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class InputGuardrail(Protocol):
    """Check a user query before it reaches the generator.

    Implementations: prompt-injection classifier, topic/scope classifier,
    Llama Guard, regex blocklist, etc.
    """

    name: str

    def check_input(self, query: str) -> GuardrailDecision: ...


@runtime_checkable
class OutputGuardrail(Protocol):
    """Check a generated answer before it returns to the caller.

    Implementations: toxicity classifier, PII redactor, policy-judge,
    citation validator, etc.
    """

    name: str

    def check_output(self, answer: str, query: str) -> GuardrailDecision: ...
