"""Stage 1 — Input Source.

Discovers PDF documents from the configured FSR volume(s) and returns a list
of document references for downstream stages.

Input:  INPUT_MODE, PDF_VOLUME_PATHS (from fsr_v2 config)
Output: list[dict] with keys: document_id, volume_path, file_size_bytes, file_last_modified
"""
from __future__ import annotations

import logging
import re
from functools import reduce
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

from pyspark.sql import functions as F
from pyspark.sql.window import Window

log = logging.getLogger("fsr.v2.input")

# Mirrors fsr_config.SKIP_SUFFIXES — non-PDF file types to ignore during volume scan.
_SKIP_SUFFIXES: frozenset[str] = frozenset({
    ".crdownload", ".tmp", ".part", ".download",
    ".DS_Store", ".json", ".txt", ".csv", ".xlsx",
})
_UUID_PREFIX = re.compile(
    r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:_|$)",
    re.IGNORECASE,
)


def _canonical_doc_id(value: str) -> str:
    """Return canonical document_id form used by metadata/chunks keys.

    Canonical rules:
    - trim whitespace
    - strip surrounding single/double quotes (if present)
    - strip optional trailing .pdf (case-insensitive)
    - lowercase
    """
    v = (value or "").strip()
    if len(v) >= 2 and ((v[0] == "'" and v[-1] == "'") or (v[0] == '"' and v[-1] == '"')):
        v = v[1:-1].strip()
    if v.lower().endswith(".pdf"):
        v = v[:-4]
    return v.lower()


def _target_document_id(value: str) -> str:
    """Use a leading UUID as the stable target-mode document identifier."""
    canonical = _canonical_doc_id(value)
    match = _UUID_PREFIX.match(canonical)
    return match.group(1).lower() if match else canonical


# Same rule as _target_document_id, expressed in Spark SQL for the discovery scan.
# Both paths MUST agree: source filenames carry a compound suffix after the UUID
# (`<uuid>_605009986-189548-299265-Final_Master_Report.pdf`), so deriving the id
# from the full stem in one path and the UUID prefix in the other registered the
# same physical PDF twice under two different document_ids.
_UUID_PREFIX_SQL = r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(_.*)?$"


def _canonical_doc_id_col(name_col):
    """Spark equivalent of `_canonical_doc_id` + `_target_document_id`."""
    stem = F.regexp_replace(F.trim(name_col), r"(?i)\.pdf$", "")
    stem = F.lower(F.regexp_replace(stem, r"^[\"']+|[\"']+$", ""))
    uuid_prefix = F.regexp_extract(stem, _UUID_PREFIX_SQL, 1)
    return F.when(uuid_prefix != "", uuid_prefix).otherwise(stem)


def _normalize_list_df(df):
    """Normalize LIST output to a uniform `mod_time_ms` (bigint) column.

    Older DBR runtimes return `modificationTime` (Timestamp); newer DBR 18+
    returns `modification_time` (bigint epoch ms).
    """
    cols = set(df.columns)
    if "modificationTime" in cols:
        return df.withColumn("mod_time_ms", F.unix_millis(F.col("modificationTime")))
    if "modification_time" in cols:
        return df.withColumn("mod_time_ms", F.col("modification_time").cast("long"))
    raise ValueError(f"LIST output missing modification time column; got {df.columns}")


