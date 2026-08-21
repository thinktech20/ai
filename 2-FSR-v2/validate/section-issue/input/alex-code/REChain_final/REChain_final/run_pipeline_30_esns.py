"""Run REChain for the 30 ESNs listed in the IBAT fallback CSV."""

from __future__ import annotations

import csv
import os
import time
from pathlib import Path

from REChainExperiment.batch import run_batch
from REChainExperiment.config import ER_K, FSR_K, OUTPUT_DIR, RunConfig
from REChainExperiment.heatmap import query_all_issues


def _resolve_serial_source_csv() -> Path:
    env_path = os.getenv("RE_CHAIN_SERIAL_SOURCE_CSV", "").strip()
    if env_path:
        return Path(env_path)

    here = Path(__file__).resolve()
    candidates = [
        here.parent / "risk_evaluation_script_gt_20260318_copy" / "input data" / "30_serial_IBAT.csv",
        here.parent.parent / "risk_evaluation_script_gt_20260318_copy" / "input data" / "30_serial_IBAT.csv",
        here.parent.parent.parent / "risk_evaluation_script_gt_20260318_copy" / "input data" / "30_serial_IBAT.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


SERIAL_SOURCE_CSV = _resolve_serial_source_csv()
SYSTEM_PROMPT_PATH = os.getenv(
    "SYSTEM_PROMPT_PATH",
    os.path.join(os.path.dirname(__file__), "REChainExperiment", "system_prompt.txt"),
)
RUN_OUTPUT_DIR = OUTPUT_DIR / os.getenv(
    "RE_CHAIN_RUN_NAME",
    "30esn_selfmanaged_litellm_20260323_gen_rel",
)


def _load_serials() -> list[str]:
    with SERIAL_SOURCE_CSV.open("r", newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        serials = []
        seen = set()
        for row in rows:
            serial = str(row.get("equip_serial_number", "")).strip()
            if not serial or serial in seen:
                continue
            seen.add(serial)
            serials.append(serial)
    return serials


def _load_system_prompt() -> str:
    prompt_path = Path(SYSTEM_PROMPT_PATH)
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    print(f"[WARN] System prompt not found at {prompt_path} - LLM step will be skipped")
    return ""


def _expand_runs(serials: list[str]) -> list[dict[str, str]]:
    all_issues = query_all_issues()
    runs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for serial in serials:
        for row in all_issues:
            component = str(row.get("component", "")).strip()
            issue_name = str(row.get("issue_name", "")).strip()
            if not component or not issue_name:
                continue
            key = (serial, issue_name.lower(), component.lower())
            if key in seen:
                continue
            seen.add(key)
            runs.append(
                {
                    "serial_number": serial,
                    "issue_name": issue_name,
                    "component": component,
                }
            )
    return runs


def main() -> None:
    t0 = time.time()
    serials = _load_serials()
    system_prompt = _load_system_prompt()
    config = RunConfig()
    config.max_workers = int(os.getenv("RE_CHAIN_MAX_WORKERS", "4"))
    config.output_csv = RUN_OUTPUT_DIR / "re_chain_results.csv"

    runs = _expand_runs(serials)

    print("=" * 60)
    print("REChain 30-ESN Batch")
    print("=" * 60)
    print(f"Serial source: {SERIAL_SOURCE_CSV}")
    print(f"Serials:       {len(serials)}")
    print(f"Runs:          {len(runs)}")
    print(f"Workers:       {config.max_workers}")
    print(f"ER k:          {ER_K}")
    print(f"FSR k:         {FSR_K}")
    print(f"Output:        {config.output_csv}")
    print(f"Prompt:        {'loaded' if system_prompt else 'not found (LLM skipped)'}")
    print("=" * 60)

    summary = run_batch(runs, config, system_prompt)

    print("\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print(f"\nTotal time: {round(time.time() - t0, 1)}s")


if __name__ == "__main__":
    main()