# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_chunks — Process 2: Chunking, Embedding & VS Sync (Gold)
#
# Reads documents with metadata_status=completed and chunk_status=pending/failed
# from the metadata registry. Extracts full text via PyMuPDF, splits into chunks,
# generates embeddings via LiteLLM, writes to the chunk Delta table, and triggers
# Vector Search index sync.
#
# Batch loop: claims P2_BATCH_SIZE docs per iteration, processes them, then
# claims the next batch until the queue is drained or P2_MAX_ITERATIONS is hit.
# VS sync fires once at the end.
#
# document_id is PK/FK, pdf_name is human-readable. Statuses: pending / completed / failed.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet PyMuPDF langchain-text-splitters

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

# MAGIC %run ../../../common/fsr_chunking

# COMMAND ----------

# MAGIC %run ../../../common/fsr_esn_identifier

# COMMAND ----------

import json, time, hashlib, os, logging
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz  # PyMuPDF
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, current_timestamp
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    DoubleType, ArrayType, TimestampType, DateType,
)

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.p2.chunks")

# COMMAND ----------

log.info("=== Process 2 — Chunk Ingestion ===")
_grand_start = datetime.now(timezone.utc)
log.info(f"  Metadata table : {METADATA_TABLE}")
log.info(f"  Chunk table    : {CHUNK_TABLE}")
log.info(f"  Run log table  : {RUN_LOG_TABLE}")
log.info(f"  VS index       : {VS_INDEX_NAME}")
log.info(f"  VS endpoint    : {VS_ENDPOINT_NAME}")
log.info(f"  Embedding model: {EMBEDDING_MODEL}")
log.info(f"  Embed dimension: {EMBEDDING_DIMENSION}")
if TARGET_PDF_NAMES:
    log.info(f"  Target PDFs    : {len(TARGET_PDF_NAMES)} (DEBUG OVERRIDE — only these docs will be processed)")
else:
    log.info(f"  Target PDFs    : all eligible")
log.info(f"  Chunk size     : {CHUNKING_CONFIG.chunk_size}")
log.info(f"  Chunk overlap  : {CHUNKING_CONFIG.chunk_overlap}")
log.info(f"  LLM base URL   : {LITELLM_BASE_URL}")
log.info(f"  API key set    : {bool(LITELLM_API_KEY)}")
log.info(f"  P2 batch size  : {P2_BATCH_SIZE}")
log.info(f"  P2 max retries : {P2_MAX_RETRIES}")
log.info(f"  P2 max iters   : {P2_MAX_ITERATIONS or 'unlimited (drain queue)'}")
log.info(f"  jb_env         : {JB_ENV or 'unset'}")
log.info(f"  Multi-ESN      : enabled={FSR_MULTI_ESN_ENABLED}, dry_run={FSR_MULTI_ESN_DRY_RUN}")
if LLM_VERIFY_SSL is False:
    log.warning("TLS certificate verification is DISABLED for embedding/LLM calls (FSR_LLM_VERIFY_SSL=false)")
elif isinstance(LLM_VERIFY_SSL, str):
    log.info(f"Using custom CA bundle for embedding/LLM calls: {LLM_VERIFY_SSL}")
if DATABRICKS_VERIFY_SSL is False:
    log.warning("TLS certificate verification is DISABLED for Databricks REST calls (FSR_DATABRICKS_VERIFY_SSL=false)")
elif isinstance(DATABRICKS_VERIFY_SSL, str):
    log.info(f"Using custom CA bundle for Databricks REST calls: {DATABRICKS_VERIFY_SSL}")

# COMMAND ----------

# ── Load fsr_pdf_ref ESN map for multi-ESN expansion ────────────────────────
_ref_esn_map = {}  # doc_id (lowercase) → set of ESNs
if FSR_MULTI_ESN_ENABLED:
    try:
        _esn_rows = spark.sql(f"""
            SELECT LOWER(TRIM(s3_filename)) AS doc_id, esn
            FROM {FSR_PDF_REF_VIEW}
            WHERE esn IS NOT NULL AND TRIM(esn) != ''
        """).collect()
        for row in _esn_rows:
            _ref_esn_map.setdefault(row.doc_id, set()).add(row.esn.strip())
        log.info(f"Multi-ESN: loaded fsr_pdf_ref map — {len(_ref_esn_map)} docs with ESN entries")
    except Exception as e:
        log.warning(f"Multi-ESN: fsr_pdf_ref not accessible ({e}). Chunk expansion disabled.")
else:
    log.info("Multi-ESN: expansion disabled (FSR_MULTI_ESN_ENABLED=false)")

# COMMAND ----------

