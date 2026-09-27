# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_heatmap_ingestion — Heatmap Issue-Prompt Embedding Pipeline
#
# Single-notebook pipeline: Extract → Embed → Write
#
# Reads from the risk matrix source view, embeds the issue_prompt column,
# and writes to a Delta table. No chunking or VS sync needed.
#
# NOTE: Unlike the ER pipeline, Heatmap does NOT use watermark-based
# incremental extraction. The source view (fsr_unit_risk_matrix_view) is a
# small, slowly-changing risk matrix (~800 rows). A full-load + MERGE on
# every run is correct and efficient. If the source ever grows or gains a
# last_modified column, add watermark support modeled on the ER pattern.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/heatmap_config

# COMMAND ----------

import hashlib
import json
import logging
import time
from datetime import datetime, timezone

import pandas as pd

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("heatmap.ingestion")

# COMMAND ----------

# ── Step 1: Extract from source view ───────────────────────────────────────

def extract_heatmap_records() -> pd.DataFrame:
    """Query the heatmap source view and return filtered DataFrame.

    User-supplied filter values (HEATMAP_EQUIPMENT_TYPES, HEATMAP_PERSONAS)
    are applied via Spark DataFrame .filter().isin() to avoid SQL injection
    through job parameters.
    """
    sql = f"SELECT * FROM {HEATMAP_SOURCE_VIEW}"

    log.info(f"Extracting heatmap records: {sql[:200]}...")
    sdf = spark.sql(sql)

    # Apply user-supplied filter values via DataFrame API (not f-string SQL)
    if HEATMAP_EQUIPMENT_TYPES:
        from pyspark.sql.functions import col as _col
        sdf = sdf.filter(_col("equipment_type").isin(HEATMAP_EQUIPMENT_TYPES))
        log.info(f"  Applied equipment_type filter: {HEATMAP_EQUIPMENT_TYPES}")

    if HEATMAP_PERSONAS:
        from pyspark.sql.functions import col as _col
        sdf = sdf.filter(_col("persona").isin(HEATMAP_PERSONAS))
        log.info(f"  Applied persona filter: {HEATMAP_PERSONAS}")

    df = sdf.toPandas()
    log.info(f"Extracted {len(df)} records from {HEATMAP_SOURCE_VIEW}")

    # Filter rows that have a non-empty issue_prompt
    before = len(df)
    df = df[df["issue_prompt"].apply(lambda v: pd.notna(v) and str(v).strip() != "")]
    log.info(f"After filtering empty issue_prompt: {len(df)} rows (dropped {before - len(df)})")

    return df


# COMMAND ----------

# ── Step 2: Embed issue_prompt ─────────────────────────────────────────────

