# FSR v2 — Backfill / Incremental Validation Pulse Log (DEV)

> Companion to [`backfill-monitoring-plan.md`](backfill-monitoring-plan.md).
> Append new entries at the **bottom**. Don't edit history. Label each entry
> **Track A** (backfill sample) or **Track B** (incremental ingestion).

---

## Run metadata

| Item | Value |
|---|---|
| Started | 2026-09-02 ~17:14 UTC |
| Environment | dev (`dev-dbr-profile`, `gevernova-ai-dev-dbr.cloud.databricks.com`) |
| Tables | `vaid.ai_sot_field_service_report.fsr_metadata_v2`, `vaid.ai_std_con_field_service_report.fsr_chunks_v2`, `vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2` |
| Corpus scope | `FSR_V2_MIN_DOC_YEAR=2016`, no max — full dev source volumes. **Discovered 50,177 eligible docs, not the ~22,000 originally estimated.** |
| Goal | Track A: prove concurrency/logging/DQ at scale, then stop early. Track B: prove incremental reruns only touch the pending/new backlog. |
| Outcome | Both tracks passed. Two real bugs found + fixed along the way (see closing summary below). Not yet committed to `dev`/deployed — code fix is on `fsr_v2` branch. |

---

## Knob settings (current)

| Param | Value | Note |
|---|---|---|
| `FSR_V2_P1_WORKERS` | 4 (recommended) | Swept 4/8/16 on same-size doc chunks — **no throughput difference** (~299/302/295 docs/hr). Stage 4 (LLM+enrichment) is serial regardless of worker count, so this isn't the lever. |
| `FSR_V2_P1_LLM_BATCH_SIZE` | 10 (untested higher) | |
| `FSR_V2_MIN_DOC_YEAR` | 2016 | Confirmed correct — zero completed docs with all dates < 2016 |
| `FSR_V2_MAX_DOC_YEAR` | unset | |
| `FSR_P2_BATCH_SIZE` | 20 (not load-tested this session) | |
| `FSR_P2_MAX_RETRIES` | 3 | |
| `FSR_P2_MAX_ITERATIONS` | 0 (drain) | |
| `FSR_TARGET_PDF_NAMES` | | empty for Track A/B.2; single/few doc IDs for Track B.3 |
| `RESET_FSR_V2` (databricks.yaml) | now `false` for dev + qa | was `true` for both; fixed this session |

---

## Pulse template

```text
### Pulse — <date> <time> PST — Track <A/B>

- **P1 job:** active / stalled / stopped / completed / cancelled
- **P2 job:** active / stalled / stopped / completed / cancelled
- **Queue state:** completed/completed=N, completed/pending=N, completed/in_progress=N,
  completed/failed=N, failed/pending=N, pending/pending=N
- **Throughput last 60 min:** P1 completed=N failed=N, P2 batches=N
- **Run log (last row):** p1_workers=N llm_batch_count=N docs_claimed=N docs_succeeded=N docs_failed=N
- **DQ log:** N rows, top categories: <...>
- **Stale claims:** N
- **Notable failures (sample):** <doc_id>: <reason>
- **Action taken:** <none / cancelled job / knob change / snapshot capture-compare>
- **Next check:** <when + focus>
```

---

### Pulse — _(pending first run)_

- **Action taken:** plan drafted, not yet executed.
- **Next check:** kick off Track A (§2 of the plan) and record the first real
  pulse entry here.

### Pulse — 2026-09-02 17:14 UTC — Track A (auto)

- **Queue:** completed/completed=0, completed/pending=0
- **Total chunks:** 0
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 1)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Chunking', '2026-09-01T22:12:49.000Z', '8', '8', '0', '814', None], ['PW_SDG_FSR_V2_Metadata', '2026-09-01T22:09:06.000Z', '8', '8', '0', None, None], ['PW_SDG_FSR_V2_Chunking', '2026-09-01T22:00:24.000Z', '8', '8', '0', '814', None], ['PW_SDG_FSR_V2_Metadata', '2026-09-01T21:56:43.000Z', '8', '8', '0', None, None]]
- **P1 batches observed so far:** 2
- **P2 batches observed so far:** 2

