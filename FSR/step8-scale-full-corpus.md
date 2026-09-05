# Step 8: Scale to Full Corpus — 17.8K Files

> **Extracted from:** `production-readiness-plan.md`  
> **Date added:** 2026-04-21  
> **Context:** Test run processed 7 docs (avg ~115 MB each) in ~7 min producing 1,125 chunks. Extrapolating serially to 17.8K files would take ~12+ days. This step covers the plan to get that down to under a day.

---

## Two-Phase Approach

| Phase | Purpose | Tables | When |
|-------|---------|--------|------|
| **A — Backfill Test** | Validate parallelism, claim logic, and throughput | POC `_backfill` tables (throwaway) | First — quick, 1-2 tests |
| **B — DEV Run** | Actual backfill into canonical DEV tables | `vaid.*` catalog tables | Immediately after Phase A passes |

Phase A is temporary — once we confirm the pipeline holds up under limited parallelism, we drop the `_backfill` tables and switch to the real DEV job.

---

## Phase A: Backfill Test Job Setup (Temporary)

### Workflow Tasks (sequential)

| Task | Notebook (relative to `pw_sdg_ai_ser_repo/`) | Purpose |
|------|----------------------------------------------|---------|
| 1. DDL | `silver/src/ddl/nb_sdg_fsr_ddl` | Create/ensure tables exist |
| 2. P1 — Metadata | `silver/src/etl/nb_sdg_fsr_metadata` | Extract metadata from PDFs |
| 3. P2 — Chunks | `gold/src/etl/nb_sdg_fsr_chunks` | Chunk, embed, write to Delta + VS |
| 4. Validate | `silver/src/validation/nb_sdg_fsr_validate` | Run automated checks |

Task dependencies: DDL → P1 → P2 → Validate (sequential).

### Job Parameters

| Key | Value | Notes |
|-----|-------|-------|
| `FSR_METADATA_TABLE` | `main.gp_services_sdg_poc.fsr_metadata_registry_backfill` | Throwaway POC table |
| `FSR_CHUNK_TABLE` | `main.gp_services_sdg_poc.fsr_chunks_backfill` | Throwaway POC table |
| `FSR_VS_INDEX` | `main.gp_services_sdg_poc.vs_fsr_chunks_backfill` | Throwaway VS index |
| `FSR_MAX_PDFS` | `10` | Start small for validation |
| `FORCE_RESET` | `true` | Clean slate for testing |
| `FSR_TARGET_PDF_NAMES` | *(optional)* | Comma-separated UUIDs to target specific PDFs |
| `LITELLM_API_KEY` | *(from existing job)* | API key for embedding + LLM calls |

> **Cleanup:** Once Phase A passes, drop the `_backfill` tables and VS index.

---

## Phase B: DEV Job Setup (Canonical Tables)

Job name: **"PW SDG FSR Ingestion -DEV"**

### Target Table Names by Environment

| Env | Catalog | Metadata Table | Chunk Table | VS Index |
|-----|---------|----------------|-------------|----------|
| **DEV** | `vaid` | `vaid.ai_sot_field_service_report.biz_metadata_field_service_report` | `vaid.ai_std_con_field_service_report.vec_field_service_report` | `vaid.ai_std_con_field_service_report.vs_vec_field_service_report` |
| QA | `vaiq` | `vaiq.ai_sot_field_service_report.biz_metadata_field_service_report` | `vaiq.ai_std_con_field_service_report.vec_field_service_report` | `vaiq.ai_std_con_field_service_report.vs_vec_field_service_report` |
| PROD | `vaip` | `vaip.ai_sot_field_service_report.biz_metadata_field_service_report` | `vaip.ai_std_con_field_service_report.vec_field_service_report` | `vaip.ai_std_con_field_service_report.vs_vec_field_service_report` |

### DEV Job Parameters

