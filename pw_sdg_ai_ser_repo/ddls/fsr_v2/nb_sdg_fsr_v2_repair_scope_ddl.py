# Databricks notebook source
# FSR v2 repair scope-table bootstrap. Safe to run repeatedly.

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

dbutils.widgets.text("REPAIR_SCOPE_TABLE", "vaid.ai_sot_field_service_report.fsr_v2_repair_scope")  # noqa: F821
SCOPE_TABLE = dbutils.widgets.get("REPAIR_SCOPE_TABLE").strip()  # noqa: F821
if not SCOPE_TABLE:
    raise ValueError("REPAIR_SCOPE_TABLE is required")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {SCOPE_TABLE} (
    run_id STRING NOT NULL,
    requested_document_id STRING NOT NULL,
    document_id STRING,
    source_volume_path STRING,
    source_file_size_bytes BIGINT,
    source_file_last_modified TIMESTAMP,
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
    actual_preprocessor_profile STRING,
    actual_preprocessor_strategy STRING,
    preprocessor_version STRING,
    parser_version STRING,
    detection_method STRING,
    detection_signals STRING,
    detection_confidence STRING,
    fallback_reason STRING,
    deployed_code_commit STRING,
    chunking_parameters STRING,
    embedding_model STRING,
    embedding_dimension INT,
    before_fingerprint STRING,
    after_fingerprint STRING,
    before_region_count INT,
    after_region_count INT,
    before_chunk_count INT,
    after_chunk_count INT,
    rollback_status STRING,
    rollback_artifact_uri STRING,
    rollback_snapshot_version STRING,
    kill_switch_requested_at TIMESTAMP
) USING DELTA
""")

# Migrate tables created by the earlier minimal scope DDL without duplicating columns.
_existing_columns = {field.name.lower() for field in spark.table(SCOPE_TABLE).schema.fields}
_missing_columns = {
    "requested_document_id": "STRING",
    "document_id": "STRING",
    "source_volume_path": "STRING",
    "source_file_size_bytes": "BIGINT",
    "source_file_last_modified": "TIMESTAMP",
    "expected_preprocessor_profile": "STRING",
    "page_fallback_enabled": "BOOLEAN",
    "page_fallback_version": "STRING",
    "resolution_status": "STRING",
    "skip_reason": "STRING",
    "p3_status": "STRING",
    "p3_run_id": "STRING",
    "actual_preprocessor_profile": "STRING",
    "actual_preprocessor_strategy": "STRING",
    "preprocessor_version": "STRING",
    "parser_version": "STRING",
    "detection_method": "STRING",
    "detection_signals": "STRING",
    "detection_confidence": "STRING",
    "fallback_reason": "STRING",
    "deployed_code_commit": "STRING",
    "chunking_parameters": "STRING",
    "embedding_model": "STRING",
    "embedding_dimension": "INT",
    "before_region_count": "INT",
    "after_region_count": "INT",
    "before_chunk_count": "INT",
    "after_chunk_count": "INT",
    "rollback_status": "STRING",
    "rollback_artifact_uri": "STRING",
    "rollback_snapshot_version": "STRING",
    "kill_switch_requested_at": "TIMESTAMP",
}
_alter_columns = ",\n    ".join(
    f"{name} {data_type}"
    for name, data_type in _missing_columns.items()
    if name not in _existing_columns
)
if _alter_columns:
    spark.sql(f"ALTER TABLE {SCOPE_TABLE} ADD COLUMNS ({_alter_columns})")

if "document_id" in _existing_columns:
    try:
        spark.sql(f"ALTER TABLE {SCOPE_TABLE} ALTER COLUMN document_id DROP NOT NULL")
    except Exception as exc:
        raise RuntimeError(
            "The existing scope table still enforces document_id NOT NULL; "
            "cannot safely support missing-target repair rows"
        ) from exc

print(f"Repair scope table ready: {SCOPE_TABLE}")
