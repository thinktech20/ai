# FSR v2 — QA Backfill Tracker

**Living document. Update it as things happen, don't rewrite history.**
The "how" lives in [qa-backfill-autonomous-plan.md](qa-backfill-autonomous-plan.md);
this is "where are we". Root cause is in
[equipment-map-gap-analysis.md](equipment-map-gap-analysis.md); per-check detail
in [backfill-pulse-log.md](backfill-pulse-log.md).

---

## Status at a glance

| | |
|---|---|
| **Current phase** | Phase 5 — backfill running, ~94.8% screened |
| **Jobs** | P1 `755284584309920` running since 2026-09-11 06:42 UTC · P2 not active; last P2 run `105184451113165` succeeded |
| **Blocked on** | nothing visible — P1 is actively moving; P2 needs another drain after more metadata completes |
| **Last updated** | 2026-09-11 14:32 UTC |

**One-line summary:** QA backfill is close to finishing P1. P1 has ~2,600 docs
left to screen, P2 is behind but cleanly idle, stale claims are zero, and the
equipment-map gate has a small active-run gap to recheck after P1 stops.

### Live snapshot — 2026-09-11 14:32 UTC

| Metric | Value |
|---|---|
| Corpus | 50,177 |
| Metadata completed | 22,198 |
| Date-filtered (pre-2016) | 25,292 |
| Metadata failed | 73 |
| **Pending** | **2,614** |
| Chunked + embedded | 19,772 |
| Chunk rows | 774,686 |
| Equipment-map rows | 23,406 |
| Gate | 15 real missing map rows while P1 is active — recheck after P1 stops |
| Throughput | ~359 docs/hr completions, ~391 docs/hr overall screening over the last 60 min |
| **Est. remaining** | **~6.7 h of P1 runtime** |

### Pulse — 2026-09-11 14:32 UTC — Phase 5

- **P1 job:** active — `PW_SDG_FSR_V2_Metadata`, run `755284584309920`, started
  2026-09-11 06:42 UTC.
- **P2 job:** not active — last run `105184451113165` succeeded at
  2026-09-11 06:44 UTC in ~1.8 min.
- **P3 / VS sync:** last successful `PW_SDG_FSR_V2_VS_Index` run was
  2026-09-03 17:00 UTC.

| Metadata status | Chunking & embeddings status | Docs |
|---|---|---:|
| completed | completed | 19,772 |
| completed | failed | 120 |
| completed | pending | 2,306 |
| date_filtered | pending | 25,292 |
| failed | pending | 73 |
| pending | pending | 2,614 |

`date_filtered` means P1 opened the document, found it outside the configured
backfill year window, and marked it terminal/out of scope. These documents are
not expected to move into chunking and embeddings.

| Check | Result |
|---|---:|
| P1 screened | 47,563 / 50,177 (~94.8%) |
| P1 last 60 min | 359 completed, 31 date-filtered, 1 failed |
| P2 last 60 min | no activity |
| Completed-before-2016 violations | 0 |
| Stale chunk claims older than 60 min | 0 |
| Completed metadata docs with chunks | 19,772 / 22,199 (89.07%) |
| Completed metadata docs with map rows | 18,653 / 22,199 (84.03%) |
| Real equipment-map gap | 15 |
| Metadata failures | 73 docs, all at retry count 1 |
| Chunk failures | 119 docs at retry count 3; 1 doc at retry count 10 |
| DQ log categories | `WARN no_text_layer_suspected_scan` = 1,276; `FAIL metadata_pipeline_error` = 73 |

**Next action:** let P1 continue. After it stops, trigger P2 to drain the
`completed`/`pending` backlog, recheck `missing_map_rows_real`, run the repair
job if the gap persists, then run P3 / VS sync.

### Historical handover — PR #244

> Historical note from 2026-09-09; no longer the current QA status.