| Key | Value | Notes |
|-----|-------|-------|
| `FSR_METADATA_TABLE` | `vaid.ai_sot_field_service_report.biz_metadata_field_service_report` | Canonical DEV metadata table |
| `FSR_CHUNK_TABLE` | `vaid.ai_std_con_field_service_report.vec_field_service_report` | Canonical DEV chunk table |
| `FSR_VS_INDEX` | `vaid.ai_std_con_field_service_report.vs_vec_field_service_report` | Canonical DEV VS index |
| `FSR_RUN_LOG_TABLE` | `vaid.ai_sot_field_service_report.fsr_run_log` | DEV P2 audit log |
| `FSR_DQ_LOG_TABLE` | `vaid.ai_sot_field_service_report.fsr_data_quality_log` | DEV validation log |
| `FSR_MAX_PDFS` | *(blank)* | No cap — process all files |
| `FORCE_RESET` | `false` | **Never reset DEV tables** |
| `FSR_BATCH_SIZE` | `8` | P1 docs per LLM call during backfill tuning |
| `FSR_P2_BATCH_SIZE` | `50` | **Current live DEV setting** for the separate chunk-only job |
| `FSR_P2_EMBED_CONCURRENCY` | `8` | Current live embed concurrency; may need reduction if 429s persist |
| `LITELLM_API_KEY` | *(from existing job)* | API key for embedding + LLM calls |

Planned scale-up target after rate-limit tuning:

| Key | Target | Notes |
|-----|--------|-------|
| `FSR_P2_BATCH_SIZE` | `500` | Throughput target, not current live setting |
| `FSR_P2_EMBED_CONCURRENCY` | `8` | Only if gateway tolerates it without repeated 429s |

---

## Phase A Testing Plan (Backfill Tables — Quick Validation)

Goal: confirm parallelism works, then move to DEV. Keep this tight.

### Test A1: Baseline (10 docs, single run)

- `FSR_MAX_PDFS=10`, `FORCE_RESET=true`
- Verify: validation passes, all 10 completed, note P2 wall-clock time

### Test A2: Parallel safety (2 concurrent P2 runs)

- First: run P1 with `FSR_MAX_PDFS=20` to populate 20 metadata rows
- Then: trigger the job twice (Run Now × 2) with `FORCE_RESET=false`, `FSR_MAX_PDFS=10`
- Verify:
  ```sql
  SELECT chunk_status, COUNT(*) FROM ...backfill GROUP BY chunk_status;
  -- Expect: 20 completed, 0 in_progress
  SELECT chunk_id, COUNT(*) AS n FROM ...chunks_backfill GROUP BY chunk_id HAVING n > 1;
  -- Expect: 0 rows (no duplicates)
  ```

**If A1 + A2 pass → drop backfill tables, move to Phase B (DEV job).**

Optional: If we want to stress-test before DEV, run 3–5 parallel with 50 docs each. Do this carefully: current P2 claim logic is `SELECT` then `UPDATE`, so concurrent runs can still race and duplicate work even though final writes are idempotent.

### Test Results Log

| Test | Date | Parallel | Docs/run | P2 time | Failures | Notes |
|------|------|:--------:|:--------:|:-------:|:--------:|-------|
| A1 | Apr 22 | 1 | 10 | 48s | 0 | 335 chunks, all completed |
| A2 | Apr 22 | 2 | 10 | ~6min each | 0 | 60 total completed (P1 also picked up new files), 0 duplicate chunks |

---

## Phase B: DEV Backfill Execution

Once Phase A passes, create the DEV job and run the full 17.8K corpus.

### Strategy

1. Create **"PW SDG FSR Ingestion -DEV"** job with DEV parameters (see table above)
2. First run: `FSR_MAX_PDFS=50`, `FORCE_RESET=true` to validate against real `vaid.*` tables
3. If clean: remove `FSR_MAX_PDFS` cap, set `FORCE_RESET=false`, launch full backfill
4. For throughput: run multiple concurrent executions (5–10 "Run Now" clicks)
5. Monitor: `chunk_status=failed` count, LiteLLM 429s in logs, wall-clock per run

### Estimating full backfill time

```
T_backfill = (17800 / (docs_per_run × parallel_runs)) × T_run
```

Example: 5 parallel × 500 docs/run × 80 min/run → ~12 hours total.

### DEV Results Log

| Date | Parallel runs | Batch size | P1 docs | P2 docs | P2 time | Failures | Cumulative total |
|------|:------------:|:----------:|:-------:|:-------:|:-------:|:--------:|:----------------:|
| Apr 22 | 1 | 50 | 10 (test) | 10 | 48s | 0 | 10 |
| Apr 22 | 1 | 50 | ~17.8K (full) | TBD | **RUNNING** | TBD | TBD |
| Apr 23 | 1 | 50 | metadata already completed | 50 | ~4+ min embedding phase observed | 429s during embed batches | 4,316 metadata completed / 254 failed / 13,293 pending |

