"""
Delta Store – Databricks
Reads and writes chunk rows in EMBEDDINGS_TABLE and applies ref-view metadata
enrichment. Chunk-derived metadata is persisted in a dedicated metadata column.
Databricks Vector Search generates embeddings from chunk_text during index sync.
"""
import json
import time
from datetime import date as _date, datetime
from typing import Any, List, Optional, Set

from langchain_core.documents import Document

from config import EMBEDDINGS_TABLE, FSR_REF_VIEW
from utils import setup_logger

logger = setup_logger("delta_store")

METADATA_COLUMN = "metadata"
METADATA_SCHEMA_VERSION = 1
DELTA_APPEND_MAX_RETRIES = 5
CHUNK_METADATA_KEYS = (
    "chunk_index",
    "chunk_count",
    "chunk_size",
    "token_count",
    "start_page",
    "end_page",
    "section_1",
    "section_2",
    "section_3",
    "section_4",
    "section_5",
    "document_extension",
    "chunk_esns",
    "esn_labels",
)


def _describe_table_columns(spark) -> Set[str]:
    rows = spark.sql(f"DESCRIBE TABLE {EMBEDDINGS_TABLE}").collect()
    columns: Set[str] = set()
    for row in rows:
        col_name = (row["col_name"] or "").strip()
        if col_name and not col_name.startswith("#"):
            columns.add(col_name)
    return columns


def ensure_metadata_column(spark) -> None:
    """Add the metadata column to the Delta table when upgrading older schemas."""
    try:
        columns = _describe_table_columns(spark)
    except Exception:
        return

    if METADATA_COLUMN in columns:
        return

    spark.sql(f"ALTER TABLE {EMBEDDINGS_TABLE} ADD COLUMNS ({METADATA_COLUMN} STRING)")
    logger.info(f"[OK] Added {METADATA_COLUMN} column to {EMBEDDINGS_TABLE}")


