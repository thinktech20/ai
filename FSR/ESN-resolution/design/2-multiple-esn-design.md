# Multiple ESN Design — data model + cardinality (ARCHIVED — Option A, not chosen)

> **Status:** ARCHIVED 2026-05-26. **Option B picked** — see [proposed-multi-ESN-design.md](proposed-multi-ESN-design.md). Kept for historical reference + comparison only. **Do not implement from this doc.**
> **Decision rationale:** [../plan.md “DECISION (2026-05-26)”](../plan.md).
> **Original status:** Draft (skeleton, 2026-05-08)
> **Related:** [Pranesh-multi-ESN-approach.md](Pranesh-multi-ESN-approach.md) (raw flow chart input), [1-esn-extractor-method.md](1-esn-extractor-method.md), [3-incremental-ingestion-and-watermark.md](3-incremental-ingestion-and-watermark.md)
> **Tracker:** ESN-06 in [../tracker.md](../tracker.md) (closed 2026-05-26)

## Problem

ESN ↔ document is **many-to-many**:
- One PDF often references multiple equipment serials (multi-ESN-per-doc).
- The same physical asset appears across multiple FSRs (multi-doc-per-ESN — already handled by the table shape, since every doc gets its own row).

Today's metadata table stores **one `esn` STRING per row**, denormalized into 3 places (metadata column + chunk column + chunk JSON). That can't represent multi-ESN docs without either an array column or row fan-out.

## Decision (per Pranesh, 2026-05-06)

Adopt **row fan-out**: one row per `(source_doc, esn)` pair. Composite identity carried by a concatenated `document_id = <uuid>_<esn>`. See [Pranesh-multi-ESN-approach.md](Pranesh-multi-ESN-approach.md) for the 3-phase flow chart.

Why row fan-out over array column:
- VS index pre-filter is single-valued; array filter would need consumer-side `array_contains`.
- Per-ESN chunk lineage is queryable directly (no JSON unpack).
- Aligns with the chunking copy step (chunk once, copy rows per ESN).

Tradeoffs accepted:
- Storage grows by avg-ESNs-per-doc factor in metadata + chunks. Measure in [../analysis/cardinality-measurement.md](../analysis/cardinality-measurement.md) (ESN-03).
- "Doc-level" queries become `GROUP BY source_doc_id`. Consumer query path stays per-row (filter by `esn`).

## Data model

### Metadata table — proposed columns

| Column | Type | Notes |
|---|---|---|
| `document_id` | STRING NOT NULL PK | Stub: `<uuid>` (bare). Expanded: `<uuid>_<esn>`. |
| `source_doc_id` | STRING NOT NULL | Bare uuid (or `hash(volume+docid)`). Same value across all expanded rows of one PDF. **New column** — needed for anti-join and source-level state. See [3-incremental-ingestion-and-watermark.md](3-incremental-ingestion-and-watermark.md). |
| `esn` | STRING | NULL on stub; populated on expanded row. |
| `esn_source` | STRING | `'esn_identifier'` / `'page1'` / `'fsr_pdf_ref'` / `'manual'`. |
| `esn_rank` | INT | 0 = primary (highest count), 1..N = others. Lets resolver pick "the one" deterministically without re-reading raw counts. |
| `esn_count` | INT | From `esn_mentions` body-text count. Useful for DQ + audit. |
| _existing columns_ | — | `volume_path`, `metadata_status`, `metadata_retry_count` (UI-18), `customer`, `equipment_type`, etc. |

PK invariant: `document_id` unique. `(source_doc_id, esn)` unique on expanded rows.

### Chunks table — proposed columns

