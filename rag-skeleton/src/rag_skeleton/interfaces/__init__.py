"""Replaceable component contracts.

Each interface is a Protocol so adapters can be plugged in without inheritance.
Keep these import-light: no Spark, no Databricks SDK.

Two groupings:
  Batch indexing:  DocumentParser, Chunker, Embedder, VectorStoreSink, Validator, Evaluator
  Serving / RAG:   Retriever, Generator, InputGuardrail, OutputGuardrail
"""
from .parser import DocumentParser
from .chunker import Chunker
from .embedder import Embedder
from .vector_store import VectorStoreSink
from .validator import Validator
from .evaluator import Evaluator
from .retriever import Retriever, RetrievalQuery
from .generator import Generator, GeneratorConfig
from .guardrail import (
    GuardrailAction,
    GuardrailDecision,
    InputGuardrail,
    OutputGuardrail,
)

__all__ = [
    "DocumentParser",
    "Chunker",
    "Embedder",
    "VectorStoreSink",
    "Validator",
    "Evaluator",
    "Retriever",
    "RetrievalQuery",
    "Generator",
    "GeneratorConfig",
    "GuardrailAction",
    "GuardrailDecision",
    "InputGuardrail",
    "OutputGuardrail",
]
