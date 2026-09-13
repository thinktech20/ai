# FSR v2 - Prod Backfill Tracker

Living tracker for production backfill status. Append new checks at the bottom;
do not rewrite history.

---

## Run metadata

| Item | Value |
|---|---|
| Environment | prod (`ai-prod-dbr`, `gevernova-ai-prod-dbr.cloud.databricks.com`) |
| SQL warehouse | `ai-pw-ser-ds-prod-sqlw` = `da2e94e4080ab641` |
| Tables | `vaip.ai_std_con_field_service_report.fsr_metadata_v2`, `fsr_chunks_v2`, `fsr_document_equipment_map_v2` |
| Run/DQ logs | `vaip.ai_sot_field_service_report.fsr_run_log_v2`, `fsr_data_quality_log_v2` |
| Current goal | Monitor P1 metadata screening, P2 chunking/embedding catch-up, equipment-map parity, and P3/vector sync handoff. |

---

## Status at a glance

| Item | Value |
|---|---|
| Current phase | Prod backfill in progress - P1 and P2 active |
| Last checked | 2026-09-11 14:12 UTC |
| P1 metadata job | `PW_SDG_FSR_V2_Metadata`, run `365698855990291`, running since 2026-09-09 16:47 UTC |
| P2 chunking + embeddings job | `PW_SDG_FSR_V2_Chunking`, run `49480459394245`, running since 2026-09-11 13:06 UTC |
| P3 / VS sync | No recent `PW_SDG_FSR_V2_VS_Index` run found yet |
| Blocked on | Nothing visible from table pulse; run log has no rows yet, so use table movement + job state as heartbeat. |

**One-line summary:** Prod is actively moving. P1 has screened about 70% of the
51,024-row queue, P2 is catching up behind it, stale chunk claims are zero, and
the QA-style equipment-map loss is not present.

---

## Pulse - 2026-09-11 14:12 UTC

### Active jobs

| Job | Run ID | State | Started | Runtime at check |
|---|---:|---|---|---:|
| `PW_SDG_FSR_V2_Metadata` | `365698855990291` | RUNNING | 2026-09-09 16:47 UTC | ~45.4 h |
| `PW_SDG_FSR_V2_Chunking` | `49480459394245` | RUNNING | 2026-09-11 13:06 UTC | ~1.1 h |

Recent completed runs:

| Job | Run ID | Result | Started | Duration |
|---|---:|---|---|---:|
| `PW_SDG_FSR_V2_DDL` | `136491903873169` | SUCCESS | 2026-09-09 16:34 UTC | ~0.9 min |
| `PW_SDG_FSR_V2_Chunking` | `143138019121628` | SUCCESS | 2026-09-10 15:42 UTC | ~341.3 min |

### Queue state

| Metadata status | Chunking & embeddings status | Docs |
|---|---|---:|
| completed | completed | 9,667 |
| completed | failed | 47 |
| completed | in_progress | 20 |
| completed | pending | 3,419 |
| date_filtered | pending | 22,608 |
| failed | pending | 61 |
| pending | pending | 15,202 |

`date_filtered` means P1 opened the document, found it outside the configured
backfill year window, and marked it as terminal/out of scope. These documents
are not expected to move into chunking and embeddings.

### Aggregate progress

| Metric | Value |
|---|---:|
| Total metadata rows / distinct docs | 51,024 / 51,024 |
| P1 pending | 15,202 |
| P1 completed | 13,153 |
| P1 failed | 61 |
| P1 date-filtered | 22,608 |
| P2 pending | 41,290 |
| P2 in progress | 20 |
| P2 completed | 9,667 |
| P2 failed | 47 |
| Chunk rows / distinct docs | 372,697 / 9,687 |
| Equipment-map rows / distinct docs | 13,999 / 11,094 |

### Throughput and freshness

| Signal | Value |
|---|---|
| Last metadata write (`scraped_at`) | 2026-09-11 14:11:59 UTC |
| Last chunk write (`chunked_at`) | 2026-09-11 14:12:21 UTC |
| Last row update (`updated_at`) | 2026-09-11 14:12:21 UTC |
| P1 last 60 min | 339 completed, 242 date-filtered, 1 failed - 582 total screened |
| P2 last 60 min | 1,354 completed, 6 failed - 1,360 total processed |
| Estimated remaining P1 time at last-hour rate | ~26 h for 15,202 pending docs |

### Gates and health checks

| Check | Result |
|---|---:|
| Completed docs before 2016 | 0 |
| Stale chunk claims older than 60 min | 0 |
| Completed metadata docs | 13,153 |
| Completed metadata docs with chunk rows | 9,687 |
| Chunk coverage for completed metadata | 73.65% |
| Completed metadata docs with map rows | 11,094 |
| Completed docs missing map rows | 2,059 |
| Missing map rows with no ESN anywhere | 2,059 |
| Real equipment-map gap | 0 |
| Map coverage for completed metadata | 84.35% |

### Failures and logs

| Item | Value |
|---|---|
| Metadata failure retry distribution | 61 docs at retry count 1 |
| Chunk failure retry distribution | 7 docs at retry count 1; 40 docs at retry count 3 |
| DQ log categories | `WARN no_text_layer_suspected_scan` = 1,258; `FAIL metadata_pipeline_error` = 61 |
| Run log schema | Present and includes `p1_workers`, `llm_batch_count`, `docs_date_filtered` |
| Run log rows | None returned yet |

High-level failure read for meeting context: the failed docs look like source
document quality edge cases, not a broad pipeline failure. The current DQ signal
points to scanned/no-text-layer PDFs and metadata extraction errors, with 61 P1
metadata failures out of 51,024 docs (~0.12%). Treat these as exceptions to
review after the main backfill completes, while the jobs continue to move.

### Notes

- Treat table movement and Databricks job state as the heartbeat until run-log
  rows appear.
- The `completed` / `pending` rows mean P1 is done and P2 has not caught up yet;
  this is expected while both jobs are running.
- The 2,059 completed docs without map rows are all no-ESN documents, so this is
  not the equipment-map loss seen in QA.
- P3/vector sync has not run yet; check or trigger it after P2 has caught up or
  at the planned sync point.