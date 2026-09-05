# ADR-007: File Registry — Stub Rows in Metadata Table vs Separate Table

| Field | Value |
|---|---|
| **Status** | ACCEPTED |
| **Date** | 2026-04-20 |
| **Decision owners** | Madhurima, Pranesh |
| **Depends on** | ADR-004 (ingestion pipeline trigger) |

---

## Context

Process 1 (scraping & metadata extraction) discovers new PDFs on volumes, extracts metadata via LLM, enriches with IBAT/EV, and writes results to a Silver metadata table. The scraping steps (1A discovery → 1B watermark filter → 1C extract/normalize/enrich → 1D write) run sequentially.

**Problem identified by Pranesh:** If scraping *fails* for a file (e.g. LLM rate limit hit during step 1C), no row is ever written to the metadata table. On the next run, the watermark has advanced past that file's `last_modified` timestamp, so the file is silently skipped and never retried.

Pranesh proposed a separate `fsr_file_registry` table (Step 0) that registers every discovered file *before* scraping, with a `scraped` status column. The scraping notebook would then read from this table instead of the volumes directly.

---

## Options Considered

### Option A: Separate `fsr_file_registry` table (Pranesh's proposal)

- New table: `fsr_file_registry` with `volume_path`, `pdf_name`, `last_modified`, `scraped`, `error_reason`, `discovered_at`, `scraped_at`
- Step 0 (new notebook/task): scan volumes, watermark filter, MERGE into registry
- Step 1: scraping notebook reads registry (where `scraped = null/failed`), writes to metadata table
- Step 2: chunking notebook reads metadata table (where `chunk_status = pending/failed`)

**Pros:**
- Clear separation of discovery vs extraction
- Registry is a simple, stable table

**Cons:**
- 3 tables instead of 2 (registry + metadata + chunks)
- 3 workflow tasks instead of 2
- Duplicated status-tracking pattern (`scraped` on registry mirrors `chunk_status` on metadata)
- Extra I/O: write rows to registry, read them back, write to a different table
- Schema definitions in two places

### Option B: Stub rows in the metadata table (selected)

- No new table — keep the existing 2-table design (metadata + chunks)
- Modify Process 1 to first **MERGE stub rows** for all discovered files (with `metadata_status = pending`) before starting extraction
- Then process rows where `metadata_status` is `pending` or `failed`
- On success: update to `metadata_status = ok`, populate all fields
- On failure: update to `metadata_status = failed`, write error

**Pros:**
- 2 tables, 2 workflow tasks — no additions
- Single status-tracking pattern
- `document_id = SHA-256(volume_path)` is already the natural MERGE key
- No extra I/O — stub rows are written and updated in the same table
- Failed files stay as `metadata_status = failed` and are retried on next run
- Watermark is read from the same table (`MAX(ingested_at)`)

**Cons:**
- Slightly more complex single notebook (discovery + stub-write + extraction in one)
- Metadata table has rows with sparse data (stub rows have only `volume_path`, `pdf_name`, `file_last_modified` — everything else null until extraction succeeds)

---

## Decision

**Option B — Stub rows in the metadata table.**

The stub-row approach solves the exact same problem (failed files get retried) without adding a table, a workflow task, or duplicating the status-tracking pattern. The metadata table's existing `metadata_status` and `metadata_error` columns already support this. The `document_id` MERGE key means re-discovered or re-uploaded files are naturally handled via upsert.

### Why single table over two

1. **No duplicated status tracking** — with two tables you'd have `scraped` on the registry AND `metadata_status` on the metadata table. Same concept, two places to keep in sync. If they disagree (registry says `scraped=done` but metadata table has no row), you have a subtle bug to debug.
2. **No extra I/O hop** — two-table flow: write stub to registry → read registry → scrape → write to metadata table → update registry status (3 writes across 2 tables per file). Single table: write stub → update same row (2 writes, 1 table).
3. **One source of truth** — "which files exist and what's their state?" has one answer, one table. With two tables, you have to decide whether to check the registry or the metadata table, and reconcile if they differ.
4. **One less table to manage** — schema migrations, permissions (Shivam creating tables), access grants, monitoring, cleanup — all halved.

### How it works

1. **Discover & filter** — scan volumes, apply watermark filter (`file.modificationTime > MAX(ingested_at)` from metadata table)
2. **MERGE stub rows** — for each candidate file, MERGE into metadata table with `metadata_status = pending`, `chunk_status = pending`. Matched rows (re-uploads) get `metadata_status` reset to `pending`.
3. **Extract & enrich** — process rows where `metadata_status IN (pending, failed)`. On success: update all fields, set `metadata_status = ok`. On failure: set `metadata_status = failed`, write error.
4. **Next run** — failed rows are picked up because their `metadata_status = failed` regardless of watermark. New files are picked up via watermark.

### Watermark confirmed working

Pranesh tested `dbutils.fs.ls` → `modificationTime` (epoch ms). The timestamp-based watermark correctly identifies new files. No path-based fallback needed at this time (can be added later if a volume type doesn't expose timestamps).

---

## Consequences

- `fsr_config.py` metadata table DDL already has `metadata_status`, `metadata_error`, `metadata_retry_count` — no schema change needed.
- The scraping notebook needs a stub-row MERGE step at the top before extraction.
- Pranesh's `fsr_file_registry` table in the POC schema (`main.gp_services_sdg_poc.fsr_file_registry`) can remain for his testing — it just won't be part of the production pipeline.
- Workflow stays as 2 tasks: `fsr_metadata_extraction` → `fsr_chunk_ingestion`.