def embed_heatmap_records(df: pd.DataFrame) -> list[dict]:
    """Embed issue_prompt for each record and return list of row dicts."""
    rows = []
    total = len(df)
    embedded = 0
    failed = 0
    failed_indices: list[int] = []

    for batch_start in range(0, total, HEATMAP_EMBEDDING_BATCH_SIZE):
        batch_df = df.iloc[batch_start : batch_start + HEATMAP_EMBEDDING_BATCH_SIZE]
        texts = batch_df["issue_prompt"].tolist()

        try:
            vectors = embed_texts_batch(
                texts,
                base_url=LITELLM_BASE_URL,
                api_key=LITELLM_API_KEY,
                model=EMBEDDING_MODEL,
                dimension=EMBEDDING_DIMENSION,
                request_path=HEATMAP_EMBEDDING_REQUEST_PATH,
                verify_ssl=LLM_VERIFY_SSL,
                max_retries=HEATMAP_MAX_RETRIES,
            )
        except Exception as e:
            log.error(f"Embedding batch failed at offset {batch_start}: {e}")
            failed += len(batch_df)
            failed_indices.extend(range(batch_start, batch_start + len(batch_df)))
            continue

        for (_, row), vec in zip(batch_df.iterrows(), vectors):
            # Build a deterministic row_id from issue_prompt alone — after
            # dedup there is exactly one row per unique prompt, so the id
            # must depend only on the text that was embedded.
            row_id = hashlib.md5(str(row["issue_prompt"]).encode()).hexdigest()

            # Metadata: all source columns as JSON
            meta = {}
            for col in row.index:
                val = row[col]
                if col != "issue_prompt" and pd.notna(val) and str(val).strip():
                    meta[col] = str(val).strip()

            rows.append({
                "row_id": row_id,
                "equipment_type": str(row.get("equipment_type", "")) if pd.notna(row.get("equipment_type")) else None,
                "persona": str(row.get("persona", "")) if pd.notna(row.get("persona")) else None,
                "issue_prompt": str(row["issue_prompt"]),
                "issue_prompt_embedding": vec,
                "metadata": json.dumps(meta),
                "created_at": datetime.now(timezone.utc),
            })
            embedded += 1

        if batch_start > 0 and batch_start % (HEATMAP_EMBEDDING_BATCH_SIZE * 10) == 0:
            log.info(f"Embedding progress: {embedded}/{total}")

    log.info(f"Embedding complete: {embedded} succeeded, {failed} failed out of {total}")
    if failed_indices:
        log.warning(f"  {len(failed_indices)} rows failed embedding at DataFrame indices: "
                    f"{failed_indices[:20]}{'...' if len(failed_indices) > 20 else ''}")

        # ── Retry pass for failed rows ─────────────────────────────────────
        log.info(f"Retry pass: attempting {len(failed_indices)} previously failed rows")
        retry_df = df.iloc[failed_indices].reset_index(drop=True)
        retry_recovered = 0

        for retry_start in range(0, len(retry_df), HEATMAP_EMBEDDING_BATCH_SIZE):
            time.sleep(5)  # brief pause to let transient issues clear
            retry_batch = retry_df.iloc[retry_start : retry_start + HEATMAP_EMBEDDING_BATCH_SIZE]
            retry_texts = retry_batch["issue_prompt"].tolist()

            try:
                retry_vectors = embed_texts_batch(
                    retry_texts,
                    base_url=LITELLM_BASE_URL,
                    api_key=LITELLM_API_KEY,
                    model=EMBEDDING_MODEL,
                    dimension=EMBEDDING_DIMENSION,
                    request_path=HEATMAP_EMBEDDING_REQUEST_PATH,
                    verify_ssl=LLM_VERIFY_SSL,
                    max_retries=HEATMAP_MAX_RETRIES,
                )
            except Exception as e:
                log.error(f"Retry batch failed at offset {retry_start}: {e}")
                continue

            for (_, row), vec in zip(retry_batch.iterrows(), retry_vectors):
                row_id = hashlib.md5(str(row["issue_prompt"]).encode()).hexdigest()

                meta = {}
                for col in row.index:
                    val = row[col]
                    if col != "issue_prompt" and pd.notna(val) and str(val).strip():
                        meta[col] = str(val).strip()

                rows.append({
                    "row_id": row_id,
                    "equipment_type": str(row.get("equipment_type", "")) if pd.notna(row.get("equipment_type")) else None,
                    "persona": str(row.get("persona", "")) if pd.notna(row.get("persona")) else None,
                    "issue_prompt": str(row["issue_prompt"]),
                    "issue_prompt_embedding": vec,
                    "metadata": json.dumps(meta),
                    "created_at": datetime.now(timezone.utc),
                })
                retry_recovered += 1

        embedded += retry_recovered
        failed -= retry_recovered
        log.info(f"Retry pass complete: recovered {retry_recovered}/{len(failed_indices)}, "
                 f"still failed: {len(failed_indices) - retry_recovered}")

    return rows


# COMMAND ----------

# ── Step 3: Write to Delta table ──────────────────────────────────────────

