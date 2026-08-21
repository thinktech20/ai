"""Batch orchestrator: runs chain per (serial, issue), writes CSV, condenses, evaluates.

Replaces the old pipeline.py. Uses live retrieval via chain.run_chain() instead of
pre-computed JSON files.
"""

from __future__ import annotations

import csv
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import RunConfig, normalize_issue_name, OUTPUT_DIR, PACKAGE_DIR
from .condense import write_condensed_csv
from .evaluation import (
    DIFF_CSV_NAME,
    ensure_ground_truth_csv,
    evaluate_condensed_against_ground_truth,
)

CSV_COLUMNS = [
    "completed_at_utc",
    "status",
    "error",
    "serial_number",
    "issue_name",
    "normalized_issue_name",
    "component",
    "issue_grouping",
    "issue_prompt",
    "heatmap_matched",
    "fsr_chunk_count",
    "er_chunk_count",
    "prompt_chars",
    "model_name",
    "latency_sec",
    "row_latency_sec",
    "summary",
    "finding_count",
    "risk",
    "condition",
    "threshold",
    "actual_value",
    "evidence",
    "citation",
    "justification",
    "ambiguity_handling",
    "output_json",
    "raw_response",
]


def _timestamp_utc() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _join_finding_values(findings: List[Dict], key: str) -> str:
    values = [str(f.get(key, "")).strip() for f in findings if str(f.get(key, "")).strip()]
    return " || ".join(values)


def _append_row(output_csv: Path, row: Dict[str, Any]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output_csv.exists()
    with output_csv.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})


def _load_completed_pairs(output_csv: Path) -> set[tuple[str, str, str]]:
    if not output_csv.exists():
        return set()
    completed: set[tuple[str, str, str]] = set()
    with output_csv.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("status") != "success":
                continue
            serial = (row.get("serial_number") or "").strip()
            issue = normalize_issue_name(row.get("issue_name") or "")
            component = (row.get("component") or "").strip().lower()
            if serial and issue and component:
                completed.add((serial, issue, component))
    return completed


def _extract_csv_row(chain_result: Dict[str, Any], config: RunConfig) -> Dict[str, Any]:
    """Convert a chain.run_chain() result dict into a flat CSV row."""
    inp = chain_result.get("input", {})
    hm = chain_result.get("heatmap", {})
    er = chain_result.get("er_results", {})
    fsr = chain_result.get("fsr_results", {})
    llm = chain_result.get("llm_response", {})
    timing = chain_result.get("timing", {})

    parsed = llm.get("parsed") or {}
    findings = parsed.get("findings", []) or []

    row = {
        "completed_at_utc": _timestamp_utc(),
        "serial_number": inp.get("serial_number", ""),
        "issue_name": inp.get("issue_name", ""),
        "normalized_issue_name": normalize_issue_name(inp.get("issue_name", "")),
        "component": inp.get("component", ""),
        "issue_grouping": (hm.get("row_used") or {}).get("issue_grouping", ""),
        "issue_prompt": hm.get("issue_prompt", ""),
        "heatmap_matched": str(bool(hm.get("row_used"))),
        "fsr_chunk_count": fsr.get("count", 0),
        "er_chunk_count": er.get("count", 0),
        "prompt_chars": 0,
        "model_name": config.model_name,
        "latency_sec": round(timing.get("llm_ms", 0) / 1000, 3),
        "row_latency_sec": round(timing.get("total_ms", 0) / 1000, 3),
    }

    if llm.get("raw") and parsed:
        row.update({
            "status": "success",
            "summary": str(parsed.get("summary", "")).strip(),
            "finding_count": len(findings),
            "risk": _join_finding_values(findings, "Risk"),
            "condition": _join_finding_values(findings, "Condition"),
            "threshold": _join_finding_values(findings, "Threshold"),
            "actual_value": _join_finding_values(findings, "Actual Value"),
            "evidence": _join_finding_values(findings, "Evidence"),
            "citation": _join_finding_values(findings, "Citation"),
            "justification": _join_finding_values(findings, "justification"),
            "ambiguity_handling": _join_finding_values(findings, "Ambiguity handling"),
            "output_json": json.dumps(parsed, ensure_ascii=False),
            "raw_response": llm.get("raw", ""),
        })
    elif llm.get("raw"):
        row.update({
            "status": "parse_error",
            "error": "Could not parse LLM JSON",
            "raw_response": llm.get("raw", ""),
        })
    else:
        row.update({
            "status": "llm_error",
            "error": "No LLM response",
        })

    return row


def _run_batch_entry(
    entry: Dict[str, str],
    config: RunConfig,
    system_prompt: str,
) -> tuple[Dict[str, Any], str, str]:
    """Execute a single batch entry and return (row, summary_status, label)."""
    from .chain import run_chain

    serial = entry["serial_number"]
    issue_name = entry["issue_name"]
    component = entry["component"]
    label = f"{serial} / {issue_name} / {component}"

    print(f"\n[Start] {label}")
    try:
        result = run_chain(
            serial_number=serial,
            issue_name=issue_name,
            component=component,
            system_prompt=system_prompt or None,
        )
        row = _extract_csv_row(result, config)
        status = row.get("status", "failed")
        return row, status if status in {"success", "parse_error", "llm_error"} else "failed", label
    except Exception as exc:
        error_row = {
            "completed_at_utc": _timestamp_utc(),
            "status": "llm_error",
            "error": str(exc),
            "serial_number": serial,
            "issue_name": issue_name,
            "normalized_issue_name": normalize_issue_name(issue_name),
            "component": component,
            "model_name": config.model_name,
        }
        return error_row, "failed", label