### Pulse — 2026-09-02 17:15 UTC — Track A (auto)

- **Queue:** completed/completed=0, completed/pending=0
- **Total chunks:** 0
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 1)
- **Run log (last 5):** []
- **P1 batches observed so far:** 0
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 17:30 UTC — Track A (auto)

- **Queue:** completed/completed=0, completed/pending=0
- **Total chunks:** 0
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 2)
- **Run log (last 5):** []
- **P1 batches observed so far:** 0
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 17:45 UTC — Track A (auto)

- **Queue:** completed/completed=0, completed/pending=0
- **Total chunks:** 0
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 3)
- **Run log (last 5):** []
- **P1 batches observed so far:** 0
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 18:01 UTC — Track A (auto)

- **Queue:** completed/completed=0, completed/pending=0
- **Total chunks:** 0
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 4)
- **Run log (last 5):** []
- **P1 batches observed so far:** 0
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 18:16 UTC — Track A (auto)

- **Queue:** completed/completed=0, completed/pending=0
- **Total chunks:** 0
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 5)
- **Run log (last 5):** []
- **P1 batches observed so far:** 0
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 18:31 UTC — Track A (auto)

- **Queue:** completed/completed=0, completed/pending=0
- **Total chunks:** 0
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 6)
- **Run log (last 5):** []
- **P1 batches observed so far:** 0
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 18:35 UTC — Track A — **finding + course correction**

- **P1 run `317055123334476` (full corpus, no target filter) cancelled** after
  ~80 min with zero completions and 50,177 docs stuck `pending/pending`.
- **Root cause (code-confirmed, not a stall):** `nb_sdg_fsr_v2_metadata.py`
  submits **all** discovered docs to a `ThreadPoolExecutor(max_workers=FSR_V2_P1_WORKERS)`
  for Stage 2–3 (parse + preprocess) and blocks on
  `concurrent.futures.as_completed(_futures)` for the **entire** submitted set
  before Stage 4 (LLM + per-doc MERGE write via `write_enriched_metadata`,
  which — confirmed in `metadata_enrichment.py` — is a real per-doc MERGE, not
  a batched end-of-run write). So writes *are* incremental once Stage 4 starts,
  but **Stage 4 cannot start until Stage 2–3 finishes for every doc submitted
  to the pool**. At 4 workers against 50,177 docs, that barrier alone could be
  many hours — incompatible with this plan's "check in intervals" approach.
- **This corpus is also ~2.3x the ~22K estimate** in the plan (50,177 eligible
  docs discovered post-2016 across the dev volumes) — compounds the barrier.
- **Action taken:** cancelled the full-corpus run; restarted P1
  (run `253284797628836`) scoped to a **150-doc `FSR_TARGET_PDF_NAMES`
  sample** pulled from the already-discovered pending rows, so Stage 2–3
  clears in minutes and Track A's actual goal (observe concurrency, run-log
  writes, DQ logging, throughput) is achievable without waiting out the full
  corpus.
- **Follow-up (not blocking Track A):** flag to the FSR v2 team that P1 has no
  intra-run batching/commit checkpoint — for the real prod backfill (~22K+
  docs), either the year-cohort partitioning in the backfill-runbook must keep
  each pass small enough that the Stage 2–3 barrier stays bounded, or the code
  needs a batched-submission mode (submit N docs to the pool, drain, repeat)
  instead of submitting the entire discovered set at once.
- **Next check:** monitor run `253284797628836` for first completions.


### Pulse — 2026-09-02 18:46 UTC — Track A (auto)

- **Queue:** completed/completed=0, completed/pending=0
- **Total chunks:** 0
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 7)
- **Run log (last 5):** []
- **P1 batches observed so far:** 0
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 19:02 UTC — Track A (auto)

