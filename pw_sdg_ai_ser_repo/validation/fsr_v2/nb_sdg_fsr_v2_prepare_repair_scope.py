# Databricks notebook source
# FSR v2 repair scope preparation: validate candidates and optionally persist a manifest.
# This notebook never writes metadata, chunks, embeddings, or vector indexes.

import re
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

_WIDGETS = {
    "REPAIR_SCOPE_TABLE": "",
    "REPAIR_CANDIDATE_TABLE": "",
    "REPAIR_RUN_ID": "",
    "REPAIR_REASON": "",
    "EXPECTED_PREPROCESSOR_PROFILE": "",
    "PAGE_FALLBACK_ENABLED": "",
    "PAGE_FALLBACK_VERSION": "",
    "REQUESTED_BY": "",
    "REPAIR_DRY_RUN": "true",
    "METADATA_TABLE_V2": "",
}
for name, default in _WIDGETS.items():
    dbutils.widgets.text(name, default)  # noqa: F821


def _param(name: str) -> str:
    return dbutils.widgets.get(name).strip()  # noqa: F821


def _sql(value: str) -> str:
    return value.replace("'", "''")


def _ident(value: str, name: str) -> str:
    # Table identifiers are parameters, so reject expressions and SQL fragments.
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){1,2}", value):
        raise ValueError(f"{name} must be a catalog.schema.table identifier")
    return value


SCOPE_TABLE = _ident(_param("REPAIR_SCOPE_TABLE"), "REPAIR_SCOPE_TABLE")
CANDIDATE_TABLE = _ident(_param("REPAIR_CANDIDATE_TABLE"), "REPAIR_CANDIDATE_TABLE")
METADATA_TABLE = _ident(_param("METADATA_TABLE_V2"), "METADATA_TABLE_V2")
RUN_ID = _param("REPAIR_RUN_ID")
REASON = _param("REPAIR_REASON")
EXPECTED_PROFILE = _param("EXPECTED_PREPROCESSOR_PROFILE")
PAGE_FALLBACK_ENABLED = _param("PAGE_FALLBACK_ENABLED").lower()
PAGE_FALLBACK_VERSION = _param("PAGE_FALLBACK_VERSION")
REQUESTED_BY = _param("REQUESTED_BY")
DRY_RUN = _param("REPAIR_DRY_RUN").lower() != "false"

if not RUN_ID:
    raise ValueError("REPAIR_RUN_ID is required")
if not REASON:
    raise ValueError("REPAIR_REASON is required")
if EXPECTED_PROFILE.lower() == "final_master_report":
    if PAGE_FALLBACK_ENABLED not in {"true", "false"} or not PAGE_FALLBACK_VERSION:
        raise ValueError(
            "PAGE_FALLBACK_ENABLED and PAGE_FALLBACK_VERSION are required "
            "for final_master_report"
        )
if PAGE_FALLBACK_ENABLED and PAGE_FALLBACK_ENABLED not in {"true", "false"}:
    raise ValueError("PAGE_FALLBACK_ENABLED must be true or false when provided")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {SCOPE_TABLE} (
    run_id STRING NOT NULL,
    requested_document_id STRING NOT NULL,
    document_id STRING,
    reason STRING NOT NULL,
    expected_preprocessor_profile STRING,
    page_fallback_enabled BOOLEAN,
    page_fallback_version STRING,
    requested_by STRING,
    requested_at TIMESTAMP,
    resolution_status STRING,
    skip_reason STRING,
    p1_status STRING,
    p2_status STRING,
    p3_status STRING,
    attempt_count INT,
    error_message STRING,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    p1_run_id STRING,
    p2_run_id STRING,
    p3_run_id STRING,
    before_fingerprint STRING,
    after_fingerprint STRING,
    before_region_count INT,
    after_region_count INT,
    before_chunk_count INT,
    after_chunk_count INT,
    rollback_status STRING,
    rollback_artifact_uri STRING,
    rollback_snapshot_version STRING
) USING DELTA
""")

existing_run = spark.sql(f"""
    SELECT COUNT(*) AS n
    FROM {SCOPE_TABLE}
    WHERE run_id = '{_sql(RUN_ID)}'