def _lookup_target_docs(
    volume_paths: list[str],
    target_document_ids: list[str],
    existing_doc_ids: set[str],  # noqa: ARG001 — unused: target requests always re-resolve, even if already ingested
    dbutils_client,
) -> list[dict]:
    """Resolve a small set of target document IDs directly via per-file stat calls.

    Mirrors the v1 TARGET mode pattern in nb_sdg_fsr_metadata.py.
    Volume files may be stored with or without `.pdf` extension:
      - FieldVision (`fv_field_service_report`): no extension (UUID = filename)
      - Manual reports (`ecrt_reports`): legacy `.pdf` suffix
    Tries the no-extension form first, then falls back to `.pdf`.
    """
    if dbutils_client is None:
        raise ValueError("target_document_ids requires a Databricks dbutils client")

    log.info(
        "Target mode debug: configured volume_paths=%s",
        ", ".join(volume_paths) if volume_paths else "<empty>",
    )

    results: list[dict] = []
    for doc_id in target_document_ids:
        requested_doc_id = (doc_id or "").strip()
        if not requested_doc_id:
            continue

        requested_stem = requested_doc_id.strip()
        if len(requested_stem) >= 2 and ((requested_stem[0] == "'" and requested_stem[-1] == "'") or (requested_stem[0] == '"' and requested_stem[-1] == '"')):
            requested_stem = requested_stem[1:-1].strip()
        if requested_stem.lower().endswith(".pdf"):
            requested_stem = requested_stem[:-4]

        # Preserve the UUID document-ID contract even when source files include
        # compound report names after the UUID.
        normalized_doc_id = _target_document_id(requested_doc_id)
        log.info(
            "Target mode debug: requested_doc_id=%s normalized_doc_id=%s requested_stem=%s",
            requested_doc_id,
            normalized_doc_id,
            requested_stem,
        )
        # Explicit target requests always get re-resolved from the volume, even if
        # a row already exists (e.g. a completed doc needs to be reprocessed).

        # Try the user-provided case first, then lowercase fallback.
        candidate_stems: list[str] = []
        for stem in (requested_stem, normalized_doc_id):
            if stem and stem not in candidate_stems:
                candidate_stems.append(stem)
        log.info(
            "Target mode debug: candidate_stems=%s",
            ", ".join(candidate_stems) if candidate_stems else "<none>",
        )

        for vol in volume_paths:
            log.info("Target mode debug: probing volume=%s", vol)
            for stem in candidate_stems:
                for candidate in (f"{vol}/{stem}", f"{vol}/{stem}.pdf"):
                    log.info("Target mode debug: trying candidate=%s", candidate)
                    try:
                        info = dbutils_client.fs.ls(candidate)
                        path = info[0].path.replace("dbfs:", "") if info[0].path.startswith("dbfs:") else info[0].path
                        mod_ts = datetime.fromtimestamp(info[0].modificationTime / 1000, tz=timezone.utc)
                        results.append({
                            "document_id": normalized_doc_id,
                            "volume_path": path,
                            "file_size_bytes": info[0].size,
                            "file_last_modified": mod_ts,
                        })
                        log.info("Target mode debug: success candidate=%s resolved_path=%s", candidate, path)
                        break
                    except Exception as e:
                        log.info("Target mode debug: miss candidate=%s error=%s", candidate, str(e).splitlines()[0])
                        continue

            # Source filenames can retain a compound name, case differences, and
            # a .pdf extension. Collect all UUID-prefix matches; the same
            # deterministic newest-file rule as full scan is applied below.
            try:
                prefix_matches = [
                    entry for entry in dbutils_client.fs.ls(vol)
                    if entry.name.lower().startswith(normalized_doc_id)
                    and entry.name.lower().endswith(".pdf")
                ]
            except Exception as e:
                log.info("Target mode debug: cannot list volume=%s error=%s", vol, str(e).splitlines()[0])
                prefix_matches = []

            for info in prefix_matches:
                path = info.path.replace("dbfs:", "") if info.path.startswith("dbfs:") else info.path
                mod_ts = datetime.fromtimestamp(info.modificationTime / 1000, tz=timezone.utc)
                results.append({
                    "document_id": normalized_doc_id,
                    "volume_path": path,
                    "file_size_bytes": info.size,
                    "file_last_modified": mod_ts,
                })
                log.info("Target mode debug: UUID-prefix resolved_path=%s", path)

        if not any(result["document_id"] == normalized_doc_id for result in results):
            log.warning(
                "Target mode: %s (normalized=%s) not found in configured volumes",
                requested_doc_id,
                normalized_doc_id,
            )

    # Several requested names can normalize to one document_id, and the same ID
    # may exist in multiple configured volumes. Keep the newest physical copy,
    # matching full-scan behavior; size and path make ties deterministic.
    deduped: dict[str, dict] = {}
    for entry in results:
        existing = deduped.get(entry["document_id"])
        if existing is None or (
            entry.get("file_last_modified"),
            entry.get("file_size_bytes") or 0,
            entry.get("volume_path") or "",
        ) > (
            existing.get("file_last_modified"),
            existing.get("file_size_bytes") or 0,
            existing.get("volume_path") or "",
        ):
            deduped[entry["document_id"]] = entry
    if len(deduped) != len(results):
        log.info("Target mode: collapsed %d resolved entries to %d unique document_id(s)",
                 len(results), len(deduped))
    results = list(deduped.values())

    _n_err = sum(1 for r in results if r.get("error"))
    log.info(
        f"Resolved {len(results) - _n_err}/{len(target_document_ids)} target document(s)"
        + (f"; {_n_err} unresolved (ambiguous source files)" if _n_err else "")
    )
    return results


