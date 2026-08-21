"""General REChain batch launcher for the active extracted runtime.

Edit RUN_LIST below, then run:

    python run_pipeline.py

The launcher expands any `ALL` issue/component entries against the heatmap,
executes the batch, writes `re_chain_results.csv`, and then condenses and
evaluates the output in the configured output directory.
"""

import os
import re
import time
from typing import List, Dict

from REChainExperiment.heatmap import query_all_issues
from REChainExperiment.batch import run_batch
from REChainExperiment.config import RunConfig, OUTPUT_DIR

# ── User-defined run list ────────────────────────────────────────

RUN_LIST = [
    # --- Specific issue runs ---
    # {"serial_number": "290T658", "issue_name": "Flux probe",      "component": "Rotor"},
    # {"serial_number": "337X380", "issue_name": "Vibration",       "component": "Rotor"},

    # --- All issues for a component ---
    # {"serial_number": "337X233", "issue_name": "ALL", "component": "Rotor"},

    # --- All issues, both components ---
    # {"serial_number": "761X004", "issue_name": "ALL", "component": "ALL"},

    # --- 30 serials × all issues (uncomment and fill in serials) ---
    *[
        {"serial_number": s, "issue_name": "ALL", "component":  "Rotor,Stator"}
        for s in [
            "290T434", "290T484", "290T503", "290T530", "290T532", "290T543",  "290T762", "337X045", "337X330", "337X336"
        ]
    ],
]

# ── Config ───────────────────────────────────────────────────────

SYSTEM_PROMPT_PATH = os.getenv(
    "SYSTEM_PROMPT_PATH",
    os.path.join(os.path.dirname(__file__), "REChainExperiment", "system_prompt.txt"),
)


def _load_system_prompt() -> str:
    if os.path.exists(SYSTEM_PROMPT_PATH):
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    print(f"[WARN] System prompt not found at {SYSTEM_PROMPT_PATH} - LLM step will be skipped")
    return ""


def _parse_components(comp_raw) -> List[str]:
    """Parse component field: 'ALL', single value, comma-separated string, or list."""
    if isinstance(comp_raw, list):
        flat = [c.strip() for c in comp_raw if c.strip()]
        return [] if any(c.upper() == "ALL" for c in flat) else flat
    comp = str(comp_raw).strip()
    if comp.upper() == "ALL":
        return []
    return [c.strip() for c in comp.split(",") if c.strip()]


def _expand_run_list(run_list: List[Dict], all_issues: List[Dict]) -> List[Dict]:
    expanded = []
    for entry in run_list:
        serial = entry["serial_number"]
        issue = entry.get("issue_name", "ALL").strip()
        comp_raw = entry.get("component", "ALL").strip()
        components = _parse_components(comp_raw)

        # Specific issue + specific single component — no expansion needed
        if issue.upper() != "ALL" and len(components) == 1:
            expanded.append({"serial_number": serial, "issue_name": issue, "component": components[0]})
            continue

        # Need heatmap expansion (ALL issue, ALL component, or multiple components)
        for row in all_issues:
            row_comp = str(row.get("component", "")).strip()
            row_issue = str(row.get("issue_name", "")).strip()
            if components and row_comp.lower() not in [c.lower() for c in components]:
                continue
            if issue.upper() != "ALL" and row_issue.lower() != issue.lower():
                continue
            expanded.append({"serial_number": serial, "issue_name": row_issue, "component": row_comp})

    seen = set()
    unique = []
    for e in expanded:
        key = (e["serial_number"], e["issue_name"].lower(), e["component"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def main():
    sys_prompt = _load_system_prompt()
    config = RunConfig()

    # Expand ALL entries from heatmap
    def _needs_expansion(e):
        comp = e.get("component", "ALL")
        if isinstance(comp, list):
            return True
        return e.get("issue_name", "").upper() == "ALL" or comp.upper() == "ALL" or "," in comp

    needs_heatmap = any(_needs_expansion(e) for e in RUN_LIST)
    all_issues = query_all_issues() if needs_heatmap else []
    runs = _expand_run_list(RUN_LIST, all_issues)

    print(f"\n{'='*60}")
    print(f"REChain Pipeline")
    print(f"{'='*60}")
    print(f"Runs: {len(RUN_LIST)} entries → {len(runs)} expanded")
    print(f"Output:  {OUTPUT_DIR}")
    print(f"CSV:     {config.output_csv}")
    print(f"Prompt:  {'loaded' if sys_prompt else 'not found (LLM skipped)'}")
    print(f"{'='*60}\n")

    # Run batch: chain per (serial, issue) → CSV → condense → evaluate
    summary = run_batch(runs, config, sys_prompt)

    print(f"\n{'='*60}")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\nTotal time: {round(time.time() - t0, 1)}s")