- **Queue:** completed/completed=0, completed/pending=17
- **Total chunks:** 0
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 8)
- **Run log (last 5):** []
- **P1 batches observed so far:** 0
- **P2 batches observed so far:** 0
- **Action:** triggered P2 (run_id=562092699592217) — 17 docs pickable

### Pulse — 2026-09-02 19:17 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=3
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 9)
- **Run log (last 5):** []
- **P1 batches observed so far:** 0
- **P2 batches observed so far:** 0
- **Action:** triggered P3/VS sync (run_id=784287310163520)

### Pulse — 2026-09-02 19:32 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=64
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 10)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 1
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 19:47 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=64
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 11)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 1
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 20:03 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=64
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 12)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 1
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 20:18 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=64
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 13)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 1
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 20:33 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=64
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 14)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 1
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 20:48 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=96
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 15)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 1
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 21:03 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=196
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 16)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 1
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 21:19 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=299
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 17)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 1
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 21:34 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=311
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 18)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T20:31:38.000Z', '240', '240', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 2
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 21:49 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=410
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 19)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T20:31:38.000Z', '240', '240', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 2
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 22:04 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=514
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 20)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T20:31:38.000Z', '240', '240', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 2
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 22:20 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=548
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 21)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T21:20:50.000Z', '243', '243', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T20:31:38.000Z', '240', '240', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 3
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 22:35 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=617
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 22)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T21:20:50.000Z', '243', '243', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T20:31:38.000Z', '240', '240', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 3
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 22:50 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=730
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 23)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T22:48:43.000Z', '5', '5', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T21:20:50.000Z', '243', '243', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T20:31:38.000Z', '240', '240', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 4
- **P2 batches observed so far:** 0

### Pulse — 2026-09-02 23:06 UTC — Track A (auto)