""").first().n
if existing_run:
    raise ValueError(f"REPAIR_RUN_ID already exists in {SCOPE_TABLE}: {RUN_ID}")

candidate_columns = {field.name.lower() for field in spark.table(CANDIDATE_TABLE).schema.fields}
if "document_id" not in candidate_columns:
    raise ValueError(f"{CANDIDATE_TABLE} must contain a document_id column")
_candidate_volume_expr = "volume_path" if "volume_path" in candidate_columns else "CAST(NULL AS STRING)"
_candidate_size_expr = "file_size_bytes" if "file_size_bytes" in candidate_columns else "CAST(NULL AS BIGINT)"
_candidate_modified_expr = "file_last_modified" if "file_last_modified" in candidate_columns else "CAST(NULL AS TIMESTAMP)"

# Normalize the operator candidate using the same suffix and UUID-prefix rules as FSR input.
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW _fsr_v2_repair_candidates AS
SELECT
    lower(trim(document_id)) AS requested_raw,
    {_candidate_volume_expr} AS source_volume_path,
    {_candidate_size_expr} AS source_file_size_bytes,
    {_candidate_modified_expr} AS source_file_last_modified,
    CASE
        WHEN lower(trim(regexp_replace(document_id, '(?i)\\.pdf$', ''))) RLIKE
             '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}_.*$'
        THEN regexp_extract(
            lower(trim(regexp_replace(document_id, '(?i)\\.pdf$', ''))),
            '^([0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}})',
            1
        )
        ELSE lower(trim(regexp_replace(document_id, '(?i)\\.pdf$', '')))
    END AS requested_document_id
FROM {CANDIDATE_TABLE}
WHERE document_id IS NOT NULL AND trim(document_id) <> ''
""")

counts = spark.sql("""
SELECT
    COUNT(*) AS candidate_count,
    COUNT(DISTINCT requested_document_id) AS distinct_candidate_count,
    SUM(CASE WHEN requested_document_id = '' THEN 1 ELSE 0 END) AS empty_count
FROM _fsr_v2_repair_candidates
""").first()
if counts.empty_count or counts.candidate_count != counts.distinct_candidate_count:
    raise ValueError(
        f"Candidate table contains empty or duplicate IDs: "
        f"rows={counts.candidate_count}, distinct={counts.distinct_candidate_count}, "
        f"empty={counts.empty_count}"
    )

active_overlap = spark.sql(f"""
SELECT COUNT(*) AS n
FROM {SCOPE_TABLE} s
JOIN _fsr_v2_repair_candidates c
    ON COALESCE(s.document_id, s.requested_document_id) = c.requested_document_id
WHERE s.resolution_status IN ('resolved', 'missing_target')
  AND s.run_id <> '{_sql(RUN_ID)}'
  AND (
      s.p1_status IN ('pending', 'in_progress')
      OR s.p2_status IN ('pending', 'in_progress')
      OR s.p3_status IN ('pending', 'in_progress')
  )
""").first().n
if active_overlap:
    raise ValueError(f"{active_overlap} candidate document(s) are in another active repair run")

