# Multi-ESN Design (Option B — CHOSEN)

> **Status:** Decided 2026-05-26. Final design for multi-ESN handling in the FSR metadata and chunk model. Schema and extraction decisions are documented inline below. Operational items to confirm before implementation are listed in §Open items.
> **Supersedes:** [2-multiple-esn-design.md](2-multiple-esn-design.md) (Option A row fan-out — archived).
> **Related:** [1-esn-extractor-method.md](1-esn-extractor-method.md) (extractor — option C, picked), [3-incremental-ingestion-and-watermark.md](3-incremental-ingestion-and-watermark.md) (anti-join + watermark mechanics; fan-out sections in that doc no longer apply), [../plan.md](../plan.md) (phase plan), [../tracker.md](../tracker.md) (ESN-NN items), [../../vistra-metadata-issue/analysis/findings-and-plan.md](../../vistra-metadata-issue/analysis/findings-and-plan.md) (Vistra Generator gap — concrete trigger for the train-sibling expansion and Approach 1/2 implementation plan).

## Problem Statement

- One PDF can mention multiple ESNs (for example, equipment roster or valve list pages).
- One ESN can appear in multiple PDFs.
- Metadata is the main / authoritative table.
- Chunk table is built from metadata rows that are ready for chunking.
- The design must support incremental discovery, retry, rollback, and re-extract without changing `document_id` when a PDF has multiple ESNs.

## Proposed Model

Use one metadata row per PDF. Store all ESNs for that PDF, along with their equipment attributes, in a structured array column.

