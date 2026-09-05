# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_chunks — Process 2: Chunking, Embedding & VS Sync (Gold)
#
# Reads documents with metadata_status=completed and chunk_status=pending/failed
# from the metadata registry. Extracts full text via PyMuPDF, splits into chunks,
# generates embeddings via LiteLLM, writes to the chunk Delta table, and triggers
# Vector Search index sync.
#
# Schema v3: document_id is PK/FK, pdf_name is derived. Statuses: pending / completed / failed.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet PyMuPDF langchain-text-splitters

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../common/fsr_config

# COMMAND ----------

import json, time, hashlib, os, logging
from pathlib import Path
from datetime import datetime, timezone

import fitz  # PyMuPDF
import requests
import urllib3
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, current_timestamp
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    DoubleType, ArrayType, TimestampType,
)

urllib3.disable_warnings()
spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.p2.chunks")

# COMMAND ----------

log.info("=== Process 2 — Chunk Ingestion ===")
log.info(f"  Metadata table : {METADATA_TABLE}")
log.info(f"  Chunk table    : {CHUNK_TABLE}")
log.info(f"  VS index       : {VS_INDEX_NAME}")
log.info(f"  VS endpoint    : {VS_ENDPOINT_NAME}")
log.info(f"  Embedding model: {EMBEDDING_MODEL}")
log.info(f"  Embed dimension: {EMBEDDING_DIMENSION}")
log.info(f"  Target PDFs    : {len(TARGET_PDF_NAMES) if TARGET_PDF_NAMES else 'all'}")
log.info(f"  Chunk size     : {CHUNKING_CONFIG.chunk_size}")
log.info(f"  Chunk overlap  : {CHUNKING_CONFIG.chunk_overlap}")
log.info(f"  LLM base URL   : {LITELLM_BASE_URL}")
log.info(f"  API key set    : {bool(LITELLM_API_KEY)}")

# COMMAND ----------

# ── Query metadata table for documents ready to chunk ───────────────────────
pending_df = spark.sql(f"""
    SELECT document_id, pdf_name, volume_path, title, esn, equipment_sys_id, equipment_type,
        event_type, ev_equipment_event_id, fsp_project_id,
        report_issued_date, outage_start_date, outage_end_date, page_count
    FROM {METADATA_TABLE}
    WHERE metadata_status = '{MetadataStatus.COMPLETED}'
      AND chunk_status IN ('{ChunkStatus.PENDING}', '{ChunkStatus.FAILED}')
""")
pending_docs = pending_df.collect()

target_pdf_names = set(TARGET_PDF_NAMES or [])
if target_pdf_names:
    pending_docs = [row for row in pending_docs if row.document_id in target_pdf_names]

if P1_MAX_PDFS and len(pending_docs) > P1_MAX_PDFS:
    pending_docs = pending_docs[:P1_MAX_PDFS]

log.info(f"{len(pending_docs)} documents to chunk")
for row in pending_docs[:5]:
    log.info(f"  {row.document_id[:50]}  pages={row.page_count}")
if len(pending_docs) > 5:
    log.info(f"  ... and {len(pending_docs) - 5} more")

# COMMAND ----------

# ── Extract full text from each PDF using PyMuPDF ───────────────────────────
doc_texts = {}   # document_id -> {pages: [...], total_pages: int}
doc_errors = {}  # document_id -> error_msg

for row in pending_docs:
    doc_key = row.document_id
    vol_path = row.volume_path
    try:
        doc = fitz.open(vol_path)
        total_pages = len(doc)
        pages = []
        for page_idx in range(total_pages):
            text = doc[page_idx].get_text()
            if text and text.strip():
                pages.append({
                    "page_num": page_idx + 1,
                    "text": text,
                })
        doc.close()

        if not pages:
            doc_errors[doc_key] = "No extractable text in PDF"
            log.warning(f"  [SKIP] {doc_key[:50]}: no text")
            continue

        doc_texts[doc_key] = {
            "pages": pages,
            "total_pages": total_pages,
        }
        total_chars = sum(len(p["text"]) for p in pages)
        log.info(f"  [OK] {doc_key[:50]}  pages={len(pages)}/{row.page_count}  chars={total_chars:,}")

    except Exception as e:
        doc_errors[doc_key] = str(e)[:500]
        log.warning(f"  [FAIL] {doc_key[:50]}: {e}")