# ── Recover stale in_progress claims (crashed previous runs) ────────────────
STALE_CLAIM_MINUTES = int(get_runtime_param("FSR_STALE_CLAIM_MINUTES", "30"))

stale_count = spark.sql(f"""
    SELECT COUNT(*) AS n FROM {METADATA_TABLE}
    WHERE chunk_status = '{ChunkStatus.IN_PROGRESS}'
      AND chunked_at < current_timestamp() - INTERVAL {STALE_CLAIM_MINUTES} MINUTES
""").first().n

if stale_count > 0:
    spark.sql(f"""
        UPDATE {METADATA_TABLE}
        SET chunk_status = '{ChunkStatus.PENDING}'
        WHERE chunk_status = '{ChunkStatus.IN_PROGRESS}'
          AND chunked_at < current_timestamp() - INTERVAL {STALE_CLAIM_MINUTES} MINUTES
    """)
    log.info(f"Recovered {stale_count} stale in_progress claims (>{STALE_CLAIM_MINUTES} min old)")

# COMMAND ----------

# ── Helper functions (defined once, used per-batch) ─────────────────────────
EMBED_BATCH_SIZE = int(get_runtime_param("FSR_EMBED_BATCH_SIZE", "32"))
EMBED_MAX_RETRIES = int(get_runtime_param("FSR_EMBED_MAX_RETRIES", "3"))
P2_EMBED_CONCURRENCY = int(get_runtime_param("FSR_P2_EMBED_CONCURRENCY", "8"))
# Strict by default: any embedding failure → fail the doc, retry whole thing
# next run. Avoids silently dropping chunks from the retrieval index.
# Override with FSR_EMBED_FAIL_THRESHOLD env var if some loss is acceptable.
EMBED_FAIL_THRESHOLD = float(get_runtime_param("FSR_EMBED_FAIL_THRESHOLD", "0.0"))

# ─────────────────────────────────────────────────────────────────────────────
# RELIABILITY / PERFORMANCE BACKLOG  (post-validation follow-up)
# Tracked here so they live next to the code; promote to issues when scoping.
#
#   [P0] Wall-clock run timeout — add FSR_P2_RUN_MAX_MINUTES (default 60) and
#        check at the top of each batch loop iteration. Today only the
#        Databricks job timeout protects against a wedged gateway.
#   [P0] Smarter retry policy in embed_batch():
#          - skip retries on 4xx (except 408/429) — they won't recover
#          - on 429, honor Retry-After header instead of fixed 5/10/20s backoff
#          - drop per-attempt timeout from 120s → 60s
#   [P1] Cache the working embeddings URL on first success — today every call
#        tries /v1/embeddings, gets 404, then tries /embeddings (wasted RTT).
#   [P1] Per-failed-doc audit rows in DQ_LOG_TABLE (table already exists,
#        currently underused for embedding failures).
#   [P2] Re-evaluate EMBED_BATCH_SIZE — gateway may accept 100–500 inputs per
#        call; bigger batches → fewer round-trips.
#   [P2] Parallel PDF chunking — use existing P2_PDF_WORKERS knob with a
#        ThreadPoolExecutor around load_pdf_snapshot + hierarchical_semantic_*.
#        PyMuPDF releases the GIL during heavy work, so threading helps.
# ─────────────────────────────────────────────────────────────────────────────


