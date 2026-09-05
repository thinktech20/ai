#!/usr/bin/env python3
"""Track A backfill monitor — polls dev tables, drives P2/P3 kickoff, appends
pulse entries, and flags when the Track A stop criteria (see
backfill-monitoring-plan.md §2.4) are met. Does not auto-cancel jobs — it
reports STOP-READY and leaves the cancel decision to a human.

Usage: nohup python3 monitor_track_a.py > /tmp/track_a_monitor.log 2>&1 &
"""

import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbx_client import DbxClient

PROFILE = "dev-dbr-profile"
WAREHOUSE_ID = "c383216f6af5c7c0"

JOBS = {
    "p1": 1003518188699476,
    "p2": 185943124898155,
    "vs": 844746489495403,
}

METADATA = "vaid.ai_sot_field_service_report.fsr_metadata_v2"
CHUNKS = "vaid.ai_std_con_field_service_report.fsr_chunks_v2"
RUN_LOG = "vaid.ai_std_con_field_service_report.fsr_run_log_v2"
DQ_LOG = "vaid.ai_std_con_field_service_report.fsr_data_quality_log_v2"

PULSE_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backfill-pulse-log.md")

POLL_SECONDS = 15 * 60  # 15 min between pulses
MAX_HOURS = 6  # hard cap regardless of stop criteria

# Only run-log rows created after this count toward stop criteria — otherwise
# leftover rows from a previous day's test run would falsely satisfy them.
RUN_START_ISO = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat()

# Stop-criteria bookkeeping
p2_triggered = False
vs_triggered = False
p1_batches_seen = set()
p2_batches_seen = set()
clean_stale_streak = 0
any_failure_logged = False


def now_pst():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def append_pulse(text):
    with open(PULSE_LOG, "a") as f:
        f.write("\n" + text + "\n")


def pulse(c):
    global p2_triggered, vs_triggered, clean_stale_streak, any_failure_logged

    queue = c.sql(
        f"SELECT metadata_status, chunk_status, count(*) FROM {METADATA} GROUP BY 1,2 ORDER BY 1,2"
    )
    completed_completed = 0
    completed_pending = 0
    for status_m, status_c, n in queue:
        n = int(n)
        if status_m == "completed" and status_c == "completed":
            completed_completed = n
        if status_m == "completed" and status_c == "pending":
            completed_pending = n

    run_log_rows = c.sql(
        f"SELECT job_name, start_time, docs_claimed, docs_succeeded, docs_failed, "
        f"chunks_written, error_summary FROM {RUN_LOG} "
        f"WHERE start_time > '{RUN_START_ISO}' ORDER BY start_time DESC LIMIT 10"
    )
    dq_rows = c.sql(f"SELECT failure_category, count(*) FROM {DQ_LOG} GROUP BY 1 ORDER BY 2 DESC")
    stale = c.scalar(
        f"SELECT count(*) FROM {METADATA} WHERE chunk_status='in_progress' "
        f"AND chunked_at < current_timestamp() - INTERVAL 60 MINUTES"
    )
    total_chunks = c.scalar(f"SELECT count(*) FROM {CHUNKS}")
    failed_meta = c.scalar(f"SELECT count(*) FROM {METADATA} WHERE metadata_status='failed'")
    failed_chunk = c.scalar(f"SELECT count(*) FROM {METADATA} WHERE chunk_status='failed'")

    if int(failed_meta or 0) > 0 or int(failed_chunk or 0) > 0:
        any_failure_logged = any_failure_logged or bool(dq_rows)

    stale = int(stale or 0)
    if stale == 0:
        clean_stale_streak += 1
    else:
        clean_stale_streak = 0

    for row in run_log_rows:
        job_name = row[0]
        if job_name and "Metadata" in job_name:
            p1_batches_seen.add(row[1])
        if job_name and "Chunking" in job_name:
            p2_batches_seen.add(row[1])

    lines = [
        f"### Pulse — {now_pst()} — Track A (auto)",
        "",
        f"- **Queue:** completed/completed={completed_completed}, completed/pending={completed_pending}",
        f"- **Total chunks:** {total_chunks}",
        f"- **Failures:** metadata_status=failed={failed_meta}, chunk_status=failed={failed_chunk}",
        f"- **DQ log categories:** {dq_rows if dq_rows else 'none yet'}",
        f"- **Stale claims (>60min):** {stale} (clean streak: {clean_stale_streak})",
        f"- **Run log (last 5):** {run_log_rows[:5]}",
        f"- **P1 batches observed so far:** {len(p1_batches_seen)}",
        f"- **P2 batches observed so far:** {len(p2_batches_seen)}",
    ]

    # Kick off P2 once there is something to claim
    if not p2_triggered and completed_completed + completed_pending > 0 and completed_pending > 0:
        run_id = c.run_job(JOBS["p2"], {})
        p2_triggered = True
        lines.append(f"- **Action:** triggered P2 (run_id={run_id}) — {completed_pending} docs pickable")

    # Kick off VS sync once P2 has produced chunks
    if p2_triggered and not vs_triggered and int(total_chunks or 0) > 0:
        run_id = c.run_job(JOBS["vs"], {})
        vs_triggered = True
        lines.append(f"- **Action:** triggered P3/VS sync (run_id={run_id})")

    stop_ready = (
        len(p1_batches_seen) >= 3
        and len(p2_batches_seen) >= 3
        and clean_stale_streak >= 2
        and vs_triggered
    )
    if stop_ready:
        lines.append(
            "- **STOP-READY:** Track A stop criteria met "
            f"(P1 batches={len(p1_batches_seen)}, P2 batches={len(p2_batches_seen)}, "
            f"stale-clean streak={clean_stale_streak}, VS triggered={vs_triggered}, "
            f"failure logged={any_failure_logged}). Cancel P1/P2 runs and close out Track A."
        )

    text = "\n".join(lines)
    print(text, flush=True)
    append_pulse(text)
    return stop_ready


def main():
    c = DbxClient(profile=PROFILE, warehouse_id=WAREHOUSE_ID)
    deadline = time.time() + MAX_HOURS * 3600
    while time.time() < deadline:
        try:
            stop_ready = pulse(c)
        except Exception as e:
            print(f"[{now_pst()}] pulse errored: {e}", flush=True)
            stop_ready = False
        if stop_ready:
            print("Stop criteria met — exiting monitor loop. Job runs left active for a human to cancel.", flush=True)
            break
        time.sleep(POLL_SECONDS)
    else:
        print(f"Hit MAX_HOURS={MAX_HOURS} cap without meeting stop criteria — exiting.", flush=True)


if __name__ == "__main__":
    main()