def load(
    spark: "SparkSession",
    volume_paths: list[str],
    existing_doc_ids: set[str],
    target_document_ids: list[str] | None = None,
    dbutils_client=None,
) -> list[dict]:
    """Scan volume(s) for new PDFs not yet in fsr_metadata_v2.

    Args:
        spark: active SparkSession
        volume_paths: list of /Volumes/... paths to scan
        existing_doc_ids: set of document_ids already in the metadata table (skip these)
        target_document_ids: optional list of specific document IDs to resolve directly
        dbutils_client: Databricks dbutils handle required for target_document_ids mode

    Returns:
        list of dicts — one per discovered PDF:
            {document_id, volume_path, file_size_bytes, file_last_modified}
    """
    if not volume_paths:
        raise ValueError("volume_paths is required — pass PDF_VOLUME_PATHS from config")

    if target_document_ids:
        return _lookup_target_docs(volume_paths, target_document_ids, existing_doc_ids, dbutils_client)

    skip_pattern = "|".join(s.replace(".", r"\.") for s in _SKIP_SUFFIXES)

    per_vol_dfs = []
    for vol in volume_paths:
        log.info(f"Scanning (LIST): {vol}")
        try:
            list_df = _normalize_list_df(spark.sql(f"LIST '{vol}'"))
            vol_df = (
                list_df
                .filter(~F.lower(F.col("name")).rlike(f"({skip_pattern})$"))
                .filter(~F.lower(F.col("name")).rlike(r"/$"))  # skip sub-directories
                .withColumn("document_id", _canonical_doc_id_col(F.col("name")))
                .select(
                    F.col("document_id"),
                    F.concat(F.lit(f"{vol}/"), F.col("name")).alias("volume_path"),
                    F.col("size").cast("long").alias("file_size_bytes"),
                    F.expr("timestamp_millis(mod_time_ms)").alias("file_last_modified"),
                )
            )
            per_vol_dfs.append(vol_df)
        except Exception as e:
            log.warning(f"Cannot list volume {vol}: {e}")

    if not per_vol_dfs:
        log.info("No volumes could be scanned — returning empty list")
        return []

    combined = reduce(lambda a, b: a.unionByName(b), per_vol_dfs)

    # Exclude already-known documents via left-anti join (scales to 50k+ doc IDs).
    if existing_doc_ids:
        existing_df = spark.createDataFrame(
            [(doc_id,) for doc_id in existing_doc_ids], ["document_id"]
        )
        combined = combined.join(existing_df, "document_id", "left_anti")

    # Dedup: keep the most recently modified copy per document_id. Now that the id
    # is the UUID prefix, this also collapses same-volume variants of one document
    # (e.g. `<uuid>_report.pdf` and `<uuid>_report_1.pdf`).
    w = Window.partitionBy("document_id").orderBy(
        F.desc("file_last_modified"), F.desc("file_size_bytes"), F.col("volume_path")
    )
    combined = (
        combined
        .withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )

    result = [row.asDict() for row in combined.collect()]
    log.info(f"Discovered {len(result)} new document(s) across {len(volume_paths)} volume(s)")
    return result