def write_heatmap_to_delta(rows: list[dict]):
    """Write embedding rows to the Heatmap Delta table."""
    if not rows:
        log.warning("No rows to write")
        return 0

    from pyspark.sql.types import (
        StructType, StructField, StringType, ArrayType, DoubleType, TimestampType,
    )

    schema = StructType([
        StructField("row_id", StringType(), False),
        StructField("equipment_type", StringType(), True),
        StructField("persona", StringType(), True),
        StructField("issue_prompt", StringType(), False),
        StructField("issue_prompt_embedding", ArrayType(DoubleType()), True),
        StructField("metadata", StringType(), True),
        StructField("created_at", TimestampType(), True),
    ])

    spark_rows = [
        (r["row_id"], r["equipment_type"], r["persona"],
         r["issue_prompt"], r["issue_prompt_embedding"],
         r["metadata"], r["created_at"])
        for r in rows
    ]

    df = spark.createDataFrame(spark_rows, schema)

    tmp_view = f"_heatmap_staging_{int(time.time())}"
    df.createOrReplaceTempView(tmp_view)

    merge_sql = f"""
        MERGE INTO {HEATMAP_EMBEDDING_TABLE} AS target
        USING {tmp_view} AS source
        ON target.row_id = source.row_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """
    spark.sql(merge_sql)
    log.info(f"Merged {len(rows)} rows into {HEATMAP_EMBEDDING_TABLE}")

    # On full-load runs, remove rows from the target table that no longer
    # exist in the source view (e.g., a risk matrix entry was deleted).
    if not FORCE_RESET:
        orphan_sql = f"""
            DELETE FROM {HEATMAP_EMBEDDING_TABLE}
            WHERE row_id NOT IN (SELECT row_id FROM {tmp_view})
        """
        orphan_result = spark.sql(orphan_sql)
        log.info("Removed orphaned rows no longer present in source view")

    return len(rows)


# COMMAND ----------

# ── Main Pipeline ───────────────────────────────────────────────────────────

# Recover Spark session if it expired while the notebook was idle or during
# config cell execution.  Also called again after embedding (below).
ensure_spark_session()

log.info("=" * 60)
log.info("Heatmap Embedding Pipeline — START")
log.info(f"  Source: {HEATMAP_SOURCE_VIEW}")
log.info(f"  Target: {HEATMAP_EMBEDDING_TABLE}")
log.info(f"  Equipment filter: {HEATMAP_EQUIPMENT_TYPES or 'all'}")
log.info(f"  Persona filter: {HEATMAP_PERSONAS or 'all'}")
log.info(f"  FORCE_RESET: {FORCE_RESET}")
log.info("=" * 60)

start_time = time.time()

# Extract
df = extract_heatmap_records()
if df.empty:
    log.info("No records to process — pipeline complete")
    dbutils.notebook.exit("NO_DATA")  # noqa: F821

# Deduplicate: identical issue_prompt produces the same embedding regardless
# of technology_group.  Keep one row per unique prompt to avoid redundant
# embedding API calls and duplicate storage.
source_total = len(df)
df = df.drop_duplicates(subset=["issue_prompt"], keep="first").reset_index(drop=True)
log.info(f"Deduplication: {source_total} → {len(df)} rows "
         f"(removed {source_total - len(df)} duplicate issue_prompts)")

# Embed + Build rows
rows = embed_heatmap_records(df)
if not rows:
    log.error("All embeddings failed — pipeline aborting")
    raise RuntimeError("All embeddings failed")

# Coverage assertion: every unique issue_prompt must have been embedded
if len(rows) < len(df):
    log.warning(f"Coverage gap: {len(rows)}/{len(df)} unique prompts embedded "
                f"({len(df) - len(rows)} failed)")

# Re-establish Spark session — embedding takes minutes of HTTP calls with
# no Spark activity, which can trigger INACTIVITY_TIMEOUT on serverless.
ensure_spark_session()

# Write
rows_written = write_heatmap_to_delta(rows)

elapsed = time.time() - start_time
log.info("=" * 60)
log.info(f"Heatmap Embedding Pipeline — DONE in {elapsed:.1f}s")
log.info(f"  Source rows: {source_total}, Unique prompts: {len(df)}, "
         f"Embedded: {len(rows)}, Written: {rows_written}")
log.info("=" * 60)

dbutils.notebook.exit(json.dumps({  # noqa: F821
    "source_total": source_total,
    "unique_prompts": len(df),
    "embedded": len(rows),
    "rows_written": rows_written,
    "elapsed_seconds": round(elapsed, 1),
}))