spark.sql(f"""
CREATE OR REPLACE TEMP VIEW _fsr_v2_repair_manifest AS
SELECT
    '{_sql(RUN_ID)}' AS run_id,
    c.requested_document_id,
    m.document_id,
    '{_sql(REASON)}' AS reason,
    COALESCE(m.volume_path, c.source_volume_path) AS source_volume_path,
    COALESCE(m.file_size_bytes, c.source_file_size_bytes) AS source_file_size_bytes,
    COALESCE(m.file_last_modified, c.source_file_last_modified) AS source_file_last_modified,
    NULLIF('{_sql(EXPECTED_PROFILE)}', '') AS expected_preprocessor_profile,
    CAST(NULLIF('{_sql(PAGE_FALLBACK_ENABLED)}', '') AS BOOLEAN) AS page_fallback_enabled,
    NULLIF('{_sql(PAGE_FALLBACK_VERSION)}', '') AS page_fallback_version,
    COALESCE(NULLIF('{_sql(REQUESTED_BY)}', ''), current_user()) AS requested_by,
    current_timestamp() AS requested_at,
    CASE
        WHEN m.document_id IS NULL AND c.source_volume_path IS NOT NULL AND trim(c.source_volume_path) <> '' THEN 'missing_target'
        WHEN COALESCE(m.volume_path, c.source_volume_path) IS NULL OR trim(COALESCE(m.volume_path, c.source_volume_path)) = '' THEN 'missing_source'
        ELSE 'resolved'
    END AS resolution_status,
    CASE
        WHEN m.document_id IS NULL AND (c.source_volume_path IS NULL OR trim(c.source_volume_path) = '') THEN 'document_id_not_found_and_source_path_not_provided'
        WHEN COALESCE(m.volume_path, c.source_volume_path) IS NULL OR trim(COALESCE(m.volume_path, c.source_volume_path)) = '' THEN 'metadata_row_has_no_volume_path'
        ELSE NULL
    END AS skip_reason,
    CASE WHEN COALESCE(m.volume_path, c.source_volume_path) IS NULL OR trim(COALESCE(m.volume_path, c.source_volume_path)) = '' THEN 'skipped' ELSE 'pending' END AS p1_status,
    CASE WHEN COALESCE(m.volume_path, c.source_volume_path) IS NULL OR trim(COALESCE(m.volume_path, c.source_volume_path)) = '' THEN 'skipped' ELSE 'pending' END AS p2_status,
    CASE WHEN COALESCE(m.volume_path, c.source_volume_path) IS NULL OR trim(COALESCE(m.volume_path, c.source_volume_path)) = '' THEN 'skipped' ELSE 'pending' END AS p3_status,
    0 AS attempt_count,
    CAST(NULL AS STRING) AS error_message,
    CAST(NULL AS TIMESTAMP) AS started_at,
    CAST(NULL AS TIMESTAMP) AS completed_at,
    CAST(NULL AS STRING) AS p1_run_id,
    CAST(NULL AS STRING) AS p2_run_id,
    CAST(NULL AS STRING) AS p3_run_id,
    CAST(NULL AS STRING) AS before_fingerprint,
    CAST(NULL AS STRING) AS after_fingerprint,
    CAST(NULL AS INT) AS before_region_count,
    CAST(NULL AS INT) AS after_region_count,
    CAST(NULL AS INT) AS before_chunk_count,
    CAST(NULL AS INT) AS after_chunk_count,
    CAST('not_needed' AS STRING) AS rollback_status,
    CAST(NULL AS STRING) AS rollback_artifact_uri,
    CAST(NULL AS STRING) AS rollback_snapshot_version
FROM _fsr_v2_repair_candidates c
LEFT JOIN {METADATA_TABLE} m
  ON lower(m.document_id) = c.requested_document_id
""")

spark.sql("""
SELECT resolution_status, p1_status, COUNT(*) AS document_count
FROM _fsr_v2_repair_manifest
GROUP BY resolution_status, p1_status
ORDER BY resolution_status
""").show(truncate=False)

if DRY_RUN:
    print(f"DRY RUN: no rows inserted into {SCOPE_TABLE}; run_id={RUN_ID}")
else:
    spark.sql(f"""
    INSERT INTO {SCOPE_TABLE} (
        run_id, requested_document_id, document_id, reason,
        source_volume_path, source_file_size_bytes, source_file_last_modified,
        expected_preprocessor_profile, page_fallback_enabled, page_fallback_version,
        requested_by, requested_at, resolution_status, skip_reason,
        p1_status, p2_status, p3_status, attempt_count, error_message,
        started_at, completed_at, p1_run_id, p2_run_id, p3_run_id,
        before_fingerprint, after_fingerprint, before_region_count, after_region_count,
        before_chunk_count, after_chunk_count, rollback_status,
        rollback_artifact_uri, rollback_snapshot_version
    )
    SELECT
        run_id, requested_document_id, document_id, reason,
        source_volume_path, source_file_size_bytes, source_file_last_modified,
        expected_preprocessor_profile, page_fallback_enabled, page_fallback_version,
        requested_by, requested_at, resolution_status, skip_reason,
        p1_status, p2_status, p3_status, attempt_count, error_message,
        started_at, completed_at, p1_run_id, p2_run_id, p3_run_id,
        before_fingerprint, after_fingerprint, before_region_count, after_region_count,
        before_chunk_count, after_chunk_count, rollback_status,
        rollback_artifact_uri, rollback_snapshot_version
    FROM _fsr_v2_repair_manifest
    """)
    print(f"Inserted repair scope manifest into {SCOPE_TABLE}; run_id={RUN_ID}")
