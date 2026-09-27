# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_esn_backfill — Tier 3: LLM ESN Backfill for Existing Documents
#
# Re-analyzes all documents in the metadata table using the Tier 2 LLM ESN
# frequency method (fsr_esn_identifier). For any doc where the LLM identifies
# ESNs not already covered by fsr_pdf_ref or metadata, this notebook:
#
#   1. Reads the source PDF via its volume_path
#   2. Runs LLM ESN count (analyze_document_text_for_esn_counts)
#   3. Qualifies ESNs with threshold (qualify_esn_counts)
#   4. Unions with fsr_pdf_ref ESNs
#   5. For any NEW ESNs not already in the chunk table:
#        - Copies existing chunk rows with new chunk_id (esn-suffixed)
#        - Reuses existing embeddings (no re-embedding)
#   6. Updates metadata.all_esns + esn_detect_status
#
# Resume capability: skip docs with esn_detect_status = 'completed'.
# DRY_RUN mode (default): previews changes without writing.
#
# Run params:
#   DRY_RUN            (default "true")  — preview only, no writes
#   FSR_BACKFILL_LIMIT (default "100")   — docs to process per run (resume from previous)
#   FSR_BACKFILL_RESET (default "false") — reset esn_detect_status for all docs (re-run from scratch)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet PyMuPDF

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

# MAGIC %run ../../../common/fsr_chunking

# COMMAND ----------

# MAGIC %run ../../../common/fsr_esn_identifier

# COMMAND ----------

import hashlib
import json
import logging
import time
from datetime import datetime, timezone

import fitz  # PyMuPDF

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, current_timestamp
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    DoubleType, ArrayType, TimestampType, DateType,
)

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.esn_backfill")

# COMMAND ----------

DRY_RUN = get_runtime_param("DRY_RUN", "true").strip().lower() == "true"
BACKFILL_LIMIT = int(get_runtime_param("FSR_BACKFILL_LIMIT", "100"))
BACKFILL_RESET = get_runtime_param("FSR_BACKFILL_RESET", "false").strip().lower() == "true"

log.info("=== FSR ESN Backfill (Tier 3) ===")
log.info(f"  Metadata table : {METADATA_TABLE}")
log.info(f"  Chunk table    : {CHUNK_TABLE}")
log.info(f"  PDF ref view   : {FSR_PDF_REF_VIEW}")
log.info(f"  ESN LLM model  : {FSR_ESN_LLM_MODEL}")
log.info(f"  Min ESN count  : {FSR_ESN_MIN_COUNT}")
log.info(f"  Min ESN frac   : {FSR_ESN_MIN_FRACTION}")
log.info(f"  Batch limit    : {BACKFILL_LIMIT}")
log.info(f"  DRY_RUN        : {DRY_RUN}")
log.info(f"  RESET          : {BACKFILL_RESET}")

# COMMAND ----------

# ── Ensure esn_detect_status column exists ─────────────────────────────────
try:
    spark.sql(f"""
        ALTER TABLE {METADATA_TABLE}
        ADD COLUMNS IF NOT EXISTS (
            esn_detect_status STRING COMMENT 'LLM ESN detection status: null/pending/completed/failed',
            all_esns STRING COMMENT 'JSON array of all associated ESNs from fsr_pdf_ref + LLM detection'
        )
    """)
    log.info("Schema: esn_detect_status + all_esns columns ensured")
except Exception as e:
    log.warning(f"ALTER TABLE failed (may already exist): {e}")

# COMMAND ----------

# ── Optionally reset all pending docs ──────────────────────────────────────
if BACKFILL_RESET:
    spark.sql(f"""
        UPDATE {METADATA_TABLE}
        SET esn_detect_status = NULL
        WHERE esn_detect_status = 'completed'
    """)
    log.info("RESET: cleared esn_detect_status for all docs")

# COMMAND ----------

# ── Load fsr_pdf_ref ESN map ───────────────────────────────────────────────
_ref_esn_map = {}
try:
    _esn_rows = spark.sql(f"""
        SELECT LOWER(TRIM(s3_filename)) AS doc_id, esn
        FROM {FSR_PDF_REF_VIEW}
        WHERE esn IS NOT NULL AND TRIM(esn) != ''
    """).collect()
    for row in _esn_rows:
        _ref_esn_map.setdefault(row.doc_id, set()).add(row.esn.strip())
    log.info(f"Loaded fsr_pdf_ref ESN map: {len(_ref_esn_map)} docs")
except Exception as e:
    log.warning(f"fsr_pdf_ref not accessible: {e}")

# COMMAND ----------

