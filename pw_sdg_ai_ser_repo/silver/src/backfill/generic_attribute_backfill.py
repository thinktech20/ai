"""Generic attribute backfill runner for FSR metadata table.

Design goals:
- Run as Databricks `spark_python_task` (no notebook magics).
- Be reusable for future attribute backfills via a strategy registry.
- Keep extraction idempotent and restart-safe.
"""

import argparse
import json
import os
import re
import uuid
from abc import ABC, abstractmethod
from collections import Counter, defaultdict

import pandas as pd
from delta.tables import DeltaTable
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StringType, StructField, StructType


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "t", "yes", "y", "on")


class BackfillStrategy(ABC):
    name: str

    @abstractmethod
    def build_scope_df(self, spark: SparkSession, table_name: str):
        pass

    @abstractmethod
    def result_schema(self) -> StructType:
        pass

    @abstractmethod
    def group_key(self) -> str:
        pass

    @abstractmethod
    def merge_condition(self, target_alias: str, source_alias: str) -> str:
        pass

    @abstractmethod
    def update_set(self) -> dict:
        pass


DOC_SUMMARY_PATTERN = re.compile(r"\bexecutive\s+summary\b|\bsummary\b", re.IGNORECASE)
DOC_SUMMARY_NOISE_PATTERN = re.compile(
    r"^[\s_\-\.\|]*$|^table\s+of\s+contents?$|^contents?$",
    re.IGNORECASE,
)
DOC_SUMMARY_ROW_TOLERANCE = 3
DOC_SUMMARY_FOOTER_CROP_RATIO = 0.90
DOC_SUMMARY_HEADER_ZONE_RATIO = 0.10
DOC_SUMMARY_FOOTER_ZONE_RATIO = 0.10


def _is_summary_title(title: str) -> bool:
    return bool(DOC_SUMMARY_PATTERN.search((title or "").strip()))


def _build_summary_sections(toc_entries, total_pages):
    sections = []
    for i, (title, start_page) in enumerate(toc_entries):
        if _is_summary_title(title):
            end_page = toc_entries[i + 1][1] - 1 if i + 1 < len(toc_entries) else total_pages
            sections.append({"title": title, "start_page": start_page, "end_page": end_page})
    return sections


def _extract_words_as_rows(page):
    words = page.extract_words(
        x_tolerance=3,
        y_tolerance=3,
        keep_blank_chars=False,
        use_text_flow=False,
    )
    if not words:
        return []

    rows = defaultdict(list)
    for w in words:
        rows[round(w["top"] / DOC_SUMMARY_ROW_TOLERANCE)].append(w)
    return [sorted(rows[k], key=lambda w: w["x0"]) for k in sorted(rows)]


def _detect_page_offset(pdf):
    offsets = []
    for i in range(min(10, len(pdf.pages))):
        page = pdf.pages[i]
        h = page.height
        for bbox in (
            (0, 0, page.width, h * DOC_SUMMARY_HEADER_ZONE_RATIO),
            (0, h * (1 - DOC_SUMMARY_FOOTER_ZONE_RATIO), page.width, h),
        ):
            text = page.within_bbox(bbox).extract_text() or ""
            for token in text.split():
                token = token.strip(".,|-()")
                if re.fullmatch(r"\d{1,4}", token):
                    printed = int(token)
                    if printed > 0:
                        offsets.append((i + 1) - printed)
    return Counter(offsets).most_common(1)[0][0] if offsets else 0


def _extract_toc_entries(pdf):
    entries, seen = [], set()
    for page_num in range(min(5, len(pdf.pages))):
        page = pdf.pages[page_num]
        split_x = page.width * 0.75
        cropped = page.within_bbox((0, 0, page.width, page.height * DOC_SUMMARY_FOOTER_CROP_RATIO))

        for row in _extract_words_as_rows(cropped):
            left = [w["text"] for w in row if w["x0"] < split_x]
            right = [w["text"] for w in row if w["x0"] >= split_x]
            title = " ".join(left).strip()
            right_clean = re.sub(r"^[\s_\.]+", "", " ".join(right).strip())

            if not title or DOC_SUMMARY_NOISE_PATTERN.match(title):
                continue
            if not re.fullmatch(r"\d+", right_clean):
                continue

            key = (title, int(right_clean))
            if key not in seen:
                seen.add(key)
                entries.append(key)
    return entries


