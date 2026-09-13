# FSR v2 — QA backfill equipment-map gap: analysis

**Date:** 2026-09-08 · **Environment:** QA · **Status:** root cause confirmed,
fixes written on `fsr_v2`, repair not yet applied

Companion docs: [backfill-monitoring-plan.md](backfill-monitoring-plan.md) §9
(checks, repair procedure, sizing), [backfill-pulse-log.md](backfill-pulse-log.md)
(the incident pulse entry),
[qa-backfill-autonomous-plan.md](qa-backfill-autonomous-plan.md) (the phased
recovery), [qa-backfill-tracker.md](qa-backfill-tracker.md) (live status),
[../qa-backfill/log.txt](../qa-backfill/log.txt).

---

## 1. Symptom

FSR v2 metadata (P1) and chunking (P2) were run in parallel in QA to backfill
documents from 2016 onward.

- P1 ran ~26h — restarted once mid-way after a driver out-of-memory — then
  cancelled.
- P2 ran ~23h, then cancelled.
- `vaiq.ai_std_con_field_service_report.fsr_metadata_v2` held **~8,000
  documents**.
- `vaiq.ai_std_con_field_service_report.fsr_document_equipment_map_v2` held
  **zero rows**.

Reported by Namruth on Slack. The analysis below independently confirms his
reading of the code and adds two further defects found while checking it.

---

## 2. Root cause

In `silver/src/etl/nb_sdg_fsr_v2_metadata.py`, the two tables had **different
durability guarantees**:

| Table | When written |
|---|---|
| `fsr_metadata_v2` | **Per document**, as each one completes — a real MERGE inside `write_enriched_metadata` (`silver/src/etl/fsr_v2/metadata_enrichment.py`) |
| `fsr_document_equipment_map_v2` | **Once**, in a single bulk MERGE in the notebook's last cell ("Stage 5"), from a `map_rows` list accumulated in driver memory across the whole run |

Consequences:

1. If the run is interrupted anywhere before that final cell, every document
   already at `metadata_status='completed'` has **no** equipment-map row.
2. Stage 1 only re-queues documents that are `pending` or retry-eligible
   `failed`. Documents at `completed` are never revisited. So the gap is
   **permanent** without a manual backfill — a later rerun will not heal it.

Both interruptions in this run (the OOM restart, then the cancel) landed before
Stage 5. That is why the map is at **zero** rather than partially filled: the
cell never ran at all, in either attempt.

This is a design asymmetry, not a transient failure. Any interruption — cancel,
OOM, cluster loss, LLM outage that aborts the notebook — produces it.

---

## 3. Two contributing defects found while confirming

### 3.1 Driver OOM

```python
_futures = {_pool.submit(_stage2_stage3, doc): doc for doc in docs}
for _idx, _future in enumerate(concurrent.futures.as_completed(_futures), start=1):
    _doc_id, _parsed_doc, _proc_out, _err, _date_filtered = _future.result()
```

Every `Future` stayed in `_futures` for the whole run, and a `Future` holds its
result until released. Each result carries the parsed PDF's **full page text**.
So driver memory grew with corpus size instead of staying bounded by
`FSR_V2_P1_LLM_BATCH_SIZE`, which is the only thing the design intends to hold
in memory at once. This is the likely cause of the OOM that forced the restart.

### 3.2 Unbounded MERGE predicate

Stage 5 built its delete predicate by string-joining every successful doc id:

```python
ids_sql = ", ".join(f"'{did}'" for did in success_ids)
... WHEN NOT MATCHED BY SOURCE AND tgt.document_id IN ({ids_sql}) THEN DELETE
```

At 8K+ documents that is a multi-megabyte SQL statement. Independent of the
timing problem in §2, this is a second way the same cell fails at corpus scale —
so even a run that reached Stage 5 cleanly was not safe.

### 3.3 No per-run document cap

FSR v1 has `FSR_MAX_PDFS` (`common/fsr_config.py`, applied in
`nb_sdg_fsr_metadata.py`). FSR v2 had no equivalent. The only available mode was
"process the entire ~50K-doc queue in one run", which at the measured ~300
docs/hr is multiple days of wall clock in a single fragile unit of work. Raised
by Namruth in the same message; valid.

---

## 4. Fix

### 4.1 Code (branch `fsr_v2`, not yet merged or deployed)

| # | Change | File |
|---|---|---|
| 1 | Equipment map written **per LLM batch**, inside `_run_llm_batch`, alongside that batch's metadata writes. Worst-case loss on interruption drops from the whole run to one batch. | `silver/src/etl/nb_sdg_fsr_v2_metadata.py` |
| 2 | Stage 5 becomes reconciliation only — reports totals and warns if any `completed` doc has no map row. | same |
| 3 | Futures released as their results are consumed, so parsed page text is no longer pinned for the whole run. | same |
| 4 | New `FSR_V2_P1_MAX_DOCS` knob (blank = unlimited). Applied **after** the stub MERGE, so discovery still registers the full queue as `pending` and only the run's slice is processed. | same, plus `databricks.yaml`, `workflows/fsr_v2/pw_sdg_fsr_v2_p1_metadata.yml`, `workflows/fsr_v2/pw_sdg_fsr_v2_ingestion.yml` |