[PR #244](https://github.apps.gevernova.net/GEV-SoX-DataBricks/pw_sdg_ai_ser_repo/pull/244)
(P2 conflict retry + stale reclaims count as attempts) is with Namruth. He will:

1. Stop both jobs
2. Merge and deploy to QA
3. Restart P1 and P2

**No repair step needed in that sequence.** The equipment-map repair does not
expire — everything it rebuilds from stays on `fsr_metadata_v2` permanently — so
one pass at the end of the backfill sweeps up every straggler accumulated across
all interruptions. Phase 6's correctness gate fails if it is forgotten.

Cost of his cancellation: ≤10 documents stranded without map rows (one LLM
batch), and ≤20 left `chunk_status='in_progress'` which self-heal after the
30-minute stale threshold.

---

## QA facts (measured 2026-09-08)

| Thing | Value |
|---|---|
| Profile | `ai-qa-dbr` (PAT) |
| Host | `gevernova-ai-qa-dbr.cloud.databricks.com` |
| SQL warehouse | `ai-pw-ser-ds-qa-sqlw` = `7edab8ce9d0a056b` |

| Stage | Job | QA job ID |
|---|---|---|
| DDL | `PW_SDG_FSR_V2_DDL` | `334275972250035` |
| P1 | `PW_SDG_FSR_V2_Metadata` | `761501966564581` |
| P2 | `PW_SDG_FSR_V2_Chunking` | `281692486694630` |
| P3 | `PW_SDG_FSR_V2_VS_Index` | `21697534238749` |
| Ingestion (chained) | `PW_SDG_FSR_V2_Ingestion` | `1042416268045266` |
| Validation | `PW_SDG_FSR_V2_Validation` | `120006218056054` |
| Repair | `PW_SDG_FSR_V2_Repair_Equipment_Map` | `371245630002583` |
| Adhoc ingestion | `PW_SDG_FSR_V2_Ingestion_Adhoc` | `849170297574792` |

**Permissions:** `vaiq` grants `SELECT` only (two consumer groups) plus `BROWSE`
for account users. **No `MODIFY` at catalog, schema or table level.** Tables are
owned by `service.globalopsfsso@gevernova.com`. The caller has `CAN_MANAGE` on
the FSR v2 jobs, so **anything that writes must go through a deployed job**,
not an interactive run.

---

## Key numbers — measured 2026-09-08

| Metric | Value | Note |
|---|---|---|
| Total docs in queue | **50,177** | exactly matches dev — QA reads the same `viud` volumes |
| `completed` / `completed` | **8,737** | |
| `completed` / `failed` (chunking) | **50** | |
| `pending` / `pending` | **41,390** | |
| `metadata_status='failed'` | **0** | see "what the data confirms" below |
| `metadata_status='date_filtered'` | **0** | see below — this is a finding, not a healthy state |
| Completed docs total | 8,787 | |
| Equipment-map rows | **9,280** (after repair) | was 0 |
| `missing_but_no_esn` (expected floor) | **1,424** | correctly unmapped, no repair needed |
| **`missing_map_rows_real`** | **0** (after repair) | was 7,363 |
| Chunk rows | 350,403 across 8,737 docs | ~40 chunks/doc |
| `chunk_retry_count` distribution | 49 docs at 3, **1 doc at 10** | |
| Failure reasons | 49 × "Chunker produced 0 chunks", 1 × "embed failure" | |
| Run log rows | **0** | schema is correct — rows never written |
| DQ log rows | **0** | lost, as predicted |
| Source catalog | `viud` for all 50,177 | confirms the §1 decision |
| P1 throughput | ~300 docs/hr | measured in **dev**, not QA |
| Repair elapsed time | **49 s** for 7,363 docs | measured |

### What the data confirms

- **The equipment-map gap is real and large.** 7,363 docs with a known ESN and
  no map row. The table is completely empty.
- **The end-of-run write bug is visible three more ways.** Zero `date_filtered`
  and zero `metadata_status='failed'` despite 8,787 docs processed, and zero run
  log rows despite two multi-hour runs. All three writes sit at the end of the
  notebook and the runs were cancelled before reaching them. The run log schema
  is *correct* — QA does **not** have the drift dev had — so an empty run log is
  cancellation, not drift.
- **The P2 `embed_failures` leak is confirmed, but it only hit one document.**
  `max_retries=3`, yet one doc sits at `chunk_retry_count=10` with the generic
  `"embed failure"` message — the exact signature of the unscoped re-marking
  (`doc_errors.get(did, "embed failure")` fallback). It cannot happen without
  the bug. **I over-estimated the blast radius**: I expected counts in the
  hundreds across many docs. Only one doc ever hit an embedding failure, so the
  damage was one document, not thousands. The fix was still correct; the
  severity was not.
- **The other 49 failures are genuine** — "Chunker produced 0 chunks", capped at
  3 retries as designed. Worth investigating separately, but not this incident.
- **All 41,390 pending docs have `doc_year IS NULL`**, meaning they were
  stub-registered but never screened. Based on dev, roughly half will turn out
  to be pre-2016 and get `date_filtered`, so the real remaining work is well
  under 41,390.

---

## Checklist

### Phase 0 — Access and facts

- [x] QA profile `ai-qa-dbr` added, authenticates as `madhurima.saxena`
- [x] QA SQL warehouse ID — `7edab8ce9d0a056b`
- [x] QA job IDs found — see the facts table above
- [x] Confirmed P1 and P2 are stopped (no run log rows, no active runs)
- [x] ~~Source volume question~~ — **settled: QA reads `viud` by design**, and
      all 50,177 docs confirm it

### Phase 1 — Measure

- [x] 1.1 Queue state
- [x] 1.2 Equipment-map gap — **7,363 real, 1,424 no-ESN floor**
- [x] 1.3 `chunk_retry_count` distribution — leak confirmed, 1 doc affected
- [x] 1.4 Failure-reason breakdown
- [x] 1.5 Run log + DQ log — **both empty**, nothing to capture
- [x] 1.6 `DESCRIBE fsr_run_log_v2` — **no drift**, schema is correct
- [x] Key-numbers table filled in

### Phase 2 — Ship

- [x] Fixes committed to `fsr_v2` (`51270b4`, 2026-09-08)
- [x] Pushed to origin
- [x] PEP 701 nested-quote check — 0 suspects
- [x] Merged `fsr_v2` → `dev` and deployed to QA
- [ ] **New:** `workflows/fsr_v2/pw_sdg_fsr_v2_repair_equipment_map.yml` written
      — needs commit, merge to `dev`, deploy. **Phase 3 is blocked on this.**
- [ ] Confirm `FSR_V2_P1_MAX_DOCS` is in the QA P1 job's declared parameters
- [ ] Confirm the validation notebooks landed in the QA workspace

### Phase 3 — Repair

Target was **7,363 docs**. Ran as job `371245630002583` (service account).

- [x] Repair job deployed to QA
- [x] Dry run — SUCCESS, 45s
- [x] Expected result computed independently in SQL: **9,280 rows / 7,363 docs**
- [x] Applied with `REPAIR_DRY_RUN=false` — SUCCESS, **49s**
- [x] **Actual: 9,280 rows / 7,363 docs — exact match**
- [x] **Gate passed:** `missing_map_rows_real = 0` (1,424 no-ESN floor remains,
      correctly unmapped)
- [x] Integrity: 0 duplicate `(document_id, esn)`, 0 blank ESNs, 0 docs with
      multiple primaries, 0 orphans
- [ ] Retry-count repair — 1 doc at `chunk_retry_count=10`, still stuck
- [ ] Decide whether to retry the 49 genuine "0 chunks" failures

**Repair elapsed time: 49 seconds for 7,363 docs.** Use this for prod planning —
the repair is cheap; it is the reprocessing alternative that would have been
expensive.

### Phase 4 — Reset

- [x] **Does not apply** — see plan §1. QA reads the right volumes; nothing is
      irreparably corrupted; a reset would discard ~27h of completed work.

### Phase 5 — Continue the backfill

- [x] Slice 1 (5,000 docs, run `383940967536807`) — SUCCESS, 18 min. 4,981
      date-filtered, 19 failed, **0 succeeded** — hit a block of 2000-2012 docs,
      so the map write was not exercised
- [x] **Per-batch equipment-map write proven under load** (slice 2, run
      `866234081266045`): map went 9,280 → 9,292 rows / 7,363 → 7,372 docs as
      completions landed. Gate rose to 9 mid-batch then returned to 0 — the
      bounded window behaving exactly as designed
- [x] Run log, date-filter and DQ writes all confirmed working (slice 1)
- [ ] Slice 2 completion
- [ ] Remaining slices
- [ ] P2 triggered once completions accumulate
- [ ] P3 / VS sync

**Gate nuance learned live:** `missing_map_rows_real` is only required to be 0
**when no P1 run is active**. While P1 runs, up to `FSR_V2_P1_LLM_BATCH_SIZE`
documents can legitimately show as unmapped — metadata is written per document
inside a batch, the map once per batch. A gap that is small and clears quickly
is normal; one that grows or persists is not.

> **Operational rule — run the repair job after any cancelled or crashed P1.**
> Confirmed on real data 2026-09-08: cancelling run `866234081266045` left
> **5 documents** permanently unmapped — its final in-flight LLM batch had
> written their metadata but not yet its map rows. That is the fix working as
> designed (5 lost, not 8,787), but those 5 are `completed`, so Stage 1 will
> never re-queue them and the gate stays non-zero forever without a repair.
> The repair takes 49 seconds and is idempotent, so there is no reason to skip
> it. Open item 11 would automate this away.

Params: `FSR_V2_P1_MAX_DOCS=5000`, `FSR_V2_P1_WORKERS=4`,
`FSR_V2_P1_LLM_BATCH_SIZE=10`, `FSR_V2_MIN_DOC_YEAR=2016`,
`FSR_TARGET_PDF_NAMES` empty, `RESET_FSR_V2=false`.

- [ ] P1 slice 1 triggered
- [ ] **After slice 1, before slice 2:** confirm the equipment map kept pace
      (hourly completed-vs-mapped query). This is the direct test of the fix.
- [ ] P2 started
- [ ] P3 / VS sync run at least once
- [ ] Pulse check every 1–2h, appended to the pulse log

Slice log — add a row per run:

| # | Date | Job run ID | Docs done | Duration | Consistency | Notes |
|---|---|---|---|---|---|---|
| 1 | | | | | | |

### Phase 6 — Sign-off

- [ ] Correctness gate with `STRICT_QUEUE_DRAINED=true` and
      `EXPECTED_COMPLETED_DOCS` set
- [ ] Zero FAIL; SKIPs explained
- [ ] Closing entry in the pulse log
- [ ] Prod carry-forward items raised

---

## Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-09-08 | **Repair, don't reset** | Nothing is irreparably corrupted. Metadata rows are correct, the map rebuilds exactly from `preprocessor_regions`, retry counts reset with an UPDATE, and chunks were never partial (`FSR_EMBED_FAIL_THRESHOLD=0.0`). Reset would discard ~27h of P1 work plus the LLM spend for no gain. |
| 2026-09-08 | **QA reads `viud` deliberately** | Confirmed intentional. The `TODO: confirm QA ingestion catalog (likely viuq)` in `databricks.yaml` is stale. Removes the only reset trigger. |
| 2026-09-08 | **Cap runs at 5,000 docs** | ~17h per run vs ~7 days for the full corpus. Bounds wall clock, driver memory, and how much is in flight when something fails. Re-running continues rather than restarts. |
| 2026-09-08 | **Keep the P2 hardening, not just the scope fix** | Only the `embed_failures` scoping is load-bearing; the `in_progress` guards, batch-scoped failed write, and partial-coverage check are defensive. Kept because they're small and the guards matter if P2 is ever run concurrently. |
| 2026-09-08 | **Don't trim the P1 job's parameter list yet** | Three params (`INPUT_MODE`, `FSR_V2_PARSER_VERSION`, `FSR_V2_METADATA_PROCESSOR_VERSION`) accept exactly one value and are noise, but changing a deployed job's parameter surface mid-incident isn't worth it. Revisit after the backfill. |
| 2026-09-09 | **Never run standalone P1 and the chained ingestion job at the same time** | P1 has no claim mechanism, so two concurrent runs would both claim the same `pending` rows. Because LLM extraction is not deterministic, overlapping runs could leave a document's metadata and its equipment-map rows disagreeing — not just doubled cost. Neither job is scheduled, so both are trigger-only and this is enforceable by process. Chosen over a same-day DDL + status-machine change on prod-promotion day. **Switchover rule: stop standalone P1/P2 and confirm no active runs before enabling the daily ingestion job.** |

---

## Open items

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | ~~Deploy `pw_sdg_fsr_v2_repair_equipment_map.yml`~~ | | **done** — job `371245630002583`, repair applied |
| 2 | ~~QA profile~~ | | **done** — `ai-qa-dbr` |
| 2b | Investigate the 49 "Chunker produced 0 chunks" failures — genuine, unrelated to this incident | | new |
| 3 | `ai-arch` docs not committed — deliberate, do later | | deferred |
| 4 | Stale `TODO: confirm QA ingestion catalog` in `databricks.yaml` | | cosmetic |
| 5 | **P1 has no claim mechanism** — two concurrent P1 runs would double-process. `max_concurrent_runs: 1` is per-job, so the exposure is the standalone `PW_SDG_FSR_V2_Metadata` and the chained `PW_SDG_FSR_V2_Ingestion` running the same notebook at once. **Controlled operationally — decision 2026-09-09: those two jobs are never run simultaneously.** Neither has a schedule, so both are trigger-only. Code fix (a `claimed_by` column, an `in_progress` status, P1 stale recovery) deferred to a tested follow-up PR. | | **operationally controlled; code fix deferred** |
| 6 | ~~P2 has no MERGE conflict retry / TOCTOU claim~~ | | **fixed** in PR #244 — retry moved to `common/fsr_v2/delta_retry.py`, all 5 P2 writes wrapped. TOCTOU half still needs a `claimed_by` column (see item 5) |
| 7 | ~~Stale-claim recovery doesn't increment `chunk_retry_count`~~ | | **fixed** in PR #244 |
| 8 | Check **prod** for the same equipment-map gap once QA is proven | | after Phase 6 |
| 9 | Check qa/stg/prod `fsr_run_log_v2` for the schema drift found in dev | | **QA checked — no drift.** stg/prod still open |
| 10 | Stage 1 discovery raises on ambiguous filenames (`_1`-suffixed duplicates) | | pre-existing, unfixed |
| 11 | **Make P1's Stage 5 reconciliation self-healing.** It currently only warns on drift. It already has `_build_map_rows` and runs as the service account, so it could repair the gap instead of reporting it — removing the manual post-interruption step entirely. | | new 2026-09-08 |
| 12 | One doc has `primary_esn = 123456`, which looks like placeholder rather than a real serial | | incidental, low priority |

---

## Update log

Append; don't edit earlier entries.

### 2026-09-08 — incident found, fixes written and pushed

- Equipment-map gap reported by Namruth; root cause confirmed in code. P1 wrote
  the map once at end of run from in-memory state, so an interrupted run left
  `completed` docs with no map rows and no way to be re-queued.
- Found two more P1 defects while confirming: futures retained for the whole run
  (the driver OOM), and an unbounded `IN (...)` MERGE predicate.
- Found a separate P2 defect: `embed_failures` declared outside the batch loop,
  so one embedding failure re-marked a doc failed once per later batch and
  blocked it from ever succeeding in that run.
- Also found the same end-of-run write pattern for failure rows, date-filter
  rows and DQ rows in P1 — meaning an interrupted run recorded no failures at
  all, so retry counts stayed 0 and the cap never engaged.
- Fixes committed `51270b4`, pushed to `fsr_v2`. Rebased onto `88a2056`
  ("update FSR v2 prod table as per the policy") — clean, different regions of
  `databricks.yaml`.
- Added three validation notebooks: pulse check, correctness gate, equipment-map
  repair. None need credentials.
- **Noted from `88a2056`:** prod metadata + equipment-map moved to
  `ai_std_con_field_service_report`, run/DQ logs to `ai_sot_field_service_report`
  — prod now matches QA's layout. Dev is the odd one out. Worth remembering when
  reading queries written against dev.
- Nothing run against QA. No numbers measured.

### 2026-09-08 (later) — Phase 0 and Phase 1 complete against QA

- QA profile `ai-qa-dbr` created; warehouse and all seven FSR v2 job IDs found.
- **Equipment-map gap confirmed and sized: 7,363 docs** need repair; 1,424 are
  correctly unmapped (no ESN anywhere); the map table has 0 rows.
- **Permissions blocker found.** `vaiq` grants `SELECT` only — no `MODIFY` at
  catalog, schema or table level. Tables are owned by
  `service.globalopsfsso@gevernova.com`. So the repair notebook **cannot** be
  run interactively; it needs a deployed job with
  `run_as: service.globalopsfsso`. Written
  (`workflows/fsr_v2/pw_sdg_fsr_v2_repair_equipment_map.yml`), not yet merged.
  This was flagged as "probably, needs verifying" earlier — verified, and the
  answer was no.
- **P2 leak confirmed but tiny.** One doc at `chunk_retry_count=10` against a
  cap of 3, with the generic "embed failure" message — only possible via the
  unscoped re-marking. Earlier severity estimate ("possibly hundreds") was
  wrong: only one document ever hit an embedding failure.
- **The end-of-run write bug is visible in three more places**: zero
  `date_filtered`, zero `metadata_status='failed'`, zero run log rows, all
  despite 8,787 docs processed over two multi-hour runs.
- **QA run log has no schema drift** — unlike dev. The empty run log is
  cancellation, not drift.
- 49 genuine chunking failures ("Chunker produced 0 chunks") at the retry cap —
  unrelated to this incident, worth a separate look.

### 2026-09-08 (evening) — repair applied, fixes proven under load

- **Repair applied:** 9,280 rows / 7,363 docs in **49 s**, matching an
  independently written SQL reimplementation exactly. Gate to 0. Attribute
  checks clean (`is_primary_esn` 0 errors both directions,
  `source_region_count` 0 mismatches across 6,807 pairs). The 94% null
  `technology_code` is faithful — only 4,587 of 64,515 source regions carry one.
- **Per-batch map write proven under load.** Watched the map grow with
  completions and the gate return to 0 after a batch flushed. The transient
  peaked at 9 — one LLM batch — versus the whole run before the fix.
- **Slice loop proven.** Run `515043957926651` processed 6,220 docs against a
  slice size of 2,000, so it cleared multiple slices on a single trigger.
- **Residual window confirmed real.** Cancelling run `866234081266045` left
  **5 documents** permanently unmapped from its final in-flight batch. Bounded
  as designed, but permanent without a repair — hence the operational rule
  above and open item 11.
- Throughput better than first estimated: ~217 docs/hr through the LLM path
  (early sample suggested 116). Overall screening ~2,195 docs/hr, since ~90% of
  the remaining corpus is pre-2016 and only costs a page-1 probe.
- QA run log has **no schema drift** — unlike dev. An empty run log was
  cancellation, not drift.

### 2026-09-11 14:32 UTC — pulse check, P1 near finish

- P1 is running as `PW_SDG_FSR_V2_Metadata` run `755284584309920`, started
  2026-09-11 06:42 UTC. P2 is not active; latest P2 run
  `105184451113165` succeeded quickly at 2026-09-11 06:44 UTC.
- Queue is 50,177 total docs: 22,198 metadata completed, 25,292 date-filtered,
  73 metadata failed, and **2,614 pending**. P1 is ~94.8% screened.
- Last 60 min: P1 screened 391 docs total (359 completed, 31 date-filtered,
  1 failed). P2 had no last-hour activity.
- Chunking coverage is 19,772 / 22,199 completed metadata docs (89.07%).
- Equipment-map coverage is 18,653 / 22,199 completed metadata docs (84.03%).
  `missing_map_rows_real = 15`; because P1 is active, treat this as a small
  active-run gap and recheck after P1 stops.
- Stale chunk claims = 0; completed-before-2016 violations = 0.
- Next: let P1 finish, trigger P2 to drain `completed`/`pending`, rerun the
  equipment-map gate, repair if still non-zero, then run P3 / VS sync.