def _extract_section_text(pdf, start_page, end_page, offset):
    total = len(pdf.pages)
    parts = []
    for p in range(start_page, end_page + 1):
        idx = p - 1 + offset
        if 0 <= idx < total:
            page = pdf.pages[idx]
            cropped = page.within_bbox((0, 0, page.width, page.height * DOC_SUMMARY_FOOTER_CROP_RATIO))
            text = (cropped.extract_text() or "").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def _get_combined_summary(volume_path: str, max_pages: int):
    try:
        import pdfplumber

        with pdfplumber.open(volume_path) as pdf:
            total_pages = len(pdf.pages)
            if total_pages > max_pages:
                return "", "too_large", f"pages={total_pages} > {max_pages}"

            toc_entries = _extract_toc_entries(pdf)
            if not toc_entries:
                return "", "no_toc", "No TOC entries found"

            sections = _build_summary_sections(toc_entries, total_pages)
            if not sections:
                return "", "no_summary_section", "No summary-like TOC section found"

            offset = _detect_page_offset(pdf)
            for section in sections:
                section["text"] = _extract_section_text(
                    pdf,
                    section["start_page"],
                    section["end_page"],
                    offset,
                )

            combined = "\n\n".join(section["text"] for section in sections if section.get("text"))
            if combined.strip():
                return combined, "extracted", None
            return "", "empty_after_extraction", "Summary section(s) found but empty"
    except Exception as e:
        return "", "failed", str(e)[:1000]


def _build_extract_partition_doc_summary(max_pages: int):
    def _extract_partition_doc_summary(pdf: pd.DataFrame) -> pd.DataFrame:
        out = []
        for _, row in pdf.iterrows():
            volume_path = row["volume_path"]
            summary, status, err = _get_combined_summary(volume_path, max_pages=max_pages)
            out.append(
                {
                    "volume_path": volume_path,
                    "document_summary": summary if status == "extracted" else None,
                    "document_summary_status": status,
                    "document_summary_error": err,
                }
            )
        return pd.DataFrame(
            out,
            columns=["volume_path", "document_summary", "document_summary_status", "document_summary_error"],
        )

    return _extract_partition_doc_summary


class DocSummaryTocStrategy(BackfillStrategy):
    name = "document_summary_toc"
    check_name = "doc_summary_extraction"

    def build_scope_df(self, spark: SparkSession, table_name: str):
        # Always-overwrite semantics: scope is every distinct volume_path.
        # Operator gates volume via --sample-limit; failures go to DQ log.
        return (
            spark.table(table_name)
            .filter(F.col("volume_path").isNotNull())
            .select("volume_path")
            .dropDuplicates(["volume_path"])
        )

    def result_schema(self) -> StructType:
        # status/error stay in the in-memory result frame so the driver can
        # route failures to the DQ log; only document_summary is merged into
        # the metadata table.
        return StructType(
            [
                StructField("volume_path", StringType(), False),
                StructField("document_summary", StringType(), True),
                StructField("document_summary_status", StringType(), True),
                StructField("document_summary_error", StringType(), True),
            ]
        )

    def group_key(self) -> str:
        return "volume_path"

    def merge_condition(self, target_alias: str, source_alias: str) -> str:
        return f"{target_alias}.volume_path = {source_alias}.volume_path"

    def update_set(self) -> dict:
        return {
            "document_summary": "src.document_summary",
        }


STRATEGY_REGISTRY = {
    DocSummaryTocStrategy.name: (DocSummaryTocStrategy(), _build_extract_partition_doc_summary),
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generic FSR attribute backfill runner")
    parser.add_argument("--table", default=os.getenv("FSR_METADATA_TABLE", ""), help="Delta table to update")
    parser.add_argument(
        "--backfill-name",
        default=os.getenv("FSR_BACKFILL_NAME", "document_summary_toc"),
        help="Backfill strategy key",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("FSR_BACKFILL_BATCH_SIZE", "200")),
        help="Unique key rows per batch",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=int(os.getenv("FSR_BACKFILL_SAMPLE_LIMIT", "0")),
        help="Stop after N keys (0 means no limit)",
    )
    parser.add_argument(
        "--dry-run",
        default=os.getenv("FSR_BACKFILL_DRY_RUN", "false"),
        help="If true, computes first batch only and skips merge",
    )
    parser.add_argument(
        "--dq-log-table",
        default=os.getenv("FSR_DQ_LOG_TABLE", ""),
        help="Delta table for per-failure WARN rows (FSR data quality log)",
    )
    parser.add_argument(
        "--run-log-table",
        default=os.getenv("FSR_RUN_LOG_TABLE", ""),
        help="Delta table for per-run summary rows (FSR run log)",
    )
    parser.add_argument(
        "--chunk-table",
        default=os.getenv("FSR_CHUNK_TABLE", ""),
        help="Optional chunk table whose metadata JSON column should be patched in lock-step",
    )
    return parser.parse_args()


