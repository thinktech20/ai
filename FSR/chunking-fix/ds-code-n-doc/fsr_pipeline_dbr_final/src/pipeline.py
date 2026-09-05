"""
FSR Hybrid Retrieval Pipeline – Databricks
End-to-end orchestration: Volume PDFs → Delta chunk rows → Vector Search sync
→ retrieval smoke test.
"""
import os
import queue
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from config import (
    PDF_VOLUME_PATHS, EMBEDDINGS_TABLE,
    chunking_config,
    PDF_PROCESS_WORKERS,
    VS_ENDPOINT_NAME, VS_INDEX_NAME,
)
from utils import setup_logger, collect_pdfs_from_volumes
from pdf_processor import process_single_pdf_with_background_doc_analysis
from document_loader import load_all_chunks_from_delta, inspect_documents
from delta_store import (
    build_delta_rows,
    chunk_table_doc_ids,
    delete_chunk_rows_for_doc_ids,
    load_ref_view_lookup,
    save_rows_to_delta,
    table_doc_ids,
)
from esn_identifier import identify_esns
from vector_embeddings import get_query_vector

logger = setup_logger("pipeline")

WRITE_QUEUE_MAX_PDFS = 200
WRITE_BATCH_MAX_PDFS = 100
WRITE_SENTINEL = object()
_PROCESS_REF_LOOKUP: dict[str, Any] = {}


def _process_worker_init(ref_lookup: dict[str, Any]) -> None:
    global _PROCESS_REF_LOOKUP
    _PROCESS_REF_LOOKUP = ref_lookup or {}
    os.environ["FSR_USE_PYMUPDF_LOCK"] = "false"


def _process_one_pdf_job(pdf_path_str: str) -> dict[str, Any]:
    from langchain_core.documents import Document as LCDoc

    pdf_path = Path(pdf_path_str)
    doc_id = pdf_path.stem
    started_at = time.time()
    chunk_elapsed = 0.0
    esn_elapsed = 0.0

    try:
        _, chunks, _, doc_counts, stage_timings = process_single_pdf_with_background_doc_analysis(
            pdf_path_str,
            chunking_config,
        )
        chunk_elapsed = stage_timings.get("chunk_elapsed", 0.0)

        if not chunks:
            return {
                "doc_id": doc_id,
                "rows": [],
                "chunk_elapsed": chunk_elapsed,
                "esn_elapsed": esn_elapsed,
                "started_at": started_at,
                "status": "skipped=no_chunks",
            }

        label_started_at = time.time()
        chunks = identify_esns(chunks, doc_counts=doc_counts)
        esn_elapsed = stage_timings.get("esn_elapsed", 0.0) + (time.time() - label_started_at)

        if not chunks:
            return {
                "doc_id": doc_id,
                "rows": [],
                "chunk_elapsed": chunk_elapsed,
                "esn_elapsed": esn_elapsed,
                "started_at": started_at,
                "status": "skipped=empty_after_esn",
            }

        docs = [
            LCDoc(page_content=chunk["text"], metadata=chunk.get("metadata", {}))
            for chunk in chunks
        ]
        if not docs:
            return {
                "doc_id": doc_id,
                "rows": [],
                "chunk_elapsed": chunk_elapsed,
                "esn_elapsed": esn_elapsed,
                "started_at": started_at,
                "status": "skipped=no_docs",
            }

        rows = build_delta_rows(
            docs,
            ref_lookup=_PROCESS_REF_LOOKUP,
            source_doc_id=doc_id,
        )
        if not rows:
            return {
                "doc_id": doc_id,
                "rows": [],
                "chunk_elapsed": chunk_elapsed,
                "esn_elapsed": esn_elapsed,
                "started_at": started_at,
                "status": "skipped=empty_rows",
            }

        return {
            "doc_id": doc_id,
            "rows": rows,
            "chunk_elapsed": chunk_elapsed,
            "esn_elapsed": esn_elapsed,
            "started_at": started_at,
            "status": "ready",
        }
    except Exception as exc:
        err_msg = str(exc)
        return {
            "doc_id": doc_id,
            "rows": [],
            "chunk_elapsed": chunk_elapsed,
            "esn_elapsed": esn_elapsed,
            "started_at": started_at,
            "status": "failed",
            "error": err_msg,
            "fatal": (
                "Missing LITELLM_API_KEY" in err_msg
                or "[ESN-LLM] Doc-level call failed" in err_msg
                or "[ESN-LLM] Failed to parse doc-level response" in err_msg
            ),
        }