| Column | Type | Purpose | Open item |
|---|---|---|---|
| `document_id` | STRING | Document key. Same key used by chunking, retry, rollback, and re-extract — **not** duplicated per ESN. Currently derived from lowercase filename stem. | [O3](#open-items) (cross-volume identity) |
| `primary_esn` | STRING | Scalar ESN for consumers that still expect a single value. Copied from the `esn_details` entry with `rank=0`. Filtering and search should use `esns`; `primary_esn` is for single-value reads, display, and transition support. | [O1](#open-items) (`rank=0` rule) |
| `esns` | ARRAY<STRING> | Helper column derived from `esn_details.esn`. The field used for Vector Search filtering. Needed because a `primary_esn`-only filter would miss PDFs where the requested ESN is present but not primary. | [O5](#open-items) (FSR index + consumer app) |
| `esn_details` | ARRAY<STRUCT<…>> | One struct entry per qualified ESN — see fields below. Covers the ESN, its equipment attributes, and the extraction evidence used to order ESNs. | [O2](#open-items) (field contract) |
| `metadata_status`, `chunk_status` | STRING | Processing-status fields used to control pipeline flow. | — |

**`esn_details` struct fields:**

| Field | Type | Why kept |
|---|---|---|
| `esn` | STRING | The ESN itself |
| `equipment_sys_id` | STRING | Equipment attribute tied to this ESN |
| `equipment_type` | STRING | Equipment attribute tied to this ESN |
| `equipment_class_code` | STRING | Equipment attribute tied to this ESN |
| `esn_source` | STRING | Where the ESN came from (extraction evidence) |
| `rank` | INT | Ordering; `rank=0` feeds `primary_esn` |
| `esn_count` | INT | Mention count — used for DQ review, audit, tie-breaking on re-extract |

`extracted_at` is intentionally **not** in the struct — extraction time already exists at the metadata-row level.

This design keeps one metadata row per PDF and does not create made-up per-ESN document IDs. It also keeps **ESN-specific attributes (`equipment_type`, `equipment_sys_id`, `equipment_class_code`) attached to the ESN they belong to** — not flattened to the document, which would lose information when one PDF references multiple ESNs of different equipment types.

### Why `esn_details` (struct array) and not a flat `esns` array

- Equipment attributes are properties of the **ESN**, not the document. A document with `[E1, E2]` may legitimately have two different `equipment_type` values.
- A flat `esns: ARRAY<STRING>` plus a single document-level `equipment_type` forces one value and loses the per-ESN association.
- A child table keyed by `(document_id, esn)` is also valid but adds a join for every consumer query and a second status surface to manage. The struct-array keeps everything row-local while preserving the per-ESN shape.

## ESN Extraction Method

ESN extraction quality and method belong to the DS team. This design does not redesign it.

**What exists today.** Three sources contribute to `all_esns` across P1 (silver) and P2 (gold). They are additive (unioned), not a strict fallback chain.

| # | Source | Scope of input | Where |
|---|---|---|---|
| 1 | LLM normalization on cover-sheet key:value pairs (with `_extract_esn_from_page1_text` regex fallback if the LLM returns empty) | **Page 1 only** | [`nb_sdg_fsr_metadata.py`](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) (`NORMALIZATION_PROMPT_SUFFIX`, `_extract_esn_from_page1_text`) |
| 2 | `fsr_pdf_ref` view join — overrides source 1 when its value is missing or not present in the ref set | External reference table (not PDF text) | [`nb_sdg_fsr_metadata.py`](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) (`_pdf_ref_esn_map`) |
| 3 | Tier-2 LLM frequency analysis — gated by `FSR_ESN_DETECT_ENABLED` (**`false` on the daily ingestion job; `true` only on the ESN backfill job [`pw_sdg_fsr_esn_backfill.yml`](../../../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_esn_backfill.yml)**) | **Full-document text, truncated to ~3 KB** (start 1000 + middle 1000 + end 1000 chars). Qualifier: `FSR_ESN_MIN_COUNT=5` and `FSR_ESN_MIN_FRACTION=0.10` | [`fsr_esn_identifier.py`](../../../pw_sdg_ai_ser_repo/common/fsr_esn_identifier.py); invoked from [`nb_sdg_fsr_chunks.py`](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py) |

Multi-ESN fan-out infrastructure is already in place — P1 writes `all_esns` and produces one metadata row per ESN; P2 produces one chunk-row set per ESN. `esn_source` on the metadata row records which of the three above produced the value (`llm` / `fsr_pdf_ref` / `ibat` after enrichment).

**Known limits of source 3.** A typical FSR is 50-100+ pages (~300 KB of text). Only ~3 KB reaches the LLM, and the qualifier requires ≥5 mentions and ≥10% share of all ESN mentions. ESNs named once or twice in the body — or work described purely in engineering keywords (e.g., "Seal Rings", "MAGIC Inspection") without naming the ESN — will not qualify. This is the root cause of the Vistra Generator gap and motivates the train-sibling expansion below.

**What this design needs from the DS team.** Confirm (a) whether to raise the 3 KB truncation cap or change the windowing strategy on source 3, (b) whether the LLM prompt and qualifier should be tuned for low-frequency-but-clearly-mentioned ESNs, and (c) the `rank` / `primary_esn` ordering rule when sources 1, 2, and 3 disagree. See open item **[O1](#open-items)**.

## Equipment-hierarchy expansion (train siblings)

In addition to ESNs extracted from the document itself, the pipeline may add ESNs derived from the IBAT train hierarchy. The trigger case is documented in [`../../vistra-metadata-issue/input/FSR_Cross_Tag_Gap_Logic 1.md`](../../vistra-metadata-issue/input/FSR_Cross_Tag_Gap_Logic%201.md) and [`Vistra_Generator_FSR_Tagging_Solution_2026-05-31.md`](../../vistra-metadata-issue/input/Vistra_Generator_FSR_Tagging_Solution_2026-05-31.md): a Field Service Report on a GT or ST train regularly describes Generator work but does not name the Generator ESN on page 1 or in `fsr_pdf_ref`. All three existing ESN sources (`llm`, `llm+ref`, `fsr_pdf_ref`) miss it, and a Generator-keyed search returns nothing.

**Rule.** For each ESN already resolved into `esn_details`, walk `ibat_equipment_mst.train_sys_id_fk → ibat_equipment_mst` to pull sibling ESNs on the same train where `equipment_type IN ('Generator', 'Gas Turbine', 'Steam Turbine')` and `equipment_status NOT IN ('Scrapped', 'Never Built (Cancelled)', 'Retired')`. Each sibling lands as a struct entry with:

- `esn_source = 'train_sibling'`
- `esn_count = 0` (no in-document mention required)
- `rank` after all text-evidenced ESNs
- equipment attributes from IBAT for the sibling ESN, **not** inherited from the prime mover

**Optional text-evidence gate.** When `FSR_TRAIN_SIBLING_REQUIRE_TEXT_EVIDENCE = true`, a sibling is only added if chunk text for the document contains either (a) the sibling ESN literal, or (b) ≥N (default 3) generator-engineering keywords from a curated list (`Seal Rings`, `Hydrogen Seal Assembly`, `Collector Rings`, `MAGIC Inspection`, `Winding Resistance`, `DC Leakage`, `AC Impedance`, `Belly Bands`, `Red Eye Repair`, …). The keyword list and threshold logic mirror Jon's gap-finder (Phase 3B). Default is `false` for v1 — trust IBAT train membership and let SME validation drive whether the gate is needed.

Open items: **[O1](#open-items)** for `rank` rule when text-evidenced and sibling ESNs co-exist; **[O8](#open-items)** for rollout sequencing, fleet-wide row-inflation estimate, and the keyword-gate decision.

## Lifecycle

### Phase 1: Discovery

1. Scan volume and discover new PDFs.
2. Insert stub metadata row per discovered UUID.

```sql
INSERT INTO metadata (document_id, volume_path, primary_esn, esn_details, metadata_status, chunk_status, ...)
VALUES (:uuid, :volume_path, NULL, NULL, 'pending', 'pending', ...)
```

### Phase 2: Extraction

1. Pick rows where `metadata_status = 'pending'`.
2. Extract ESN signal from page-1 + body windows.
3. Resolve `primary_esn` and the per-ESN attributes into `esn_details`.
4. Update the same metadata row.

```sql
UPDATE metadata
SET primary_esn = 'E1',
    esns = array('E1', 'E2', 'E3'),
    esn_details = array(
      named_struct('esn', 'E1', 'equipment_sys_id', 'S1', 'equipment_type', 'T1', 'equipment_class_code', 'C1', 'esn_source', 'llm',           'rank', 0, 'esn_count', 12),
      named_struct('esn', 'E2', 'equipment_sys_id', 'S2', 'equipment_type', 'T2', 'equipment_class_code', 'C2', 'esn_source', 'llm+ref',       'rank', 1, 'esn_count', 4),
      named_struct('esn', 'E3', 'equipment_sys_id', 'S3', 'equipment_type', 'T1', 'equipment_class_code', 'C1', 'esn_source', 'fsr_pdf_ref',   'rank', 2, 'esn_count', 0)
    ),
    metadata_status = 'completed'
WHERE document_id = :uuid
```

### Phase 3: Chunking

1. Pick rows where `metadata_status = 'completed'` and `chunk_status = 'pending'`.
2. Chunk text once per PDF.
3. Insert one chunk set for the document. Chunk schema:
   - Top-level `esn` STRING = `primary_esn` (kept for legacy consumers).
   - Top-level `esns` ARRAY<STRING> = duplicate copy of `esn_details.esn` (pre-filter column for vector search).
   - `metadata` JSON payload includes the full `esn_details` struct array.
   - Equipment attrs aren't mirrored as top-level chunk columns — they don't drive VS filtering at chunk granularity, and lifting the full struct onto every chunk is heavier than carrying it once in the JSON payload.
4. Mark chunking complete.

```sql
UPDATE metadata
SET chunk_status = 'completed'
WHERE document_id = :uuid
```

## Operational Flows

### Retry (chunking failure)

- Keep metadata row unchanged.
- Set `chunk_status = 'pending'`.
- Next run re-chunks the same `document_id`.

### Rollback (bad chunk output)

```sql
DELETE FROM chunks WHERE document_id = :uuid;

UPDATE metadata
SET metadata_status = 'pending',
    chunk_status = 'pending'
WHERE document_id = :uuid;
```

### Re-extract (improved extraction logic)

```sql
DELETE FROM chunks WHERE document_id = :uuid;

UPDATE metadata
SET primary_esn = NULL,
    esns = NULL,
    esn_details = NULL,
    metadata_status = 'pending',
    chunk_status = 'pending'
WHERE document_id = :uuid;
```

## Design at a glance

| Aspect | Proposed Design |
|---|---|
| Row count | 1 metadata row per PDF |
| `document_id` behavior | One `document_id` on the metadata row; P2 fills `esn_details` on that row instead of creating per-ESN document keys. Current code derives `document_id` from filename stem (refer open item `O3`). |
| Discovery anti-join | `LEFT ANTI JOIN` on `document_id` |
| State tracking | Existing status fields, no extra coordination |
| Retry/rollback | Idempotent and scoped to the row |
| Re-extract | Reset ESN fields on the same row and rerun with the same `document_id` |
| Chunk storage | Stored once per PDF |
| ESN-equipment binding | Equipment attributes carried per-ESN inside `esn_details` (no loss when one doc has multiple equipment types) |
| Query model | `exists(esn_details, x -> x.esn = 'E1')` |
| DQ table key | Unchanged — stays `(document_id, check_name)`. One `document_id` per PDF, so no per-ESN keys are introduced. |

## Query Trade-Off

- Consumer query shifts from equality to struct-array predicates.
- Single ESN filter:

```sql
WHERE exists(esn_details, x -> x.esn = 'E1')
```

- OR query across ESNs:

```sql
WHERE exists(esn_details, x -> x.esn IN ('E1', 'E2'))
```

- Filter by ESN + equipment attribute together (now possible because they stay bound):

```sql
WHERE exists(esn_details, x -> x.esn = 'E1' AND x.equipment_type = 'T1')
```

This is an acceptable adaptation for better pipeline consistency, lower data duplication, and accurate per-ESN attribution.

## Incremental Discovery Pattern

```sql
WITH discovered AS (
  SELECT file_uuid AS document_id, volume_path, mod_time
  FROM volume_listing
  WHERE mod_time > :watermark
)
INSERT INTO metadata
SELECT d.document_id, d.volume_path, NULL /* primary_esn */, NULL /* esns */, NULL /* esn_details */, 'pending', 'pending', ...
FROM discovered d
LEFT ANTI JOIN metadata m
  ON d.document_id = m.document_id
```

This remains simple because extraction and chunking keep working against the same `document_id`; multi-ESN handling updates columns on that row instead of creating per-ESN rows. Refer to open items `O3` (cross-volume identity) and `O7` (incremental discovery cost).

Re-uploads of an existing PDF (same filename, newer `mod_time`) are surfaced by the watermark but skipped by the anti-join, since `document_id` already exists. Re-extract is operator-driven (see [§Operational Flows → Re-extract](#re-extract-improved-extraction-logic)), not watermark-driven.

## Why not duplicate rows per ESN

An alternative shape is to create one row per `(document, ESN)` in metadata and chunks (row fan-out). This was considered and rejected:

- Storage scales by ESN multiplicity, not by document count.
- Embeddings and metadata payloads are repeated with minimal value gain.
- Rollback becomes harder because multiple derived rows must be identified and cleaned consistently.
- Re-extract becomes heavier because duplicate sets must be recreated or reconciled.
- When the document key differs across the duplicate rows, retry/rollback/re-extract logic gets harder to keep consistent.

A row-duplication approach can serve as a one-time fix, but is not recommended as a long-term production design for the reasons above.

## Open items

Items below must be confirmed before implementation.

| # | Topic | What's open |
|---|---|---|
| O1 | **ESN extraction tuning (DS team to confirm)** | <ul><li>Today: three sources contribute (page-1 LLM+regex, `fsr_pdf_ref` join, Tier-2 full-doc LLM frequency capped at ~3 KB with `min_count=5`/`min_fraction=0.10`). Multi-ESN fan-out is already wired through P1 and P2.</li><li>Open: whether to raise the Tier-2 3 KB truncation cap or change the windowing strategy, and whether the qualifier should be tuned for low-frequency-but-clearly-mentioned ESNs.</li><li>Per-ESN confidence signal: should the extractor expose evidence location / strength? If yes, how should consumers (OSA, URA) use it — block, downweight, flag, or just cite?</li><li>`rank` / `primary_esn` ordering rule when sources 1, 2, and 3 disagree: `primary_esn` = `rank=0`. Tiebreak rule to be written down once tuning is decided. Text-evidenced ESNs always rank ahead of `train_sibling` entries.</li></ul> |
| O2 | **`esn_details` field contract** | <ul><li>Confirm the current struct fields are enough, or one more per-ESN field is needed before locking the schema.</li><li>Candidates: evidence location (`page_num` / span), extractor version, per-ESN timestamp.</li><li>Each extra field has to be propagated through metadata, chunk JSON, migration, and docs.</li></ul> |
| O3 | **Cross-volume document identity** | <ul><li>Today: [`nb_sdg_fsr_metadata.py`](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) derives `document_id` from lowercase filename stem only — no `hash(volume+docid)`. Anti-join / MERGE use that key.</li><li>If two source volumes can hold the same stem, decide: (a) same logical doc or distinct docs? (b) stem-based or volume-qualified identity?</li><li>Today's anti-join treats same-stem-across-volumes as the same document.</li></ul> |
| O4 | **v2 tables vs altering existing ones** | <ul><li>Schema change (new `esn_details`, `primary_esn`, status columns) on top of a corpus that already has a temporary fix duplicating chunk rows per ESN.</li><li>**In-place alter — not viable.** Prod is actively serving consumers; backfilling `esn_details` from current `esn` / `equipment_*` columns and de-duplicating per-ESN chunk rows would happen while writes and reads continue, so data accuracy is at risk during the rewrite window. Running both shapes side-by-side means dual-write coordination and inconsistent reads until cutover.</li><li>**Recommended: new v2 tables** (`metadata_v2`, `chunks_v2`, new VS index off v2). Existing prod path stays untouched while v2 is built and validated; consumers cut over in one step; v1 + the temporary fix retired together; clean revert (drop v2); no dual-write window.</li><li>**Trade-off of v2:** requires re-running metadata extraction + chunking for the full corpus into the new tables — compute, time, and LLM-call cost. Mitigated by the fact that the pipeline is mature and the layout is known, so this run is expected to be faster than the original backfill.</li></ul> |
| O5 | **FSR index + consumer app change** | <ul><li>Expose `esns ARRAY<STRING>` on the rebuilt FSR vector index.</li><li>Update consumer app query path to send the multi-value vector-search filter format instead of the current single-ESN contract.</li><li>Both must land together for v2 search to work end-to-end.</li></ul> |
| O6 | **Chunk-level ESN tagging — doc-wide vs per-chunk** | <ul><li>Current plan: every chunk gets the doc's full ESN list (`esns = [A, B, C]`), even chunks that only mention ESN-A. A filter on ESN-B still returns that chunk.</li><li>Question: is doc-level enough, or do we need per-chunk tagging based on chunk text?</li><li>Doc-level is simpler and cheaper. Per-chunk is more precise but means scanning every chunk's text at chunk time.</li><li>Decide based on a precision measurement on multi-ESN docs.</li></ul> |
| O7 | **Incremental discovery cost as metadata grows** | <ul><li>Measure whether incremental LIST + left-anti-join stays a small share of end-to-end runtime as the metadata table grows.</li><li>Compare: (a) current LIST + anti-join, (b) volume scan time, (c) anti-join / MERGE time, (d) backlog-only runs with no discovery scan.</li><li>Independent of O5 — affects pipeline runtime, not search correctness.</li></ul> |
| O8 | **Train-sibling expansion — config, rollout, evidence gate** | <ul><li>Config flags: `FSR_TRAIN_SIBLING_EXPANSION` (default `false` for v1 cutover, flip after fleet review), `FSR_TRAIN_SIBLING_TYPES` (default `Generator,Gas Turbine,Steam Turbine`), `FSR_TRAIN_SIBLING_REQUIRE_TEXT_EVIDENCE` (default `false`), `FSR_TRAIN_SIBLING_KEYWORD_THRESHOLD` (default `3`).</li><li>Where the join lives: shared helper (`common/fsr_train_resolver.py`) consumed by P1 metadata fan-out, P2 chunk fan-out, and the Tier-3 backfill — single source of truth for the IBAT walk.</li><li>Fleet-wide row-inflation estimate before turn-on (how many train-paired Generator/GT/ST adds across ~17.8K docs; storage + VS index size impact).</li><li>Keyword list: lift Jon's curated set from [`FSR_Cross_Tag_Gap_Logic 1.md`](../../vistra-metadata-issue/input/FSR_Cross_Tag_Gap_Logic%201.md) (Phase 3B). Owner for ongoing curation: D&A + Vistra-style SMEs.</li><li>Rollout sequence: dev backfill with flag on → row-count + sample SME validation → prod cutover. Reversible by flipping the flag off and running revert against `train_sibling`-sourced rows only.</li><li>`rank` interaction with O1: text-evidenced ESNs (`llm`, `llm+ref`, `fsr_pdf_ref`) rank ahead of `train_sibling` regardless of `esn_count` ties.</li></ul> |

Cross-refs for the open items: [../plan.md §Open items — Option B → Operational](../plan.md), [../tracker.md ESN-06d / ESN-06e](../tracker.md).