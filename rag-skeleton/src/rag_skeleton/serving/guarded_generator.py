"""GuardedGenerator: a Generator decorator that runs input/output guardrails.

Composition pattern (no inheritance): wraps any Generator implementation,
applies a list of InputGuardrails before the LLM call and a list of
OutputGuardrails after. On BLOCK, returns a refusal GenerationResult instead
of calling/returning the generator output.

Skeleton scope: stub only. The orchestration shape is fixed; the policy for
constructing refusal messages and the behavior on REWRITE chains are left to
the implementation in the target repo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..interfaces.generator import Generator
from ..interfaces.guardrail import (
    GuardrailAction,
    InputGuardrail,
    OutputGuardrail,
)
from ..types import GenerationResult, RetrievedChunk


@dataclass
class GuardedGenerator:
    inner: Generator
    input_guardrails: list[InputGuardrail] = field(default_factory=list)
    output_guardrails: list[OutputGuardrail] = field(default_factory=list)

    def generate(
        self, query: str, context: list[RetrievedChunk]
    ) -> GenerationResult:
        """Run input guardrails -> inner.generate -> output guardrails.

        Expected behavior (to be implemented):
          1. For each input guardrail: call check_input(query).
             - ALLOW: continue
             - BLOCK: return a refusal GenerationResult with violated_rules
             - REWRITE: replace query with decision.rewritten_text and continue
          2. Call self.inner.generate(query, context).
          3. For each output guardrail: call check_output(answer, query).
             - ALLOW: continue
             - BLOCK: return a refusal GenerationResult
             - REWRITE: replace answer with decision.rewritten_text and continue
          4. Return final GenerationResult.
        """
        raise NotImplementedError


def compose_guardrails(
    generator: Generator,
    input_guardrails: Iterable[InputGuardrail] = (),
    output_guardrails: Iterable[OutputGuardrail] = (),
) -> GuardedGenerator:
    """Convenience factory."""
    return GuardedGenerator(
        inner=generator,
        input_guardrails=list(input_guardrails),
        output_guardrails=list(output_guardrails),
    )