| Column | Type | Notes |
|---|---|---|
| `chunk_id` | STRING NOT NULL PK | `MD5(document_id + '_' + chunk_index)`. Because `document_id` already includes ESN, no `__esn` suffix needed (UI-14's pattern dissolves). |
| `document_id` | STRING NOT NULL FK | `<uuid>_<esn>`. |
| `source_doc_id` | STRING NOT NULL | Carried forward for source-level joins / DQ / VS soft-delete. |
| `esn` | STRING NOT NULL | VS pre-filter column. |
| `metadata` JSON | — | `"esn"` key matches column. No `"esns"` array key — fan-out makes it redundant. |

### What goes away

- UI-14's row-duplication patch + alt `chunk_id = MD5(doc_id + '_' + chunk_idx + '__' + esn)` shape. Reverts via [`pw_sdg_fsr_revert_multi_esn.yml`](../../../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_revert_multi_esn.yml) once new design is live and recovers the same docs.
- `esns ARRAY<STRING>` + `esns_source` columns prototyped on `fix/multiple-esns` (UI-07 branch). Not needed under fan-out.

## Phase 2 expansion semantics (open — confirm with Pranesh)

Pranesh's flow chart says: on success, **UPDATE the bare stub → `<uuid>_<esn0>` and INSERT rows for `esn1..esnN`**.

Implications:
- The bare stub is gone after expansion. Source-level state (e.g. P1 retry counter, last-extracted-at, error history) only lives on the renamed primary row, or must be denormalized across all expanded rows.
- Re-extract path: SRE has to delete N expanded rows + chunks and re-insert the bare stub. Runbook step.
- Phase 2 work-queue gate `document_id NOT LIKE '%\_%'` works (uuids contain no `_`).

Alternative: **keep the bare stub** as a permanent "source-doc marker" with `metadata_status='expanded'`. Source-level state has a clear home. Phase 2 gate becomes `metadata_status='pending'` instead of LIKE pattern.

Pick one before Phase 2 implementation. Picking the **keep-bare-stub** variant simplifies re-extract + DQ + run-log, at the cost of an extra row per source PDF (+18K rows total — negligible).

## Re-extract semantics (open)

When does Phase 2 re-run for an already-expanded source PDF? Three triggers:
1. **Operator-driven** (data-fix job, UI-13 lineage). Default path.
2. **mod_time bump on the volume.** Today: bumps file's mod_time → discovered → anti-join skips because doc_id already present. Tomorrow: same, unless we add an explicit "PDF changed" branch.
3. **Never automatically.** Treat re-extract as an SRE-only operation.

Recommend (3) for v1. Document-content drift is rare; explicit operator action is safer than auto-replay.

When re-extract runs: compute the delta between new ESN set and current expanded rows for the same `source_doc_id`. Drop rows for ESNs no longer present + their chunks. Insert rows for new ESNs. Update rows for kept ESNs. Audit table records the delta for rollback.

## ESN child-row propagation rules

For each expanded row sharing one `source_doc_id`:
- All non-ESN P1 metadata fields (customer, install_date, equipment_type, …) are **identical copies**. Source of truth = primary (rank 0); copies are denormalized at write time.
- `esn`, `esn_source`, `esn_rank`, `esn_count` differ per row.
- Chunks: chunk text + embeddings are computed once per source PDF, then copied to N row sets with different `chunk_id`s (because `document_id` differs). See `Pranesh-multi-ESN-approach.md` Phase 3.

## VS index implications

- Pre-filter on `esn` continues to work. A query for ESN `X` returns hits from every doc that mentions `X`, regardless of whether `X` is primary or secondary on its source PDF — exactly the desired behaviour.
- VS payload `metadata` JSON's `"esn"` value matches the row's ESN. No "primary vs secondary" leakage to the consumer.
- Consumer-side dedup by `source_doc_id` if a single PDF has multiple ESNs matching the query (rare but possible with fuzzy ESN search).

## Migration

- DDL: additive `source_doc_id`, `esn_rank`, `esn_count` on metadata; `source_doc_id` on chunks. Idempotent ALTER.
- Backfill `source_doc_id` on existing rows = current `document_id` (because today every row is bare-uuid). One-time UPDATE.
- New-doc path: P1 writes `source_doc_id` natively from the discovery step.
- Existing-doc fan-out: data-fix job (UI-13 lineage) re-runs extractor on consumer-flagged docs at minimum; bulk only if greenlit. See [../plan.md](../plan.md) Phase 4 (M7/M8).
- UI-14 row-dup patch reverted in prod once new path covers same docs.

## Open questions

1. **Keep bare stub vs rename on expansion** — see "Phase 2 expansion semantics" above.
2. **`document_id` strategy** — uuid (today) vs `hash(volume+docid)` per Pranesh. Orthogonal to fan-out; affects re-ingest idempotency only. Decide separately.
3. **Composite PK `(source_doc_id, esn)` vs concatenated STRING `document_id`** — the only thing concatenated buys us is "single STRING PK that fits existing downstream contracts." Worth a 5-min weigh-in.
4. **`esn_count` thresholding policy** — what to do when no body-text mention reaches `MIN_ESN_COUNT=1`. Fall back to page-1? Mark as `low_confidence` and skip fan-out? Lives partially in [1-esn-extractor-method.md](1-esn-extractor-method.md).
5. **Re-extract trigger** — confirm operator-only (option 3 above).

## Cross-refs

- Extractor that produces the ESN list: [1-esn-extractor-method.md](1-esn-extractor-method.md)
- Pipeline cursor / anti-join / watermark: [3-incremental-ingestion-and-watermark.md](3-incremental-ingestion-and-watermark.md)
- Pranesh's raw flow input: [Pranesh-multi-ESN-approach.md](Pranesh-multi-ESN-approach.md)
- Phase plan: [../plan.md](../plan.md)
