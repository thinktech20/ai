"""Lightweight FSR retrieval metrics.

This v1 module intentionally focuses on one metric only:
"number of FSRs retrieved vs what exists" for an ESN.
"""
from __future__ import annotations

import json
import re
from typing import Any


def retrieved_doc_ids(results: list[dict[str, Any]]) -> set[str]:
    """Unique FSR document ids surfaced by retrieval for a probe."""
    return {
        _normalize_doc_id(r.get("document_id"))
        for r in results
        if _normalize_doc_id(r.get("document_id"))
    }


def exists_doc_ids(known_doc_ids: set[str]) -> set[str]:
    """Normalized set of FSR doc ids known to exist for an ESN."""
    return {
        _normalize_doc_id(doc_id)
        for doc_id in known_doc_ids
        if _normalize_doc_id(doc_id)
    }


def retrieved_vs_exists_ratio(results: list[dict[str, Any]], known_doc_ids: set[str]) -> float:
    """Fraction of known FSRs that retrieval surfaced for an ESN.

    This is a lightweight ceiling metric, not semantic relevance ground truth.
    """
    known = exists_doc_ids(known_doc_ids)
    if not known:
        return 0.0
    return len(retrieved_doc_ids(results) & known) / len(known)


def retrieved_vs_exists_counts(results: list[dict[str, Any]], known_doc_ids: set[str]) -> dict[str, int]:
    """Count view for the same metric, useful for per-probe debugging."""
    known = exists_doc_ids(known_doc_ids)
    retrieved = retrieved_doc_ids(results)
    retrieved_known = retrieved & known
    return {
        "known_fsr_count": len(known),
        "retrieved_fsr_count": len(retrieved),
        "retrieved_known_fsr_count": len(retrieved_known),
    }


def doc_hit_at_k_metrics(
    results: list[dict[str, Any]],
    expected_document_ids: set[str],
    min_expected_doc_hits_top_k: int,
) -> dict[str, float | int]:
    expected = exists_doc_ids(expected_document_ids)
    retrieved = retrieved_doc_ids(results)
    hit_count = len(retrieved & expected)
    expected_count = len(expected)
    return {
        "expected_doc_count": expected_count,
        "hit_doc_count": hit_count,
        "doc_hit_at_k": 1 if hit_count >= max(min_expected_doc_hits_top_k, 1) else 0,
        "doc_recall_at_k": (hit_count / expected_count) if expected_count else 0.0,
    }


def doc_id_diff_details(
    results: list[dict[str, Any]],
    expected_document_ids: set[str],
) -> dict[str, Any]:
    """Detailed doc-id comparison for probe-level diagnostics.

    Returns sorted lists so per-probe artifacts are deterministic and easy to diff.
    """
    expected = exists_doc_ids(expected_document_ids)
    retrieved = retrieved_doc_ids(results)
    missing = sorted(expected - retrieved)
    additional = sorted(retrieved - expected)
    return {
        "expected_document_ids": sorted(expected),
        "retrieved_document_ids": sorted(retrieved),
        "missing_expected_document_ids": missing,
        "additional_retrieved_document_ids": additional,
        "doc_ids_exact_match": 1 if not missing and not additional else 0,
        "doc_ids_not_same_flag": 1 if (missing or additional) else 0,
    }


def evidence_term_at_k_metrics(
    results: list[dict[str, Any]],
    expected_terms: list[str],
    chunk_text_field: str = "chunk_text",
) -> dict[str, float | int]:
    norm_terms = [t.strip().lower() for t in expected_terms if (t or "").strip()]
    if not norm_terms:
        return {
            "expected_terms_count": 0,
            "matched_terms_count": 0,
            "term_coverage": 0.0,
            "evidence_term_hit_at_k": 0,
        }

    merged_text = "\n".join(str(r.get(chunk_text_field) or "").lower() for r in results)
    matched = [t for t in norm_terms if t in merged_text]
    matched_count = len(set(matched))
    return {
        "expected_terms_count": len(norm_terms),
        "matched_terms_count": matched_count,
        "term_coverage": matched_count / len(norm_terms),
        "evidence_term_hit_at_k": 1 if matched_count >= 1 else 0,
    }


def filter_fidelity_at_k_metrics(
    results: list[dict[str, Any]],
    probe_esn: str,
    probe_equip_type: str | None,
    esn_field: str,
    equip_type_field: str,
    eligible_document_ids: set[str] | None = None,
) -> dict[str, float]:
    total = len(results)
    if total == 0:
        return {
            "retrieval_filter_match_rate_at_k": 0.0,
            "equip_type_match_rate_at_k": 0.0,
        }

    norm_probe_esn = (probe_esn or "").strip().upper()
    norm_probe_equip_type = (probe_equip_type or "").strip().lower()

    esn_matches = 0
    allowed_matches = 0
    equip_matches = 0
    for row in results:
        row_esn = str(row.get(esn_field) or "").strip().upper()
        if row_esn and row_esn == norm_probe_esn:
            esn_matches += 1
            allowed_matches += 1

        row_doc = _normalize_doc_id(row.get("document_id"))
        row_equip_type = str(row.get(equip_type_field) or "").strip().lower()
        eligible_docs = {_normalize_doc_id(doc) for doc in (eligible_document_ids or set())}
        if row_equip_type == "shared" and row_doc in eligible_docs:
            allowed_matches += 1

        if norm_probe_equip_type:
            row_equip = str(row.get(equip_type_field) or "").strip().lower()
            if row_equip and row_equip == norm_probe_equip_type:
                equip_matches += 1
        else:
            equip_matches += 1

    return {
        "retrieval_filter_match_rate_at_k": allowed_matches / total,
        "equip_type_match_rate_at_k": equip_matches / total,
    }


