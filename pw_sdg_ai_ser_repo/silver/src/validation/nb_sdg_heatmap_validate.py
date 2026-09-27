# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_heatmap_validate — Post-run validation for Heatmap pipeline
#
# Runs after Heatmap ingestion to verify data quality: table not empty,
# no duplicate row_ids, embeddings present and correct dimension.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/heatmap_config

# COMMAND ----------

import json
import logging
from pyspark.sql.functions import col, size

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("heatmap.validate")

results = []

def check(name, condition, detail=""):
    passed = bool(condition)
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    log.info(f"[{status}] {name}" + (f"  — {detail}" if detail else ""))

# COMMAND ----------

# ── 1. Table exists and is not empty ────────────────────────────────────────

embed_df = spark.table(HEATMAP_EMBEDDING_TABLE)
row_count = embed_df.count()
check("1.1 Embedding table not empty", row_count > 0, f"{row_count} rows")

# COMMAND ----------

# ── 2. No duplicate row_ids ────────────────────────────────────────────────

distinct_ids = embed_df.select("row_id").distinct().count()
check("2.1 No duplicate row_ids",
      distinct_ids == row_count,
      f"distinct={distinct_ids}, total={row_count}")

# COMMAND ----------

# ── 3. Required fields populated ──────────────────────────────────────────

for c in ["row_id", "issue_prompt"]:
    null_count = embed_df.filter(col(c).isNull() | (col(c) == "")).count()
    check(f"3.x No nulls in '{c}'", null_count == 0, f"{null_count} nulls")

# COMMAND ----------

# ── 4. Embeddings present and correct dimension ──────────────────────────

no_embed = embed_df.filter(col("issue_prompt_embedding").isNull()).count()
check("4.1 All rows have embeddings", no_embed == 0,
      f"{no_embed} rows missing embedding")

if no_embed < row_count:
    sample = embed_df.filter(col("issue_prompt_embedding").isNotNull()).select(
        size("issue_prompt_embedding").alias("dim")
    ).distinct().collect()
    dims = {r.dim for r in sample}
    check("4.2 Embedding dimension correct",
          dims == {EMBEDDING_DIMENSION},
          f"found dimensions: {dims}, expected: {EMBEDDING_DIMENSION}")

# COMMAND ----------

# ── 5. Every source issue_prompt has an embedding ──────────────────────────

source_prompts = (
    spark.sql(f"SELECT DISTINCT issue_prompt FROM {HEATMAP_SOURCE_VIEW}")
    .filter(col("issue_prompt").isNotNull() & (col("issue_prompt") != ""))
)
target_prompts = embed_df.select("issue_prompt").distinct()

missing = source_prompts.join(target_prompts, on="issue_prompt", how="left_anti")
missing_count = missing.count()
source_unique = source_prompts.count()
check("5.1 All source issue_prompts have embeddings",
      missing_count == 0,
      f"{missing_count} missing out of {source_unique} unique source prompts")

if missing_count > 0:
    sample_missing = [r.issue_prompt[:80] for r in missing.limit(5).collect()]
    log.warning(f"  Sample missing prompts: {sample_missing}")

# ── 6. No duplicate issue_prompts in embedding table ──────────────────────

distinct_prompts = embed_df.select("issue_prompt").distinct().count()
check("6.1 No duplicate issue_prompts",
      distinct_prompts == row_count,
      f"distinct_prompts={distinct_prompts}, total_rows={row_count}")

# ── 7. Coverage stats ──────────────────────────────────────────────────────

eq_types = embed_df.select("equipment_type").distinct().count()
personas = embed_df.select("persona").distinct().count()
log.info(f"  Equipment types: {eq_types}, Personas: {personas}, Total rows: {row_count}")
log.info(f"  Source unique prompts: {source_unique}, Target rows: {row_count}")

# COMMAND ----------

# ── Summary ─────────────────────────────────────────────────────────────────

passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
total = len(results)

log.info("=" * 60)
log.info(f"Heatmap Validation: {passed}/{total} passed, {failed} failed")
log.info("=" * 60)

if failed > 0:
    for name, p, detail in results:
        if not p:
            log.error(f"  FAILED: {name} — {detail}")

# ── DQ summary metrics ──────────────────────────────────────────────────────────────────
dq_summary = {
    "checks_passed": passed,
    "checks_failed": failed,
    "checks_total": total,
    "row_count": row_count,
    "distinct_row_ids": distinct_ids,
    "equipment_types": eq_types,
    "personas": personas,
}
log.info(f"DQ metrics: {json.dumps(dq_summary)}")

if failed > 0:
    raise RuntimeError(
        f"Heatmap validation failed: {failed}/{total} checks failed. "
        f"See logs above for details."
    )

dbutils.notebook.exit(json.dumps(dq_summary))  # noqa: F821
