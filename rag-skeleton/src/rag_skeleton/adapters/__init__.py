"""Concrete adapters live here.

Convention:
  parsers/        — implementations of interfaces.parser.DocumentParser
  chunkers/       — implementations of interfaces.chunker.Chunker
  embedders/      — implementations of interfaces.embedder.Embedder
  vector_stores/  — implementations of interfaces.vector_store.VectorStoreSink

Adapters are the only place Spark, Databricks SDK, or external SDK imports
should appear. Keep the rest of the package import-light.
"""