def _normalize_metadata_value(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [item for item in value if item is not None]
    return value


def _serialize_chunk_metadata(meta: dict[str, Any]) -> str:
    payload: dict[str, Any] = {"schema_version": METADATA_SCHEMA_VERSION}
    for key in CHUNK_METADATA_KEYS:
        value = meta.get(key)
        if value is None or value == "":
            continue
        payload[key] = _normalize_metadata_value(value)
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def chunk_table_doc_ids() -> Set[str]:
    """Return pdf_name values already present in EMBEDDINGS_TABLE."""
    return table_doc_ids(EMBEDDINGS_TABLE)


def table_doc_ids(table_name: str, id_column: str = "pdf_name") -> Set[str]:
    """Return distinct document ids from any Delta table that exposes pdf_name."""
    try:
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()
        spark.sql(f"DESCRIBE TABLE {table_name}")
        rows = spark.sql(
            f"SELECT DISTINCT {id_column} FROM {table_name}"
        ).collect()
        return {row[id_column] for row in rows if row[id_column]}
    except Exception:
        return set()


def _sql_string_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def delete_chunk_rows_for_doc_ids(doc_ids: Set[str] | List[str], batch_size: int = 200) -> int:
    """Delete existing chunk rows for a document subset before one-time reingest."""
    unique_doc_ids = sorted({doc_id for doc_id in doc_ids if doc_id})
    if not unique_doc_ids:
        return 0

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    deleted_rows = 0

    for start in range(0, len(unique_doc_ids), batch_size):
        batch = unique_doc_ids[start:start + batch_size]
        ids_sql = ", ".join(_sql_string_literal(doc_id) for doc_id in batch)
        row_count = spark.sql(
            f"SELECT COUNT(*) AS row_count FROM {EMBEDDINGS_TABLE} WHERE pdf_name IN ({ids_sql})"
        ).collect()[0]["row_count"]
        if row_count:
            spark.sql(f"DELETE FROM {EMBEDDINGS_TABLE} WHERE pdf_name IN ({ids_sql})")
            deleted_rows += int(row_count)

    if deleted_rows:
        logger.info(
            f"[OK] Deleted {deleted_rows} existing rows for {len(unique_doc_ids)} targeted PDFs"
        )

    return deleted_rows


def _dedupe_esn_values(*groups: Any) -> List[str]:
    merged: List[str] = []
    seen: Set[str] = set()

    for group in groups:
        for value in group or []:
            token = str(value or "").strip().upper()
            if not token or token in seen:
                continue
            seen.add(token)
            merged.append(token)

    return merged


def _pick_ref_report_date(raw_values: List[Any] | None) -> Optional[_date]:
    parsed_dates: List[_date] = []

    for raw_value in raw_values or []:
        if raw_value is None:
            continue
        if isinstance(raw_value, datetime):
            parsed_dates.append(raw_value.date())
            continue
        if isinstance(raw_value, _date):
            parsed_dates.append(raw_value)
            continue

        text = str(raw_value).strip()
        if not text:
            continue
        if "T" in text:
            text = text.split("T", 1)[0]
        try:
            parsed_dates.append(_date.fromisoformat(text))
        except (ValueError, TypeError):
            continue

    if not parsed_dates:
        return None

    return max(parsed_dates)


def load_ref_view_lookup() -> dict:
    """Load the FSR reference view into a Python dict for in-process lookups."""
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    lookup: dict = {}
    multi_esn_doc_ids = 0

    try:
        rows = spark.sql(
            f"""
            SELECT regexp_replace(lower(s3_filename), '\\.pdf$', '') AS norm_key,
                   sort_array(collect_set(esn))          AS esns,
                   collect_set(report_issued_date)       AS report_issued_dates
            FROM {FSR_REF_VIEW}
            WHERE s3_filename IS NOT NULL
              AND esn IS NOT NULL
            GROUP BY regexp_replace(lower(s3_filename), '\\.pdf$', '')
            """
        ).collect()

        for row in rows:
            esns = _dedupe_esn_values(row["esns"])
            if not esns:
                continue

            lookup[row["norm_key"]] = {
                "esns": esns,
                "report_date": _pick_ref_report_date(row["report_issued_dates"]),
            }
            if len(esns) > 1:
                multi_esn_doc_ids += 1

        logger.info(
            f"[OK] Loaded {len(lookup)} entries from {FSR_REF_VIEW} "
            f"({multi_esn_doc_ids} with multiple ESNs)"
        )
    except Exception as exc:
        logger.warning(
            f"[WARN] Could not load ref view {FSR_REF_VIEW}: {exc} — ref enrichment disabled"
        )

    return lookup


def _delta_schema():
    from pyspark.sql.types import (
        DateType,
        IntegerType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    return StructType([
        StructField("chunk_id", StringType(), nullable=False),
        StructField("pdf_name", StringType(), nullable=False),
        StructField("page_number", IntegerType(), nullable=True),
        StructField("generator_serial", StringType(), nullable=True),
        StructField("report_date", DateType(), nullable=True),
        StructField("chunk_text", StringType(), nullable=False),
        StructField(METADATA_COLUMN, StringType(), nullable=True),
        StructField("created_at", TimestampType(), nullable=True),
        StructField("uploaded_at", TimestampType(), nullable=True),
    ])


def _parse_date(value):
    if value is None:
        return None
    if isinstance(value, _date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return _date.fromisoformat(value.strip())
        except (ValueError, TypeError):
            return None
    return None


def build_delta_rows(
    documents: List[Document],
    ref_lookup: dict | None = None,
    source_doc_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> List[dict]:
    """Resolve documents into Delta-ready rows without writing them."""
    if not documents:
        logger.warning(
            f"[WARN] Empty document batch for {source_doc_id or 'unknown source'} — skipping Delta write"
        )
        return []

    now = created_at or datetime.utcnow()
    rows = []

    for doc in documents:
        meta = doc.metadata
        doc_id = meta.get("document_id", "")
        chunk_index = int(meta.get("chunk_index", 0))
        esn_labels = _dedupe_esn_values(meta.get("esn_labels", []) or [])
        report_date = _parse_date(meta.get("report_date"))

        ref_esns: List[str] = []
        ref_date = None
        if ref_lookup:
            ref_entry = ref_lookup.get(doc_id.lower())
            if ref_entry:
                ref_esns = _dedupe_esn_values(ref_entry.get("esns", []) or [])
                ref_date = ref_entry["report_date"]

        final_esns = _dedupe_esn_values(ref_esns, esn_labels)
        primary_esn = final_esns[0] if final_esns else meta.get("generator_serial")

        final_date = ref_date if ref_date is not None else report_date
        common = {
            "pdf_name": doc_id,
            "page_number": meta["start_page"],
            "report_date": final_date,
            "chunk_text": doc.page_content,
            METADATA_COLUMN: _serialize_chunk_metadata(meta),
            "created_at": now,
            "uploaded_at": now,
        }

        if len(final_esns) > 1:
            for esn in final_esns:
                rows.append({
                    **common,
                    "chunk_id": f"{doc_id}_{chunk_index}__{esn}",
                    "generator_serial": esn,
                })
        else:
            rows.append({
                **common,
                "chunk_id": f"{doc_id}_{chunk_index}",
                "generator_serial": primary_esn,
            })

    if not rows:
        logger.warning(
            f"[WARN] Empty Delta row batch for {source_doc_id or 'unknown source'} — skipping Delta write"
        )

    return rows


def save_rows_to_delta(rows: List[dict]) -> int:
    """Append pre-built Delta rows in a single transaction."""
    if not rows:
        return 0

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    ensure_metadata_column(spark)
    df = spark.createDataFrame(rows, schema=_delta_schema())

    for attempt in range(1, DELTA_APPEND_MAX_RETRIES + 1):
        try:
            df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(EMBEDDINGS_TABLE)
            return len(rows)
        except Exception as exc:
            error_text = str(exc)
            is_concurrent_append = (
                "ConcurrentAppendException" in error_text
                or "DELTA_CONCURRENT_APPEND" in error_text
            )
            if not is_concurrent_append or attempt >= DELTA_APPEND_MAX_RETRIES:
                raise

            wait_seconds = attempt * 5
            logger.warning(
                f"[WARN] Delta append hit concurrent update on attempt {attempt}/{DELTA_APPEND_MAX_RETRIES}; retrying in {wait_seconds}s"
            )
            time.sleep(wait_seconds)

    return len(rows)


def save_chunks_to_delta(
    documents: List[Document],
    ref_lookup: dict | None = None,
    source_doc_id: Optional[str] = None,
) -> int:
    """
    Build fully-resolved rows and append them to EMBEDDINGS_TABLE.

    ESN expansion duplicates one row per ESN label so equality filters on
    generator_serial surface the chunk for every tagged unit.
    """
    rows = build_delta_rows(
        documents,
        ref_lookup=ref_lookup,
        source_doc_id=source_doc_id,
    )
    return save_rows_to_delta(rows)


def merge_ref_view_metadata(spark):
    """Overwrite generator_serial and report_date from the FSR reference view."""
    try:
        spark.sql(
            f"""
            MERGE INTO {EMBEDDINGS_TABLE} AS t
            USING (
                SELECT regexp_replace(lower(s3_filename), '\\.pdf$', '') AS norm_key,
                       FIRST(esn)                AS esn,
                       FIRST(report_issued_date) AS report_issued_date
                FROM {FSR_REF_VIEW}
                WHERE s3_filename IS NOT NULL
                  AND esn IS NOT NULL
                GROUP BY regexp_replace(lower(s3_filename), '\\.pdf$', '')
            ) AS ref
            ON lower(t.pdf_name) = ref.norm_key
            WHEN MATCHED THEN UPDATE SET
                t.generator_serial = ref.esn,
                t.report_date = CAST(ref.report_issued_date AS DATE)
            """
        )
        logger.info(
            f"[OK] Enriched generator_serial + report_date from {FSR_REF_VIEW}"
        )
    except Exception as exc:
        logger.warning(f"[WARN] Metadata enrichment failed (non-fatal): {exc}")