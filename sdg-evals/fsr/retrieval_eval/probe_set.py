"""Build and load the FSR retrieval probe set.

A probe set is a fixed list of ``(esn, query, known_doc_ids)`` rows we hit
the index with on every eval run. Stored as a Delta table so each run pins
to a snapshot and is reproducible.

For v1 we stratify by FSR count per ESN — small / medium / large — so we get
signal on both the easy case (1 FSR) and the homogeneity case (many FSRs).
The query template is intentionally generic; once SME-labeled queries arrive
we will swap this for real URM-style questions.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fsr.retrieval_eval.validation import validate_probe_labels


DEFAULT_QUERY_TEMPLATE = "field service report findings for unit {esn}"


@dataclass
class ProbeQuery:
    esn: str
    query: str
    known_doc_ids: set[str]
    bucket: str  # "small" | "medium" | "large"
    equip_type: str | None = None
    component: str | None = None
    issue_name: str | None = None
    issue_prompt: str | None = None
    expected_document_ids: set[str] | None = None
    expected_cited_doc_pages: list[tuple[str, int]] | None = None
    expected_chunk_ids: set[str] | None = None
    chunk_table_version: str | None = None
    min_expected_doc_hits_top_k: int = 1
    expected_evidence_terms: list[str] | None = None
    expected_section_hints: list[str] | None = None
    label_source: str | None = None
    confidence: str | None = None
    notes: str | None = None


def _split_pipe(value: str) -> list[str]:
    text = (value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def _derive_query(esn: str, equip_type: str | None, component: str | None, issue_name: str | None) -> str:
    """Derive a retrieval query from simplified probe metadata.

    Include ESN and equipment context to improve target matching when
    retrieval is run without explicit ESN filtering.
    """
    tokens = [
        "field service report",
        f"unit {esn}" if esn else "",
        equip_type or "",
        component or "",
        issue_name or "",
    ]
    return " ".join(t.strip() for t in tokens if (t or "").strip())


def _parse_expected_cited_doc_pages(value: str) -> list[tuple[str, int]]:
    """Parse cited doc+page pairs from a compact string.

    Accepted examples:
    - "DOC-1,42|DOC-2,300|DOC-2,40"
    - "[DOC-1,42]|[DOC-2,300]"
    """
    text = (value or "").strip()
    if not text:
        return []

    out: list[tuple[str, int]] = []
    tokens = _split_pipe(text.replace(";", "|"))
    for token in tokens:
        raw = token.strip().strip("[]()")
        if not raw:
            continue
        # Split on the first comma and keep any comma in the doc id suffix.
        m = re.match(r"^(?P<doc>.+?),(?P<page>-?\d+)$", raw)
        if not m:
            raise ValueError(
                "expected_cited_doc_pages entries must be 'document_id,page' "
                f"(got '{token}')"
            )
        doc_id = (m.group("doc") or "").strip()
        page_num = int(m.group("page"))
        if not doc_id:
            raise ValueError(f"document_id is empty in expected_cited_doc_pages entry '{token}'")
        if page_num < 0:
            raise ValueError(
                f"page number must be >= 0 in expected_cited_doc_pages entry '{token}'"
            )
        out.append((doc_id, page_num))

    return out


def _parse_pipe_ids(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def build_probe_set(
    spark: Any,
    metadata_table: str,
    output_table: str,
    per_bucket: int = 15,
    seed: int = 7,
) -> None:
    """Sample ESNs from biz_metadata stratified by FSR count and persist."""
    spark.sql(
        f"""
        CREATE OR REPLACE TABLE {output_table} AS
        WITH esn_counts AS (
            SELECT esn, COUNT(DISTINCT document_id) AS fsr_count,
                   collect_set(document_id) AS known_doc_ids
            FROM {metadata_table}
            WHERE esn IS NOT NULL
              AND metadata_status = 'completed'
            GROUP BY esn
        ),
        bucketed AS (
            SELECT
                esn,
                fsr_count,
                known_doc_ids,
                CASE
                    WHEN fsr_count = 1 THEN 'small'
                    WHEN fsr_count BETWEEN 2 AND 9 THEN 'medium'
                    ELSE 'large'
                END AS bucket
            FROM esn_counts
        ),
        ranked AS (
            SELECT *, row_number() OVER (
                PARTITION BY bucket ORDER BY rand({seed})
            ) AS rn
            FROM bucketed
        )
        SELECT
            esn,
            CONCAT('field service report findings for unit ', esn) AS query,
            known_doc_ids,
            fsr_count,
            bucket,
            current_timestamp() AS built_at
        FROM ranked
        WHERE rn <= {per_bucket}
        """
    )


def load_probe_set(spark: Any, table: str) -> list[ProbeQuery]:
    rows = spark.sql(f"SELECT esn, query, known_doc_ids, bucket FROM {table}").collect()
    return [
        ProbeQuery(
            esn=r["esn"],
            query=r["query"],
            known_doc_ids=set(r["known_doc_ids"] or []),
            bucket=r["bucket"],
        )
        for r in rows
    ]


def load_probe_set_csv(csv_path: str | Path) -> list[ProbeQuery]:
    """Load fixed weak-label retrieval probes from a CSV template.

    Expected columns:
    - probe_id, esn, expected_document_ids, expected_cited_doc_pages
    - expected_chunk_ids, chunk_table_version, label_source, confidence, notes

    Optional columns for metadata-driven probe inputs:
    - component, issue_name, issue_prompt
    - expected_cited_doc_pages (pipe-delimited "document_id,page" pairs)
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Probe CSV not found: {path}")

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Probe CSV header is missing")

        required = ["probe_id", "esn", "expected_document_ids"]
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Missing required probe columns: {missing}")

        rows = list(reader)

    if not rows:
        raise ValueError("Probe CSV has no data rows")

    probes: list[ProbeQuery] = []
    for idx, row in enumerate(rows, start=2):
        esn = (row.get("esn") or "").strip().upper()
        query = (row.get("query_text") or "").strip()
        component = (row.get("component") or "").strip() or None
        issue_name = (row.get("issue_name") or "").strip() or None
        issue_prompt = (row.get("issue_prompt") or "").strip() or None

        equip_type = (row.get("equip_type") or "").strip() or None

        # Keep backward compatibility with query_text while allowing
        # metadata source fields for deriving a query input.
        if not query:
            if issue_prompt:
                query = issue_prompt
            elif component and issue_name:
                query = _derive_query(esn=esn, equip_type=equip_type, component=component, issue_name=issue_name)

        expected_docs = {doc.strip() for doc in _split_pipe(row.get("expected_document_ids") or "")}
        if not esn:
            raise ValueError(f"row {idx}: esn is required")
        if not query:
            raise ValueError(
                f"row {idx}: query_text is required (or provide issue_prompt, or component+issue_name)"
            )
        if not expected_docs:
            raise ValueError(f"row {idx}: expected_document_ids is required")

        try:
            expected_cited_doc_pages = _parse_expected_cited_doc_pages(
                row.get("expected_cited_doc_pages") or ""
            )
        except ValueError as exc:
            raise ValueError(f"row {idx}: {exc}") from exc

        expected_chunk_ids = _parse_pipe_ids(row.get("expected_chunk_ids") or "")
        chunk_table_version = (row.get("chunk_table_version") or "").strip() or None
        try:
            validate_probe_labels(
                esn=esn,
                expected_document_ids=sorted(expected_docs),
                expected_cited_doc_pages=expected_cited_doc_pages,
                expected_chunk_ids=expected_chunk_ids,
                chunk_table_version=chunk_table_version,
            )
        except ValueError as exc:
            raise ValueError(f"row {idx}: {exc}") from exc

        probes.append(
            ProbeQuery(
                esn=esn,
                query=query,
                known_doc_ids=set(expected_docs),
                bucket=(row.get("confidence") or "weak_label").strip() or "weak_label",
                equip_type=equip_type,
                component=component,
                issue_name=issue_name,
                issue_prompt=issue_prompt,
                expected_document_ids=set(expected_docs),
                expected_cited_doc_pages=expected_cited_doc_pages,
                min_expected_doc_hits_top_k=1,
                expected_chunk_ids=set(expected_chunk_ids),
                chunk_table_version=chunk_table_version,
                expected_evidence_terms=_split_pipe(row.get("expected_evidence_terms") or ""),
                expected_section_hints=_split_pipe(row.get("expected_section_hints") or ""),
                label_source=(row.get("label_source") or "").strip() or None,
                confidence=(row.get("confidence") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
            )
        )

    return probes


def build_probe_set_in_memory(
    spark: Any,
    metadata_table: str,
    per_bucket: int = 15,
    seed: int = 7,
    metadata_version: int | None = None,
    query_template: str = DEFAULT_QUERY_TEMPLATE,
    probe_set_version: str = "v1",
) -> tuple[list[ProbeQuery], int]:
    """Read-only probe builder. Pins to a Delta version of ``metadata_table`` so
    the probe set is reproducible without writing anything.

    Versioning has two parts, both meant to land in MLflow params:

    * ``metadata_version`` — which snapshot of the metadata table we sampled
      ESNs from. Returned so the caller can log it.
    * ``probe_set_version`` + ``query_template`` — which probe definition we
      built against that snapshot. ``probe_set_version`` is an opaque label
      (e.g. ``"v1"``, ``"v2_sme_q1"``); ``query_template`` is the actual
      text used to build each probe's query, with ``{esn}`` substituted.

    Returns ``(probes, version_used)``. Pass the returned ``version_used`` back
    in a later run — together with the same ``probe_set_version`` and
    ``query_template`` — to reproduce the exact same probe set.
    """
    if metadata_version is None:
        v_rows = spark.sql(
            f"DESCRIBE HISTORY {metadata_table} LIMIT 1"
        ).collect()
        if not v_rows:
            raise RuntimeError(f"No history found for {metadata_table}")
        metadata_version = int(v_rows[0]["version"])

    rows = spark.sql(
        f"""
        WITH esn_counts AS (
            SELECT esn, COUNT(DISTINCT document_id) AS fsr_count,
                   collect_set(document_id) AS known_doc_ids
            FROM {metadata_table} VERSION AS OF {metadata_version}
            WHERE esn IS NOT NULL
              AND metadata_status = 'completed'
            GROUP BY esn
        ),
        bucketed AS (
            SELECT esn, fsr_count, known_doc_ids,
                   CASE
                       WHEN fsr_count = 1 THEN 'small'
                       WHEN fsr_count BETWEEN 2 AND 9 THEN 'medium'
                       ELSE 'large'
                   END AS bucket
            FROM esn_counts
        ),
        ranked AS (
            SELECT *, row_number() OVER (
                PARTITION BY bucket ORDER BY rand({seed})
            ) AS rn
            FROM bucketed
        )
        SELECT esn, known_doc_ids, fsr_count, bucket
        FROM ranked WHERE rn <= {per_bucket}
        """
    ).collect()

    probes = [
        ProbeQuery(
            esn=r["esn"],
            query=query_template.format(esn=r["esn"]),
            known_doc_ids=set(r["known_doc_ids"] or []),
            bucket=r["bucket"],
        )
        for r in rows
    ]
    return probes, metadata_version