def _write_dq_findings(spark: SparkSession, dq_table: str, run_id: str,
                       check_name: str, failures: list) -> None:
    """Append per-failed-path WARN rows to the FSR data quality log.

    failures is a list of (volume_path, status, error) tuples for rows where
    extraction did not return 'extracted'.
    """
    if not dq_table or not failures:
        return
    import hashlib
    from datetime import datetime, timezone
    from pyspark.sql.types import StructType, StructField, StringType, TimestampType

    now = datetime.now(timezone.utc)
    rows = []
    for vp, status, err in failures:
        dq_id = hashlib.md5(f"{run_id}|{vp}|{check_name}".encode()).hexdigest()
        detail = f"status={status}" + (f"; error={err}" if err else "")
        rows.append({
            "dq_id": dq_id,
            "run_id": run_id,
            "document_id": None,    # backfill is per volume_path; doc_id resolved at query time
            "pdf_name": vp,
            "check_name": check_name,
            "severity": "WARN",
            "failure_category": status,
            "detail": (detail or "")[:500],
            "created_at": now,
        })
    schema = StructType([
        StructField("dq_id", StringType(), False),
        StructField("run_id", StringType(), True),
        StructField("document_id", StringType(), True),
        StructField("pdf_name", StringType(), True),
        StructField("check_name", StringType(), False),
        StructField("severity", StringType(), False),
        StructField("failure_category", StringType(), True),
        StructField("detail", StringType(), True),
        StructField("created_at", TimestampType(), True),
    ])
    try:
        spark.createDataFrame(rows, schema=schema).write.mode("append").saveAsTable(dq_table)
        print(f"DQ log: wrote {len(rows)} WARN row(s) to {dq_table}")
    except Exception as e:
        print(f"DQ log write failed (non-blocking): {e}")


def _patch_chunks_doc_summary(spark: SparkSession, chunk_table: str,
                              metadata_table: str, success_results) -> int:
    """Patch the document_summary key inside the chunk table's metadata JSON.

    Re-uses chunk text + embeddings (no re-chunking, no re-embedding). Maps
    each successfully extracted volume_path back to its document_id(s) via the
    metadata table (handles multi-ESN fan-out where one volume_path -> N
    document_ids).

    Returns the number of chunk rows updated.
    """
    if not chunk_table:
        print("Chunk table not configured; skipping chunk metadata patch.")
        return 0
    if success_results is None or success_results.limit(1).count() == 0:
        print("No successful extractions; skipping chunk metadata patch.")
        return 0

    from pyspark.sql.functions import pandas_udf

    meta_df = (
        spark.table(metadata_table)
        .select("document_id", "volume_path")
        .filter(F.col("document_id").isNotNull() & F.col("volume_path").isNotNull())
    )
    updates = (
        success_results.alias("s")
        .join(meta_df.alias("m"), "volume_path")
        .select("m.document_id", "s.document_summary")
    )
    n_docs = updates.count()
    if n_docs == 0:
        print("No matching document_id rows for successful volume_paths; skipping chunk patch.")
        return 0

    @pandas_udf(StringType())
    def _patch(meta_json: pd.Series, new_summary: pd.Series) -> pd.Series:
        out = []
        for m, s in zip(meta_json, new_summary):
            if m is None:
                out.append(json.dumps({"document_summary": s}))
                continue
            try:
                d = json.loads(m)
            except Exception:
                out.append(m)
                continue
            d["document_summary"] = s
            out.append(json.dumps(d, default=str))
        return pd.Series(out)

    chunks = spark.table(chunk_table).select("chunk_id", "document_id", "metadata")
    patched_raw = (
        chunks.alias("c")
        .join(updates.alias("u"), "document_id")
        .withColumn("new_metadata", _patch(F.col("c.metadata"), F.col("u.document_summary")))
        .select("chunk_id", F.col("new_metadata").alias("metadata"))
    )

    # Serverless does not support .cache(); materialize to a temp Delta table so
    # the join + UDF runs once for both the count and the MERGE.
    catalog_schema = ".".join(chunk_table.split(".")[:2])
    temp_chunk_patch = f"{catalog_schema}._tmp_chunk_patch_{uuid.uuid4().hex[:8]}"
    print(f"Materializing chunk patch to temp table: {temp_chunk_patch}")
    patched_raw.write.mode("overwrite").saveAsTable(temp_chunk_patch)
    patched = spark.table(temp_chunk_patch)

    try:
        n_chunks = patched.count()
        if n_chunks == 0:
            print(f"No chunks found for {n_docs} document_id(s); nothing to patch.")
            return 0

        chunk_delta = DeltaTable.forName(spark, chunk_table)
        (
            chunk_delta.alias("tgt")
            .merge(patched.alias("src"), "tgt.chunk_id = src.chunk_id")
            .whenMatchedUpdate(set={"metadata": "src.metadata"})
            .execute()
        )
        print(
            f"Chunk table: patched document_summary in metadata JSON for "
            f"{n_chunks} chunk row(s) across {n_docs} document_id(s) in {chunk_table}"
        )
        return n_chunks
    finally:
        try:
            spark.sql(f"DROP TABLE IF EXISTS {temp_chunk_patch}")
            print(f"Dropped temp table: {temp_chunk_patch}")
        except Exception as e:
            print(f"WARN: failed to drop temp table {temp_chunk_patch}: {e}")