def embed_batch(texts):
    """Call LiteLLM embedding endpoint. Returns list of float vectors."""
    base = LITELLM_BASE_URL.rstrip("/")
    urls = [f"{base}/v1/embeddings", f"{base}/embeddings"]
    payload = {"model": EMBEDDING_MODEL, "input": texts}
    headers = {
        "Authorization": f"Bearer {LITELLM_API_KEY}",
        "Content-Type": "application/json",
    }
    for attempt in range(1, EMBED_MAX_RETRIES + 1):
        for url in urls:
            try:
                resp = requests.post(url, headers=headers, json=payload,
                                     timeout=120, verify=LLM_VERIFY_SSL)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json().get("data", [])
                if len(data) != len(texts):
                    raise RuntimeError(f"Expected {len(texts)} embeddings, got {len(data)}")
                ordered = sorted(data, key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in ordered]
            except Exception as e:
                if "CERTIFICATE_VERIFY_FAILED" in str(e):
                    continue
                if attempt == EMBED_MAX_RETRIES:
                    raise
                wait = 5 * (2 ** (attempt - 1))
                log.warning(f"Embed attempt {attempt} failed ({e}); retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError("Embedding call failed after all retries")


def safe_embed_batch(batch_idx, texts, refs):
    """Embed a batch; on failure, bisect to per-chunk to isolate poison inputs.

    Without bisect, a single bad chunk in a batch of 32 would mark all 32
    failed — and with EMBED_FAIL_THRESHOLD=0.0, that fails 4+ sibling docs.
    Bisect re-tries the failed batch one chunk at a time so good chunks still
    get embedded; only the actual poison chunk(s) are reported as failures.
    """
    try:
        vectors = embed_batch(texts)
        return [(ref, vec) for ref, vec in zip(refs, vectors)]
    except Exception as batch_exc:
        log.error(f"Batch {batch_idx} failed ({batch_exc}); bisecting {len(texts)} chunks individually")
        results = []
        n_ok = n_bad = 0
        for ref, text in zip(refs, texts):
            try:
                vec = embed_batch([text])[0]
                results.append((ref, vec))
                n_ok += 1
            except Exception as one_exc:
                results.append((ref, None))
                n_bad += 1
                log.warning(f"  Bisect: chunk {ref} failed: {str(one_exc)[:120]}")
        log.info(f"Batch {batch_idx} bisect result: {n_ok} recovered, {n_bad} failed")
        return results


def _parse_date(s):
    """Convert YYYY-MM-DD string to datetime.date or None."""
    if not s:
        return None
    try:
        from datetime import date as _date
        return _date.fromisoformat(s)
    except Exception:
        return None

# COMMAND ----------

# ── process_one_batch: claim → extract → chunk → embed → merge → status ────

def process_one_batch(run_id, batch_limit, target_filter):
    """Process a single batch of docs. Returns (claimed, succeeded, failed, chunks_written)."""
    batch_start = datetime.now(timezone.utc)

    # ── Claim ────────────────────────────────────────────────────────────────
    _claim_df = spark.sql(f"""
        SELECT document_id FROM {METADATA_TABLE}
        WHERE metadata_status = '{MetadataStatus.COMPLETED}'
          AND chunk_status IN ('{ChunkStatus.PENDING}', '{ChunkStatus.FAILED}')
          AND COALESCE(chunk_retry_count, 0) < {P2_MAX_RETRIES}
          {target_filter}
        LIMIT {batch_limit}
    """)
    claimed_ids = [row.document_id for row in _claim_df.collect()]

    if not claimed_ids:
        return 0, 0, 0, 0  # nothing to do

    _ids_sql = ", ".join(f"'{did}'" for did in claimed_ids)
    spark.sql(f"""
        UPDATE {METADATA_TABLE}
        SET chunk_status = '{ChunkStatus.IN_PROGRESS}',
            chunked_at = current_timestamp()
        WHERE document_id IN ({_ids_sql})
          AND chunk_status IN ('{ChunkStatus.PENDING}', '{ChunkStatus.FAILED}')
    """)

    # ── Read claimed rows ────────────────────────────────────────────────────
    pending_df = spark.sql(f"""
        SELECT document_id, pdf_name, volume_path, title, customer, esn,
            equipment_sys_id, equipment_type, equipment_class_code,
            event_type, ev_project_id, ev_equipment_event_id,
            ofs_event_id, fsp_project_id, xxx_project_id, fsr_number,
            report_issued_date, outage_start_date, outage_end_date,
            outage_type, technology_type, prepared_by, approved_by,
            document_summary, page_count
        FROM {METADATA_TABLE}
        WHERE document_id IN ({_ids_sql})
    """)
    pending_docs = pending_df.collect()

    log.info(f"[batch {run_id}] {len(pending_docs)} docs claimed")
    for row in pending_docs[:5]:
        log.info(f"  {row.document_id[:50]}  pages={row.page_count}")
    if len(pending_docs) > 5:
        log.info(f"  ... and {len(pending_docs) - 5} more")

    # ── PDF chunking (DS V3 hierarchical chunker — see common/fsr_chunking) ──
    # Combines text extraction + section-aware chunking in one pass per doc.
    doc_chunks = {}   # document_id -> list[chunk dicts]
    doc_errors = {}   # document_id -> error_msg
    doc_full_text = {}  # document_id -> full text (for ESN detection)

    for idx, row in enumerate(pending_docs):
        doc_key = row.document_id
        vol_path = row.volume_path
        try:
            snapshot = load_pdf_snapshot(vol_path)
            total_pages = len(snapshot)

            raw_chunks = hierarchical_semantic_chunking_from_snapshot(
                snapshot,
                vol_path,
                chunk_size=CHUNKING_CONFIG.chunk_size,
                chunk_overlap=CHUNKING_CONFIG.chunk_overlap,
                verbose=False,
                split_subsections=True,
            )

            if not raw_chunks:
                doc_errors[doc_key] = "Chunker produced 0 chunks (no extractable text or filtered out)"
                log.warning(f"  [SKIP] {doc_key[:50]}: 0 chunks produced")
                continue

            # Flatten: lift the 5-level section path + page range out of metadata
            chunks = []
            for ci, ch in enumerate(raw_chunks):
                m = ch.get("metadata", {}) or {}
                start_page = m.get("start_page")
                end_page = m.get("end_page")
                chunks.append({
                    "chunk_index": ci,
                    "chunk_text": ch.get("text", ""),
                    "page_number": start_page,  # legacy column = start_page
                    "start_page":  start_page,
                    "end_page":    end_page,
                    "section_1":   m.get("section_1"),
                    "section_2":   m.get("section_2"),
                    "section_3":   m.get("section_3"),
                    "section_4":   m.get("section_4"),
                    "section_5":   m.get("section_5"),
                    "chunk_count": m.get("chunk_count"),
                })

            doc_chunks[doc_key] = chunks

            # Store full text for Tier 2 ESN detection (reuses already-loaded snapshot)
            if FSR_ESN_DETECT_ENABLED:
                doc_full_text[doc_key] = "\n\n".join(
                    page_text_from_snapshot(p) for p in snapshot
                )

            sec_cov = sum(1 for c in chunks if c["section_1"]) * 100 // max(len(chunks), 1)
            log.info(f"  [OK] {doc_key[:50]}  pages={total_pages}/{row.page_count}  "
                     f"chunks={len(chunks)}  "
                     f"avg_size={sum(len(c['chunk_text']) for c in chunks) // max(len(chunks), 1)}  "
                     f"section_cov={sec_cov}%")

        except Exception as e:
            doc_errors[doc_key] = str(e)[:500]
            log.warning(f"  [FAIL] {doc_key[:50]}: {e}")

        if (idx + 1) % 100 == 0:
            log.info(f"  Chunking progress: {idx + 1}/{len(pending_docs)} docs")

    log.info(f"Chunked {len(doc_chunks)} docs, "
             f"total chunks: {sum(len(c) for c in doc_chunks.values())}, "
             f"failed: {len(doc_errors)}")

    # ── Embedding ────────────────────────────────────────────────────────────
    # ── Tier 2: LLM ESN detection (optional, per FSR_ESN_DETECT_ENABLED) ─────
    doc_llm_esns = {}  # document_id -> list of ESNs from LLM frequency analysis
    if FSR_ESN_DETECT_ENABLED and doc_full_text:
        log.info(f"Tier 2: Running LLM ESN detection on {len(doc_full_text)} docs "
                 f"(model={FSR_ESN_LLM_MODEL})...")
        for doc_key, full_text in doc_full_text.items():
            try:
                counts = analyze_document_text_for_esn_counts(full_text)
                qualified = qualify_esn_counts(
                    counts,
                    min_count=FSR_ESN_MIN_COUNT,
                    min_fraction=FSR_ESN_MIN_FRACTION,
                )
                if qualified:
                    doc_llm_esns[doc_key] = qualified
                    log.info(f"  [ESN-LLM] {doc_key[:40]}: {qualified} (counts={counts})")
            except Exception as exc:
                log.warning(f"  [ESN-LLM-SKIP] {doc_key[:40]}: {exc}")
        log.info(f"Tier 2: ESN detection complete — {len(doc_llm_esns)} docs with LLM ESNs")

    # ── Embedding ────────────────────────────────────────────────────────────
    all_chunk_refs = []
    all_chunk_texts = []
    for doc_key, chunks in doc_chunks.items():
        for chunk in chunks:
            all_chunk_refs.append((doc_key, chunk["chunk_index"]))
            all_chunk_texts.append(chunk["chunk_text"])

    log.info(f"Generating embeddings for {len(all_chunk_texts)} chunks "
             f"(batch_size={EMBED_BATCH_SIZE}, concurrency={P2_EMBED_CONCURRENCY})...")

    all_embeddings = {}
    embed_failures = set()
    t0 = time.time()

    batches = [
        (i // EMBED_BATCH_SIZE, all_chunk_texts[i:i + EMBED_BATCH_SIZE],
         all_chunk_refs[i:i + EMBED_BATCH_SIZE])
        for i in range(0, len(all_chunk_texts), EMBED_BATCH_SIZE)
    ]
    total_batches = len(batches)
    completed_batches = 0

    with ThreadPoolExecutor(max_workers=P2_EMBED_CONCURRENCY) as pool:
        futures = {
            pool.submit(safe_embed_batch, bidx, texts, refs): bidx
            for bidx, texts, refs in batches
        }
        for future in as_completed(futures):
            completed_batches += 1
            for ref, vec in future.result():
                if vec is not None:
                    all_embeddings[ref] = vec
                else:
                    embed_failures.add(ref[0])
            if completed_batches % 10 == 0 or completed_batches == total_batches:
                log.info(f"  Embed progress: {completed_batches}/{total_batches} batches  "
                         f"elapsed={time.time() - t0:.1f}s")

    log.info(f"Generated {len(all_embeddings)} embeddings in {time.time() - t0:.1f}s")
    if embed_failures:
        log.warning(f"  Embedding failures in {len(embed_failures)} documents")
    if all_embeddings:
        sample_dim = len(next(iter(all_embeddings.values())))
        log.info(f"  Embedding dimension: {sample_dim} (expected {EMBEDDING_DIMENSION})")
        if sample_dim != EMBEDDING_DIMENSION:
            log.warning("Dimension mismatch! Update EMBEDDING_DIMENSION in config.")

    # Per-doc coverage check
    for doc_key, chunks in doc_chunks.items():
        total_c = len(chunks)
        embedded_c = sum(1 for c in chunks if (doc_key, c["chunk_index"]) in all_embeddings)
        missing_pct = 1.0 - (embedded_c / total_c) if total_c > 0 else 0.0
        if missing_pct > EMBED_FAIL_THRESHOLD:
            embed_failures.add(doc_key)
            doc_errors[doc_key] = (f"Embedding coverage too low: {embedded_c}/{total_c} "
                                   f"chunks ({missing_pct:.0%} missing, "
                                   f"threshold={EMBED_FAIL_THRESHOLD:.0%})")
            log.warning(f"  [FAIL] {doc_key[:50]}: {doc_errors[doc_key]}")

    # ── Determine success / failure sets before assembling rows ──────────────
    all_failed_ids = set(doc_errors.keys()) | embed_failures
    success_doc_ids = [did for did in doc_chunks.keys()
                       if did not in all_failed_ids]

    if all_failed_ids & doc_chunks.keys():
        excluded = all_failed_ids & doc_chunks.keys()
        excluded_chunks = sum(len(doc_chunks[d]) for d in excluded)
        log.info(f"Excluding {len(excluded)} failed docs ({excluded_chunks} chunks) "
                 f"from chunk table write to prevent partial ingestion")

    # ── Assemble chunk rows + MERGE (only fully successful docs) ─────────────
    doc_metadata = {row.document_id: row for row in pending_docs}
    chunk_rows = []
    now = datetime.now(timezone.utc)
    for doc_key in success_doc_ids:
        chunks = doc_chunks[doc_key]
        meta = doc_metadata.get(doc_key)
        if not meta:
            continue

        # Determine all ESNs for this doc (fsr_pdf_ref + metadata ESN + LLM detection)
        ref_esns = _ref_esn_map.get(doc_key.lower(), set())
        all_esns = set(ref_esns)
        if meta.esn and meta.esn.strip():
            all_esns.add(meta.esn.strip())
        # Add Tier 2 LLM-detected ESNs
        for llm_esn in doc_llm_esns.get(doc_key, []):
            all_esns.add(llm_esn)
        # If no ref ESNs, use single metadata ESN (original behavior)
        if not all_esns:
            all_esns = {meta.esn} if meta.esn else {""}

        for chunk in chunks:
            ci = chunk["chunk_index"]
            embedding = all_embeddings.get((doc_key, ci))
            if embedding is None:
                continue

            primary_esn = (meta.esn or "").strip()
            for esn in sorted(all_esns):
                # Multi-ESN chunk_id includes ESN suffix for uniqueness
                if len(all_esns) > 1:
                    chunk_id = hashlib.md5(f"{doc_key}_{ci}__{esn}".encode("utf-8")).hexdigest()
                else:
                    chunk_id = hashlib.md5(f"{doc_key}_{ci}".encode("utf-8")).hexdigest()

                # Secondary ESN rows use document_id + "_" + esn to match metadata fan-out
                if len(all_esns) > 1 and esn != primary_esn:
                    row_doc_id = f"{doc_key}_{esn}"
                else:
                    row_doc_id = doc_key

                metadata_json = json.dumps({
                    "pdf_name": meta.pdf_name,
                    "page_number": chunk["page_number"],
                    "start_page": chunk.get("start_page"),
                    "end_page":   chunk.get("end_page"),
                    "section_1":  chunk.get("section_1"),
                    "section_2":  chunk.get("section_2"),
                    "section_3":  chunk.get("section_3"),
                    "section_4":  chunk.get("section_4"),
                    "section_5":  chunk.get("section_5"),
                    "chunk_count": chunk.get("chunk_count"),
                    "title": meta.title,
                    "customer": meta.customer,
                    "esn": esn,
                    "equipment_sys_id": meta.equipment_sys_id,
                    "equipment_type": meta.equipment_type,
                    "equipment_class_code": meta.equipment_class_code,
                    "event_type": meta.event_type,
                    "ev_project_id": meta.ev_project_id,
                    "ev_equipment_event_id": meta.ev_equipment_event_id,
                    "ofs_event_id": meta.ofs_event_id,
                    "fsp_project_id": meta.fsp_project_id,
                    "xxx_project_id": meta.xxx_project_id,
                    "fsr_number": meta.fsr_number,
                    "report_issued_date": meta.report_issued_date,
                    "outage_start_date": meta.outage_start_date,
                    "outage_end_date": meta.outage_end_date,
                    "outage_type": meta.outage_type,
                    "technology_type": meta.technology_type,
                    "prepared_by": meta.prepared_by,
                    "approved_by": meta.approved_by,
                    "document_summary": meta.document_summary,
                }, default=str)

                chunk_rows.append({
                    "chunk_id": chunk_id,
                    "chunk_index": ci,
                    "document_id": row_doc_id,
                    "pdf_name": meta.pdf_name,
                    "page_number": chunk["page_number"],
                    "chunk_text": chunk["chunk_text"],
                    "esn": esn,
                    "report_date": _parse_date(meta.report_issued_date),
                    "chunk_embedding": [float(v) for v in embedding],
                    "metadata": metadata_json,
                    "created_at": now,
                })

    log.info(f"Assembled {len(chunk_rows)} chunk rows for {len(success_doc_ids)} documents"
             f" (excluded {len(all_failed_ids & doc_chunks.keys())} failed docs)")

    if chunk_rows and FSR_MULTI_ESN_DRY_RUN:
        # ── DRY_RUN: log what would be written, skip actual MERGE ────────────
        _secondary_chunks = [r for r in chunk_rows if "_" in r["document_id"]]
        _primary_chunks = [r for r in chunk_rows if "_" not in r["document_id"]]
        _esn_dist = {}
        for r in chunk_rows:
            _esn_dist.setdefault(r["esn"], 0)
            _esn_dist[r["esn"]] += 1
        log.info("=" * 70)
        log.info("  MULTI-ESN CHUNKS DRY RUN — NO WRITES WILL BE PERFORMED")
        log.info("=" * 70)
        log.info(f"  Total chunk rows that would be written: {len(chunk_rows)}")
        log.info(f"  Primary ESN chunks   : {len(_primary_chunks)}")
        log.info(f"  Secondary ESN chunks : {len(_secondary_chunks)}")
        log.info(f"  Distinct ESNs        : {len(_esn_dist)}")
        log.info(f"  Distinct documents   : {len(set(r['document_id'] for r in chunk_rows))}")
        log.info("")
        log.info("  ESN distribution (top 15):")
        for esn, cnt in sorted(_esn_dist.items(), key=lambda x: -x[1])[:15]:
            log.info(f"    {esn}: {cnt} chunks")
        log.info("")
        log.info("  Sample rows (first 10):")
        for r in chunk_rows[:10]:
            log.info(f"    chunk_id={r['chunk_id'][:12]}...  doc_id={r['document_id'][:40]}  "
                     f"esn={r['esn']}  ci={r['chunk_index']}")
        log.info("=" * 70)
        log.info("*** DRY_RUN=true — Set FSR_MULTI_ESN_DRY_RUN=false to execute writes. ***")
        chunk_rows = []  # Clear to skip MERGE

    if chunk_rows:
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

        chunk_df = spark.createDataFrame(chunk_rows, schema=schema)
        chunk_df.createOrReplaceTempView("_fsr_new_chunks")

        spark.sql(f"""
            MERGE INTO {CHUNK_TABLE} AS tgt
            USING _fsr_new_chunks AS src
            ON tgt.chunk_id = src.chunk_id
            WHEN MATCHED THEN UPDATE SET
                tgt.chunk_index = src.chunk_index,
                tgt.document_id = src.document_id,
                tgt.pdf_name = src.pdf_name,
                tgt.page_number = src.page_number,
                tgt.chunk_text = src.chunk_text,
                tgt.esn = src.esn,
                tgt.report_date = src.report_date,
                tgt.chunk_embedding = src.chunk_embedding,
                tgt.metadata = src.metadata,
                tgt.created_at = src.created_at
            WHEN NOT MATCHED THEN INSERT *
        """)
        log.info(f"MERGE complete: {len(chunk_rows)} chunk rows")

    # ── Update metadata status ───────────────────────────────────────────────
    if success_doc_ids:
        ids_sql = ", ".join(f"'{did}'" for did in success_doc_ids)
        spark.sql(f"""
            UPDATE {METADATA_TABLE}
            SET chunk_status = '{ChunkStatus.COMPLETED}',
                chunk_error = NULL,
                chunk_retry_count = 0,
                chunked_at = current_timestamp()
            WHERE document_id IN ({ids_sql})
        """)
        log.info(f"Updated {len(success_doc_ids)} docs → chunk_status=completed")

        # Also mark secondary metadata rows (uuid_ESN) as completed.
        # These should already be 'completed' from P1, but catch legacy rows.
        _like_clauses = " OR ".join(
            f"document_id LIKE '{did}\\_%' ESCAPE '\\\\'"
            for did in success_doc_ids
        )
        _sec_updated = spark.sql(f"""
            UPDATE {METADATA_TABLE}
            SET chunk_status = '{ChunkStatus.COMPLETED}',
                chunk_error = NULL,
                chunked_at = current_timestamp()
            WHERE ({_like_clauses})
              AND chunk_status != '{ChunkStatus.COMPLETED}'
        """)
        log.info("Ensured secondary metadata rows marked chunk_status=completed")

    if all_failed_ids:
        failed_rows = [{
            "document_id": doc_key,
            "chunk_error": (doc_errors.get(doc_key, "Embedding failure — see embed_failures log") or "")[:200],
        } for doc_key in all_failed_ids]
        spark.createDataFrame(failed_rows).createOrReplaceTempView("_fsr_failed_docs")
        spark.sql(f"""
            MERGE INTO {METADATA_TABLE} AS tgt
            USING _fsr_failed_docs AS src
            ON tgt.document_id = src.document_id
            WHEN MATCHED THEN UPDATE SET
                tgt.chunk_status = '{ChunkStatus.FAILED}',
                tgt.chunk_error = src.chunk_error,
                tgt.chunk_retry_count = COALESCE(tgt.chunk_retry_count, 0) + 1,
                tgt.chunked_at = current_timestamp()
        """)
        log.info(f"Marked {len(all_failed_ids)} docs → chunk_status=failed")

    # ── Audit log for this batch ─────────────────────────────────────────────
    batch_end = datetime.now(timezone.utc)
    duration = (batch_end - batch_start).total_seconds()
    docs_succeeded = len(success_doc_ids)
    docs_failed = len(all_failed_ids)
    chunks_written = len(chunk_rows) if chunk_rows else 0
    error_summary = "; ".join(
        f"{k[:30]}: {v[:80]}" for k, v in list(doc_errors.items())[:10]
    ) if doc_errors else None

    try:
        _err_sql = f"'{error_summary[:500].replace(chr(39), chr(39)*2)}'" if error_summary else "NULL"
        spark.sql(f"""
            INSERT INTO {RUN_LOG_TABLE} VALUES (
                '{run_id}',
                NULL,
                '{batch_start.strftime('%Y-%m-%dT%H:%M:%S')}',
                '{batch_end.strftime('%Y-%m-%dT%H:%M:%S')}',
                {duration:.1f},
                {len(pending_docs)},
                {docs_succeeded},
                {docs_failed},
                {chunks_written},
                {_err_sql},
                current_timestamp()
            )
        """)
        log.info(f"Audit: run={run_id}, claimed={len(pending_docs)}, "
                 f"ok={docs_succeeded}, fail={docs_failed}, chunks={chunks_written}, "
                 f"duration={duration:.0f}s")
    except Exception as e:
        log.warning(f"Failed to write run audit log: {e}")

    return len(pending_docs), docs_succeeded, docs_failed, chunks_written

# COMMAND ----------

# ── Batch loop — drain the queue ────────────────────────────────────────────
import uuid as _uuid

target_filter = ""
if TARGET_PDF_NAMES:
    target_ids = ", ".join(f"'{tid}'" for tid in TARGET_PDF_NAMES)
    target_filter = f"AND document_id IN ({target_ids})"

batch_limit = P2_BATCH_SIZE
log.info(f"  Batch limit    : {batch_limit} docs (P2_BATCH_SIZE)")
if TARGET_PDF_NAMES:
    log.info(f"  Target filter  : {len(TARGET_PDF_NAMES)} specific doc IDs (debug mode)")
log.info(f"  Max iterations : {P2_MAX_ITERATIONS or 'unlimited'}")

grand_claimed = 0
grand_succeeded = 0
grand_failed = 0
grand_chunks = 0
iteration = 0

while True:
    iteration += 1
    if P2_MAX_ITERATIONS and iteration > P2_MAX_ITERATIONS:
        log.info(f"Reached P2_MAX_ITERATIONS={P2_MAX_ITERATIONS}, stopping")
        break

    run_id = _uuid.uuid4().hex[:12]
    log.info(f"── Iteration {iteration} (run={run_id}) ──")

    claimed, succeeded, failed, chunks = process_one_batch(run_id, batch_limit, target_filter)

    if claimed == 0:
        log.info("Queue drained — no more pending docs")
        break

    grand_claimed += claimed
    grand_succeeded += succeeded
    grand_failed += failed
    grand_chunks += chunks

    log.info(f"Running totals: claimed={grand_claimed}, ok={grand_succeeded}, "
             f"fail={grand_failed}, chunks={grand_chunks}")

_grand_end = datetime.now(timezone.utc)
_grand_duration = (_grand_end - _grand_start).total_seconds()
log.info(f"=== Batch loop complete: {iteration - 1 if (P2_MAX_ITERATIONS and iteration > P2_MAX_ITERATIONS) or claimed == 0 else iteration} iterations, "
         f"{grand_claimed} docs, {grand_chunks} chunks in {_grand_duration:.0f}s ===")

# ── Verify ──────────────────────────────────────────────────────────────────
chunk_count = spark.sql(f"SELECT COUNT(*) AS n FROM {CHUNK_TABLE}").first().n
doc_count = spark.sql(f"SELECT COUNT(DISTINCT document_id) AS n FROM {CHUNK_TABLE}").first().n
log.info(f"Chunk table: {chunk_count} rows, {doc_count} documents")

# COMMAND ----------

# ── Trigger Vector Search index sync ────────────────────────────────────────

def _get_dbr_auth():
    return get_dbr_auth()


def sync_vector_search():
    ws_url, token = _get_dbr_auth()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Check endpoint status
    ep_url = f"{ws_url}/api/2.0/vector-search/endpoints/{VS_ENDPOINT_NAME}"
    try:
        resp = requests.get(ep_url, headers=headers, timeout=30, verify=DATABRICKS_VERIFY_SSL)
        if resp.ok:
            state = resp.json().get("endpoint_status", {}).get("state", "")
            log.info(f"VS endpoint '{VS_ENDPOINT_NAME}' state: {state}")
            if state != "ONLINE":
                log.warning("Endpoint not ONLINE — skipping sync")
                return
        else:
            log.warning(f"Cannot check endpoint: HTTP {resp.status_code}")
            return
    except Exception as e:
        log.warning(f"Cannot reach endpoint: {e}")
        return

    # Check if index exists; create if not
    idx_url = f"{ws_url}/api/2.0/vector-search/indexes/{VS_INDEX_NAME}"
    resp = requests.get(idx_url, headers=headers, timeout=30, verify=DATABRICKS_VERIFY_SSL)
    if resp.status_code == 404:
        log.info(f"Creating VS index: {VS_INDEX_NAME}")
        create_body = {
            "name": VS_INDEX_NAME,
            "endpoint_name": VS_ENDPOINT_NAME,
            "primary_key": "chunk_id",
            "index_type": "DELTA_SYNC",
            "delta_sync_index_spec": {
                "source_table": CHUNK_TABLE,
                "pipeline_type": "TRIGGERED",
                "embedding_vector_columns": [{
                    "name": "chunk_embedding",
                    "embedding_dimension": EMBEDDING_DIMENSION,
                }],
            },
        }
        create_resp = requests.post(
            f"{ws_url}/api/2.0/vector-search/indexes",
            headers=headers, json=create_body, timeout=60, verify=DATABRICKS_VERIFY_SSL,
        )
        if create_resp.ok:
            log.info(f"VS index created: {VS_INDEX_NAME}")
        else:
            log.warning(f"VS index create failed: HTTP {create_resp.status_code} "
                        f"{create_resp.text[:300]}")
            return
    elif not resp.ok:
        log.warning(f"Cannot check index: HTTP {resp.status_code}")
        return
    else:
        log.info(f"VS index exists: {VS_INDEX_NAME}")

    # Trigger sync
    sync_url = f"{ws_url}/api/2.0/vector-search/indexes/{VS_INDEX_NAME}/sync"
    for attempt in range(1, 4):
        try:
            resp = requests.post(sync_url, headers=headers, json={},
                                 timeout=30, verify=DATABRICKS_VERIFY_SSL)
            if resp.ok:
                log.info("VS sync triggered")
                return
            if resp.status_code == 400 and "not ready" in resp.text.lower():
                log.info(f"Endpoint warming (attempt {attempt}/3) — waiting 20s...")
                time.sleep(20)
                continue
            log.warning(f"VS sync failed: HTTP {resp.status_code} {resp.text[:200]}")
            return
        except Exception as e:
            log.warning(f"VS sync error: {e}")
            return
    log.warning("VS sync failed after 3 attempts")


sync_vector_search()
log.info("=== Process 2 complete ===")