Fix 2 also removes the giant `IN (...)` list: per-batch writes mean the
predicate is bounded by `FSR_V2_P1_LLM_BATCH_SIZE`.

### 4.2 Repair for data already on disk — rebuild, do not re-queue

**The equipment map is fully reconstructable from `fsr_metadata_v2` alone.**
Every input `_build_map_rows` uses is already a persisted column:

| Needed by the map | Persisted as |
|---|---|
| per-region ESN, equip type, technology code | `preprocessor_regions` (JSON array, written by `metadata_enrichment.py`) |
| document-level primary ESN + equip type | `primary_esn`, `primary_equip_type` |
| equipment anchors | `gt_esn`, `gen_esn`, `st_esn` |
| active/inactive flag | `inactive_esns` (JSON array) |

So the map can be rebuilt **exactly**, with no PDF parsing and no LLM calls.

**Why not reset `metadata_status` to `'pending'` and reprocess:**

- At ~300 docs/hr, ~8K documents is over a day of wall clock, plus the LLM
  spend to re-extract metadata that is already correct.
- Reprocessing **overwrites** correct metadata. LLM extraction is not
  deterministic, so the rewritten rows would not necessarily match what is
  there now. That is a data-correctness risk introduced by the fix itself.
- It does not fix anything the rebuild does not. The map is the only thing
  missing.

Repair notebook:
`pw_sdg_ai_ser_repo/validation/fsr_v2/nb_fsr_v2_repair_equipment_map.py`

- Dry-run by default (`REPAIR_DRY_RUN=true`).
- Selects target docs by `LEFT ANTI JOIN`, then writes insert-only
  (`WHEN NOT MATCHED THEN INSERT`) — it cannot update or delete an existing
  map row.
- Duplicates `_build_map_rows` from the P1 notebook. **Keep the two in sync.**

---

## 5. Why monitoring did not catch it

The pulse checks in [backfill-monitoring-plan.md](backfill-monitoring-plan.md)
§2.3 query **one table at a time**: queue state, chunk volume, run log, DQ log.
Every one of those looked healthy — metadata rows were landing, statuses were
advancing, no failures were logged. Nothing compared the three tables against
each other, so a table sitting at zero rows was invisible for two days.

A check for exactly this existed — `check_equipment_map` in
[../automation/checks.py](../automation/checks.py) — but it is hardcoded to the
dev profile and dev warehouse, lives outside the product repo, and is not wired
into anything that runs during a backfill. So the 26-hour QA run had no
correctness gate on it at all. It also does not subtract the "no ESN at all"
floor, so it would false-alarm on a real corpus.

Fixed two ways:

- §9.2 of the plan: cross-table consistency queries with an explicit gate —
  `missing_map_rows - missing_but_no_esn` must be **0**, treated as
  stop-and-repair rather than a warning.
- Packaged as deployable notebooks in `pw_sdg_ai_ser_repo`
  (`validation/fsr_v2/nb_fsr_v2_01_pulse_check` and
  `nb_fsr_v2_02_data_correctness_full`), parameterised by table name so they
  work against dev, QA and prod.

The floor distinction matters: a document with no ESN anywhere is *correctly*
unmapped, so a raw "completed docs with no map row" count always has a non-zero
floor. Both the query and the notebooks separate the two so the gate is
meaningful.

---

## 6. Order of operations

Data correctness first; jobs second. Expanded into gated phases in
[qa-backfill-autonomous-plan.md](qa-backfill-autonomous-plan.md), which is the
execution order to follow. Its §1 records why the data is repaired and the
backfill continued rather than QA being reset: nothing in QA is irreparably
corrupted, and a reset would discard ~27 hours of completed work for no gain.

1. Run plan §9.2 query **A** against QA — real `missing_map_rows` and
   `missing_but_no_esn` numbers.
2. Run §9.2 queries **B** and **C** — confirm chunks and orphan rows are clean,
   i.e. this is only an equipment-map problem.
3. Repair notebook, `REPAIR_DRY_RUN=true` — review the assessment log line.
4. Repair notebook, `REPAIR_DRY_RUN=false` — re-check query A until the gate is
   met.
5. **Then** merge the code fixes to `dev`, deploy, and restart the backfill with
   `FSR_V2_P1_MAX_DOCS=5000`.

> Steps 1–2 are not yet done. There is no QA profile in `~/.databrickscfg` on
> the dev box (dev only), so the automation tooling cannot pulse QA. Run the
> queries from a QA SQL editor, or add a QA profile first.

---

## 7. Carry into prod

- Deploy the P1 fixes before any prod backfill — prod has the same corpus scale
  and the same interruption risk.
- Set `FSR_V2_P1_MAX_DOCS` for prod runs. Year-cohort partitioning from the
  backfill runbook is still the coarse control; this is the per-run one.
- Add the §9.2 cross-table queries to the prod pulse cadence, not just QA.
- Check whether prod `fsr_document_equipment_map_v2` has the same gap from any
  earlier interrupted run, using query A against the prod tables.