log.info(f"Extracted: {len(doc_texts)}, Failed: {len(doc_errors)}")

# COMMAND ----------

# ── Recursive chunking with page tracking ───────────────────────────────────
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNKING_CONFIG.chunk_size,
    chunk_overlap=CHUNKING_CONFIG.chunk_overlap,
    separators=["\n\n", "\n", ". ", " ", ""],
    length_function=len,
)

doc_chunks = {}  # document_id -> [{chunk_index, chunk_text, start_page, end_page, chunk_size}]

for doc_key, text_data in doc_texts.items():
    pages = text_data["pages"]

    # Build full text and page offset map
    full_text = ""
    page_spans = []  # [(start_offset, end_offset, page_num)]
    for page in pages:
        start = len(full_text)
        full_text += page["text"] + "\n\n"
        end = len(full_text)
        page_spans.append((start, end, page["page_num"]))

    if not full_text.strip():
        doc_errors[doc_key] = "Empty text after joining pages"
        continue

    chunk_texts = splitter.split_text(full_text)

    chunks = []
    search_from = 0
    for ci, ctext in enumerate(chunk_texts):
        idx = full_text.find(ctext, search_from)
        if idx == -1:
            idx = full_text.find(ctext.strip(), max(0, search_from - 200))
        if idx >= 0:
            c_start = idx
            c_end = idx + len(ctext)
            chunk_pages = [pn for (ps, pe, pn) in page_spans
                           if ps < c_end and pe > c_start]
            search_from = idx + 1
        else:
            chunk_pages = [p["page_num"] for p in pages]

        start_page = min(chunk_pages) if chunk_pages else 1
        end_page = max(chunk_pages) if chunk_pages else text_data["total_pages"]

        chunks.append({
            "chunk_index": ci,
            "chunk_text": ctext,
            "start_page": start_page,
            "end_page": end_page,
            "chunk_size": len(ctext),
        })

    doc_chunks[doc_key] = chunks
    log.info(f"  [OK] {doc_key[:50]}  chunks={len(chunks)}  "
             f"avg_size={sum(c['chunk_size'] for c in chunks) // max(len(chunks), 1)}")

log.info(f"Chunked {len(doc_chunks)} documents, "
         f"total chunks: {sum(len(c) for c in doc_chunks.values())}")

# COMMAND ----------

# ── Generate embeddings via LiteLLM ─────────────────────────────────────────
EMBED_BATCH_SIZE = 32
EMBED_MAX_RETRIES = 3


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


# Flatten all chunks for batched embedding
all_chunk_refs = []   # (document_id, chunk_index)
all_chunk_texts = []

for doc_key, chunks in doc_chunks.items():
    for chunk in chunks:
        all_chunk_refs.append((doc_key, chunk["chunk_index"]))
        all_chunk_texts.append(chunk["chunk_text"])

log.info(f"Generating embeddings for {len(all_chunk_texts)} chunks (batch size={EMBED_BATCH_SIZE})...")

all_embeddings = {}  # (document_id, chunk_index) -> [float, ...]
t0 = time.time()