def page_level_metrics(
    results: list[dict[str, Any]],
    expected_cited_doc_pages: list[tuple[str, int]],
) -> dict[str, Any]:
    """Score default evidence labels at unique document/page-pair level."""
    expected = {(_normalize_doc_id(doc), int(page)) for doc, page in expected_cited_doc_pages}
    retrieved_pairs: set[tuple[str, int]] = set()
    relevant_rows = 0
    for row in results:
        doc_id = _normalize_doc_id(row.get("document_id"))
        pages = _extract_row_page_numbers(row)
        row_pairs = {(doc_id, page) for page in pages if doc_id}
        retrieved_pairs.update(row_pairs)
        if row_pairs & expected:
            relevant_rows += 1
    matched = len(expected & retrieved_pairs)
    recall = matched / len(expected) if expected else 0.0
    precision = relevant_rows / len(results) if results else 0.0
    return {
        "expected_page_pair_count": len(expected),
        "matched_page_pair_count": matched,
        "retrieved_page_pair_count": len(retrieved_pairs),
        "recall_at_k": recall,
        "precision_at_k": precision,
        "f1_at_k": _f1(precision, recall),
        "page_recall_at_k": recall,
        "page_precision_at_k": precision,
        "page_f1_at_k": _f1(precision, recall),
        "missing_page_pairs": sorted(expected - retrieved_pairs),
        "retrieved_document_page_pairs": sorted(retrieved_pairs),
    }


def exact_chunk_metrics(
    results: list[dict[str, Any]],
    expected_chunk_ids: set[str],
) -> dict[str, Any]:
    expected = {_normalize_doc_id(chunk_id) for chunk_id in expected_chunk_ids}
    retrieved = {
        _normalize_doc_id(row.get("chunk_id"))
        for row in results
        if _normalize_doc_id(row.get("chunk_id"))
    }
    matched = len(expected & retrieved)
    recall = matched / len(expected) if expected else 0.0
    precision = matched / len(retrieved) if retrieved else 0.0
    return {
        "chunk_recall_at_k": recall,
        "chunk_precision_at_k": precision,
        "chunk_f1_at_k": _f1(precision, recall),
        "missing_chunk_ids": sorted(expected - retrieved),
    }


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def cited_doc_page_hit_metrics(
    results: list[dict[str, Any]],
    expected_cited_doc_pages: list[tuple[str, int]],
) -> dict[str, Any]:
    """Check expected cited document+page pairs against top-k results.

    Each expected pair gets a yes/no flag plus matching chunk ids when present.
    """
    if not expected_cited_doc_pages:
        return {
            "expected_cited_pairs_count": 0,
            "matched_cited_pairs_count": 0,
            "cited_doc_page_hit_rate": 0.0,
            "cited_doc_page_all_hit": 0,
            "cited_doc_page_flags": [],
        }

    flags: list[dict[str, Any]] = []
    matched = 0
    for doc_id, page_num in expected_cited_doc_pages:
        expected_norm_doc_id = _normalize_doc_id(doc_id)
        matching_chunk_ids: list[str] = []
        for row in results:
            row_doc = _normalize_doc_id(row.get("document_id"))
            if row_doc != expected_norm_doc_id:
                continue
            row_pages = _extract_row_page_numbers(row)
            if page_num in row_pages:
                chunk_id = str(row.get("chunk_id") or "")
                if chunk_id:
                    matching_chunk_ids.append(chunk_id)

        hit = bool(matching_chunk_ids)
        if hit:
            matched += 1
        flags.append(
            {
                "document_id": doc_id,
                "page_number": page_num,
                "hit": 1 if hit else 0,
                "matched_chunk_ids": sorted(set(matching_chunk_ids)),
            }
        )

    total = len(expected_cited_doc_pages)
    return {
        "expected_cited_pairs_count": total,
        "matched_cited_pairs_count": matched,
        "cited_doc_page_hit_rate": (matched / total) if total else 0.0,
        "cited_doc_page_all_hit": 1 if matched == total and total > 0 else 0,
        "cited_doc_page_flags": flags,
    }


def _extract_row_page_numbers(row: dict[str, Any]) -> set[int]:
    pages: set[int] = set()
    for key in (
        "page",
        "page_num",
        "page_number",
        "pdf_page",
        "source_page",
        "source_page_number",
        "page_idx",
    ):
        pages.update(_coerce_pages(row.get(key)))

    metadata = row.get("metadata")
    if isinstance(metadata, str) and metadata.strip():
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = None
    if isinstance(metadata, dict):
        for key in (
            "page",
            "page_num",
            "page_number",
            "pdf_page",
            "source_page",
            "source_page_number",
            "page_idx",
        ):
            pages.update(_coerce_pages(metadata.get(key)))

    return pages


def _coerce_pages(value: Any) -> set[int]:
    if value is None:
        return set()
    if isinstance(value, list):
        out: set[int] = set()
        for item in value:
            out.update(_coerce_pages(item))
        return out

    text = str(value).strip()
    if not text:
        return set()
    try:
        n = int(float(text))
    except Exception:
        return set()
    return {n} if n >= 0 else set()


def _normalize_doc_id(value: Any) -> str:
    """Normalize document IDs for tolerant matching across systems.

    Keeps semantics stable while removing common formatting drift:
    - leading/trailing whitespace
    - case differences
    - repeated internal whitespace
    """
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)