### Apr 23 runtime note

- A separate chunk-only job is now being used for P2: `nb_sdg_fsr_chunks`
- The code path is correct: P2 selects `metadata_status='completed'` with `chunk_status in ('pending','failed')`
- Current operational bottleneck is not claim logic; it is LiteLLM rate limiting during embeddings
- Observed log sample: 50 docs claimed, 4,233 chunks created, then repeated `429 Too Many Requests` responses at embed concurrency 8
- Practical next tuning lever is lower `FSR_P2_EMBED_CONCURRENCY`, then lower `FSR_EMBED_BATCH_SIZE` if needed

---

## 8.1 Current Bottleneck Analysis

The pipeline has 4 workflow tasks: `DDL → P1 (metadata) → P2 (chunks) → Validate`.

P2 (chunk ingestion) is the bottleneck. Within P2:

| Step | Current behavior | Time share | Bottleneck? |
|------|-----------------|:----------:|:-----------:|
| PDF text extraction (PyMuPDF) | Sequential for-loop over docs | ~10% | No |
| Embedding generation (LiteLLM) | Serial batches of 32, one API call at a time | **~85%** | **Yes** |
| Delta MERGE + status update | Single Spark SQL statement | ~5% | No |

The embedding loop sends 32 texts to LiteLLM, waits for response, then sends the next 32. All network latency is serial.

## 8.2 Failure Handling Audit

Current failure hooks in the pipeline code:

**P1 — Metadata Extraction (`nb_sdg_fsr_metadata.py`):**
| Scenario | Current handling | Adequate? |
|----------|-----------------|:---------:|
| PDF open failure | Caught per-doc, saved in `failures` dict, marked `metadata_status=failed` with error message | ✅ |
| LLM call failure | 3 retries with exponential backoff; batch-level failure marks all docs in batch as `failed` | ⚠️ See gap 1 |
| LLM returns no match for a doc | Detected, marked as `llm_failures` with message | ✅ |
| LLM returns malformed JSON | Caught by `json.loads`, entire batch marked failed | ⚠️ See gap 2 |
| IBAT/EV enrichment table not accessible | Caught, logged, continues without enrichment | ✅ |
| IBAT join multiplies rows | Handled by `dropDuplicates(["document_id"])` | ✅ |
| pdf_name derivation fails | Falls back to volume_path stem | ✅ |
| Status updates after failure | `metadata_status=failed`, `metadata_error` populated, `scraped_at` set | ✅ |
| Re-processing failed docs | Picks up `FAILED` docs up to `P1_MAX_RETRIES` per run | ✅ |

**P2 — Chunk Ingestion (`nb_sdg_fsr_chunks.py`):**
| Scenario | Current handling | Adequate? |
|----------|-----------------|:---------:|
| PDF text extraction fails | Caught per-doc, added to `doc_errors`, marked `chunk_status=failed` | ✅ |
| Empty text after extraction | Caught, added to `doc_errors` | ✅ |
| Embedding API fails | 3 retries with exponential backoff per batch | ⚠️ See gap 3 |
| Embedding dimension mismatch | Logged as warning but continues | ✅ |
| Missing embedding for a chunk | Skipped silently (no chunk row written) | ⚠️ See gap 4 |
| MERGE to Delta | Standard Spark SQL, idempotent on `chunk_id` | ✅ |
| VS endpoint not online | Detected, sync skipped with warning | ✅ |
| VS index doesn't exist | Auto-created with correct schema | ✅ |
| VS sync fails | 3 retries with 20s backoff; warns and continues | ✅ |
| Status tracking | Success → `chunk_status=completed`; failures → `chunk_status=failed` + error | ✅ |

**Identified gaps to fix before scaling:**