for i in range(0, len(all_chunk_texts), EMBED_BATCH_SIZE):
    batch_texts = all_chunk_texts[i:i + EMBED_BATCH_SIZE]
    batch_refs = all_chunk_refs[i:i + EMBED_BATCH_SIZE]
    batch_num = (i // EMBED_BATCH_SIZE) + 1
    total_batches = (len(all_chunk_texts) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE

    vectors = embed_batch(batch_texts)
    for ref, vec in zip(batch_refs, vectors):
        all_embeddings[ref] = vec

    log.info(f"  Batch {batch_num}/{total_batches}: {len(batch_texts)} texts  "
             f"dim={len(vectors[0])}  elapsed={time.time() - t0:.1f}s")

log.info(f"Generated {len(all_embeddings)} embeddings in {time.time() - t0:.1f}s")
if all_embeddings:
    sample_dim = len(next(iter(all_embeddings.values())))
    log.info(f"  Embedding dimension: {sample_dim} (expected {EMBEDDING_DIMENSION})")
    if sample_dim != EMBEDDING_DIMENSION:
        log.warning("Dimension mismatch! Update EMBEDDING_DIMENSION in config.")

# COMMAND ----------

# ── Assemble chunk rows and MERGE to Delta ──────────────────────────────────
doc_metadata = {row.document_id: row for row in pending_docs}

chunk_rows = []
now = datetime.now(timezone.utc)
for doc_key, chunks in doc_chunks.items():
    meta = doc_metadata.get(doc_key)
    if not meta:
        continue
    chunk_count = len(chunks)
    for chunk in chunks:
        ci = chunk["chunk_index"]
        chunk_id = hashlib.md5(f"{doc_key}_{ci}".encode("utf-8")).hexdigest()
        embedding = all_embeddings.get((doc_key, ci))
        if embedding is None:
            continue
        chunk_rows.append({
            "chunk_id": chunk_id,
            "document_id": doc_key,
            "pdf_name": meta.pdf_name,
            "chunk_index": ci,
            "chunk_text": chunk["chunk_text"],
            "embedding": [float(v) for v in embedding],
            "title": meta.title,
            "esn": meta.esn,
            "equipment_sys_id": meta.equipment_sys_id,
            "equipment_type": meta.equipment_type,
            "event_type": meta.event_type,
            "ev_equipment_event_id": meta.ev_equipment_event_id,
            "fsp_project_id": meta.fsp_project_id,
            "report_issued_date": meta.report_issued_date,
            "outage_start_date": meta.outage_start_date,
            "outage_end_date": meta.outage_end_date,
            "page_count": meta.page_count,
            "chunk_count": chunk_count,
            "start_page": chunk["start_page"],
            "end_page": chunk["end_page"],
            "chunk_size": chunk["chunk_size"],
            "ingested_at": now,
        })

log.info(f"Assembled {len(chunk_rows)} chunk rows for {len(doc_chunks)} documents")

if chunk_rows:
    schema = StructType([
        StructField("chunk_id", StringType(), False),
        StructField("document_id", StringType(), False),
        StructField("pdf_name", StringType(), True),
        StructField("chunk_index", IntegerType(), False),
        StructField("chunk_text", StringType(), False),
        StructField("embedding", ArrayType(DoubleType()), True),
        StructField("title", StringType(), True),
        StructField("esn", StringType(), True),
        StructField("equipment_sys_id", StringType(), True),
        StructField("equipment_type", StringType(), True),
        StructField("event_type", StringType(), True),
        StructField("ev_equipment_event_id", StringType(), True),
        StructField("fsp_project_id", StringType(), True),
        StructField("report_issued_date", StringType(), True),
        StructField("outage_start_date", StringType(), True),
        StructField("outage_end_date", StringType(), True),
        StructField("page_count", IntegerType(), True),
        StructField("chunk_count", IntegerType(), True),
        StructField("start_page", IntegerType(), True),
        StructField("end_page", IntegerType(), True),
        StructField("chunk_size", IntegerType(), True),
        StructField("ingested_at", TimestampType(), True),
    ])

    chunk_df = spark.createDataFrame(chunk_rows, schema=schema)
    chunk_df.createOrReplaceTempView("_fsr_new_chunks")

    spark.sql(f"""
        MERGE INTO {CHUNK_TABLE} AS tgt
        USING _fsr_new_chunks AS src
        ON tgt.chunk_id = src.chunk_id
        WHEN MATCHED THEN UPDATE SET
            tgt.document_id = src.document_id,
            tgt.pdf_name = src.pdf_name,
            tgt.chunk_text = src.chunk_text,
            tgt.embedding = src.embedding,
            tgt.title = src.title,
            tgt.esn = src.esn,
            tgt.equipment_sys_id = src.equipment_sys_id,
            tgt.equipment_type = src.equipment_type,
            tgt.event_type = src.event_type,
            tgt.ev_equipment_event_id = src.ev_equipment_event_id,
            tgt.fsp_project_id = src.fsp_project_id,
            tgt.report_issued_date = src.report_issued_date,
            tgt.outage_start_date = src.outage_start_date,
            tgt.outage_end_date = src.outage_end_date,
            tgt.page_count = src.page_count,
            tgt.chunk_count = src.chunk_count,
            tgt.start_page = src.start_page,
            tgt.end_page = src.end_page,
            tgt.chunk_size = src.chunk_size,
            tgt.ingested_at = src.ingested_at
        WHEN NOT MATCHED THEN INSERT *
    """)
    log.info(f"MERGE complete: {len(chunk_rows)} chunk rows")

    # ── Update metadata: chunk_status → completed ───────────────────────────
    success_doc_ids = list(doc_chunks.keys())
    if success_doc_ids:
        ids_sql = ", ".join(f"'{did}'" for did in success_doc_ids)
        spark.sql(f"""
            UPDATE {METADATA_TABLE}
            SET chunk_status = '{ChunkStatus.COMPLETED}',
                chunk_error = NULL,
                updated_at = current_timestamp()
            WHERE document_id IN ({ids_sql})
        """)
        log.info(f"Updated {len(success_doc_ids)} docs → chunk_status=completed")

# ── Handle failures: mark chunk_status=failed ───────────────────────────────
if doc_errors:
    for doc_key, err in doc_errors.items():
        safe_err = err[:200].replace("'", "''")
        spark.sql(f"""
            UPDATE {METADATA_TABLE}
            SET chunk_status = '{ChunkStatus.FAILED}',
                chunk_error = '{safe_err}',
                updated_at = current_timestamp()
            WHERE document_id = '{doc_key}'
        """)
    log.info(f"Marked {len(doc_errors)} docs → chunk_status=failed")

# ── Verify ──────────────────────────────────────────────────────────────────
chunk_count = spark.sql(f"SELECT COUNT(*) AS n FROM {CHUNK_TABLE}").first().n
doc_count = spark.sql(f"SELECT COUNT(DISTINCT document_id) AS n FROM {CHUNK_TABLE}").first().n
log.info(f"Chunk table: {chunk_count} rows, {doc_count} documents")

# COMMAND ----------

# ── Trigger Vector Search index sync ────────────────────────────────────────

def _get_dbr_auth():
    ws_url = "https://gevernova-ai-dev-dbr.cloud.databricks.com"
    token = None
    try:
        token = (dbutils.notebook.entry_point  # noqa: F821
                 .getDbutils().notebook().getContext()
                 .apiToken().get())
    except Exception:
        token = os.getenv("DATABRICKS_TOKEN", "")
    return ws_url, token or ""


def sync_vector_search():
    ws_url, token = _get_dbr_auth()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Check endpoint status
    ep_url = f"{ws_url}/api/2.0/vector-search/endpoints/{VS_ENDPOINT_NAME}"
    try:
        resp = requests.get(ep_url, headers=headers, timeout=30, verify=False)
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
    resp = requests.get(idx_url, headers=headers, timeout=30, verify=False)
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
                    "name": "embedding",
                    "embedding_dimension": EMBEDDING_DIMENSION,
                }],
            },
        }
        create_resp = requests.post(
            f"{ws_url}/api/2.0/vector-search/indexes",
            headers=headers, json=create_body, timeout=60, verify=False,
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
                                 timeout=30, verify=False)
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