# ── Query: pending backfill docs ──────────────────────────────────────────
pending_df = spark.sql(f"""
    SELECT document_id, volume_path, esn, all_esns
    FROM {METADATA_TABLE}
    WHERE chunk_status = 'completed'
      AND (esn_detect_status IS NULL OR esn_detect_status = 'failed')
    LIMIT {BACKFILL_LIMIT}
""")
pending_rows = pending_df.collect()
total_pending = spark.sql(f"""
    SELECT COUNT(*) AS cnt FROM {METADATA_TABLE}
    WHERE chunk_status = 'completed'
      AND (esn_detect_status IS NULL OR esn_detect_status = 'failed')
""").first().cnt

log.info(f"Pending: {total_pending} docs total; processing batch of {len(pending_rows)}")

if not pending_rows:
    log.info("Nothing to process — all docs already have esn_detect_status=completed")
    dbutils.notebook.exit("NOOP: no pending docs")  # noqa: F821

# COMMAND ----------

# ── Process each doc ──────────────────────────────────────────────────────
stats = {"processed": 0, "esns_found": 0, "new_chunks": 0, "errors": 0, "no_new_esns": 0}
chunk_rows_to_insert = []
metadata_updates = []  # list of {document_id, all_esns, esn_detect_status}

for idx, row in enumerate(pending_rows):
    doc_key = row.document_id
    vol_path = row.volume_path
    meta_esn = (row.esn or "").strip()

    try:
        # ── Extract text from PDF ────────────────────────────────────────
        snapshot = load_pdf_snapshot(vol_path)
        full_text = "\n\n".join(page_text_from_snapshot(p) for p in snapshot)

        # ── LLM ESN detection ────────────────────────────────────────────
        counts = analyze_document_text_for_esn_counts(full_text)
        llm_esns = qualify_esn_counts(
            counts,
            min_count=FSR_ESN_MIN_COUNT,
            min_fraction=FSR_ESN_MIN_FRACTION,
        )

        # ── Union all sources ────────────────────────────────────────────
        ref_esns = _ref_esn_map.get(doc_key.lower(), set())
        all_esns = set(ref_esns) | set(llm_esns)
        if meta_esn:
            all_esns.add(meta_esn)
        all_esns_list = sorted(all_esns)
        all_esns_json = json.dumps(all_esns_list)

        # ── Check which ESNs are not yet in chunk table ──────────────────
        if all_esns:
            existing_esns_rows = spark.sql(f"""
                SELECT DISTINCT esn FROM {CHUNK_TABLE}
                WHERE document_id = '{doc_key}'
                  AND esn IS NOT NULL
            """).collect()
            existing_esns = {r.esn for r in existing_esns_rows}
            new_esns = all_esns - existing_esns
        else:
            new_esns = set()

        if not new_esns:
            stats["no_new_esns"] += 1
            metadata_updates.append({
                "document_id": doc_key,
                "all_esns": all_esns_json,
                "esn_detect_status": "completed",
            })
            log.info(f"  [SKIP] {doc_key[:40]}: no new ESNs (all {len(all_esns)} already present)")
            stats["processed"] += 1
            continue

        stats["esns_found"] += len(new_esns)
        log.info(f"  [NEW] {doc_key[:40]}: {new_esns} (ref={ref_esns}, llm={set(llm_esns)})")

        # ── Copy existing chunks for each new ESN (reuse embeddings) ────
        existing_chunks_rows = spark.sql(f"""
            SELECT chunk_index, chunk_text, page_number, chunk_embedding, metadata,
                   pdf_name, report_date
            FROM {CHUNK_TABLE}
            WHERE document_id = '{doc_key}'
            ORDER BY chunk_index, esn
        """).dropDuplicates(["chunk_index"]).collect()

        now = datetime.now(timezone.utc)
        for esn in sorted(new_esns):
            for cr in existing_chunks_rows:
                ci = cr.chunk_index
                chunk_id = hashlib.md5(f"{doc_key}_{ci}__{esn}".encode("utf-8")).hexdigest()

                # Update metadata JSON to reflect correct ESN
                try:
                    meta_dict = json.loads(cr.metadata or "{}")
                except Exception:
                    meta_dict = {}
                meta_dict["esn"] = esn
                metadata_json = json.dumps(meta_dict)

                chunk_rows_to_insert.append({
                    "chunk_id": chunk_id,
                    "chunk_index": ci,
                    "document_id": doc_key,
                    "pdf_name": cr.pdf_name,
                    "page_number": cr.page_number,
                    "chunk_text": cr.chunk_text,
                    "esn": esn,
                    "report_date": cr.report_date,
                    "chunk_embedding": cr.chunk_embedding,
                    "metadata": metadata_json,
                    "created_at": now,
                })
                stats["new_chunks"] += 1

        metadata_updates.append({
            "document_id": doc_key,
            "all_esns": all_esns_json,
            "esn_detect_status": "completed",
        })
        stats["processed"] += 1

    except Exception as exc:
        log.warning(f"  [FAIL] {doc_key[:40]}: {exc}")
        stats["errors"] += 1
        metadata_updates.append({
            "document_id": doc_key,
            "all_esns": None,
            "esn_detect_status": "failed",
        })

    if (idx + 1) % 10 == 0:
        log.info(f"Progress: {idx + 1}/{len(pending_rows)} | "
                 f"new_chunks={stats['new_chunks']} errors={stats['errors']}")

