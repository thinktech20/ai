"""SQL assertions for the FSR v2 verification plan.

Each check returns (name, passed, detail). Column names match the live dev
schema of fsr_metadata_v2 / fsr_chunks_v2 / fsr_document_equipment_map_v2.
Note: chunk_status lives on the metadata table, not the chunks table.
"""

DATE_COLS = [
    "report_issued_date",
    "outage_start_date",
    "outage_end_date",
    "job_start_date",
    "approved_date",
]

# Databricks SQL uses Java regex; \\d survives the Python string into SQL as \d.
DATE_RE = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"


def _quote_list(names):
    return ", ".join("'" + n.replace("'", "''") + "'" for n in names)


def check_expected_completed(c, cfg):
    """Every expected doc reached metadata_status='completed'.

    Matches on document_id, not pdf_name: P1 rewrites pdf_name to a derived
    label like 'Generator_337X581_2020-12-12'. document_id keeps the source
    UUID, and target names may carry a suffix after it.
    """
    expected = cfg["expected_pdf_names"]
    if not expected:
        return ("expected docs completed", None, "no EXPECTED_PDF_NAMES given, skipped")
    rows = c.sql(
        f"""
        SELECT e.name, coalesce(m.metadata_status, 'MISSING') AS status
        FROM (SELECT explode(array({_quote_list(expected)})) AS name) e
        LEFT JOIN {cfg['metadata']} m
          ON lower(e.name) = lower(m.document_id)
          OR lower(e.name) LIKE lower(m.document_id) || '%'
        WHERE coalesce(m.metadata_status,'MISSING') <> 'completed'
        """
    )
    bad = [f"{r[0]}={r[1]}" for r in rows]
    # Date-filtered docs are legitimately absent; caller lists them.
    allowed = set(cfg.get("expected_absent") or [])
    bad = [b for b in bad if b.split("=")[0] not in allowed]
    return (
        f"expected docs completed ({len(expected)})",
        not bad,
        "all completed" if not bad else f"{len(bad)} not completed: {bad[:8]}",
    )


def check_no_in_progress(c, cfg):
    n_meta = int(c.scalar(f"SELECT count(*) FROM {cfg['metadata']} WHERE metadata_status='in_progress'"))
    n_chunk = int(c.scalar(f"SELECT count(*) FROM {cfg['metadata']} WHERE chunk_status='in_progress'"))
    ok = n_meta == 0 and n_chunk == 0
    return ("no rows stuck in_progress", ok, f"metadata={n_meta}, chunk={n_chunk}")


def check_failed_docs(c, cfg):
    rows = c.sql(
        f"""SELECT pdf_name, substr(coalesce(metadata_error,''),1,120)
            FROM {cfg['metadata']} WHERE metadata_status='failed' LIMIT 10"""
    )
    return (
        "no failed docs",
        not rows,
        "none" if not rows else f"{len(rows)} failed, e.g. {rows[0]}",
    )


def check_primary_esn(c, cfg):
    n = int(
        c.scalar(
            f"""SELECT count(*) FROM {cfg['metadata']}
                WHERE metadata_status='completed' AND (primary_esn IS NULL OR trim(primary_esn)='')"""
        )
    )
    return ("primary_esn populated on completed docs", n == 0, f"{n} missing")


def check_parsed_path(c, cfg):
    n = int(
        c.scalar(
            f"""SELECT count(*) FROM {cfg['metadata']}
                WHERE metadata_status='completed' AND (parsed_volume_path IS NULL OR trim(parsed_volume_path)='')"""
        )
    )
    return ("parsed_volume_path populated", n == 0, f"{n} missing")


def check_date_formats(c, cfg):
    conds = " OR ".join(
        f"({col} IS NOT NULL AND trim({col}) <> '' AND {col} NOT RLIKE '{DATE_RE}')"
        for col in DATE_COLS
    )
    rows = c.sql(
        f"""SELECT pdf_name, {', '.join(DATE_COLS)} FROM {cfg['metadata']}
            WHERE metadata_status='completed' AND ({conds}) LIMIT 5"""
    )
    return (
        "all date columns are YYYY-MM-DD",
        not rows,
        "ok" if not rows else f"{len(rows)} bad rows, e.g. {rows[0]}",
    )