| # | Gap | Impact at scale | Fix |
|---|-----|----------------|-----|
| 1 | LLM batch failure marks all docs in batch as failed, even if only one caused the issue | At P1_BATCH_SIZE=4 this is minor; at larger batches, a single bad doc wastes the whole batch | Add per-doc fallback: on batch failure, retry each doc individually |
| 2 | Malformed LLM JSON response fails entire batch | Same batch-blast-radius issue | Parse response defensively; extract what we can, mark remainder as failed |
| 3 | Embedding failure kills the entire P2 run (exception propagates) | A single bad batch (e.g., text too long) stops all remaining docs | Wrap per-batch in try/except; skip failed batch, mark affected docs as failed |
| 4 | Missing embedding for a chunk → chunk silently dropped | A doc could appear "completed" but have missing chunks | Log a warning; if >10% of a doc's chunks have no embedding, mark doc as failed instead of completed |
| 5 | No `in_progress` state → concurrent runs grab same docs | Wasted compute when running parallel jobs | Add claim-based locking (see 8.3 Phase 2) |
| 6 | No per-run progress tracking | If a run crashes mid-batch, we only know from the job failure log | Add a progress counter log every N docs; consider writing a `_run_log` temp table |

## 8.3 Scaling Plan — Three Phases

### Phase 1: Concurrent Embedding Calls (code change, high impact)

Parallelize embedding API calls within a single run using `ThreadPoolExecutor`.

**File:** `gold/src/etl/nb_sdg_fsr_chunks.py`  
**New config param:** `FSR_P2_EMBED_CONCURRENCY` (default 8)  
**Also:** Wrap each embedding batch in try/except so one failed batch doesn't kill the run.

```python
# Current (serial):
for i in range(0, len(all_chunk_texts), EMBED_BATCH_SIZE):
    vectors = embed_batch(batch_texts)
    ...

# New (concurrent + fault-tolerant):
from concurrent.futures import ThreadPoolExecutor, as_completed

P2_EMBED_CONCURRENCY = int(get_runtime_param("FSR_P2_EMBED_CONCURRENCY", "8"))

def safe_embed_batch(batch_idx, texts, refs):
    """Embed a batch, return results or error."""
    try:
        vectors = embed_batch(texts)
        return [(ref, vec) for ref, vec in zip(refs, vectors)]
    except Exception as e:
        log.error(f"Batch {batch_idx} failed: {e}")
        return [(ref, None) for ref in refs]  # mark as failed

batches = [
    (i // EMBED_BATCH_SIZE, all_chunk_texts[i:i+EMBED_BATCH_SIZE],
     all_chunk_refs[i:i+EMBED_BATCH_SIZE])
    for i in range(0, len(all_chunk_texts), EMBED_BATCH_SIZE)
]

with ThreadPoolExecutor(max_workers=P2_EMBED_CONCURRENCY) as pool:
    futures = {
        pool.submit(safe_embed_batch, idx, texts, refs): idx
        for idx, texts, refs in batches
    }
    for future in as_completed(futures):
        for ref, vec in future.result():
            if vec is not None:
                all_embeddings[ref] = vec
            else:
                embed_failures.add(ref[0])  # track doc_id
```

**Expected impact:** 4–8x speedup on embedding step (currently ~85% of runtime).  
**Risk:** LiteLLM rate limiting. Start at 8 concurrent workers, monitor for 429 responses.

### Phase 2: Claim-Based Locking for Parallel Job Runs (code change)

Add `chunk_status = 'in_progress'` so multiple concurrent job runs don't process the same files.

**File:** `gold/src/etl/nb_sdg_fsr_chunks.py`

```python
# Step 1: Claim a batch atomically
spark.sql(f"""
    UPDATE {METADATA_TABLE}
    SET chunk_status = 'in_progress',
        chunked_at = current_timestamp()
    WHERE document_id IN (
        SELECT document_id FROM {METADATA_TABLE}
        WHERE metadata_status = 'completed'
          AND chunk_status IN ('pending', 'failed')
        LIMIT {P2_BATCH_SIZE}
    )
""")

# Step 2: Read only claimed rows
pending_df = spark.sql(f"""
    SELECT ... FROM {METADATA_TABLE}
    WHERE chunk_status = 'in_progress'
""")
```

**Also add stale-claim recovery** (at the start of each run):
```python
spark.sql(f"""
    UPDATE {METADATA_TABLE}
    SET chunk_status = 'pending'
    WHERE chunk_status = 'in_progress'
      AND chunked_at < current_timestamp() - INTERVAL 30 MINUTES
""")
```