log.info(f"\nSummary: processed={stats['processed']}, no_new_esns={stats['no_new_esns']}, "
         f"esns_found={stats['esns_found']}, new_chunks={stats['new_chunks']}, "
         f"errors={stats['errors']}")

# COMMAND ----------

if DRY_RUN:
    log.info("\n*** DRY_RUN=true — No changes written. ***")
    log.info(f"Would insert {stats['new_chunks']} new chunk rows for {stats['esns_found']} new ESNs")
    log.info(f"Would update {len(metadata_updates)} metadata rows")
    dbutils.notebook.exit(  # noqa: F821
        f"DRY_RUN: {stats['new_chunks']} chunks to insert, {len(metadata_updates)} metadata to update"
    )

# COMMAND ----------

# ── Write new chunk rows ──────────────────────────────────────────────────
if chunk_rows_to_insert:
    schema = StructType([
        StructField("chunk_id", StringType(), False),
        StructField("chunk_index", IntegerType(), True),
        StructField("document_id", StringType(), False),
        StructField("pdf_name", StringType(), True),
        StructField("page_number", IntegerType(), True),
        StructField("chunk_text", StringType(), False),
        StructField("esn", StringType(), True),
        StructField("report_date", DateType(), True),
        StructField("chunk_embedding", ArrayType(DoubleType()), True),
        StructField("metadata", StringType(), True),
        StructField("created_at", TimestampType(), True),
    ])

    new_chunk_df = spark.createDataFrame(chunk_rows_to_insert, schema=schema)
    new_chunk_df.createOrReplaceTempView("_fsr_backfill_chunks")

    spark.sql(f"""
        MERGE INTO {CHUNK_TABLE} AS tgt
        USING _fsr_backfill_chunks AS src
        ON tgt.chunk_id = src.chunk_id
        WHEN NOT MATCHED THEN INSERT *
    """)
    log.info(f"Inserted {stats['new_chunks']} new chunk rows")
else:
    log.info("No new chunk rows to insert")

# COMMAND ----------

# ── Update metadata rows (all_esns + esn_detect_status) ──────────────────
if metadata_updates:
    import pandas as pd
    meta_df = spark.createDataFrame(pd.DataFrame(metadata_updates))
    meta_df.createOrReplaceTempView("_fsr_backfill_meta_updates")

    spark.sql(f"""
        MERGE INTO {METADATA_TABLE} AS tgt
        USING _fsr_backfill_meta_updates AS src
        ON tgt.document_id = src.document_id
        WHEN MATCHED THEN UPDATE SET
            tgt.all_esns = src.all_esns,
            tgt.esn_detect_status = src.esn_detect_status
    """)
    log.info(f"Updated {len(metadata_updates)} metadata rows")

# COMMAND ----------

log.info("\n=== Backfill complete ===")
log.info(f"  Processed    : {stats['processed']} docs")
log.info(f"  No new ESNs  : {stats['no_new_esns']}")
log.info(f"  New ESNs     : {stats['esns_found']}")
log.info(f"  New chunks   : {stats['new_chunks']}")
log.info(f"  Errors       : {stats['errors']}")
log.info(f"  Remaining    : {total_pending - stats['processed'] - stats['errors']} docs still pending")
log.info("")
log.info("Next steps:")
log.info("  1. Re-run to process next batch (resume from esn_detect_status=failed or null)")
log.info("  2. After all docs complete, trigger VS index sync")
log.info("     Run: nb_sdg_fsr_vs_sync")

dbutils.notebook.exit(  # noqa: F821
    f"BACKFILL: {stats['new_chunks']} chunks inserted, "
    f"{stats['processed']} docs done, {stats['errors']} errors, "
    f"{total_pending - stats['processed'] - stats['errors']} remaining"
)
