# Incremental Ingestion + Watermark Design

> **⚠️ ARCHIVED — Option A semantics, no longer applies (2026-05-26).**
> This doc was written assuming Option A row fan-out (`document_id = <uuid>_<esn>` + a separate `source_doc_id`). We chose **Option B** ([proposed-multi-ESN-design.md](proposed-multi-ESN-design.md)) on 2026-05-26: `document_id` stays a stable uuid per PDF, ESN cardinality is captured in an `esn_details` STRUCT array on the single metadata row, no fan-out.
>
> Under Option B, the incremental ingestion + watermark mechanics **don't change** vs. today's pipeline:
> - Volume anti-join still keys on `document_id` (one per PDF, stable).
> - Volume watermark advances after P1 commits — unchanged.
> - P2 work queue gate: `metadata_status='pending' AND retry_count < MAX` — unchanged.
> - P3 work queue gate: same, against `chunk_status` — unchanged.
> - VS sync: single chunk-set per PDF — unchanged.
> - DQ dedup key: stays `(document_id, check_name)` — unchanged (see [proposed-multi-ESN-design.md §Design at a glance](proposed-multi-ESN-design.md#design-at-a-glance)).
>
> The only relevant cross-ref from this doc to today's design is the **re-extract / rollback runbook outline** further down — the *intent* (delete chunks, reset metadata to pending, replay) carries over but the SQL needs rewriting against Option B's single-row model (just reset the row, no expanded-sibling deletion).
>
> **Keep this doc for history.** Don't implement from it.

---

## Why this needs its own doc

Multi-ESN row fan-out (per [2-multiple-esn-design.md](2-multiple-esn-design.md)) breaks today's identity assumption: **one PDF = one metadata row**. The volume watermark, the Phase 2 work queue, the Phase 3 work queue, the VS sync cursor, and the DQ dedup window all key off `document_id` today. Once `document_id = <uuid>_<esn>`, those need to be re-derived against a stable per-source-PDF identity.

This doc defines the cursors / anti-joins / dedup keys phase by phase.

## Identity model

Two identity columns, both required on metadata + chunks:

| Column | Meaning | Cardinality | Stability |
|---|---|---|---|
| `source_doc_id` | One per source PDF in the volume. Bare uuid (or `hash(volume+docid)`). | 1 per PDF | Stable across re-extract |
| `document_id` | Row PK. Stub: `<uuid>`. Expanded: `<uuid>_<esn>`. | 1 per `(PDF, ESN)` row | Changes on expansion |

Anti-join, watermark, VS soft-delete, and source-level DQ all key on `source_doc_id`. Per-row state (chunks, retry counters, audit) keys on `document_id`.

## Phase 1 — volume watermark + anti-join

Today: `volume_listing v LEFT ANTI JOIN metadata m ON v.uuid = m.document_id`, filtered by `v.mod_time > :volume_watermark`.

Tomorrow:

```sql
WITH discovered AS (
  SELECT
    file_uuid          AS source_doc_id,
    volume_path,
    mod_time
  FROM volume_listing
  WHERE mod_time > :volume_watermark
),
known AS (
  SELECT DISTINCT source_doc_id
  FROM biz_metadata_field_service_report
)
INSERT INTO biz_metadata_field_service_report (
  document_id, source_doc_id, esn, volume_path, metadata_status, ...
)
SELECT
  d.source_doc_id      AS document_id,    -- stub: bare uuid
  d.source_doc_id      AS source_doc_id,
  NULL                 AS esn,
  d.volume_path,
  'pending'            AS metadata_status,
  ...
FROM discovered d
LEFT ANTI JOIN known k
  ON d.source_doc_id = k.source_doc_id;
```

Volume watermark advances after Phase 1 commits the stubs. P2/P3 failures don't hold it back — same as today.

### Anti-join walk-through

| Scenario | Metadata state before scan | Anti-join behaviour |
|---|---|---|
| Brand new PDF | no rows with this `source_doc_id` | inserts bare stub |
| Stub exists, P2 not yet run | 1 row, `document_id = source_doc_id` | match → skip |
| Stub exists, P2 failed retry < MAX | 1 row, still bare, `metadata_status='failed'` | match → skip (P2 picks via status) |
| Stub permanently failed (retry exhausted) | 1 row, still bare | match → skip. SRE re-ingest = `UPDATE … SET metadata_status='pending', metadata_retry_count=0`. |
| Successfully expanded to N rows | N rows, all share `source_doc_id` | match → skip |
| PDF re-uploaded, same filename, newer mod_time | N expanded rows | volume yields it; anti-join skips. **Re-extract is operator-driven, not mod_time-driven** ([2-multiple-esn-design.md](2-multiple-esn-design.md) §"Re-extract semantics"). |
| Filename rename | new `file_uuid` derived | no match → inserts as new doc. Doc-content de-dup is a separate problem. |

## Phase 2 — extraction work queue

Pranesh's flow chart gates Phase 2 with `metadata_status IN ('pending','failed') AND document_id NOT LIKE '%\_%'`. The LIKE pattern works because uuids contain no `_`, but it conflates two signals (status + shape).

**Recommend** the cleaner gate:

```sql
SELECT * FROM metadata
WHERE metadata_status = 'pending'
  AND COALESCE(metadata_retry_count, 0) < :P1_MAX_RETRIES
```

Combined with **keep-bare-stub variant** in [2-multiple-esn-design.md](2-multiple-esn-design.md) §"Phase 2 expansion semantics":
- On success: stub stays, `metadata_status='expanded'`. INSERT N expanded rows with `metadata_status='completed'`.
- On failure: stub stays, `metadata_status='failed'`, `metadata_retry_count += 1`.
- Re-extract: operator sets stub back to `pending`, plus deletes existing expanded rows + chunks for that `source_doc_id`.

This drops the LIKE gate entirely and makes status the single source of truth — same pattern as today's UI-18 P1 retry gate.

If we instead go with the **rename-on-expansion variant**, the LIKE gate stays but: (a) `metadata_retry_count` lives on the row that gets renamed, so post-expansion the counter survives on the primary row only; (b) re-extract requires deleting all expanded rows and re-inserting the bare stub.

## Phase 3 — chunking work queue

```sql
SELECT * FROM metadata
WHERE metadata_status = 'completed'        -- expanded rows only
  AND chunk_status IN ('pending','failed')
  AND COALESCE(chunk_retry_count, 0) < :P2_MAX_RETRIES
```

One unit of work = one expanded row = one `(source_doc_id, esn)` pair. Status / retry per row, independent of siblings.

The "first ESN chunks + embeds, others batch-copy" optimization (Pranesh's flow Phase 3) saves compute but creates a soft dependency: if the primary row's chunking succeeds, copy-rows succeed by definition. Implementation choice — doesn't affect the cursor.

`chunk_id = MD5(document_id + '_' + chunk_index)` is uniqueness-safe across siblings because `document_id` differs per row. UI-14's `__esn` suffix dissolves.

## VS sync cursor

`PW_SDG_FSR_VS_Sync` reads chunks by Delta CDC / `last_modified`. Multi-ESN fan-out produces N× chunk inserts per source PDF, each with distinct `chunk_id`s — sync handles them as ordinary inserts.

Two new responsibilities:
1. **Partial visibility (acceptable):** ESN-1 chunks visible in VS while ESN-2 still chunking is the design intent.
2. **Stale-row deletion on re-extract:** drop chunks where `(source_doc_id, esn) NOT IN <new ESN set>`. Keys on `source_doc_id` — so chunks need that column.

## DQ dedup window (UI-17 follow-up)

Today: `(document_id, check_name)` 2-day skip in `nb_sdg_fsr_validate.py` 5.7. Post fan-out, a single broken PDF logs N rows per check.

Tier the dedup key:

| Check class | Dedup key | Example |
|---|---|---|
| Source-level (PDF won't open, no /Root, OCR failed wholesale) | `(source_doc_id, check_name)` | check 5.7 corrupt-source |
| Per-row (specific ESN row missing chunks, partial embed) | `(document_id, check_name)` | check 5.5 partial embed |

Single column to switch on. Same 2-day window.

`pdf_name` backfill (UI-17 #3) keys on `source_doc_id` going forward — clearer than today's `s3_filename` lookup.

## Run log + retry counters (UI-18 follow-up)

- P1 audit row: per commit batch, `docs_claimed/succeeded/failed` count **source PDFs** (one per `source_doc_id`), not expanded rows.
- P2 audit row: per commit batch, counts expanded rows. (Same as today's chunk-row counts.)
- `metadata_retry_count`: lives on the bare stub. Resets to 0 on first successful expansion. Operator reset via runbook for re-ingest.
- `chunk_retry_count`: lives on expanded row. Independent per ESN sibling.

## Re-extract / rollback runbook impact

A delete-and-replay path is needed because Phase 2 success now writes N rows + N×K chunks. Outline:

```sql
-- 1. snapshot what we're about to delete (audit table)
INSERT INTO esn_fix_audit
SELECT *, current_timestamp() AS snapshotted_at
FROM biz_metadata_field_service_report
WHERE source_doc_id = :pdf;

-- 2. drop expanded rows + chunks
DELETE FROM biz_chunks_field_service_report  WHERE source_doc_id = :pdf;
DELETE FROM biz_metadata_field_service_report WHERE source_doc_id = :pdf AND document_id <> source_doc_id;

-- 3. reset stub
UPDATE biz_metadata_field_service_report
SET metadata_status='pending',
    metadata_retry_count=0,
    chunk_status=NULL,
    chunk_retry_count=0
WHERE source_doc_id = :pdf;

-- 4. next P1 run picks it up via status; or trigger data-fix job for targeted re-extract.
-- 5. VS sync after P3 completes.
```

The data-fix job (UI-13 lineage) wraps this. SRE-runbook handoff post-merge.

## Open questions

1. **`document_id` strategy** — uuid vs `hash(volume+docid)`. Affects whether re-uploaded PDFs map to the same `source_doc_id` (idempotent re-ingest) or a new one. Lean toward `hash(volume+docid)` because it eliminates the "filename rename = new doc" footgun.
2. **Bare stub: keep or rename on expansion** — see [2-multiple-esn-design.md](2-multiple-esn-design.md) §"Phase 2 expansion semantics". Recommend keep.
3. **VS soft-delete vs hard-delete on re-extract** — Delta supports both. Hard-delete is simpler if `source_doc_id` is indexed.
4. **Volume watermark column** — today is per-volume `last_mod_time` in a state table. Doesn't change shape under fan-out, but worth confirming no edge case where the watermark advances ahead of P1's commit (would skip a doc forever). Today's behaviour is "advance after INSERT commits" — preserve.

## Cross-refs

- Extractor producing the ESN list: [1-esn-extractor-method.md](1-esn-extractor-method.md)
- Data model for fan-out + identity columns: [2-multiple-esn-design.md](2-multiple-esn-design.md)
- Pranesh's raw flow input: [Pranesh-multi-ESN-approach.md](Pranesh-multi-ESN-approach.md)
- UI-18 P1 retry gate (existing): [`nb_sdg_fsr_metadata.py`](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py)
- UI-17 DQ dedup (existing): [`nb_sdg_fsr_validate.py`](../../../pw_sdg_ai_ser_repo/silver/src/validation/nb_sdg_fsr_validate.py) §5.7
