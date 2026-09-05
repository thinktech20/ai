#!/usr/bin/env python3
"""FSR v2 prod-hardening verification driver.

Runs the pipeline jobs and asserts the verification-plan checklist without
anyone watching a notebook.

  # just check current table state
  ./verify_fsr_v2.py check --track 1

  # snapshot now, then compare after a rerun (idempotency)
  ./verify_fsr_v2.py check --track 1 --snapshot capture
  ./verify_fsr_v2.py check --track 1 --snapshot compare

  # full unattended sequence: ddl -> p1 -> p2 -> vs -> check -> rerun -> compare
  ./verify_fsr_v2.py run --track 1

Exit code is non-zero if any check fails, so this can gate a promotion.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import checks as C
from dbx_client import DbxClient

WAREHOUSE_ID = "c383216f6af5c7c0"  # ai-pw-ser-ds-dev-sqlw
PROFILE = "dev-dbr-profile"

JOBS = {
    "ddl": 542681720135008,       # PW_SDG_FSR_V2_DDL
    "p1": 1003518188699476,       # PW_SDG_FSR_V2_Metadata
    "p2": 185943124898155,        # PW_SDG_FSR_V2_Chunking
    "vs": 844746489495403,        # PW_SDG_FSR_V2_VS_Index
}

# Sandbox mode runs the same notebooks from a personal workspace folder instead of
# the deployed bundle. CI/CD only deploys from the dev branch, so this is the only
# way to exercise an unmerged branch. Paths are repo-relative, matching the jobs.
SANDBOX_ROOT = "/Users/madhurima.saxena@gevernova.com/fsr_v2_sandbox"
NOTEBOOKS = {
    "ddl": "ddls/fsr_v2/nb_sdg_fsr_v2_ddl",
    "p1": "silver/src/etl/nb_sdg_fsr_v2_metadata",
    "p2": "gold/src/etl/nb_sdg_fsr_v2_chunks",
    "vs": "vs/src/etl/nb_sdg_fsr_v2_index",
}

CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracks.json")
SNAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".snapshots")


def load_track(track):
    with open(CFG_PATH) as f:
        all_tracks = json.load(f)
    cfg = all_tracks[str(track)]
    parent = cfg.get("_inherits")
    if parent:
        merged = json.loads(json.dumps(all_tracks[str(parent)]))
        for k, v in cfg.items():
            if k == "params":
                for stage, overrides in v.items():
                    merged.setdefault("params", {}).setdefault(stage, {}).update(overrides)
            elif k != "_inherits":
                merged[k] = v
        cfg = merged
    return cfg


def resolve_params(params, stage):
    """Secrets stay out of tracks.json; ${VAR} placeholders resolve from the env."""
    out = {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            name = v[2:-1]
            val = os.environ.get(name)
            if not val:
                raise SystemExit(f"env var {name} is not set (needed for {stage}.{k})")
            v = val
        out[k] = v
    return out


def banner(msg):
    print(f"\n{'=' * 72}\n{msg}\n{'=' * 72}", flush=True)


# --- snapshots ----------------------------------------------------------

def take_snapshot(c, cfg):
    rows = c.sql(
        f"""SELECT m.document_id, m.parsed_volume_path, count(k.chunk_id) AS n_chunks
            FROM {cfg['metadata']} m
            LEFT JOIN {cfg['chunks']} k ON k.document_id = m.document_id
            WHERE m.metadata_status = 'completed'
            GROUP BY m.document_id, m.parsed_volume_path"""
    )
    return {r[0]: [r[1], r[2]] for r in rows}


def snapshot_compare(before, after):
    diffs = []
    for doc, (path, n) in before.items():
        if doc not in after:
            diffs.append(f"{doc}: disappeared after rerun")
        elif after[doc] != [path, n]:
            diffs.append(f"{doc}: {[path, n]} -> {after[doc]}")
    for doc in after:
        if doc not in before:
            diffs.append(f"{doc}: appeared after rerun")
    return diffs


# --- reporting ----------------------------------------------------------

def report(results):
    width = max(len(r[0]) for r in results) + 2
    failed = 0
    print()
    for name, ok, detail in results:
        if ok is None:
            mark = "SKIP"
        elif ok:
            mark = "PASS"
        else:
            mark = "FAIL"
            failed += 1
        print(f"  [{mark}] {name.ljust(width)} {detail}")
    print(f"\n  {len(results)} checks, {failed} failed\n")
    return failed


def run_checks(c, cfg, snapshot=None, log_text=None):
    results = []
    for fn in C.ALL_CHECKS:
        try:
            results.append(fn(c, cfg))
        except Exception as e:  # a broken check must not hide the other results
            results.append((fn.__name__, False, f"check errored: {e}"))

    if snapshot:
        os.makedirs(SNAP_DIR, exist_ok=True)
        path = os.path.join(SNAP_DIR, f"track{cfg['track']}.json")
        current = take_snapshot(c, cfg)
        if snapshot == "capture":
            # Overwriting a baseline then comparing against it compares a state
            # to itself and always passes, so make that impossible by accident.
            if os.path.exists(path) and not cfg.get("force_snapshot"):
                results.append((
                    "snapshot captured", False,
                    f"refusing to overwrite existing baseline {path} — "
                    "pass --force-snapshot if that is really what you want",
                ))
            else:
                with open(path, "w") as f:
                    json.dump(current, f, indent=2)
                results.append(("snapshot captured", True, f"{len(current)} docs -> {path}"))
        else:
            if not os.path.exists(path):
                results.append(("idempotency compare", False, "no snapshot captured yet"))
            else:
                with open(path) as f:
                    before = json.load(f)
                diffs = snapshot_compare(before, current)
                results.append(
                    (
                        "idempotency: state unchanged after rerun",
                        not diffs,
                        f"{len(before)} docs stable" if not diffs else f"{len(diffs)} diffs: {diffs[:5]}",
                    )
                )
    return results


# --- job orchestration --------------------------------------------------

def launch(c, stage, cfg, dry_run=False, sandbox=False):
    params = resolve_params(cfg["params"][stage], stage)

    if sandbox:
        path = f"{SANDBOX_ROOT}/{NOTEBOOKS[stage]}"
        if dry_run:
            print(f"  [dry-run] would submit {stage} -> {path} with {len(params)} params")
            return None
        run_id = c.submit_notebook(f"fsr_v2_sandbox_{stage}", path, params)
        print(f"  {stage}: sandbox run {run_id} -> {c.run_url(run_id)}", flush=True)
    else:
        job_id = JOBS[stage]
        declared = c.job_parameter_names(job_id)
        unknown = [k for k in params if k not in declared]
        if unknown:
            # run-now rejects undeclared names outright, so drop them but stay loud.
            print(f"  WARNING {stage}: job does not declare {unknown} — dropping. "
                  f"Add them to the job definition if they are needed.")
            params = {k: v for k, v in params.items() if k in declared}
        if dry_run:
            print(f"  [dry-run] would run {stage} (job {job_id}) with {len(params)} params")
            return None
        run_id = c.run_job(job_id, params)
        print(f"  {stage}: run {run_id} -> {c.run_url(run_id)}", flush=True)

    r = c.wait_for_run(run_id)
    state = r["state"]
    result = state.get("result_state")
    print(f"  {stage}: {result} ({state.get('state_message', '')[:200]})", flush=True)
    if result != "SUCCESS":
        raise SystemExit(f"{stage} failed: {c.run_url(run_id)}")
    return run_id


def cmd_run(args):
    cfg = load_track(args.track)
    cfg["track"] = args.track
    cfg["force_snapshot"] = True  # a fresh run legitimately establishes the baseline
    c = DbxClient(PROFILE, WAREHOUSE_ID)

    stages = args.stages.split(",") if args.stages else ["ddl", "p1", "p2", "vs"]

    where = f"sandbox ({SANDBOX_ROOT})" if args.sandbox else "deployed bundle"
    banner(f"Track {args.track}: {' -> '.join(stages)}   [{where}]")
    p1_run = None
    for stage in stages:
        rid = launch(c, stage, cfg, args.dry_run, args.sandbox)
        if stage == "p1":
            p1_run = rid
    if args.dry_run:
        return 0

    log_text = c.run_output(p1_run) if p1_run else None

    banner(f"Track {args.track}: checks (first pass)")
    results = run_checks(c, cfg, snapshot="capture", log_text=log_text)
    failed = report(results)

    if args.no_rerun:
        return 1 if failed else 0

    banner(f"Track {args.track}: idempotency rerun (p1 -> p2)")
    for stage in ("p1", "p2"):
        launch(c, stage, cfg, sandbox=args.sandbox)

    banner(f"Track {args.track}: checks (after rerun)")
    failed += report(run_checks(c, cfg, snapshot="compare"))
    return 1 if failed else 0


def cmd_check(args):
    cfg = load_track(args.track)
    cfg["track"] = args.track
    cfg["force_snapshot"] = getattr(args, "force_snapshot", False)
    c = DbxClient(PROFILE, WAREHOUSE_ID)
    banner(f"Track {args.track}: checks against {cfg['metadata']}")
    return 1 if report(run_checks(c, cfg, snapshot=args.snapshot)) else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="run assertions against current table state")
    pc.add_argument("--track", default="1")
    pc.add_argument("--snapshot", choices=["capture", "compare"])
    pc.add_argument("--force-snapshot", action="store_true",
                    help="allow capture to overwrite an existing baseline")
    pc.set_defaults(func=cmd_check)

    pr = sub.add_parser("run", help="trigger pipeline jobs, then assert")
    pr.add_argument("--track", default="1")
    pr.add_argument("--stages", help="comma list, default ddl,p1,p2,vs")
    pr.add_argument("--no-rerun", action="store_true", help="skip the idempotency rerun")
    pr.add_argument("--sandbox", action="store_true",
                    help="run notebooks from the personal workspace sandbox instead of "
                         "the deployed bundle (for unmerged branches)")
    pr.add_argument("--dry-run", action="store_true")
    pr.set_defaults(func=cmd_run)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