def _get_worker_stagger_seconds() -> float:
    raw_value = os.getenv("RE_CHAIN_WORKER_STAGGER_SECONDS", "0").strip()
    if not raw_value:
        return 0.0
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        print(f"[Batch] Ignoring invalid RE_CHAIN_WORKER_STAGGER_SECONDS={raw_value!r}")
        return 0.0


def run_batch(
    runs: List[Dict[str, str]],
    config: RunConfig,
    system_prompt: str,
) -> Dict[str, Any]:
    """
    Execute run_chain() for each (serial, issue, component) entry,
    write CSV rows incrementally, then condense + evaluate.

    Args:
        runs: List of {"serial_number", "issue_name", "component"} dicts
        config: RunConfig with LLM/batch settings
        system_prompt: System prompt text (empty string to skip LLM)

    Returns:
        Summary dict with counts and output paths
    """
    config.ensure_output_dir()
    completed_pairs = set()
    if not config.force_rerun:
        completed_pairs = _load_completed_pairs(config.output_csv)

    # Filter out already-completed pairs
    pending: List[Dict[str, str]] = []
    skipped = 0
    for entry in runs:
        pair = (
            entry["serial_number"],
            normalize_issue_name(entry["issue_name"]),
            entry["component"].strip().lower(),
        )
        if pair in completed_pairs:
            skipped += 1
        else:
            pending.append(entry)

    summary: Dict[str, Any] = {
        "total": len(runs),
        "success": 0,
        "parse_error": 0,
        "llm_error": 0,
        "skipped": skipped,
        "failed": 0,
        "output_csv": str(config.output_csv),
    }

    if skipped:
        print(f"[Batch] Skipped {skipped} already-completed pairs")

    if not pending:
        print("[Batch] Nothing to run - all pairs already completed")
    else:
        max_workers = max(1, min(config.max_workers, len(pending)))
        mode = "parallel" if max_workers > 1 else "sequential"
        worker_stagger_seconds = _get_worker_stagger_seconds()
        print(f"[Batch] Running {len(pending)} entries with {max_workers} worker(s) ({mode})")
        if worker_stagger_seconds > 0 and max_workers > 1:
            print(f"[Batch] Staggering worker starts by {worker_stagger_seconds:.1f}s")

        def _record_result(index: int, total: int, row: Dict[str, Any], summary_status: str, label: str) -> None:
            _append_row(config.output_csv, row)
            row_status = row.get("status", "failed")
            if summary_status in summary:
                summary[summary_status] += 1
            else:
                summary["failed"] += 1
            print(f"  [{index}/{total}] {label} -> {row_status}")

        if max_workers == 1:
            for index, entry in enumerate(pending, 1):
                row, summary_status, label = _run_batch_entry(entry, config, system_prompt)
                _record_result(index, len(pending), row, summary_status, label)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                pending_iter = iter(enumerate(pending, 1))
                futures: Dict[Any, tuple[int, Dict[str, str]]] = {}
                next_submit_at = 0.0

                def _submit_next() -> bool:
                    nonlocal next_submit_at
                    try:
                        index, entry = next(pending_iter)
                    except StopIteration:
                        return False

                    if worker_stagger_seconds > 0:
                        now = time.monotonic()
                        if next_submit_at > now:
                            time.sleep(next_submit_at - now)

                    future = pool.submit(_run_batch_entry, entry, config, system_prompt)
                    futures[future] = (index, entry)

                    if worker_stagger_seconds > 0:
                        next_submit_at = time.monotonic() + worker_stagger_seconds
                    return True

                for _ in range(max_workers):
                    if not _submit_next():
                        break

                while futures:
                    future = next(as_completed(futures))
                    index, _entry = futures.pop(future)
                    row, summary_status, label = future.result()
                    _record_result(index, len(pending), row, summary_status, label)
                    _submit_next()

    # ── Post-processing: condense + evaluate ─────────────────────
    condensed_csv = config.output_csv.parent / "re_chain_condensed.csv"

    if summary["success"] > 0 or summary["skipped"] > 0:
        try:
            matrix = write_condensed_csv(config.output_csv, condensed_csv)
            summary["condensed_csv"] = str(condensed_csv)
            summary["condensed_shape"] = [matrix.shape[0], matrix.shape[1]]
            print(f"\n[Condense] Matrix: {matrix.shape[0]} issues x {matrix.shape[1]} serials -> {condensed_csv}")
        except Exception as e:
            print(f"\n[Condense] Failed: {e}")

        # Evaluate against ground truth
        gt_csv = config.ground_truth_csv
        if not gt_csv.exists():
            gt_csv_alt = ensure_ground_truth_csv(PACKAGE_DIR)
            if gt_csv_alt:
                gt_csv = gt_csv_alt

        if gt_csv and gt_csv.exists():
            try:
                diff_csv = config.output_csv.parent / DIFF_CSV_NAME
                evaluation = evaluate_condensed_against_ground_truth(condensed_csv, gt_csv, diff_csv)
                summary["evaluation"] = evaluation["stats"]
                print(f"[Evaluate] {evaluation['stats']}")
            except Exception as e:
                print(f"[Evaluate] Failed: {e}")

    return summary
