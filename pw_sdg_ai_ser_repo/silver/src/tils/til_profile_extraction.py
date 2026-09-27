"""TIL profile extraction — Spark-based PDF discovery and I/O.

Shared utilities for discovering, identifying, and matching TIL PDFs.

Field naming and identifier normalization follow the DS team contract from
``SDG_Scoping_Feedback_Loop/code_assets/experiments/step6`` (see
``run_til_profile_extraction_pilot.py`` and ``til_pdf_utils.py``):

  - ``til_number``         e.g. ``"2342-R1"`` — derived from filename via
                            the regex ``TIL\\s+([\\d\\-R]+)``.
  - ``base_til_num``       e.g. ``"2342"`` — TIL identifier without revision.
  - ``revision_number``    int parsed from a trailing ``R<n>``; ``-1`` when absent.
  - ``normalized_til_key`` uppercased, alphanumeric-only — used as the
                            canonical lookup key.
  - ``match_type``         ``"exact_til_number"`` or ``"base_til_latest_revision"``.
"""
from __future__ import annotations

import re
from functools import reduce
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    col, concat, lit, lower, regexp_extract, regexp_replace, upper, when,
)
from pyspark.sql.types import (
    LongType, StringType, StructField, StructType, TimestampType,
)


# ── Identifier normalization helpers (aligned with DS team) ────────────────

_TIL_FILENAME_RE = re.compile(r"TIL\s+([\d\-R]+)", re.IGNORECASE)


def clean_text(value: object) -> str:
    """Trim and coerce to string; return empty string for None."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def til_number_from_filename(filename: str) -> str:
    """Extract canonical TIL identifier (e.g. ``"2342-R1"``) from a PDF filename.

    Returns ``""`` when the filename does not match the expected ``TIL <id>`` shape.
    """
    match = _TIL_FILENAME_RE.search(clean_text(filename))
    return match.group(1).strip() if match else ""


def normalize_til_key(value: object) -> str:
    """Canonical comparison key: uppercase + strip non-alphanumeric."""
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def extract_base_til_num(value: object) -> str:
    """Strip optional leading ``TIL`` and trailing ``R<n>`` to get the base TIL number."""
    text = re.sub(r"^TIL\s*", "", clean_text(value).upper())
    text = re.sub(r"-?R\d+$", "", text)
    match = re.search(r"\d+(?:-\d+)?", text)
    return match.group(0) if match else ""


def parse_revision_number(value: object) -> int:
    """Parse trailing ``R<n>``; return ``-1`` when no revision is present."""
    match = re.search(r"R(\d+)$", clean_text(value).upper())
    return int(match.group(1)) if match else -1


# ── Spark discovery ─────────────────────────────────────────────────────────

def discover_tils(
    spark: SparkSession,
    volume_paths: list[str],
    skip_suffixes: list[str] | None = None,
    max_results: int | None = None,
) -> DataFrame | None:
    """Discover TIL PDFs via Spark SQL LIST and emit DS-aligned identifier columns.

    Returns a Spark DataFrame with columns:

      - ``source``             ``"databricks_volume"``
      - ``pdf_path``           full ``/Volumes/...`` path
      - ``file_name``          PDF filename
      - ``til_number``         DS-canonical TIL id (e.g. ``"2342-R1"``)
      - ``normalized_til_key`` uppercased alphanumeric form
      - ``base_til_num``       TIL id without revision
      - ``revision_number``    int (``-1`` when no revision)
      - ``file_size_bytes``
      - ``file_last_modified_ms``

    Rows whose filename does not match the ``TIL <id>`` pattern are dropped.
    Returns ``None`` when no volume was accessible.
    """
    skip_suffixes = skip_suffixes or [".md", ".txt", ".csv"]
    skip_pattern = "|".join(s.replace(".", r"\.") for s in skip_suffixes)

    result_dfs: list[DataFrame] = []
    for vol in volume_paths:
        try:
            list_df = spark.sql(f"LIST '{vol}'")

            cols = set(list_df.columns)
            if "modificationTime" in cols:
                from pyspark.sql.functions import unix_millis as _unix_millis
                list_df = list_df.withColumn("mod_time_ms", _unix_millis(col("modificationTime")))
            elif "modification_time" in cols:
                list_df = list_df.withColumn("mod_time_ms", col("modification_time").cast("long"))
            else:
                raise ValueError(f"LIST output missing modification time; got columns: {list_df.columns}")

            til_number_col = regexp_extract(col("name"), r"(?i)TIL\s+([\d\-R]+)", 1)
            til_number_upper = upper(til_number_col)
            base_til_col = regexp_extract(
                regexp_replace(til_number_upper, r"-?R\d+$", ""),
                r"\d+(?:-\d+)?",
                0,
            )
            revision_match = regexp_extract(til_number_upper, r"R(\d+)$", 1)
            revision_col = when(revision_match == "", lit(-1)).otherwise(revision_match.cast("int"))
            normalized_key_col = regexp_replace(til_number_upper, r"[^A-Z0-9]", "")

            vol_df = (
                list_df
                .filter(~lower("name").rlike(f"({skip_pattern})$"))
                .filter(~lower("name").rlike(r"/$"))
                .filter(lower("name").rlike(r"\.pdf$"))
                .withColumn("til_number", til_number_col)
                .filter(col("til_number") != "")
                .select(
                    lit("databricks_volume").alias("source"),
                    concat(lit(f"{vol}/"), col("name")).alias("pdf_path"),
                    col("name").alias("file_name"),
                    col("til_number"),
                    normalized_key_col.alias("normalized_til_key"),
                    base_til_col.alias("base_til_num"),
                    revision_col.alias("revision_number"),
                    col("size").cast("long").alias("file_size_bytes"),
                    col("mod_time_ms").alias("file_last_modified_ms"),
                )
            )
            result_dfs.append(vol_df)
        except Exception:
            # Log and continue to next volume (caller can decide on severity)
            pass

    if not result_dfs:
        return None

    combined_df = reduce(lambda a, b: a.unionByName(b), result_dfs)
    if max_results:
        combined_df = combined_df.limit(max_results)

    return combined_df


# ── Catalog collection + matching (aligned with DS team's pick_pdf_row) ────

def build_pdf_catalog(
    spark: SparkSession,
    volume_paths: list[str],
) -> list[dict[str, Any]]:
    """Discover all TIL PDFs and collect them into an in-memory catalog.

    Returns a list of dicts with the same column set as ``discover_tils``.
    Use this with ``pick_pdf_row`` to resolve requested TIL identifiers.
    """
    catalog_df = discover_tils(spark, volume_paths)
    if catalog_df is None:
        return []
    return [row.asDict() for row in catalog_df.collect()]


def pick_pdf_row(
    requested_til: str,
    catalog: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Resolve a requested TIL identifier against a catalog.

    Matching strategy mirrors the DS team's ``pick_pdf_row``:

      1. Exact match on ``normalized_til_key``.
      2. Otherwise, base TIL with the highest revision number.

    Returns a copy of the matched catalog row enriched with:

      - ``match_type``           ``"exact_til_number"`` or ``"base_til_latest_revision"``
      - ``requested_til_number`` the caller's requested identifier
    """
    normalized_requested = normalize_til_key(requested_til)
    base_requested = extract_base_til_num(requested_til)

    exact_matches = [row for row in catalog if row.get("normalized_til_key") == normalized_requested]
    base_matches = [row for row in catalog if row.get("base_til_num") == base_requested]

    ranked_base_matches = sorted(
        base_matches,
        key=lambda row: (-(row.get("revision_number") or -1), row.get("til_number") or ""),
    )
    ranked_matches = exact_matches or ranked_base_matches
    if not ranked_matches:
        return None

    selected = dict(ranked_matches[0])
    selected["match_type"] = "exact_til_number" if exact_matches else "base_til_latest_revision"
    selected["requested_til_number"] = requested_til
    return selected