On success → `chunk_status = 'completed'`. On failure → `chunk_status = 'failed'`.

**File:** `Common/fsr_config.py`  
- Add `in_progress` to `ChunkStatus` enum.

**Expected impact:** Reduces overlap risk for parallel job runs (5–10 concurrent).  
**Risk:** Low — Delta table transactions are ACID.

### Phase 3: Increase Batch Sizes (config only)

| Parameter | Current | Proposed | Rationale |
|-----------|:-------:|:--------:|-----------|
| `FSR_P2_BATCH_SIZE` | 50 | 500 | Fewer job runs needed once gateway limits are under control |
| `EMBED_BATCH_SIZE` | 32 | 128 | Fewer API calls, more efficient |
| `FSR_P2_EMBED_CONCURRENCY` | N/A | 8 | New param from Phase 1 |

**Risk:** Monitor memory on larger batches. 500 docs × ~161 chunks × 3072-dim float vectors ≈ 1.5 GB in memory. Should fit on serverless, but test with 200 first.

## 8.4 Failure Hardening Changes (alongside scaling)

These changes should ship together with Phase 1 since they share the same file:

| Change | File | Description |
|--------|------|-------------|
| Per-batch embedding fault tolerance | `nb_sdg_fsr_chunks.py` | Wrap each batch in try/except, skip failed batches, mark affected docs as failed |
| Missing-embedding threshold check | `nb_sdg_fsr_chunks.py` | After embedding loop, check each doc. If >10% of chunks have no embedding, mark doc as `failed` instead of `completed` |
| Per-doc LLM fallback (P1) | `nb_sdg_fsr_metadata.py` | On batch LLM failure, retry each doc individually before marking all as failed |
| Configurable `EMBED_BATCH_SIZE` | `fsr_config.py` | Move from hardcoded `32` to `get_runtime_param("FSR_EMBED_BATCH_SIZE", "32")` |
| Add `in_progress` chunk status | `fsr_config.py` | New status value for claim-based locking |
| Progress logging | `nb_sdg_fsr_chunks.py` | Log every 100 docs processed (not just every embedding batch) |

## 8.5 Projected Timeline

| Scenario | Parallel runs | Docs/run | Est. time/run | Total wall-clock |
|----------|:------------:|:--------:|:--------------:|:----------------:|
| Current (serial, batch=50) | 1 | 50 | ~50 min | ~12 days |
| Phase 1 only (concurrent embed) | 1 | 50 | ~10 min | ~2.5 days |
| Phase 1 + 3 (bigger batches) | 1 | 500 | ~80 min | ~2.4 days |
| **Phase 1 + 2 + 3 (5 parallel)** | **5** | **500** | **~80 min** | **~12 hours** |
| Phase 1 + 2 + 3 (10 parallel) | 10 | 500 | ~80 min | ~6 hours |

## 8.6 Implementation Sequence

1. **Implement Phase 1 + failure hardening** in `nb_sdg_fsr_chunks.py` (concurrent embedding + per-batch fault tolerance)
2. **Implement Phase 2** (claim-based locking) in same file + `fsr_config.py`
3. **Test with 100-doc batch** to validate timing + error handling
4. **Bump config** (Phase 3) and launch 5 parallel runs
5. **Monitor** LiteLLM rate limits, cluster memory, and `chunk_status=failed` count
6. **Full 17.8K corpus** should complete in under a day

## 8.7 Rollback Plan

All changes are backward-compatible:
- If concurrent embedding causes issues, set `FSR_P2_EMBED_CONCURRENCY=1` (reverts to serial)
- If claim-based locking has issues, run jobs sequentially (only one at a time) — `in_progress` rows auto-recover after 30 min
- If batch size is too large, reduce via runtime params without code changes

---

## Design Review — Open Questions & Answers

> Questions raised during design review (Apr 22)

### Q1: Retries = 3 — won't this increase overall processing time?

**Short answer:** Marginally, but only for failing documents — not for the happy path.

The 3 retries (with exponential backoff) only fire when an API call actually fails. For healthy docs, there are zero retries and zero extra time. The backoff sequence is roughly 2s → 4s → 8s, so worst case a single failing batch adds ~14s before moving on.

