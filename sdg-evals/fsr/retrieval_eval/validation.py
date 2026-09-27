"""Probe and label validation rules for the FSR retrieval evaluation.

This module is intentionally separate from retriever policy so label decisions
can change without changing the retrieval implementations.
"""
from __future__ import annotations

import re
from typing import Any


def normalize_esn(value: Any) -> str:
    return str(value or "").strip().upper()


def normalize_id(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_page(value: Any) -> int:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d+", text):
        raise ValueError(f"page number must be a non-negative integer: {value!r}")
    return int(text)


def validate_probe_labels(
    *,
    esn: str,
    expected_document_ids: list[str],
    expected_cited_doc_pages: list[tuple[str, int]],
    expected_chunk_ids: list[str],
    chunk_table_version: str | None,
) -> None:
    if not normalize_esn(esn):
        raise ValueError("esn is required")
    if not expected_document_ids and not expected_cited_doc_pages:
        raise ValueError("at least one document or cited page label is required")

    normalized_docs = [normalize_id(value) for value in expected_document_ids]
    if len(normalized_docs) != len(set(normalized_docs)):
        raise ValueError("expected_document_ids contains duplicates")

    normalized_pages = [(normalize_id(doc), normalize_page(page)) for doc, page in expected_cited_doc_pages]
    if len(normalized_pages) != len(set(normalized_pages)):
        raise ValueError("expected_cited_doc_pages contains duplicates")

    normalized_chunks = [normalize_id(value) for value in expected_chunk_ids]
    if len(normalized_chunks) != len(set(normalized_chunks)):
        raise ValueError("expected_chunk_ids contains duplicates")
    if normalized_chunks and not (chunk_table_version or "").strip():
        raise ValueError("chunk_table_version is required when expected_chunk_ids is populated")


def validate_chunk_labels(
    *,
    expected_chunk_ids: list[str],
    chunk_table_version: str | None,
    chunk_rows_by_id: dict[str, dict[str, Any]],
    expected_cited_doc_pages: list[tuple[str, int]],
) -> None:
    if not expected_chunk_ids:
        return
    if not (chunk_table_version or "").strip():
        raise ValueError("chunk_table_version is required for chunk labels")
    expected_pages = {(normalize_id(doc), int(page)) for doc, page in expected_cited_doc_pages}
    for chunk_id in expected_chunk_ids:
        row = chunk_rows_by_id.get(normalize_id(chunk_id))
        if row is None:
            raise ValueError(f"chunk_id {chunk_id!r} is missing from the chunk-table snapshot")
        identity = (normalize_id(row.get("document_id")), normalize_page(row.get("page_number")))
        if expected_pages and identity not in expected_pages:
            raise ValueError(
                f"chunk_id {chunk_id!r} maps to {identity}, which is not in expected_cited_doc_pages"
            )