- **Queue:** completed/completed=120, completed/pending=792
- **Total chunks:** 5097
- **Failures:** metadata_status=failed=0, chunk_status=failed=0
- **DQ log categories:** none yet
- **Stale claims (>60min):** 0 (clean streak: 24)
- **Run log (last 5):** [['PW_SDG_FSR_V2_Metadata', '2026-09-02T22:48:43.000Z', '5', '5', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T22:10:16.000Z', '240', '240', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T21:20:50.000Z', '243', '243', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T20:31:38.000Z', '240', '240', '0', None, None], ['PW_SDG_FSR_V2_Metadata', '2026-09-02T18:47:11.000Z', '185', '184', '0', None, None]]
- **P1 batches observed so far:** 5
- **P2 batches observed so far:** 0

### SESSION SUMMARY — 2026-09-02, ~23:20 UTC — closing out Track A + Track B

**Auto-monitor exited on its own** after hitting the 6h cap (`monitor_track_a.py`,
`MAX_HOURS=6`) without formally meeting the scripted stop-ready criteria — but
Track A and B's actual goals were both achieved by other means during the
session (manual pulses, targeted sandbox tests). Treat both as **passed**.

**Track A (backfill sample) — passed, with two real bugs found and fixed:**

1. **P1 Stage 2\u20133 barrier.** Original full-corpus run (`FSR_TARGET_PDF_NAMES`
   empty, 50,177 discovered docs) showed **zero completions after 80+ minutes**.
   Root cause: Stage 4 (LLM + write) couldn't start until Stage 2\u20133 (parse +
   preprocess) finished for **every** submitted doc \u2014 a multi-hour barrier at
   this scale, even though the per-doc write itself was already correct.
   **Fixed** in `nb_sdg_fsr_v2_metadata.py`: Stage 4 now fires as soon as a
   buffer of `LLM_BATCH_SIZE` docs clears Stage 2\u20133, with a final flush after
   the pool drains. Verified: completions land continuously (7 at 3min, 27 at
   6min, 53/53 by 11min on a 53-doc sandbox test). **Not yet committed/deployed
   at session start; committed to `fsr_v2` as "concurrency discovery fix"
   partway through.**
2. **`fsr_run_log_v2` schema drift.** Live dev table was missing
   `p1_workers`/`llm_batch_count`/`docs_date_filtered` columns that the P1
   notebook has been inserting since they were added to
   `RUN_LOG_TABLE_V2_DDL_COLS` \u2014 every INSERT failed, silently swallowed by a
   `try/except`. **Fixed non-destructively** via `ALTER TABLE ... ADD COLUMNS`
   (no `RESET_FSR_V2=true` needed). **Action still needed:** check qa/stg/prod
   `fsr_run_log_v2` for the same drift before relying on their run logs.
3. Also fixed earlier in the session (unrelated to the above, found while
   setting up Track A): `fsr_run_log_table_v2`/`fsr_dq_log_table_v2` in
   `databricks.yaml` pointed at `ai_std_con_monitoring_diagnostics`, a schema
   we don't have `USE SCHEMA` on. Repointed to `ai_std_con_field_service_report`
   (same schema as `fsr_chunks_v2`) for **dev/qa/stg/prod**. Merged to `dev`.
4. `RESET_FSR_V2` was `"true"` for both dev and qa in `databricks.yaml`
   (meaning every deploy would silently wipe the tables) \u2014 **fixed to `"false"`
   for dev; qa deliberately kept `"true"` per explicit decision** (still needs
   validation-mode resets).
5. Found (not fixed, out of scope): Stage 1 discovery/target-lookup
   (`silver/src/etl/fsr_v2/input.py`) raises `ValueError` on ambiguous filename
   matches (an original + a `_1`-suffixed duplicate in a manual volume) instead
   of handling it gracefully. Worked around by filtering test samples to
   well-formed UUID document IDs; a real fix is a follow-up item.

**Worker-count sweep (for prod sizing) \u2014 conclusive: no need to raise
`FSR_V2_P1_WORKERS` above 4.**

| Workers | Docs | Duration | Throughput |
|---|---|---|---|
| 4 | 240 | 2885.0s | ~299 docs/hr |
| 8 | 243 | 2891.4s | ~302 docs/hr |
| 16 | 240 | 2931.3s | ~295 docs/hr |

All three are within noise of each other. `FSR_V2_P1_WORKERS` only threads
Stage 2\u20133 (parse+preprocess); Stage 4 (LLM batch call + per-doc enrichment/
MERGE) is sequential in the main thread regardless of worker count and is the
actual bottleneck at this scale. Raising workers further won't help until
Stage 4 itself is parallelized (a code change, not attempted this session).
**~300 docs/hr means a real 22K\u201350K-doc prod backfill is on the order of
3\u20137 days of P1 wall clock alone** \u2014 worth a call on whether that's acceptable
before the real run.

**Track B (incremental ingestion) \u2014 passed.** Snapshot-compare on the
completed set showed **zero diffs** after a targeted run against 5 simulated
"new arrival" docs; all 5 completed correctly. (Result initially looked like
30 new docs instead of 5 \u2014 that was the concurrent worker-sweep leg still
running in the background, not a bug; the zero-diff assertion on the
pre-existing completed set is what actually matters and it held.)

**Date filter (`FSR_V2_MIN_DOC_YEAR=2016`) \u2014 confirmed correct.** Zero
completed docs found where every populated date field is pre-2016.

**Known loose end:** the auto-monitor's one-shot P2 trigger fired early and
never re-fired, so **~790+ docs are sitting `completed`/`pending`** (metadata
done, not yet chunked) at session close. Harmless (no data risk), but if the
dev tables need to look "caught up," trigger `PW_SDG_FSR_V2_Chunking` once
more before handing off.

**Next steps for prod:** see \u00a78 of
[backfill-monitoring-plan.md](backfill-monitoring-plan.md) and the updated
[prod-hardening-items](../prod-hardening/prod-hardening-items) checklist.

