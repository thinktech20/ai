"""Serving-side composition utilities.

This package is where Retriever + Generator + Guardrails get composed into
the shape that a PyFunc + Model Serving endpoint will eventually wrap.

Kept separate from `jobs/` (which is batch-only) and from `interfaces/` (which
holds protocols, not concrete composition).
"""
