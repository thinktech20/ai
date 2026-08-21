"""
REChainExperiment Pipeline
--------------------------
Single-execution pipeline: one user action triggers one full chain.

User provides:  serial_number + issue_name + component (rotor/stator)
Pipeline does:
  Step 1: Heatmap lookup  → resolves issue_prompt + severity_criteria
  Step 2: ER retrieval    → uses issue_prompt + severity as query
  Step 3: IBAT lookup     → fetches equipment metadata for the serial
  Step 4: FSR retrieval   → fetches field service report chunks
  Step 5: LLM call        → formats prompt, calls LLM, parses risk rating
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

from .heatmap import query_heatmap, build_query_from_heatmap
from .ibat import query_ibat
from .fsr import query_fsr
from .llm import build_user_prompt, call_llm, parse_llm_response
from .prompting import PromptBuildResult
from .config import ER_K, FSR_K, ER_USE_VECTOR_SEARCH

if ER_USE_VECTOR_SEARCH:
    from .er_vs import query_er_vs as _query_er_impl
else:
    from .er import query_er as _query_er_impl


def _should_serialize_retrievals() -> bool:
    raw = os.getenv("RE_CHAIN_SERIALIZE_RETRIEVALS", "")
    return raw.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _query_er(serial_number, query, retriever_type="ensemble", k=10, do_rerank=True):
    """Dispatch to er.py or er_vs.py based on config flag."""
    if ER_USE_VECTOR_SEARCH:
        return _query_er_impl(serial_number=serial_number, query=query, k=k)
    return _query_er_impl(
        serial_number=serial_number, query=query,
        retriever_type=retriever_type, k=k, do_rerank=do_rerank,
    )

# ── API client (uncomment when data service is available) ────
# from .api_client import query_heatmap_api, filter_heatmap_by_issue, query_ibat_api


def run_chain(
    serial_number: str,
    issue_name: str = "",
    component: str = "",
    query: str = None,
    retriever_type: str = "ensemble",
    er_k: int = None,
    fsr_k: int = None,
    do_rerank: bool = True,
    system_prompt: str = None,
    model: str = None,
) -> Dict[str, Any]:
    """
    Single execution of the full chain: heatmap → ER retrieve → IBAT.

    This represents one user interaction — the user selects a serial number
    and either:
      a) inputs issue_name + component → heatmap resolves the query, OR
      b) provides a free-text query directly (skips heatmap)

    Args:
        serial_number: Equipment serial (e.g. "290T658")
        issue_name: Heatmap issue name (e.g. "Rotor Vibration") — ignored if query is set
        component: "Rotor" or "Stator" — ignored if query is set
        query: Optional free-text query. If provided, skips heatmap lookup.
        retriever_type: "bm25", "faiss", or "ensemble"
        er_k: Number of ER results (default from config.ER_K)
        fsr_k: Number of FSR results (default from config.FSR_K)
        do_rerank: Whether to apply reranking
        system_prompt: System prompt text for LLM. If None, LLM step is skipped.
        model: LLM model name override (default: gemini-3-flash)

    Returns:
        Dict with keys: heatmap, er_results, fsr_results, ibat, llm_response, input, timing
    """
    if er_k is None:
        er_k = ER_K
    if fsr_k is None:
        fsr_k = FSR_K

    t_start = time.time()
    print(f"\n{'='*60}")
    print(f"REChain: serial={serial_number}, issue={issue_name}, component={component}")
    print(f"{'='*60}")

    # ── Step 1: Resolve query ────────────────────────────────────
    heatmap_rows = []
    heatmap_row_used = {}
    issue_prompt = ""
    severity_criteria = {}
    heatmap_ms = 0.0

    if query:
        # User provided free-text query — skip heatmap
        query_text = query.strip()
        print(f"[Query] User-provided ({len(query_text)} chars)")
    else:
        # Resolve from heatmap: issue_name + component → issue_prompt + severity
        t0 = time.time()
        # ── Direct Databricks query (current) ────────────────
        heatmap_rows = query_heatmap(issue_name, component)
        # ── Via API (uncomment when data service is running) ─
        # heatmap_rows = filter_heatmap_by_issue(
        #     query_heatmap_api(equipment_type="GEN", component=component),
        #     issue_name,
        # )
        heatmap_ms = round((time.time() - t0) * 1000, 1)

        if not heatmap_rows:
            print(f"[WARN] No heatmap data. Fallback query: '{issue_name} {component}'")
            query_text = f"{issue_name} {component}"
        else:
            heatmap_row_used = heatmap_rows[0]
            issue_prompt = str(heatmap_row_used.get("issue_prompt") or "").strip()
            severity_criteria = _extract_severity(heatmap_row_used)
            query_text = build_query_from_heatmap(heatmap_row_used)
            print(f"[Heatmap] issue_prompt: {issue_prompt[:100]}...")
            print(f"[Heatmap] severity levels: {len(severity_criteria)}")
            print(f"[Heatmap] query built ({len(query_text)} chars)")

    # ── Steps 2/3/4: ER + IBAT + FSR in parallel ────────────────
    er_results, ibat_rows, fsr_results = [], [], []
    er_ms = ibat_ms = fsr_ms = 0.0

    def _fetch_er():
        nonlocal er_results, er_ms
        t0 = time.time()
        er_results = _query_er(
            serial_number=serial_number,
            query=query_text,
            retriever_type=retriever_type,
            k=er_k,
            do_rerank=do_rerank,
        )
        er_ms = round((time.time() - t0) * 1000, 1)

    def _fetch_ibat():
        nonlocal ibat_rows, ibat_ms
        t0 = time.time()
        ibat_rows = query_ibat(serial_number)
        ibat_ms = round((time.time() - t0) * 1000, 1)

    def _fetch_fsr():
        nonlocal fsr_results, fsr_ms
        t0 = time.time()
        fsr_results = query_fsr(serial_number, query_text, k=fsr_k)
        fsr_ms = round((time.time() - t0) * 1000, 1)

    if _should_serialize_retrievals():
        _fetch_ibat()
        _fetch_er()
        _fetch_fsr()
    else:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(fn) for fn in (_fetch_er, _fetch_ibat, _fetch_fsr)]
            for f in futures:
                f.result()  # wait + propagate exceptions

    if not ibat_rows:
        raise RuntimeError(f"IBAT lookup returned no rows for serial '{serial_number}'")

    # ── Step 5: LLM ──────────────────────────────────────────────
    llm_raw = None
    llm_parsed = None
    llm_ms = 0.0

    if system_prompt:
        # Build user prompt from all 4 data sources
        prompt_result = build_user_prompt(
            ibat=ibat_rows[0] if ibat_rows else {},
            heatmap=heatmap_row_used,
            fsr_chunks=fsr_results,
            er_chunks=er_results,
        )
        user_prompt = prompt_result.user_prompt
        print(f"[LLM] User prompt: {len(user_prompt)} chars ({prompt_result.er_chunk_count} ER, {prompt_result.fsr_chunk_count} FSR)")

        t0 = time.time()
        llm_raw = call_llm(system_prompt, user_prompt, model=model)
        llm_ms = round((time.time() - t0) * 1000, 1)

        if llm_raw:
            llm_parsed = parse_llm_response(llm_raw)
            print(f"[LLM] Response parsed: {'OK' if llm_parsed else 'FAILED'}")
        else:
            print("[LLM] No response from LLM")
    else:
        print("[LLM] Skipped (no system_prompt provided)")

    total_ms = round((time.time() - t_start) * 1000, 1)

    result = {
        "heatmap": {
            "issue_prompt": issue_prompt,
            "severity_criteria": severity_criteria,
            "query_built": query_text,
            "row_used": heatmap_row_used,
            "all_rows": heatmap_rows,
            "latency_ms": heatmap_ms,
        },
        "er_results": {
            "results": er_results,
            "count": len(er_results),
            "retriever_type": retriever_type,
            "k": er_k,
            "do_rerank": do_rerank,
            "latency_ms": er_ms,
        },
        "fsr_results": {
            "results": fsr_results,
            "count": len(fsr_results),
            "latency_ms": fsr_ms,
        },
        "ibat": {
            "rows": ibat_rows,
            "latency_ms": ibat_ms,
        },
        "input": {
            "serial_number": serial_number,
            "issue_name": issue_name,
            "component": component,
        },
        "llm_response": {
            "raw": llm_raw,
            "parsed": llm_parsed,
            "latency_ms": llm_ms,
        },
        "timing": {
            "heatmap_ms": heatmap_ms,
            "er_ms": er_ms,
            "fsr_ms": fsr_ms,
            "ibat_ms": ibat_ms,
            "llm_ms": llm_ms,
            "total_ms": total_ms,
        },
    }

    # ── Build LLM-ready context payload ──────────────────────────
    result["llm_context"] = _build_llm_context(
        serial_number=serial_number,
        issue_name=issue_name,
        component=component,
        issue_prompt=issue_prompt,
        severity_criteria=severity_criteria,
        er_results=er_results,
        fsr_results=fsr_results,
        ibat_rows=ibat_rows,
    )

    print(f"\n{'-'*60}")
    print(f"Done: heatmap={heatmap_ms}ms, ER={er_ms}ms, FSR={fsr_ms}ms, IBAT={ibat_ms}ms, LLM={llm_ms}ms, total={total_ms}ms")
    print(f"  Heatmap rows: {len(heatmap_rows)}, ER chunks: {len(er_results)}, FSR chunks: {len(fsr_results)}, IBAT rows: {len(ibat_rows)}")
    return result


def _extract_severity(row: Dict) -> Dict[str, str]:
    """Pull severity_criteria_0..4 into a clean dict."""
    sev_map = {
        "severity_criteria_0_no_data": "No Data",
        "severity_criteria_1_light": "Light",
        "severity_criteria_2_medium": "Medium",
        "severity_criteria_3_heavy": "Heavy",
        "severity_criteria_4_immediate": "Immediate",
    }
    out = {}
    for col, label in sev_map.items():
        val = row.get(col)
        if val and str(val).strip():
            out[label] = str(val).strip()
    return out


def prepare_serial_issues(serial_number: str, issues: List[Dict[str, str]]) -> Dict[str, Any]:
    """Fetch IBAT once and resolve all issue prompts for a serial."""
    t_start = time.time()
    print(f"\n{'='*60}")
    print(f"REChain serial-batch: serial={serial_number}, {len(issues)} issues")
    print(f"{'='*60}")

    t0 = time.time()
    ibat_rows = query_ibat(serial_number)
    ibat_ms = round((time.time() - t0) * 1000, 1)
    print(f"[IBAT] {len(ibat_rows)} rows, {ibat_ms}ms (shared across {len(issues)} issues)")
    if not ibat_rows:
        raise RuntimeError(f"IBAT lookup returned no rows for serial '{serial_number}'")

    resolved: List[Dict[str, Any]] = []
    for entry in issues:
        issue_name = entry["issue_name"]
        component = entry["component"]
        hm_rows = query_heatmap(issue_name, component)
        hm_row = hm_rows[0] if hm_rows else {}
        issue_prompt = str(hm_row.get("issue_prompt") or "").strip()
        severity_criteria = _extract_severity(hm_row) if hm_row else {}
        query_text = build_query_from_heatmap(hm_row) if hm_row else f"{issue_name} {component}"
        resolved.append({
            "issue_name": issue_name,
            "component": component,
            "heatmap_rows": hm_rows,
            "heatmap_row_used": hm_row,
            "issue_prompt": issue_prompt,
            "severity_criteria": severity_criteria,
            "query_text": query_text,
        })

    return {
        "serial_number": serial_number,
        "ibat_rows": ibat_rows,
        "ibat_ms": ibat_ms,
        "resolved": resolved,
        "started_at": t_start,
    }


def run_prepared_issue(
    serial_ctx: Dict[str, Any],
    item: Dict[str, Any],
    retriever_type: str = "ensemble",
    er_k: int = None,
    fsr_k: int = None,
    do_rerank: bool = True,
    system_prompt: str = None,
    model: str = None,
) -> Dict[str, Any]:
    """Execute one prepared issue for a serial context."""
    if er_k is None:
        er_k = ER_K
    if fsr_k is None:
        fsr_k = FSR_K

    serial_number = serial_ctx["serial_number"]
    ibat_rows = serial_ctx["ibat_rows"]
    ibat_ms = serial_ctx["ibat_ms"]
    issue_name = item["issue_name"]
    component = item["component"]
    query_text = item["query_text"]
    t_issue = time.time()

    er_results, fsr_results = [], []
    er_ms = fsr_ms = 0.0

    def _fetch_er():
        nonlocal er_results, er_ms
        t0 = time.time()
        er_results = _query_er(
            serial_number=serial_number,
            query=query_text,
            retriever_type=retriever_type,
            k=er_k,
            do_rerank=do_rerank,
        )
        er_ms = round((time.time() - t0) * 1000, 1)

    def _fetch_fsr():
        nonlocal fsr_results, fsr_ms
        t0 = time.time()
        fsr_results = query_fsr(serial_number, query_text, k=fsr_k)
        fsr_ms = round((time.time() - t0) * 1000, 1)

    try:
        if _should_serialize_retrievals():
            _fetch_er()
            _fetch_fsr()
        else:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(fn) for fn in (_fetch_er, _fetch_fsr)]
                for future in futures:
                    future.result()
    except Exception as exc:
        print(f"  [{issue_name}] retrieval failed: {exc}")
        return {
            "input": {
                "serial_number": serial_number,
                "issue_name": issue_name,
                "component": component,
            },
            "error": str(exc),
            "error_type": "retrieval_error",
        }

    llm_raw, llm_parsed, llm_ms = None, None, 0.0
    if system_prompt:
        prompt_result = build_user_prompt(
            ibat=ibat_rows[0] if ibat_rows else {},
            heatmap=item["heatmap_row_used"],
            fsr_chunks=fsr_results,
            er_chunks=er_results,
        )
        t0 = time.time()
        llm_raw = call_llm(system_prompt, prompt_result.user_prompt, model=model)
        llm_ms = round((time.time() - t0) * 1000, 1)
        if llm_raw:
            llm_parsed = parse_llm_response(llm_raw)

    total_issue_ms = round((time.time() - t_issue) * 1000, 1)
    print(f"  [{issue_name}] ER={er_ms}ms FSR={fsr_ms}ms LLM={llm_ms}ms total={total_issue_ms}ms")

    return {
        "heatmap": {
            "issue_prompt": item["issue_prompt"],
            "severity_criteria": item["severity_criteria"],
            "query_built": query_text,
            "row_used": item["heatmap_row_used"],
            "all_rows": item["heatmap_rows"],
            "latency_ms": 0.0,
        },
        "er_results": {
            "results": er_results,
            "count": len(er_results),
            "retriever_type": retriever_type,
            "k": er_k,
            "do_rerank": do_rerank,
            "latency_ms": er_ms,
        },
        "fsr_results": {
            "results": fsr_results,
            "count": len(fsr_results),
            "latency_ms": fsr_ms,
        },
        "ibat": {
            "rows": ibat_rows,
            "latency_ms": ibat_ms,
        },
        "input": {
            "serial_number": serial_number,
            "issue_name": issue_name,
            "component": component,
        },
        "llm_response": {
            "raw": llm_raw,
            "parsed": llm_parsed,
            "latency_ms": llm_ms,
        },
        "timing": {
            "heatmap_ms": 0.0,
            "er_ms": er_ms,
            "fsr_ms": fsr_ms,
            "ibat_ms": ibat_ms,
            "llm_ms": llm_ms,
            "total_ms": total_issue_ms,
        },
        "llm_context": _build_llm_context(
            serial_number=serial_number,
            issue_name=issue_name,
            component=component,
            issue_prompt=item["issue_prompt"],
            severity_criteria=item["severity_criteria"],
            er_results=er_results,
            fsr_results=fsr_results,
            ibat_rows=ibat_rows,
        ),
    }


def run_serial(
    serial_number: str,
    issues: List[Dict[str, str]],
    retriever_type: str = "ensemble",
    er_k: int = None,
    fsr_k: int = None,
    do_rerank: bool = True,
    system_prompt: str = None,
    model: str = None,
    max_workers: int = 2,
) -> List[Dict[str, Any]]:
    """
    Run the full chain for one serial across multiple issues.

    Fetches IBAT once, resolves all heatmap prompts, then fans out
    (ER + FSR + LLM) per issue in parallel.

    Args:
        serial_number: Equipment serial (e.g. "290T658")
        issues: List of {"issue_name": ..., "component": ...} dicts
        max_workers: Max parallel issue threads (default 5)
        (remaining args same as run_chain)

    Returns:
        List of run_chain-style result dicts, one per issue.
    """
    serial_ctx = prepare_serial_issues(serial_number, issues)
    resolved = serial_ctx["resolved"]
    if not resolved:
        print(f"\n{'-'*60}")
        print(f"Serial {serial_number} done: 0 issues, 0.0ms total")
        return []

    results = []
    workers = min(max_workers, len(resolved))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(
                run_prepared_issue,
                serial_ctx,
                item,
                retriever_type=retriever_type,
                er_k=er_k,
                fsr_k=fsr_k,
                do_rerank=do_rerank,
                system_prompt=system_prompt,
                model=model,
            ): item
            for item in resolved
        }
        for future in as_completed(future_map):
            try:
                results.append(future.result())
            except Exception as e:
                item = future_map[future]
                print(f"  x [{item['issue_name']}] FAILED: {e}")
                results.append({
                    "input": {"serial_number": serial_number, "issue_name": item["issue_name"], "component": item["component"]},
                    "error": str(e),
                })

    total_ms = round((time.time() - serial_ctx["started_at"]) * 1000, 1)
    print(f"\n{'-'*60}")
    print(f"Serial {serial_number} done: {len(results)} issues, {total_ms}ms total")
    return results


def _build_llm_context(
    serial_number: str,
    issue_name: str,
    component: str,
    issue_prompt: str,
    severity_criteria: Dict[str, str],
    er_results: List[Dict],
    fsr_results: List[Dict],
    ibat_rows: List[Dict],
) -> Dict[str, Any]:
    """
    Build a structured JSON payload for the LLM system prompt.
    Combines heatmap issue context, ER engineering records, FSR field service
    reports, and IBAT equipment profile.
    """
    # Equipment profile from IBAT (first row, or empty)
    equipment = {}
    if ibat_rows:
        r = ibat_rows[0]
        equipment = {
            "serial_number": r.get("equip_serial_number", serial_number),
            "equipment_type": r.get("equipment_type"),
            "equipment_code": r.get("equipment_code"),
            "equipment_class": r.get("equipment_class"),
            "plant_name": r.get("plant_name"),
            "site_country": r.get("site_country"),
            "site_customer_name": r.get("site_customer_name"),
            "cooling_system": r.get("cooling_system"),
            "duty_cycle": r.get("duty_cycle"),
            "rotor_rewind": r.get("rotor_rewind"),
            "stator_rewind": r.get("stator_rewind"),
            "fuel_type": r.get("fuel_type"),
            "contract_type": r.get("contract_type"),
            "sales_channel": r.get("sales_channel"),
        }

    # ER records — full detail per chunk
    er_records = []
    for r in er_results:
        er_records.append({
            "chunk_id": r.get("chunk_id"),
            "er_case_number": r.get("er_case_number"),
            "er_number": r.get("er_number"),
            "opened_at": r.get("opened_at"),
            "status": r.get("status"),
            "component": r.get("u_component"),
            "field_action_taken": r.get("u_field_action_taken"),
            "equipment_id": r.get("equipment_id"),
            "chunk_text": r.get("chunk_text"),
            "chunk_index": r.get("chunk_index"),
            "relevance_score": r.get("score"),
        })

    # FSR records — full detail per chunk
    fsr_records = []
    for r in fsr_results:
        fsr_records.append({
            "chunk_id": r.get("chunk_id"),
            "pdf_name": r.get("pdf_name"),
            "page_number": r.get("page_number"),
            "chunk_text": r.get("chunk_text"),
            "generator_serial": r.get("generator_serial"),
            "relevance_score": r.get("score"),
        })

    return {
        "issue": {
            "issue_name": issue_name,
            "component": component,
            "issue_prompt": issue_prompt,
            "severity_criteria": severity_criteria,
        },
        "equipment": equipment,
        "engineering_records": er_records,
        "field_service_reports": fsr_records,
    }