The alternative — no retries — means any transient network blip or LiteLLM 429 (rate limit) immediately marks the doc as `failed`, requiring a full re-run later. That re-run is far more expensive than a 14s retry window.

**Net effect at scale:** If 1% of 17.8K docs hit transient failures, retries add ~4 min total across the entire corpus. Without retries, those 178 docs would need a separate reprocessing pass (minutes of overhead just to spin up the job again).

**Recommendation:** Keep retries=3. We could make it configurable (`FSR_P2_MAX_RETRIES`) if we want to tune it down during backfill when we're prioritizing throughput over recovery.

### Q2: Do we have "in_progress" status during metadata extraction (P1) too?

**Current state:** No — `in_progress` is only planned for P2 (chunk ingestion) in Phase 2.

**Why P2 only (for now):** P1 (metadata extraction) is much faster per doc (~1-2s vs ~50s for P2), and we're not planning parallel P1 runs. P1 processes docs that have `metadata_status = 'pending'` and is expected to complete the full 17.8K corpus in a single sequential pass in a few hours.

**Should we add it for P1?** If we ever need parallel P1 runs (unlikely given the speed), yes. For now, adding `in_progress` to P1 would be over-engineering. The claim-based locking pattern in Phase 2 is designed to be reusable though — we can copy it to P1 later if needed.

**Parallel processing in P1:** The LLM calls in P1 are already batched (P1_BATCH_SIZE=4 docs per LLM call). We could add thread-level parallelism to P1 like we're doing for P2 embeddings, but P1 isn't the bottleneck, so it's not worth the complexity right now.

### Q3: How do we guarantee no duplicate records?

**Three layers of protection:**

1. **MERGE with unique key (primary defense):** Both the metadata and chunk tables use `MERGE INTO ... USING ... ON` with unique keys:
   - Metadata table: `document_id` (UUID derived from file path) — a file can only produce one metadata row
   - Chunk table: `chunk_id` (hash of `document_id + chunk_index`) — a chunk is uniquely identified by its parent doc + position
   - If a doc is reprocessed, the MERGE updates the existing row instead of inserting a duplicate

2. **Status-based filtering (prevents reprocessing):** The pipeline only picks up docs with `chunk_status IN ('pending', 'failed')`. Once a doc reaches `completed`, it's never picked up again unless manually reset.

3. **Claim-based locking (Phase 2, prevents concurrent duplicates):** The `in_progress` status ensures two parallel runs can't claim the same doc. Even if they did (race condition), the MERGE's `ON` clause would deduplicate at write time.

**So the answer is: MERGE with unique key is the primary guarantee.** Status filtering and claim locking are additional safeguards for efficiency (avoid wasted work), but even without them, duplicates can't land in the table.

### Q4: Are we planning a separate job for reprocessing failed docs?

**Current plan:** No separate job needed. The existing pipeline already handles reprocessing.

Each run picks up docs where `chunk_status IN ('pending', 'failed')`, up to `P2_BATCH_SIZE`. Failed docs automatically get retried on the next run. There's a `P1_MAX_RETRIES` / retry counter that prevents infinite retry loops — after N failures, the doc stays `failed` and requires manual investigation.

**For the backfill specifically:** After the initial 17.8K run completes, we'd do a sweep:
1. Query: `SELECT COUNT(*) FROM metadata WHERE chunk_status = 'failed'`
2. If the count is low (say <100), just re-trigger the same job — it'll pick up only the failed docs
3. If the count is high, investigate the common failure reasons first (bad PDFs? API issues?) before retrying

**A separate "reprocessing" job would only make sense if** we need different config (e.g., smaller batch size, more retries, different model) for known-problematic docs. We can create that later if needed, but it would just be the same notebook with different runtime params.

### Q5: Are we keeping an audit table for monitoring progress?

**Current state:** No dedicated audit table. Progress is tracked implicitly through status columns on the metadata table:
- `metadata_status`: `pending` → `completed` / `failed`
- `chunk_status`: `pending` → `in_progress` → `completed` / `failed`
- `scraped_at`, `chunked_at`: timestamps for when each step completed

**What we can query today:**
```sql
SELECT chunk_status, COUNT(*) 
FROM metadata_table 
GROUP BY chunk_status;
-- Shows: 15000 completed, 200 in_progress, 50 failed, 2550 pending
```