def check_date_filter(c, cfg):
    """No completed doc where every populated date year is below the cutoff."""
    min_year = int(cfg["min_doc_year"])
    years = ", ".join(
        f"CASE WHEN {col} RLIKE '{DATE_RE}' THEN int(substr({col},1,4)) END" for col in DATE_COLS
    )
    rows = c.sql(
        f"""SELECT pdf_name, max_year FROM (
              SELECT pdf_name, array_max(array({years})) AS max_year
              FROM {cfg['metadata']} WHERE metadata_status='completed'
            ) WHERE max_year IS NOT NULL AND max_year < {min_year} LIMIT 10"""
    )
    return (
        f"no completed docs older than {min_year}",
        not rows,
        "ok" if not rows else f"{len(rows)} leaked through, e.g. {rows[0]}",
    )


def check_equipment_map(c, cfg):
    n = int(
        c.scalar(
            f"""SELECT count(*) FROM {cfg['metadata']} m
                WHERE m.metadata_status='completed'
                  AND NOT EXISTS (SELECT 1 FROM {cfg['equip_map']} e WHERE e.document_id = m.document_id)"""
        )
    )
    return ("equipment map row for every completed doc", n == 0, f"{n} docs with no map row")


def check_chunks_exist(c, cfg):
    n = int(
        c.scalar(
            f"""SELECT count(*) FROM {cfg['metadata']} m
                WHERE m.chunk_status='completed'
                  AND NOT EXISTS (SELECT 1 FROM {cfg['chunks']} k WHERE k.document_id = m.document_id)"""
        )
    )
    return ("chunks exist for every chunked doc", n == 0, f"{n} docs with no chunks")


def check_orphan_chunks(c, cfg):
    n = int(
        c.scalar(
            f"""SELECT count(*) FROM {cfg['chunks']} k
                WHERE NOT EXISTS (SELECT 1 FROM {cfg['metadata']} m WHERE m.document_id = k.document_id)"""
        )
    )
    return ("no orphan chunks", n == 0, f"{n} orphan chunk rows")


def check_embedding_dim(c, cfg):
    want = int(cfg["embedding_dim"])
    rows = c.sql(
        f"""SELECT DISTINCT coalesce(embedding_dimension, -1), size(chunk_embedding)
            FROM {cfg['chunks']} LIMIT 10"""
    )
    if not rows:
        return ("embedding dimension", None, "no chunk rows yet, skipped")
    bad = [r for r in rows if str(r[0]) != str(want) or str(r[1]) != str(want)]
    return (
        f"embedding dimension == {want}",
        not bad,
        "ok" if not bad else f"found {rows}",
    )


def check_empty_chunk_text(c, cfg):
    n = int(
        c.scalar(
            f"SELECT count(*) FROM {cfg['chunks']} WHERE chunk_text IS NULL OR trim(chunk_text)=''"
        )
    )
    return ("no empty chunk_text", n == 0, f"{n} empty chunks")


def check_run_log_concurrency(c, cfg):
    """P1 worker count, LLM batching and date filtering, read from the run log.

    These were previously greps over driver stdout, which serverless does not
    return — they reported 'not found' on healthy runs.
    """
    run_log = cfg.get("run_log")
    if not run_log:
        return ("run log: concurrency + batching", None, "no run_log table configured")
    rows = c.sql(
        f"""SELECT p1_workers, llm_batch_count, docs_date_filtered, docs_claimed
            FROM {run_log} WHERE job_name = 'PW_SDG_FSR_V2_Metadata'
            ORDER BY start_time DESC LIMIT 1"""
    )
    if not rows:
        return ("run log: concurrency + batching", False, "no P1 row in the run log")
    workers, batches, filtered, claimed = rows[0]
    want = cfg.get("p1_workers")
    ok = str(workers) == str(want) and int(batches or 0) > 0
    return (
        f"run log: p1_workers={want}, batching, date filter",
        ok,
        f"workers={workers} batches={batches} date_filtered={filtered} claimed={claimed}",
    )


ALL_CHECKS = [
    check_expected_completed,
    check_no_in_progress,
    check_failed_docs,
    check_primary_esn,
    check_parsed_path,
    check_date_formats,
    check_date_filter,
    check_equipment_map,
    check_chunks_exist,
    check_orphan_chunks,
    check_embedding_dim,
    check_empty_chunk_text,
    check_run_log_concurrency,
]