def _write_run_summary(spark: SparkSession, run_log_table: str, run_id: str,
                       job_name: str, start_time, end_time,
                       docs_claimed: int, docs_succeeded: int, docs_failed: int,
                       error_summary: str, chunks_written: int = None) -> None:
    if not run_log_table:
        return
    from datetime import datetime, timezone
    from pyspark.sql.types import (
        StructType, StructField, StringType, TimestampType, DoubleType, IntegerType,
    )

    duration = (end_time - start_time).total_seconds() if end_time and start_time else None
    schema = StructType([
        StructField("run_id", StringType(), False),
        StructField("job_name", StringType(), True),
        StructField("start_time", TimestampType(), False),
        StructField("end_time", TimestampType(), True),
        StructField("duration_seconds", DoubleType(), True),
        StructField("docs_claimed", IntegerType(), True),
        StructField("docs_succeeded", IntegerType(), True),
        StructField("docs_failed", IntegerType(), True),
        StructField("chunks_written", IntegerType(), True),
        StructField("error_summary", StringType(), True),
        StructField("created_at", TimestampType(), True),
    ])
    row = [{
        "run_id": run_id,
        "job_name": job_name,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration,
        "docs_claimed": docs_claimed,
        "docs_succeeded": docs_succeeded,
        "docs_failed": docs_failed,
        "chunks_written": chunks_written,
        "error_summary": error_summary,
        "created_at": datetime.now(timezone.utc),
    }]
    try:
        spark.createDataFrame(row, schema=schema).write.mode("append").saveAsTable(run_log_table)
        print(f"Run log: wrote run summary to {run_log_table} (run_id={run_id})")
    except Exception as e:
        print(f"Run log write failed (non-blocking): {e}")