**What's missing (and should we add it):**

| Audit capability | Current | Recommendation |
|-----------------|---------|----------------|
| Overall progress (completed/total) | ✅ Query metadata table | Sufficient |
| Per-run summary (docs processed, failures, duration) | ❌ Only in job logs | **Add: write a summary row to a `_run_log` table at end of each run** |
| Per-doc error history | ⚠️ Only latest error in `metadata_error` | Consider appending errors instead of overwriting |
| Historical throughput trends | ❌ | The `_run_log` table would give this |

**Recommendation:** Add a lightweight `fsr_run_log` table (or just a Delta table with `run_id, start_time, end_time, docs_attempted, docs_succeeded, docs_failed, error_summary`). This is listed as gap #6 in section 8.2. It's low effort (~20 lines of code) and high value for monitoring the backfill.

### Q6: Is concurrency only for backfill, or for regular jobs too? How is it handled in code?

**Both backfill and regular runs use the same code.** The difference is purely config:

| Aspect | Backfill | Regular (steady-state) |
|--------|----------|----------------------|
| Job runs | 5–10 parallel runs of same job | 1 scheduled run (daily/weekly) |
| `P2_BATCH_SIZE` | 500 | 50 |
| `EMBED_CONCURRENCY` | 8 | 4–8 |
| Claim-based locking | Essential (prevents overlap) | Still active but less critical (only 1 run) |

**How it's handled in code:** There's no "backfill mode" flag. The same notebook runs in both scenarios. The behavior is controlled entirely by runtime parameters passed to the Databricks job:

```
# Backfill target after tuning:
FSR_P2_BATCH_SIZE=500, FSR_P2_EMBED_CONCURRENCY=8

# Current live run:
FSR_P2_BATCH_SIZE=50, FSR_P2_EMBED_CONCURRENCY=4
```

**For parallel runs during backfill:** We'd spin up multiple runs of the same job (each claiming its own batch via Phase 2 locking). After backfill is done, we switch to a single scheduled run with smaller batch size.

**The claim-based locking design (Phase 2) is intended to be always active**, but the current code still does a `SELECT` followed by `UPDATE`, so it reduces overlap only partially until the claim becomes atomic.

### Q7: Databricks "Run Backfill" feature — is it useful for our case?

**Short answer: No, the Databricks "Run backfill" feature is not a fit for our use case.**

The screenshot shows Databricks' built-in backfill UI, which is designed for **time-partitioned data pipelines** — it replays a job across a date range (e.g., reprocess data for Apr 15–21, one run per day). It requires the job to reference `{{backfill.[format]}}` as a time parameter.

Our pipeline doesn't work on date partitions. We're processing a corpus of 17.8K PDF files — the work is partitioned by document, not by date. There's no meaningful way to split "process these PDFs" into daily windows.

**What we'll actually do for parallel backfill runs:**

There are three options in Databricks:

| Option | How | Pros | Cons |
|--------|-----|------|------|
| **A. Multiple runs of same job** | Trigger the same job 5–10 times manually or via API. Each run claims its own batch via Phase 2 locking. | Simplest. Same code, same job definition. Easy to monitor in one place. | Need claim-based locking to prevent overlap. All runs share same runtime params. |
| B. Multiple tasks in same job | Define 5 parallel tasks within one workflow, each pointing to the same notebook with different params. | Single job to monitor. Can set different batch ranges per task. | Tasks within a job share a cluster (unless configured separately). More complex workflow YAML. |
| C. Separate jobs per batch | Create `fsr-backfill-1`, `fsr-backfill-2`, etc., each with a different doc range. | Full isolation. | Tedious to set up and monitor. Have to manually split the doc range. |

**Recommendation: Option A — multiple runs of the same job.** With claim-based locking (Phase 2), each run automatically grabs the next unclaimed batch. No manual range splitting needed. We just trigger the job N times, and each run processes a different set of docs.

To trigger multiple runs:
- **Manual:** Click "Run Now" 5 times in the Databricks UI (each creates an independent run)
- **API/CLI:** `databricks jobs run-now --job-id <id>` in a loop
- **Scheduled (if needed):** Set a CRON trigger that fires every 5 minutes during the backfill window — each trigger starts a new run that claims its own batch

---

> More questions to follow — this is a living document.