# ============================================================================
# HELPERS
# ============================================================================

def _fmt(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    return f"{int(s // 60)}m {s % 60:.0f}s"


def _get_spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder.getOrCreate()


def _table_exists(spark, name: str) -> bool:
    try:
        spark.sql(f"DESCRIBE TABLE {name}")
        return True
    except Exception:
        return False


def _target_doc_ids_from_table(source_table: str) -> set[str]:
    doc_ids = table_doc_ids(source_table)
    if not doc_ids:
        raise RuntimeError(
            f"No pdf_name values found in source table {source_table}. "
            "Cannot run targeted reingest."
        )
    return doc_ids


# ============================================================================
# VECTOR SEARCH MANAGEMENT
# ============================================================================

def _build_ca_bundle() -> str:
    """
    Build a combined CA bundle: system CAs + GE Enterprise Root CA.

    The GE cert alone isn't enough (Databricks endpoints use public CAs too).
    We append the GE cert to the default certifi bundle and write a temp file
    that can be set as REQUESTS_CA_BUNDLE so the VS client trusts both.
    """
    import tempfile, shutil
    from config import CERT_PATH

    if not CERT_PATH or not Path(CERT_PATH).exists():
        return ""                                   # no GE cert available

    # Use a user-writable temp file (avoids permission issues with shared /tmp dirs)
    combined_path = Path(tempfile.gettempdir()) / f"fsr_combined_ca_{os.getpid()}.pem"
    if combined_path.exists():
        return str(combined_path)                   # already built in this run

    # Locate the default system / certifi CA bundle
    system_bundle = ""
    try:
        import certifi
        system_bundle = certifi.where()
    except ImportError:
        for candidate in [
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/etc/ssl/ca-bundle.pem",
        ]:
            if Path(candidate).exists():
                system_bundle = candidate
                break

    try:
        if system_bundle:
            shutil.copy2(system_bundle, combined_path)
        else:
            combined_path.write_bytes(b"")          # start empty – GE cert only

        # Append the GE Enterprise Root CA
        with open(combined_path, "a") as f:
            f.write("\n")
            f.write(Path(CERT_PATH).read_text())

        logger.info(f"[OK] Combined CA bundle: {combined_path}")
        return str(combined_path)
    except Exception as e:
        logger.warning(f"[WARN] Could not build combined CA bundle: {e}")
        return ""

def _get_dbr_auth():
    """Return (workspace_url, bearer_token) for direct Databricks REST API calls."""
    ws_url = os.getenv("DATABRICKS_HOST", "https://gevernova-ai-dev-dbr.cloud.databricks.com")
    token  = None
    try:
        from pyspark.sql import SparkSession
        from pyspark.dbutils import DBUtils
        spark   = SparkSession.builder.getOrCreate()
        dbutils = DBUtils(spark)
        token   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    except Exception:
        token = os.getenv("DATABRICKS_TOKEN", "")
    return ws_url.rstrip("/"), (token or "")


# NOTE: Delta table + VS index are created by _setup_tables.py (one-time).
# The pipeline assumes they already exist.


def _wait_for_vs_endpoint(ws_url: str, token: str, endpoint_name: str,
                           timeout_s: int = 300, poll_s: int = 15) -> bool:
    """Poll the VS endpoint until its state is ONLINE (or timeout)."""
    import requests, time
    url     = f"{ws_url}/api/2.0/vector-search/endpoints/{endpoint_name}"
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.ok:
                state = r.json().get("endpoint_status", {}).get("state", "")
                if state == "ONLINE":
                    logger.info(f"[OK] VS endpoint '{endpoint_name}' is ONLINE")
                    return True
                logger.info(f"  VS endpoint state: {state} — waiting {poll_s}s …")
            else:
                logger.warning(f"  VS endpoint status check HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.warning(f"  VS endpoint status check failed: {e}")
        time.sleep(poll_s)
    logger.warning(f"[WARN] VS endpoint '{endpoint_name}' not ONLINE after {timeout_s}s — skipping sync")
    return False


def _sync_vs_index():
    """Wait for VS endpoint to be ONLINE, then trigger an incremental index sync.
    Retries the sync POST if the endpoint reports 'not ready yet' (status API can
    return ONLINE before the sync handler is fully accepting requests).
    """
    import requests, time
    ws_url, token = _get_dbr_auth()

    # Endpoint must be ONLINE before sync will be accepted
    if not _wait_for_vs_endpoint(ws_url, token, VS_ENDPOINT_NAME):
        return

    url     = f"{ws_url}/api/2.0/vector-search/indexes/{VS_INDEX_NAME}/sync"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    retries = 6
    wait_s  = 20  # seconds between retries

    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, headers=headers, json={}, timeout=30)
        except Exception as e:
            logger.warning(f"[WARN] VS sync request failed (attempt {attempt}/{retries}): {e}")
            time.sleep(wait_s)
            continue

        if resp.ok:
            logger.info(f"[OK] VS index sync triggered: {VS_INDEX_NAME}")
            return

        # "not ready yet" → endpoint status API returned ONLINE too early; keep waiting
        if resp.status_code == 400 and "not ready yet" in resp.text:
            logger.info(f"  Endpoint not fully ready (attempt {attempt}/{retries}) — retrying in {wait_s}s …")
            time.sleep(wait_s)
            continue

        # Any other error is permanent — log and give up
        logger.warning(f"[WARN] VS sync returned HTTP {resp.status_code}: {resp.text[:300]}")
        return

    logger.warning(f"[WARN] VS sync failed after {retries} attempts — endpoint never became fully ready")


def _fire_and_forget_endpoint_wake():
    """Send a single non-blocking GET to the VS endpoint to trigger its wake-up.
    The endpoint starts warming immediately; chunking gives it plenty of time.
    """
    import threading, requests
    def _ping():
        try:
            ws_url, token = _get_dbr_auth()
            url = f"{ws_url}/api/2.0/vector-search/endpoints/{VS_ENDPOINT_NAME}"
            requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
            logger.info(f"  [VS wake-up ping sent to '{VS_ENDPOINT_NAME}']")
        except Exception:
            pass  # best-effort, ignore all errors
    threading.Thread(target=_ping, daemon=True).start()


# ── Retrieval smoke-test ────────────────────────────────────────────────────

TEST_QUERIES = [
    "borescope inspection findings",
    "turbine blade damage or cracking",
    "combustion system maintenance",
    "bearing failure root cause",
    "IGV bushing migration",
]

def _test_retrieval(num_results: int = 5):
    """Compare hybrid vs dense-only retrieval using explicit LiteLLM query vectors."""
    import requests as _req
    ws_url, token = _get_dbr_auth()
    url = f"{ws_url}/api/2.0/vector-search/indexes/{VS_INDEX_NAME}/query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    columns = ["chunk_id", "pdf_name", "page_number", "chunk_text"]

    for mode in ("HYBRID", "ANN"):
        label = "HYBRID (vector + keyword)" if mode == "HYBRID" else "DENSE ONLY (vector)"
        logger.info(f"\n  ── {label} ──")

        all_scores  = []
        all_doc_ids = set()

        for q in TEST_QUERIES:
            query_vector = get_query_vector(q)
            body = {
                "query_text": q,
                "query_vector": query_vector,
                "columns": columns,
                "num_results": num_results,
                "query_type": mode,
            }

            try:
                resp = _req.post(url, headers=headers, json=body, timeout=30)
                if not resp.ok:
                    logger.warning(f"    [{mode}] HTTP {resp.status_code}: {resp.text[:200]}")
                    continue
                data      = resp.json()
                col_names = [c["name"] for c in data.get("manifest", {}).get("columns", [])]
                rows      = data.get("result", {}).get("data_array", [])

                score_idx = col_names.index("score") if "score" in col_names else -1
                text_idx  = col_names.index("chunk_text") if "chunk_text" in col_names else -1
                pdf_idx   = col_names.index("pdf_name") if "pdf_name" in col_names else -1
                page_idx  = col_names.index("page_number") if "page_number" in col_names else -1

                top = rows[0] if rows else None
                if top and score_idx >= 0:
                    score   = float(top[score_idx])
                    pdf     = top[pdf_idx] if pdf_idx >= 0 else "?"
                    page    = top[page_idx] if page_idx >= 0 else "?"
                    snippet = (str(top[text_idx])[:100] + "…") if text_idx >= 0 else "?"
                    logger.info(f"    Q: \"{q}\"")
                    logger.info(f"      #1 score={score:.4f}  pdf={pdf}  page={page}")
                    logger.info(f"         {snippet}")

                for row in rows:
                    s = float(row[score_idx]) if score_idx >= 0 else 0
                    all_scores.append(s)
                    if pdf_idx >= 0:
                        all_doc_ids.add(row[pdf_idx])

            except Exception as e:
                logger.warning(f"    [{mode}] Query failed: {e}")

        if all_scores:
            logger.info(f"\n  [{mode}] Summary")
            logger.info(f"    Queries         : {len(TEST_QUERIES)}")
            logger.info(f"    Total results   : {len(all_scores)}")
            logger.info(f"    Unique docs hit : {len(all_doc_ids)}")
            logger.info(f"    Score range     : {min(all_scores):.4f} – {max(all_scores):.4f}")
            logger.info(f"    Avg score       : {sum(all_scores)/len(all_scores):.4f}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main(
    force_reset: bool = False,
    max_pdfs: int = None,
    doc_source_table: str | None = None,
    replace_existing_docs: bool = False,
) -> bool:

    spark = _get_spark()
    t0    = time.time()

    # ── Set SSL cert bundle FIRST before any HTTP calls are made ────────────
    bundle = _build_ca_bundle()
    if bundle:
        os.environ["REQUESTS_CA_BUNDLE"] = bundle
        os.environ["SSL_CERT_FILE"]      = bundle
        os.environ["CURL_CA_BUNDLE"]     = bundle
        logger.info(f"[OK] SSL cert bundle set: {bundle}")

    # Wake the VS endpoint early so it's ONLINE by the time chunking finishes
    _fire_and_forget_endpoint_wake()

    logger.info("=" * 90)
    logger.info("FSR HYBRID RETRIEVAL PIPELINE – DATABRICKS DEV")
    logger.info("=" * 90)
    logger.info(f"Mode:  {'FORCE RESET' if force_reset else 'CACHE-FIRST'}")
    if doc_source_table:
        logger.info(f"Doc source table: {doc_source_table}")
        logger.info(f"Replace targeted docs: {replace_existing_docs}")
    if max_pdfs:
        logger.info(f"Limit: first {max_pdfs} PDFs only (max_pdfs override)")
    logger.info(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # ── Optional force-reset: truncate Delta tables ─────────────────────────
    if force_reset:
        try:
            if _table_exists(spark, EMBEDDINGS_TABLE):
                spark.sql(f"TRUNCATE TABLE {EMBEDDINGS_TABLE}")
                logger.info(f"[OK] Truncated {EMBEDDINGS_TABLE}")
        except Exception as e:
            logger.warning(f"Could not truncate {EMBEDDINGS_TABLE}: {e}")

    # ── STEP 0: Locate PDFs in Volume ────────────────────────────────────────
    logger.info("\n" + "=" * 90)
    logger.info("STEP 0: LOCATE PDF VOLUME")
    logger.info("=" * 90)
    t_step = time.time()

    all_pdf_files, active_volumes, duplicate_doc_ids = collect_pdfs_from_volumes(PDF_VOLUME_PATHS)
    if not all_pdf_files:
        raise RuntimeError(
            "No PDFs found in any configured Volume path.\n"
            f"  Checked: {PDF_VOLUME_PATHS}\n"
            "  Ensure you have READ access to at least one of these volumes."
        )

    logger.info(f"Active volumes : {len(active_volumes)}")
    logger.info(f"Unique PDFs    : {len(all_pdf_files)}")
    if duplicate_doc_ids:
        logger.warning(f"Duplicate stems skipped across volumes: {len(duplicate_doc_ids)}")

    logger.info(f"Step 0 done in {_fmt(time.time() - t_step)}\n")

    # ── STEP 1: Chunk PDFs → Delta (no local embedding) ─────────────────────
    #  Retrieval against the self-managed VS index supplies explicit query
    #  vectors via LiteLLM rather than relying on Databricks-managed embeddings.
    logger.info("=" * 90)
    logger.info("STEP 1: CHUNK PDFs → Delta  (10 threads, background doc-level LLM + chunking)")
    logger.info("=" * 90)
    t_step = time.time()

    try:
        target_doc_ids: set[str] = set()
        if doc_source_table:
            target_doc_ids = _target_doc_ids_from_table(doc_source_table)
            logger.info(f"  Target docs from source table : {len(target_doc_ids)}")
            all_pdf_files = [p for p in all_pdf_files if p.stem in target_doc_ids]
            missing_in_volumes = sorted(target_doc_ids - {p.stem for p in all_pdf_files})
            logger.info(f"  Matching PDFs in volumes      : {len(all_pdf_files)}")
            if missing_in_volumes:
                logger.warning(
                    f"  Target docs missing from configured volumes: {len(missing_in_volumes)}"
                )

        if max_pdfs:
            all_pdf_files = all_pdf_files[:max_pdfs]

        targeted_doc_ids = {p.stem for p in all_pdf_files}
        if doc_source_table and replace_existing_docs and targeted_doc_ids:
            deleted_rows = delete_chunk_rows_for_doc_ids(targeted_doc_ids)
            logger.info(f"  Existing rows deleted : {deleted_rows}")

        existing_doc_ids = chunk_table_doc_ids()
        pdfs_to_do = [p for p in all_pdf_files if p.stem not in existing_doc_ids]

        logger.info(
            f"  Volume PDFs : {len(all_pdf_files)} (capped to {max_pdfs})" if max_pdfs
            else f"  Volume PDFs : {len(all_pdf_files)}"
        )
        logger.info(f"  Already in Delta : {len(existing_doc_ids)}")
        logger.info(f"  To process       : {len(pdfs_to_do)}")

        if not pdfs_to_do:
            logger.info("  All PDFs already in Delta — skipping Step 1.")
        else:
            logger.info("  Loading FSR ref view for in-process ESN enrichment…")
            ref_lookup = load_ref_view_lookup()
            logger.info(f"  PDF workers      : {PDF_PROCESS_WORKERS} process(es) on driver")

            _progress_lock = threading.Lock()
            _fatal = threading.Event()
            _counters = {"completed": 0}
            _writer_error = {"exc": None}
            write_queue: queue.Queue = queue.Queue(maxsize=WRITE_QUEUE_MAX_PDFS)
            total = len(pdfs_to_do)

            def _log_progress(
                *,
                chunk_elapsed: float = 0.0,
                esn_elapsed: float = 0.0,
                write_elapsed: float = 0.0,
                total_elapsed: float = 0.0,
                status: str = "saved",
                level: str = "info",
                doc_id: str = "",
                error: str = "",
            ):
                with _progress_lock:
                    _counters["completed"] += 1
                    prefix = f"[{_counters['completed']}/{total}]"

                parts = [prefix]
                if doc_id and level != "info":
                    parts.append(doc_id)
                parts.append(f"chunk={_fmt(chunk_elapsed)}")
                parts.append(f"esn={_fmt(esn_elapsed)}")
                parts.append(f"write={_fmt(write_elapsed)}")
                if status:
                    parts.append(status)
                parts.append(f"total={_fmt(total_elapsed)}")
                if error:
                    parts.append(error)

                message = "  ".join(parts)
                if level == "error":
                    logger.error(message)
                elif level == "warning":
                    logger.warning(message)
                else:
                    logger.info(message)

            def _enqueue_write_item(item: dict) -> bool:
                while True:
                    if _fatal.is_set() or _writer_error["exc"] is not None:
                        return False
                    try:
                        write_queue.put(item, timeout=0.5)
                        return True
                    except queue.Full:
                        continue

            def _writer_loop():
                while True:
                    item = write_queue.get()
                    if item is WRITE_SENTINEL:
                        break

                    batch = [item]
                    stop_after_batch = False
                    while len(batch) < WRITE_BATCH_MAX_PDFS:
                        try:
                            queued_item = write_queue.get_nowait()
                        except queue.Empty:
                            break

                        if queued_item is WRITE_SENTINEL:
                            stop_after_batch = True
                            break

                        batch.append(queued_item)

                    batch_done = time.time()
                    try:
                        batch_rows = []
                        for queued_item in batch:
                            batch_rows.extend(queued_item["rows"])

                        if batch_rows:
                            save_rows_to_delta(batch_rows)
                        batch_done = time.time()

                        for queued_item in batch:
                            _log_progress(
                                chunk_elapsed=queued_item["chunk_elapsed"],
                                esn_elapsed=queued_item["esn_elapsed"],
                                write_elapsed=batch_done - queued_item["ready_for_write_at"],
                                total_elapsed=batch_done - queued_item["started_at"],
                                status="saved" if batch_rows else "skipped=empty_rows",
                            )
                    except Exception as exc:
                        _writer_error["exc"] = exc
                        _fatal.set()
                        batch_done = time.time()
                        for queued_item in batch:
                            _log_progress(
                                chunk_elapsed=queued_item["chunk_elapsed"],
                                esn_elapsed=queued_item["esn_elapsed"],
                                write_elapsed=batch_done - queued_item["ready_for_write_at"],
                                total_elapsed=batch_done - queued_item["started_at"],
                                status="failed",
                                level="error",
                                doc_id=queued_item["doc_id"],
                                error=str(exc),
                            )
                        break

                    if stop_after_batch:
                        break

            writer_thread = threading.Thread(
                target=_writer_loop,
                name="delta-writer",
                daemon=True,
            )
            writer_thread.start()

            pool = ProcessPoolExecutor(
                max_workers=PDF_PROCESS_WORKERS,
                initializer=_process_worker_init,
                initargs=(ref_lookup,),
            )
            try:
                futures = {
                    pool.submit(_process_one_pdf_job, str(pdf_path)): pdf_path.stem
                    for pdf_path in pdfs_to_do
                }
                for fut in as_completed(futures):
                    result = fut.result()
                    doc_id = result.get("doc_id", futures[fut])
                    chunk_elapsed = float(result.get("chunk_elapsed", 0.0) or 0.0)
                    esn_elapsed = float(result.get("esn_elapsed", 0.0) or 0.0)
                    total_elapsed = time.time() - float(result.get("started_at", time.time()))
                    status = result.get("status", "failed")

                    if status != "ready":
                        _log_progress(
                            chunk_elapsed=chunk_elapsed,
                            esn_elapsed=esn_elapsed,
                            total_elapsed=total_elapsed,
                            status=status,
                            level="error" if status == "failed" else "info",
                            doc_id=doc_id,
                            error=result.get("error", ""),
                        )
                        if result.get("fatal"):
                            _fatal.set()
                            raise RuntimeError(result.get("error", f"Fatal error for {doc_id}"))
                        continue

                    ready_for_write_at = time.time()
                    enqueued = _enqueue_write_item({
                        "doc_id": doc_id,
                        "rows": result["rows"],
                        "chunk_elapsed": chunk_elapsed,
                        "esn_elapsed": esn_elapsed,
                        "started_at": float(result["started_at"]),
                        "ready_for_write_at": ready_for_write_at,
                    })
                    if not enqueued and _writer_error["exc"] is not None:
                        raise _writer_error["exc"]
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
                if writer_thread.is_alive():
                    write_queue.put(WRITE_SENTINEL)
                writer_thread.join()

            if _writer_error["exc"] is not None:
                raise _writer_error["exc"]
    except Exception as e:
        logger.error(f"Chunk step failed: {e}")
        raise

    logger.info(f"Step 1 done in {_fmt(time.time() - t_step)}\n")

    # ── STEP 2: Load documents from EMBEDDINGS_TABLE ─────────────────────────
    logger.info("=" * 90)
    logger.info("STEP 2: LOAD DOCUMENTS FROM EMBEDDINGS TABLE")
    logger.info("=" * 90)
    t_step = time.time()

    try:
        documents, doc_stats = load_all_chunks_from_delta()
        logger.info(
            f"Loaded {len(documents):,} chunks  |  "
            f"{doc_stats['unique_sources']} documents  |  "
            f"{doc_stats['total_tokens']:,} tokens"
        )
        inspect_documents(documents, sample_size=3)
    except Exception as e:
        logger.error(f"Failed to load documents: {e}")
        raise

    logger.info(f"Step 2 done in {_fmt(time.time() - t_step)}\n")

    # ── STEP 3: Vector Search index sync ──────────────────────────────────
    #  VS auto-embeds from chunk_text using databricks-gte-large-en on sync.
    #  No local embeddings array needed — skip old Steps 3 & 5.
    logger.info("=" * 90)
    logger.info("STEP 3: VECTOR SEARCH INDEX SYNC")
    logger.info("=" * 90)
    t_step = time.time()

    _sync_vs_index()   # table + index created by _setup_tables.py

    logger.info(f"Step 3 done in {_fmt(time.time() - t_step)}\n")

    # ── STEP 4: Retrieval smoke-test ──────────────────────────────────────────
    logger.info("=" * 90)
    logger.info("STEP 4: RETRIEVAL SMOKE TEST")
    logger.info("=" * 90)
    t_step = time.time()

    _test_retrieval(num_results=5)

    logger.info(f"Step 4 done in {_fmt(time.time() - t_step)}\n")

    # ── Done ─────────────────────────────────────────────────────────────────
    logger.info("=" * 90)
    logger.info(f"PIPELINE COMPLETE  |  Total: {_fmt(time.time() - t0)}")
    logger.info("=" * 90)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