def pick_pdf_row_by_name(
    target_pdf_name: str,
    catalog: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve a requested PDF by case-insensitive substring match on ``file_name``.

    Strict semantics — returns the row only when exactly one file matches:

      - 1 match  -> (row, None) with ``match_type="pdf_name_match"``
      - 0 match  -> (None, "no_match: <target>")
      - N match  -> (None, "ambiguous_match: <N> files (<first three>...)")

    The caller is expected to surface the error message via a ``pdf_not_found``
    audit row so misnamed / over-broad targets are visible rather than silent.
    """
    needle = (target_pdf_name or "").strip().lower()
    if not needle:
        return None, "no_match: empty target"

    matches = [row for row in catalog if needle in (row.get("file_name") or "").lower()]

    if len(matches) == 1:
        selected = dict(matches[0])
        selected["match_type"] = "pdf_name_match"
        selected["requested_pdf_name"] = target_pdf_name
        return selected, None

    if not matches:
        return None, f"no_match: {target_pdf_name}"

    sample = ", ".join((row.get("file_name") or "") for row in matches[:3])
    suffix = "..." if len(matches) > 3 else ""
    return None, f"ambiguous_match: {len(matches)} files ({sample}{suffix})"


def build_til_stub_schema() -> StructType:
    """Return standard schema for TIL metadata stub rows (discovery + staging).

    Mirrors the column shape produced by ``discover_tils``.
    """
    return StructType([
        StructField("source", StringType(), False),
        StructField("pdf_path", StringType(), False),
        StructField("file_name", StringType(), False),
        StructField("til_number", StringType(), False),
        StructField("normalized_til_key", StringType(), False),
        StructField("base_til_num", StringType(), True),
        StructField("revision_number", LongType(), True),
        StructField("file_size_bytes", LongType(), True),
        StructField("file_last_modified_ms", LongType(), True),
    ])