def main():
    from datetime import datetime, timezone

    args = _parse_args()
    if not args.table:
        raise ValueError("Missing --table or FSR_METADATA_TABLE")

    if args.backfill_name not in STRATEGY_REGISTRY:
        available = ", ".join(sorted(STRATEGY_REGISTRY.keys()))
        raise ValueError(f"Unsupported backfill '{args.backfill_name}'. Available: {available}")

    strategy, extractor_factory = STRATEGY_REGISTRY[args.backfill_name]
    partition_extractor = extractor_factory(args.docsummary_max_pages)
    dry_run = _as_bool(args.dry_run, default=False)

    spark = SparkSession.builder.getOrCreate()
    delta_table = DeltaTable.forName(spark, args.table)

    dq_table = args.dq_log_table
    run_log_table = args.run_log_table
    chunk_table = args.chunk_table
    run_id = f"backfill-{args.backfill_name}-{uuid.uuid4().hex[:12]}"
    job_name = f"PW_SDG_FSR_Generic_Attribute_Backfill[{args.backfill_name}]"
    start_time = datetime.now(timezone.utc)

    print(f"Starting backfill: {args.backfill_name}")
    print(f"Run ID: {run_id}")
    print(f"Target table: {args.table}")
    print(f"Repartition hint (--batch-size): {args.batch_size}")
    print(f"Sample limit: {args.sample_limit or 'none'}")
    print(f"Dry run: {dry_run}")

    # Single-pass scope: every distinct key in the table (no status gating).
    scope_df = strategy.build_scope_df(spark, args.table)
    if args.sample_limit:
        scope_df = scope_df.limit(args.sample_limit)

    n = scope_df.count()
    print(f"Scope: {n} key(s) to process")
    if n == 0:
        print("Empty scope. Nothing to do.")
        return

    n_parts = max(1, min(n, args.batch_size) // 25 or 1)
    raw_results = (
        scope_df.repartition(n_parts)
        .groupBy(strategy.group_key())
        .applyInPandas(partition_extractor, schema=strategy.result_schema())
    )

    # Serverless does not support .cache(); materialize via a temp Delta table so
    # pdfplumber runs once and downstream reads (dry-run sample, MERGE, chunk
    # patch) all hit the same materialized result.
    catalog_schema = ".".join(args.table.split(".")[:2])
    temp_results_table = f"{catalog_schema}._tmp_backfill_{args.backfill_name}_{uuid.uuid4().hex[:8]}"
    print(f"Materializing results to temp table: {temp_results_table}")
    raw_results.write.mode("overwrite").saveAsTable(temp_results_table)
    results = spark.table(temp_results_table)

    try:
        if dry_run:
            print("Dry run enabled. Sample output:")
            results.show(10, truncate=False)
            end_time = datetime.now(timezone.utc)
            _write_run_summary(
                spark, run_log_table, run_id, job_name, start_time, end_time,
                docs_claimed=n, docs_succeeded=0, docs_failed=0,
                error_summary="dry_run",
            )
            return

        # Status breakdown for run-log + DQ-log routing (driver-side collect).
        status_rows = results.groupBy("document_summary_status").count().collect()
        status_counts = {r["document_summary_status"]: r["count"] for r in status_rows}
        extracted = status_counts.get("extracted", 0)
        failed = sum(c for s, c in status_counts.items() if s != "extracted")
        print(f"Status breakdown: {status_counts}")

        failures = [
            (r["volume_path"], r["document_summary_status"], r["document_summary_error"])
            for r in results.filter(F.col("document_summary_status") != "extracted").collect()
        ]
        check_name = getattr(strategy, "check_name", args.backfill_name)
        _write_dq_findings(spark, dq_table, run_id, check_name, failures)

        # Merge only the successful rows; leave failed paths' summary untouched.
        success_results = results.filter(F.col("document_summary_status") == "extracted") \
                                 .select("volume_path", "document_summary")
        (
            delta_table.alias("tgt")
            .merge(success_results.alias("src"), strategy.merge_condition("tgt", "src"))
            .whenMatchedUpdate(set=strategy.update_set())
            .execute()
        )
        print(f"Merged {extracted} extracted summary rows into {args.table}")

        # Patch document_summary inside chunk table's metadata JSON for the same
        # documents (no re-chunk, no re-embed). Skipped if --chunk-table not set.
        chunks_patched = _patch_chunks_doc_summary(
            spark, chunk_table, args.table, success_results
        )

        end_time = datetime.now(timezone.utc)
        error_summary = ", ".join(f"{s}={c}" for s, c in sorted(status_counts.items()))
        _write_run_summary(
            spark, run_log_table, run_id, job_name, start_time, end_time,
            docs_claimed=n, docs_succeeded=extracted, docs_failed=failed,
            error_summary=error_summary, chunks_written=chunks_patched,
        )

        print("Backfill runner finished.")
    finally:
        try:
            spark.sql(f"DROP TABLE IF EXISTS {temp_results_table}")
            print(f"Dropped temp table: {temp_results_table}")
        except Exception as e:
            print(f"WARN: failed to drop temp table {temp_results_table}: {e}")


if __name__ == "__main__":
    main()
