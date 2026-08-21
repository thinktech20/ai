"""Run REChain for the 26 ESNs present in the FSR GT subset table."""

from __future__ import annotations

import os
import time
from pathlib import Path

from REChainExperiment.batch import run_batch
from REChainExperiment.config import ER_K, FSR_K, OUTPUT_DIR, RunConfig
from REChainExperiment.heatmap import query_all_issues


SERIALS = [
    "290T434",
    "290T484",
    "290T503",
    "290T530",
    "290T532",
    "290T543",
    "290T658",
    "290T762",
    "337X045",
    "337X233",
    "337X305",
    "337X330",
    "337X336",
    "337X369",
    "337X708",
    "337X709",
    "338X408",
    "338X424",
    "338X425",
    "338X426",
    "338X427",
    "338X713",
    "338X722",
    "338X724",
    "338X765",
    "761X004",
]

SYSTEM_PROMPT_PATH = os.getenv(
    "SYSTEM_PROMPT_PATH",
    os.path.join(os.path.dirname(__file__), "REChainExperiment", "system_prompt.txt"),
)
RUN_OUTPUT_DIR = OUTPUT_DIR / os.getenv(
    "RE_CHAIN_RUN_NAME",
    "26esn_selfmanaged_litellm_20260318",
)


def _load_system_prompt() -> str:
    prompt_path = Path(SYSTEM_PROMPT_PATH)
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    print(f"[WARN] System prompt not found at {prompt_path} - LLM step will be skipped")
    return ""


def _expand_runs() -> list[dict[str, str]]:
    all_issues = query_all_issues()
    runs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for serial in SERIALS:
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
    system_prompt = _load_system_prompt()
    config = RunConfig()
    config.max_workers = int(os.getenv("RE_CHAIN_MAX_WORKERS", "5"))
    config.output_csv = RUN_OUTPUT_DIR / "re_chain_results.csv"

    runs = _expand_runs()

    print("=" * 60)
    print("REChain 26-ESN Batch")
    print("=" * 60)
    print(f"Serials: {len(SERIALS)}")
    print(f"Runs:    {len(runs)}")
    print(f"Workers: {config.max_workers}")
    print(f"ER k:    {ER_K}")
    print(f"FSR k:   {FSR_K}")
    print(f"Output:  {config.output_csv}")
    print(f"Prompt:  {'loaded' if system_prompt else 'not found (LLM skipped)'}")
    print("=" * 60)

    summary = run_batch(runs, config, system_prompt)

    print("\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print(f"\nTotal time: {round(time.time() - t0, 1)}s")


if __name__ == "__main__":
    main()