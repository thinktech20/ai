"""Stage 5 — Chunking & Embedding.

Reads docs with chunk_status=pending/failed from fsr_metadata_v2, splits text
into chunks, generates embeddings, and writes to fsr_chunks_v2.

Behavior differences from v1 P2:
    v1:
        - chunked with the older hierarchical flow
        - fanned out one chunk row per ESN regardless of where that ESN appeared
        - assigned doc-level equipment metadata to every chunk
    v2:
        - loads persisted parsed artifacts from P1 when available (parse-once path)
        - falls back to PyMuPDF extraction when parsed artifacts are unavailable
        - splits text region-first and carries owning-region metadata into each chunk
        - writes one chunk row per chunk with per-chunk ESN / equip_type metadata

Why this is not just a metadata_json change:
    preprocessor_regions stores char-offset boundaries from the P1 text representation.
    If P2 chunking uses a different extraction/chunking representation, chunk-to-region
    attribution becomes unreliable, especially near section/equipment boundaries.
    See the FSR v2 design doc for an example.

Knobs:
    Chunking is fixed to region-first recursive splitting. P1 regions define
        attribution boundaries; recursive splitting only controls size within a region.

Reuses from existing P2:
    - Embedding via LiteLLM (ThreadPoolExecutor, P2_EMBED_CONCURRENCY)
    - Batch claim / status update / MERGE pattern from nb_sdg_fsr_chunks.py

Input:  fsr_metadata_v2 (metadata_status=completed, chunk_status=pending/failed)
Output: fsr_chunks_v2 (one chunk row per chunk, ESN attributed by region)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

# ── common/fsr_v2 imports ────────────────────────────────────────────────────
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../"))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from common.fsr_v2.enums import MergeStrategy, RegionAttributionMethod, CHUNK_METADATA_JSON_CONTRACT_VERSION  # noqa: E402
from common.fsr_v2.delta_retry import run_with_retry  # noqa: E402
from common.fsr_v2.mlflow_logger import log_p2_experiment_start, log_p2_experiment_end  # noqa: E402
from fsr_v2.chunk_splitter import chunk_region_metadata, split_region_first_with_offsets  # noqa: E402
from fsr_v2.embedding_client import safe_embed_batch  # noqa: E402
from fsr_v2.text_extraction import char_to_page, load_parsed_for_chunking  # noqa: E402

log = logging.getLogger("fsr.v2.chunking")


def _parse_date(s: str | None) -> _date | None:
    if not s:
        return None
    try:
        return _date.fromisoformat(s)
    except Exception:
        return None


def _norm_esn(value: str | None) -> str:
    return (value or "").strip().upper()


def _build_active_esns(
    *,
    regions: list[dict],
    inactive_esns: list[str],
    doc_primary_esn: str | None,
    doc_gt_esn: str | None,
    doc_gen_esn: str | None,
    doc_st_esn: str | None = None,
) -> list[str]:
    """Build a sorted list of normalized active ESNs for this document.

    Stored as ARRAY<STRING> in fsr_chunks_v2 for native VS array-contains filtering.
    """
    inactive = {_norm_esn(v) for v in (inactive_esns or []) if _norm_esn(v)}
    esns: set[str] = set()

    for region in regions or []:
        region_meta = region.get("metadata") or {}
        esn = _norm_esn(region_meta.get("primary_esn"))
        if esn:
            esns.add(esn)

    for esn in [doc_primary_esn, doc_gt_esn, doc_gen_esn, doc_st_esn]:
        norm = _norm_esn(esn)
        if norm:
            esns.add(norm)

    return sorted(e for e in esns if e not in inactive)


# ── Main entry point ─────────────────────────────────────────────────────────

def run(
    spark: "SparkSession",
    metadata_table: str,
    chunk_table: str,
    *,
    llm_base_url: str,
    llm_api_key: str,
    embedding_model: str,
    llm_verify_ssl: Any = True,
    chunk_size: int = 2000,
    chunk_overlap: int = 150,
    min_chunk_size: int = 450,
    batch_size: int = 50,
    max_retries: int = 3,
    max_iterations: int = 0,
    embed_batch_size: int = 32,
    embed_concurrency: int = 8,
    embed_fail_threshold: float = 0.0,
    stale_claim_minutes: int = 30,
    upload_meta: dict | None = None,
    merge_strategy: str = MergeStrategy.V2_4LEVEL_CASCADE.value,
    region_attribution_method: str = RegionAttributionMethod.CHAR_OFFSET_MAX_OVERLAP.value,
    pipeline_version: str = "fsr_v2.0",
    run_id: str | None = None,
    expected_embed_dimension: int = 0,
    repair_scope_table: str | None = None,
    repair_run_id: str | None = None,
    document_ids: list[str] | None = None,
) -> dict:
    """Batch-claim docs and write chunks to fsr_chunks_v2.

    Args:
        spark: active SparkSession
        metadata_table: fsr_metadata_v2 (source of doc metadata + preprocessor_regions)
        chunk_table: fsr_chunks_v2 (target for chunk rows)
        llm_base_url / llm_api_key / embedding_model / llm_verify_ssl: LiteLLM config
        chunk_size / chunk_overlap / min_chunk_size: chunking size controls
        batch_size: docs per claim batch
        max_retries: max chunk_retry_count before a doc is skipped
        max_iterations: 0 = drain queue; >0 = stop after N batches (testing)
        repair_scope_table / repair_run_id: optional scope-table filter for a
            controlled repair run; normal ingestion leaves these unset.
        embed_batch_size: inputs per embedding API call
        embed_fail_threshold: fraction of missing embeddings before failing a doc
        stale_claim_minutes: reclaim in_progress docs older than this
        upload_meta: optional upload-level metadata dict (doc_type, priority, file_path, ...)
            Applied as baseline; doc-level, section, and region metadata override it.
        document_ids: optional explicit scope — when set, the claim query is
            additionally restricted to these document_ids (e.g. for a caller that
            must only ever touch documents from one Volume). None (default)
            preserves today's unscoped queue-drain behavior.

    Merge Priority (per chunk):
        upload_meta (lowest) < doc-level < section < region (highest, overwrites all)

    Steps:
        1. Claim a batch of docs (chunk_status=pending/failed) from metadata_table
          2. For each doc: load ParsedDocument from parsed_volume_path when present,
              else parse the source volume with PyMuPDF for fallback
          3. Split text region-first using preprocessor_regions and recursive sub-chunking
          4. Embed all chunks in parallel (ThreadPoolExecutor, LiteLLM)
          5. Assemble chunk rows with region-scoped ESN / equip_type metadata
          6. MERGE INTO chunk_table ON chunk_id
          7. Update chunk_status in metadata_table (completed / failed)

    Returns:
        dict with iteration/succeeded/failed/chunks_written counts

        Note:
                The backfill orchestrator may reuse parts of this module's chunk assembly
                and embedding flow, but region attribution in this path is inherited directly
                from the owning preprocessor region emitted by split_region_first_with_offsets.
    """
    from pyspark.sql.types import (  # noqa: PLC0415
        ArrayType, DateType, DoubleType, IntegerType,
        StringType, StructField, StructType, TimestampType,
    )

    if merge_strategy not in {
        MergeStrategy.V2_4LEVEL_CASCADE.value,
        MergeStrategy.V2_DOC_SECTION_ONLY.value,
    }:
        raise ValueError(
            f"Unsupported merge_strategy={merge_strategy!r}; expected "
            f"'{MergeStrategy.V2_4LEVEL_CASCADE.value}' or "
            f"'{MergeStrategy.V2_DOC_SECTION_ONLY.value}'"
        )
    if region_attribution_method not in {
        RegionAttributionMethod.CHAR_OFFSET_MAX_OVERLAP.value,
        RegionAttributionMethod.CHAR_OFFSET_START_CHAR.value,
    }:
        raise ValueError(
            f"Unsupported region_attribution_method={region_attribution_method!r}; "
            "expected 'char_offset_max_overlap' or 'char_offset_start_char'"
        )
    if document_ids is not None and not document_ids:
        log.info("document_ids scope provided but empty — nothing to claim.")
        return {"iterations": 0, "succeeded": 0, "failed": 0, "chunks_written": 0}

    # Initialize upload_meta baseline (lowest priority in merge cascade)
    if upload_meta is None:
        upload_meta = {}

    # ── Recover stale in_progress claims ─────────────────────────────────────
    # Scoped to document_ids when provided — otherwise a scoped caller would
    # still reclaim (and inflate the retry count of) stale claims belonging to
    # documents entirely outside its own scope.
    _stale_scope_sql = ""
    if document_ids is not None:
        _stale_scope_ids_sql = ", ".join("'" + did.replace("'", "''") + "'" for did in document_ids)
        _stale_scope_sql = f"AND document_id IN ({_stale_scope_ids_sql})"

    stale_n = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {metadata_table}
        WHERE chunk_status = 'in_progress'
          AND chunked_at < current_timestamp() - INTERVAL {stale_claim_minutes} MINUTES
          {_stale_scope_sql}
    """).first().n
    if stale_n:
        # Counts as an attempt. Without this a document that reliably kills the
        # worker is reclaimed forever: the retry cap only applies to documents
        # that reach an explicit 'failed', which a crashed run never sets.
        run_with_retry(spark, f"""
            UPDATE {metadata_table}
            SET chunk_status = 'pending',
                chunk_retry_count = COALESCE(chunk_retry_count, 0) + 1,
                chunk_error = 'reclaimed after stale in_progress claim'
            WHERE chunk_status = 'in_progress'
              AND chunked_at < current_timestamp() - INTERVAL {stale_claim_minutes} MINUTES
              {_stale_scope_sql}
        """, "stale-claim recovery")
        log.info(f"Recovered {stale_n} stale in_progress claims (>{stale_claim_minutes} min)")

    chunk_schema = StructType([
        StructField("chunk_id",                StringType(),             False),
        StructField("chunk_index",             IntegerType(),            True),
        StructField("document_id",             StringType(),             False),
        StructField("pdf_name",                StringType(),             True),
        StructField("page_number",             IntegerType(),            True),
        StructField("chunk_text",              StringType(),             False),
        StructField("region_primary_esn",      StringType(),             True),
        StructField("region_primary_equip_type", StringType(),           True),
        StructField("active_esns",              ArrayType(StringType()),   True),
        StructField("report_date",             DateType(),               True),
        StructField("outage_start_date",        DateType(),               True),
        StructField("chunk_embedding",         ArrayType(DoubleType()),  True),
        StructField("chunk_strategy",          StringType(),             True),
        StructField("embedding_model",         StringType(),             True),
        StructField("merge_strategy",          StringType(),             True),
        StructField("region_attribution_method", StringType(),           True),
        StructField("embedding_dimension",     IntegerType(),            True),
        StructField("pipeline_version",        StringType(),             True),
        StructField("run_id",                  StringType(),             True),
        StructField("metadata",                StringType(),             True),
        StructField("created_at",              TimestampType(),          True),
    ])

    # ── MLflow experiment logging start ────────────────────────────────────────
    mlflow_context = log_p2_experiment_start(
        chunking_strategy="region_first:recursive",
        embedding_model=embedding_model,
        merge_strategy=merge_strategy,
        region_attribution_method=region_attribution_method,
        pipeline_version=pipeline_version,
        run_id=run_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    total_succeeded = total_failed = total_chunks = iteration = 0
    embedding_dimension = 0
    total_embed_failures = 0

    while True:
        if max_iterations > 0 and iteration >= max_iterations:
            log.info(f"Reached max_iterations={max_iterations}; stopping.")
            break

        iteration += 1
        log.info(f"=== Batch {iteration} ===")
        batch_start = datetime.now(timezone.utc)

        # Per batch, not per run: a set that outlives the batch keeps re-failing
        # docs it no longer owns, and blocks them from ever succeeding on retry.
        embed_failures: set[str] = set()

        # ── 1. Claim ──────────────────────────────────────────────────────────
        scope_filter = ""
        if repair_scope_table and repair_run_id:
            safe_scope_run_id = repair_run_id.replace("'", "''")
            run_with_retry(spark, f"""
                UPDATE {repair_scope_table}
                SET p2_status = 'failed',
                    error_message = 'stale P2 claim recovered; retry is allowed'
                WHERE run_id = '{safe_scope_run_id}'
                  AND p2_status = 'in_progress'
                  AND started_at < current_timestamp() - INTERVAL {stale_claim_minutes} MINUTES
            """, f"recover stale repair P2 claims {iteration}")
            candidate_rows = spark.sql(f"""
                SELECT m.document_id
                FROM {metadata_table} m
                WHERE m.metadata_status = 'completed'
                  AND m.chunk_status IN ('pending', 'failed')
                  AND COALESCE(m.chunk_retry_count, 0) < {max_retries}
                  AND EXISTS (
                      SELECT 1 FROM {repair_scope_table} s
                      WHERE s.run_id = '{safe_scope_run_id}'
                        AND s.document_id = m.document_id
                        AND s.resolution_status = 'resolved'
                        AND s.p1_status = 'completed'
                        AND s.p2_status IN ('pending', 'failed')
                  )
                LIMIT {batch_size}
            """).collect()
            if candidate_rows:
                candidate_ids_sql = ", ".join(
                    "'" + row.document_id.replace("'", "''") + "'" for row in candidate_rows
                )
                run_with_retry(spark, f"""
                    UPDATE {repair_scope_table}
                    SET p2_status = 'in_progress',
                        p2_run_id = '{(run_id or '').replace("'", "''")}',
                        started_at = current_timestamp(),
                        error_message = NULL
                    WHERE run_id = '{safe_scope_run_id}'
                      AND document_id IN ({candidate_ids_sql})
                      AND resolution_status = 'resolved'
                      AND p1_status = 'completed'
                      AND p2_status IN ('pending', 'failed')
                """, f"claim repair scope batch {iteration}")
            scope_filter = f"""
              AND EXISTS (
                  SELECT 1 FROM {repair_scope_table} s
                  WHERE s.run_id = '{safe_scope_run_id}'
                    AND s.document_id = m.document_id
                    AND s.resolution_status = 'resolved'
                    AND s.p1_status = 'completed'
                    AND s.p2_status = 'in_progress'
                    AND s.p2_run_id = '{(run_id or '').replace("'", "''")}'
              )
            """
        if document_ids is not None:
            _scope_ids_sql = ", ".join("'" + did.replace("'", "''") + "'" for did in document_ids)
            scope_filter += f"AND m.document_id IN ({_scope_ids_sql})"

        claimed_rows = spark.sql(f"""
            SELECT m.document_id FROM {metadata_table} m
            WHERE m.metadata_status = 'completed'
              AND m.chunk_status IN ('pending', 'failed')
              AND COALESCE(m.chunk_retry_count, 0) < {max_retries}
              {scope_filter}
            LIMIT {batch_size}
        """).collect()

        if not claimed_rows:
            log.info("Queue drained — no more docs to process.")
            break

        claimed_ids = [r.document_id for r in claimed_rows]
        # Concatenation, not a nested-quote f-string: Databricks serverless is
        # Python 3.10 and PEP 701 nested same-type quotes fail to parse there.
        _ids_sql = ", ".join("'" + did.replace("'", "''") + "'" for did in claimed_ids)

        run_with_retry(spark, f"""
            UPDATE {metadata_table}
            SET chunk_status = 'in_progress',
                chunked_at = current_timestamp()
            WHERE document_id IN ({_ids_sql})
              AND chunk_status IN ('pending', 'failed')
        """, f"claim batch {iteration}")

        # ── Read full metadata — only docs we actually claimed ─────────────────
        pending_docs = spark.sql(f"""
            SELECT document_id, pdf_name, volume_path, title, customer,
                   primary_esn, primary_equip_type, gt_esn, gen_esn, st_esn,
                   event_type, ev_project_id, ev_equipment_event_id,
                   ofs_event_id, fsp_project_id, xxx_project_id, fsr_number,
                   report_issued_date, outage_start_date, outage_end_date,
                   outage_type, technology_type, prepared_by, approved_by,
                   preprocessor_regions, inactive_esns, parsed_volume_path
            FROM {metadata_table}
            WHERE document_id IN ({_ids_sql})
              AND chunk_status = 'in_progress'
        """).collect()

        log.info(f"Claimed {len(pending_docs)} docs")
        log.info("Chunking strategy: region_first:recursive")

        # ── 2-4. PDF extraction + chunking + attribution ──────────────────────
        doc_chunks: dict[str, list[dict]] = {}
        doc_errors: dict[str, str] = {}

        for row in pending_docs:
            doc_id = row.document_id
            try:
                parsed_doc = load_parsed_for_chunking(row.volume_path, parsed_volume_path=getattr(row, "parsed_volume_path", None))
                pages = parsed_doc.pages
                page_offsets = parsed_doc.page_offsets
                full_text = parsed_doc.full_text

                # Deserialize preprocessor_regions (stored as JSON string)
                regions = json.loads(row.preprocessor_regions) if row.preprocessor_regions else []

                split_chunks = split_region_first_with_offsets(
                    full_text,
                    regions,
                    chunk_size,
                    chunk_overlap,
                    min_chunk_size,
                    volume_path=row.volume_path,
                )
                if not split_chunks:
                    doc_errors[doc_id] = "Chunker produced 0 chunks"
                    log.warning(f"  [SKIP] {doc_id[:50]}: 0 chunks produced")
                    continue

                mapping_miss_indices: set[int] = set()

                chunks = []
                for ci, chunk in enumerate(split_chunks):
                    chunk_text = chunk["chunk_text"]
                    start_char = chunk["start_char"]
                    end_char = chunk["end_char"]
                    region_meta = dict(chunk.get("region_metadata") or {})

                    page_num = char_to_page(start_char, page_offsets)
                    section_meta = chunk.get("section_metadata") or {}
                    chunks.append({
                        "chunk_index":        ci,
                        "chunk_text":         chunk_text,
                        "chunk_start_char":   start_char,
                        "page_number":        page_num,
                        "region_primary_esn":        region_meta.get("primary_esn", ""),
                        "region_primary_equip_type": region_meta.get("primary_equip_type", ""),
                        "region_metadata":    region_meta,
                        "section":            section_meta or {},
                    })

                doc_chunks[doc_id] = chunks
                log.info(f"  [OK] {doc_id[:50]}  chunks={len(chunks)}"
                         f"  avg_size={sum(len(c['chunk_text']) for c in chunks) // max(len(chunks), 1)}")

            except Exception as e:
                doc_errors[doc_id] = str(e)[:500]
                log.warning(f"  [FAIL] {doc_id[:50]}: {e}")

        log.info(f"Chunked {len(doc_chunks)} docs, "
                 f"total chunks: {sum(len(c) for c in doc_chunks.values())}, "
                 f"failed: {len(doc_errors)}")

        # ── 6. Embed ──────────────────────────────────────────────────────────
        all_refs:  list[tuple[str, int]] = []
        all_texts: list[str] = []
        for doc_id, chunks in doc_chunks.items():
            for ch in chunks:
                all_refs.append((doc_id, ch["chunk_index"]))
                all_texts.append(ch["chunk_text"])

        log.info(f"Embedding {len(all_texts)} chunks "
                 f"(batch={embed_batch_size}, concurrency={embed_concurrency})...")

        all_embeddings: dict[tuple, list[float]] = {}
        t0 = time.time()

        batches = [
            (i // embed_batch_size,
             all_texts[i:i + embed_batch_size],
             all_refs[i:i + embed_batch_size])
            for i in range(0, len(all_texts), embed_batch_size)
        ]

        with ThreadPoolExecutor(max_workers=embed_concurrency) as pool:
            futures = {
                pool.submit(
                    safe_embed_batch, bidx, texts, refs,
                    llm_base_url, llm_api_key, embedding_model,
                    llm_verify_ssl, 3,
                ): bidx
                for bidx, texts, refs in batches
            }
            for future in as_completed(futures):
                try:
                    for ref, vec in future.result():
                        if vec is not None:
                            all_embeddings[ref] = vec
                        else:
                            embed_failures.add(ref[0])
                except Exception as _exc:
                    _bidx = futures[future]
                    for ref in batches[_bidx][2]:
                        embed_failures.add(ref[0])
                    log.warning("Embedding batch %d raised: %s", _bidx, _exc)

        # ── Dimension tracking ─────────────────────────────────────────────────────
        embedding_dimension = 0
        if all_embeddings:
            first_vec = next(iter(all_embeddings.values()), None)
            if first_vec:
                embedding_dimension = len(first_vec)
                log.info(f"Embedding dimension: {embedding_dimension} ({embedding_model})")

        if expected_embed_dimension > 0 and embedding_dimension > 0 and embedding_dimension != expected_embed_dimension:
            _dim_err = f"Embedding dimension mismatch: got {embedding_dimension}, expected {expected_embed_dimension}"
            log.error(_dim_err)
            for _did in list(doc_chunks):
                doc_errors[_did] = _dim_err
            doc_chunks.clear()
            embed_failures.clear()

        log.info(f"Embedded {len(all_embeddings)} chunks in {time.time() - t0:.1f}s"
                 f" (dimension={embedding_dimension})")

        # Per-doc coverage check
        partial_coverage: dict[str, tuple[int, int]] = {}
        for doc_id, chunks in doc_chunks.items():
            total_c = len(chunks)
            embedded_c = sum(1 for c in chunks if (doc_id, c["chunk_index"]) in all_embeddings)
            missing_pct = 1.0 - (embedded_c / total_c) if total_c else 0.0
            if missing_pct > embed_fail_threshold:
                embed_failures.add(doc_id)
                doc_errors[doc_id] = (
                    f"Embedding coverage too low: {embedded_c}/{total_c} chunks "
                    f"({missing_pct:.0%} missing)"
                )
            elif embedded_c < total_c:
                partial_coverage[doc_id] = (embedded_c, total_c)

        # A doc under the threshold but not fully embedded would otherwise be written
        # as a partial chunk set, marked 'completed', and — because the MERGE below
        # deletes chunks not present in this write — destroy the complete set from a
        # previous run. Nothing downstream can tell a partial doc from a whole one.
        if partial_coverage:
            for doc_id, (embedded_c, total_c) in partial_coverage.items():
                embed_failures.add(doc_id)
                doc_errors[doc_id] = (
                    f"Incomplete embedding coverage: {embedded_c}/{total_c} chunks. "
                    f"Under embed_fail_threshold={embed_fail_threshold} but a partial "
                    f"chunk set is not a valid 'completed' document."
                )
            log.warning(
                "%d doc(s) had partial embedding coverage within threshold and were failed "
                "rather than written partially", len(partial_coverage),
            )

        all_failed = set(doc_errors) | embed_failures
        success_ids = [did for did in doc_chunks if did not in all_failed]

        # ── 7-8. Assemble rows + MERGE ────────────────────────────────────────
        doc_meta = {row.document_id: row for row in pending_docs}
        chunk_rows = []
        now = datetime.now(timezone.utc)

        for doc_id in success_ids:
            meta = doc_meta[doc_id]
            regions = json.loads(meta.preprocessor_regions) if meta.preprocessor_regions else []
            inactive = []
            if meta.inactive_esns:
                try:
                    inactive = json.loads(meta.inactive_esns)
                except Exception:
                    inactive = [e.strip() for e in meta.inactive_esns.split(",") if e.strip()]
            active_esns = _build_active_esns(
                regions=regions,
                inactive_esns=inactive,
                doc_primary_esn=meta.primary_esn,
                doc_gt_esn=getattr(meta, "gt_esn", None),
                doc_gen_esn=getattr(meta, "gen_esn", None),
                doc_st_esn=getattr(meta, "st_esn", None),
            )

            for ch in doc_chunks[doc_id]:
                ci = ch["chunk_index"]
                embedding = all_embeddings.get((doc_id, ci))
                if embedding is None:
                    continue

                chunk_id = hashlib.md5(f"{doc_id}_{ci}".encode()).hexdigest()

                # Assemble metadata JSON with full merge cascade:
                # Start with upload_meta baseline, then doc-level, then region-attributed values.
                base_metadata = dict(upload_meta)
                doc_level_meta = {
                    "title":                meta.title or "",
                    "customer":             meta.customer or "",
                    "event_type":           meta.event_type or "",
                    "ev_project_id":        meta.ev_project_id or "",
                    "ev_equipment_event_id": meta.ev_equipment_event_id or "",
                    "ofs_event_id":         meta.ofs_event_id or "",
                    "fsp_project_id":       meta.fsp_project_id or "",
                    "xxx_project_id":       meta.xxx_project_id or "",
                    "fsr_number":           meta.fsr_number or "",
                    "report_issued_date":   meta.report_issued_date or "",
                    "outage_start_date":    meta.outage_start_date or "",
                    "outage_end_date":      meta.outage_end_date or "",
                    "outage_type":          meta.outage_type or "",
                    "technology_type":      meta.technology_type or "",
                    "inactive_esns":        inactive,
                }
                chunk_context = {
                    # Helpful for debugging attribution boundaries; not a top-level chunk column.
                    "chunk_start_char":     ch.get("chunk_start_char"),
                }
                base_metadata.update({
                    "metadata_contract_version": CHUNK_METADATA_JSON_CONTRACT_VERSION,
                    # Scoped contract fields (no duplication of top-level chunk columns).
                    "doc":     doc_level_meta,
                    # Preserve all P1 provenance, including confidence, source,
                    # section_path, and fallback_chain, for retrieval/audit use.
                    "region": chunk_region_metadata(ch),
                    "section": ch.get("section") or {},
                    "chunk_context": chunk_context,
                })
                metadata_json = json.dumps(base_metadata, default=str)

                # Use actual_strategy if fallback occurred (for data lineage)
                actual_strategy = "region_first:recursive"

                chunk_rows.append({
                    "chunk_id":                chunk_id,
                    "chunk_index":             ci,
                    "document_id":             doc_id,
                    "pdf_name":                meta.pdf_name,
                    "page_number":             ch["page_number"],
                    "chunk_text":              ch["chunk_text"],
                    "region_primary_esn":      ch["region_primary_esn"],
                    "region_primary_equip_type": ch["region_primary_equip_type"],
                    "active_esns":             active_esns,
                    "report_date":             _parse_date(meta.report_issued_date),
                    "outage_start_date":        _parse_date(meta.outage_start_date),
                    "chunk_embedding":         [float(v) for v in embedding],
                    "chunk_strategy":          actual_strategy,
                    "embedding_model":         embedding_model,
                    "merge_strategy":          merge_strategy,
                    "region_attribution_method": region_attribution_method,
                    "embedding_dimension":     embedding_dimension,
                    "pipeline_version":        pipeline_version,
                    "run_id":                  run_id,
                    "metadata":                metadata_json,
                    "created_at":              now,
                })

        log.info(f"Assembled {len(chunk_rows)} chunk rows for {len(success_ids)} docs")

        if chunk_rows:
            chunk_df = spark.createDataFrame(chunk_rows, schema=chunk_schema)
            chunk_df.createOrReplaceTempView("_fsr_v2_new_chunks")
            success_ids_sql = ", ".join("'" + did.replace("'", "''") + "'" for did in success_ids)

            run_with_retry(spark, f"""
                MERGE INTO {chunk_table} AS tgt
                USING _fsr_v2_new_chunks AS src
                ON tgt.chunk_id = src.chunk_id
                WHEN MATCHED THEN UPDATE SET
                    tgt.chunk_index        = src.chunk_index,
                    tgt.document_id        = src.document_id,
                    tgt.pdf_name           = src.pdf_name,
                    tgt.page_number        = src.page_number,
                    tgt.chunk_text         = src.chunk_text,
                    tgt.region_primary_esn = src.region_primary_esn,
                    tgt.region_primary_equip_type = src.region_primary_equip_type,
                    tgt.active_esns        = src.active_esns,
                    tgt.report_date        = src.report_date,
                    tgt.outage_start_date  = src.outage_start_date,
                    tgt.chunk_embedding    = src.chunk_embedding,
                    tgt.chunk_strategy     = src.chunk_strategy,
                    tgt.metadata           = src.metadata,
                    tgt.created_at         = src.created_at
                WHEN NOT MATCHED THEN INSERT *
                WHEN NOT MATCHED BY SOURCE AND tgt.document_id IN ({success_ids_sql}) THEN DELETE
            """, f"chunk merge batch {iteration}")
            log.info(f"MERGE complete: {len(chunk_rows)} rows into {chunk_table}")

        # ── 8. Update chunk_status in metadata_table ──────────────────────────
        # Both writes are guarded on chunk_status='in_progress' so a batch can only
        # resolve claims it still holds — not one a stale-claim recovery reassigned.
        if success_ids:
            ids_sql = ", ".join("'" + did.replace("'", "''") + "'" for did in success_ids)
            run_with_retry(spark, f"""
                UPDATE {metadata_table}
                SET chunk_status       = 'completed',
                    chunk_error        = NULL,
                    chunk_retry_count  = 0,
                    chunked_at         = current_timestamp(),
                    updated_at         = current_timestamp()
                WHERE document_id IN ({ids_sql})
                  AND chunk_status = 'in_progress'
            """, f"mark completed batch {iteration}")
            if repair_scope_table and repair_run_id:
                safe_scope_run_id = repair_run_id.replace("'", "''")
                for _doc_id in success_ids:
                    _new_doc_chunks = doc_chunks.get(_doc_id, [])
                    _after_fingerprint = hashlib.sha256(
                        "|".join(sorted(str(chunk.get("chunk_id") or "") for chunk in _new_doc_chunks)).encode()
                    ).hexdigest()
                    run_with_retry(spark, f"""
                        UPDATE {repair_scope_table}
                        SET p2_status = 'completed',
                            p2_run_id = '{(run_id or '').replace("'", "''")}',
                            after_chunk_count = {len(_new_doc_chunks)},
                            after_fingerprint = '{_after_fingerprint}',
                            completed_at = current_timestamp(),
                            error_message = NULL
                        WHERE run_id = '{safe_scope_run_id}'
                          AND document_id = '{_doc_id.replace("'", "''")}'
                          AND p2_status = 'in_progress'
                          AND p2_run_id = '{(run_id or '').replace("'", "''")}'
                    """, f"mark repair scope P2 complete {_doc_id}")

        # Restricted to this batch's claims: re-marking a doc that failed in an earlier
        # batch would inflate chunk_retry_count once per subsequent batch.
        _claimed_set = set(claimed_ids)
        batch_failed = [did for did in all_failed if did in _claimed_set]
        if batch_failed:
            failed_rows = [
                {"document_id": did,
                 "chunk_error": (doc_errors.get(did, "embed failure") or "")[:200]}
                for did in batch_failed
            ]
            spark.createDataFrame(failed_rows).createOrReplaceTempView("_fsr_v2_failed_docs")
            run_with_retry(spark, f"""
                MERGE INTO {metadata_table} AS tgt
                USING _fsr_v2_failed_docs AS src
                ON tgt.document_id = src.document_id
                WHEN MATCHED AND tgt.chunk_status = 'in_progress' THEN UPDATE SET
                    tgt.chunk_status       = 'failed',
                    tgt.chunk_error        = src.chunk_error,
                    tgt.chunk_retry_count  = COALESCE(tgt.chunk_retry_count, 0) + 1,
                    tgt.chunked_at         = current_timestamp(),
                    tgt.updated_at         = current_timestamp()
            """, f"mark failed batch {iteration}")
            if repair_scope_table and repair_run_id:
                safe_scope_run_id = repair_run_id.replace("'", "''")
                failed_ids_sql = ", ".join("'" + did.replace("'", "''") + "'" for did in batch_failed)
                run_with_retry(spark, f"""
                    UPDATE {repair_scope_table}
                    SET p2_status = 'failed',
                        p2_run_id = '{(run_id or '').replace("'", "''")}',
                        error_message = 'P2 chunking or embedding failed; see metadata chunk_error'
                    WHERE run_id = '{safe_scope_run_id}'
                        AND document_id IN ({failed_ids_sql})
                        AND p2_status = 'in_progress'
                        AND p2_run_id = '{(run_id or '').replace("'", "''")}'
                """, f"mark repair scope P2 failed batch {iteration}")

        elapsed = (datetime.now(timezone.utc) - batch_start).total_seconds()
        log.info(f"Batch {iteration} done: {len(success_ids)} succeeded, "
                 f"{len(batch_failed)} failed, {len(chunk_rows)} chunks, {elapsed:.1f}s")

        total_succeeded += len(success_ids)
        total_failed += len(batch_failed)
        total_chunks += len(chunk_rows)
        total_embed_failures += len(embed_failures)

    log.info(f"Stage 5 complete: {total_succeeded} docs, "
             f"{total_failed} failed, {total_chunks} chunks, {iteration} batches")
    
    # ── MLflow experiment logging end ──────────────────────────────────────────
    log_p2_experiment_end(
        start_context=mlflow_context,
        docs_succeeded=total_succeeded,
        docs_failed=total_failed,
        chunks_written=total_chunks,
        embedding_dimension=embedding_dimension,
        embed_failures=total_embed_failures,
    )

    return {
        "iterations":     iteration,
        "succeeded":      total_succeeded,
        "failed":         total_failed,
        "chunks_written": total_chunks,
    }

