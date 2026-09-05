# Review: Pranesh Design Doc vs Vince Metadata Materialization Plan

**Date:** 2026-04-17

---

## Summary

Pranesh's design doc is well-structured and covers the two-process architecture cleanly. The overall direction — scraping first, then chunking reads from the metadata output — matches what Vince and Tao have been converging on. There are a few areas where Vince's feedback introduces design changes that the doc doesn't yet reflect.

---

## What Aligns Well

### 1. Two independent processes, correct dependency direction
Pranesh's design correctly separates Process 1 (scraping/metadata) and Process 2 (chunking/embedding). Process 2 reads from Process 1's output table using the `processed` status flag. This is exactly the integration Vince's plan describes in Phase C and matches what the transcript discussed — no DAG dependency needed, the `processed` column drives it.

### 2. Watermark-based incremental detection
The `MAX(ingestion_timestamp)` watermark for new file detection is practical and was confirmed in the transcript as tested. First-run bootstrap (null watermark = full scan) and `FORCE_RESET` override are good additions.

### 3. Process 2 filters on `processed` status
Process 2 only picks up rows where `processed` is null/empty/failed. This makes retries automatic without extra config. The transcript confirmed this is the agreed approach.

### 4. Error tracking on the metadata table
`processed` / `error` / `error_reason` columns let both processes communicate status cleanly. Failed rows get retried on next run. This was discussed and agreed in the transcript.

---

## Gaps Based on Vince's Plan

### 1. Chunk metadata should be top-level columns, not just a JSON blob

**Pranesh's design:** All metadata on the chunk row goes into a single `metadata` STRING (JSON) column.

**Vince's recommendation:** Materialize high-value metadata fields as **top-level columns** on the chunk table, not buried in a JSON blob.

**Why this matters:**
- Top-level columns enable Delta/Vector Search filtering and indexing directly
- A JSON blob requires parsing at query time and can't be used for native SQL filtering
- Retrieval becomes simpler — no JSON extraction needed for common fields

**Recommendation:** The chunk table schema should have the Phase 1 fields (`title`, `customer`, `esn`, `equipment_type`, `event_type`, `report_issued_date`, etc.) as top-level columns. The `metadata` JSON column can remain as a catch-all for less-used fields, but the retrieval-critical ones should be promoted.

### 2. No field precedence rules defined

**Pranesh's design:** Metadata comes through a single pipeline (PDF extraction → LLM normalization → IBAT/EV enrichment), but there's no explicit statement of which source wins when values conflict.

**Vince's plan:** Emphasizes this as the most important design step. For example:
- `esn`: prefer `fsr_pdf_ref` → scraping-resolved → chunk-level detection
- `equipment_type`/`equipment_code`: prefer IBAT-enriched output
- `event_type`, `ev_project_id`: prefer Event Vision-enriched output

**Recommendation:** Add a precedence table to the design doc for each metadata field. Even if the current pipeline is sequential and there's only one source path today, documenting the precedence now avoids confusion when sources get added.

### 3. No lineage or audit columns on the metadata table

**Vince's plan** suggests:
- `metadata_resolution_version` — version of the enrichment logic that produced the row
- `metadata_resolved_at` — when the metadata was resolved
- `field_source_map` — which source contributed each field

**Pranesh's design** has `ingestion_timestamp` but no resolution versioning or field-level provenance.

**Recommendation:** At minimum, add `metadata_resolution_version` to the canonical metadata table. Full `field_source_map` can come later.

### 4. No re-materialization path defined

If canonical metadata changes (e.g. IBAT data gets corrected, or a new enrichment source is added), Pranesh's design doesn't describe how chunk rows get refreshed.

**Vince's plan** addresses this in Phase E — backfill/re-materialization with options for full reingestion, targeted update by `pdf_name`, or a new versioned chunk table.

**Recommendation:** At least document the intended approach. The `FORCE_RESET` mechanism covers Process 1, but there's no equivalent for Process 2 — resetting `processed` back to null on affected rows would be the natural path.

### 5. Re-uploaded file handling is still open

Both documents flag this. A PDF replaced in the volume (same filename, newer `last_modified`) will re-trigger Process 1 and create a duplicate row unless upsert logic is used.

**Recommendation:** Resolve this before implementation. Upsert by `volume_path` (or `pdf_name`) is the cleaner option — it also resets `processed = null` which triggers Process 2 to re-chunk. Append mode would accumulate stale rows.

---

## Minor Items

### `chunk_id` generation
Pranesh uses `md5(pdf_name + chunk_index)`. This is deterministic, which is good. But if a file is re-uploaded and re-chunked, the same `chunk_id` values will be regenerated — which is fine for upsert but needs to be intentional.

### `document_summary` field
Both documents list this as an open item. Vince's plan says "only materialize if there is agreement on how it is generated and refreshed." Pranesh's doc lists it as a TBC item with key questions (which LLM, which pages, stored on all chunks or just first). Keep it out of v1 and revisit.

### Volume paths for environments
Pranesh's design uses `viud` catalog paths for the source volumes and `vaid/vaiq/vaip` for the output. Need to confirm these map to the right environments (DEV/UAT/PROD). The transcript mentions this needs validation.

### Multi-ESN PDFs
Vince's plan mentions preserving ESN row-splitting for multi-ESN documents. Pranesh's design doesn't explicitly discuss this. If a single PDF covers multiple ESNs, does Process 1 create one row or multiple? This affects chunk materialization downstream.

---

## Transcript Takeaways

Key points from Pranesh's 4/17 call:
1. The watermark logic is tested and works
2. Two notebooks, two independent Airflow tasks — no DAG dependency between them
3. The `processed` column is the handoff mechanism between the two processes
4. LiteLLM proxy was having intermittent 503 issues (now resolved)
5. Monday plan: connect with Abhijit and Tao to solidify the flow
6. Chatra (Pacific TZ) and the IST-based developer are contacts for Databricks support questions

---

## Tao Discussion (4/15) — Additional Context

Reviewed: `Tao-metadata-4-15`

### Points that reinforce the design direction

1. **Purposeful vector index** — Tao stressed that the vector index should be built on purpose, not by dumping everything. Only ingest what's needed for retrieval. This aligns with Vince's "materialize only high-value metadata" principle and validates being selective about what goes into chunk rows.

2. **Scraping and ingestion are currently separate** — Tao confirmed the two pipelines (scraping and chunking) are disconnected today. The DS team runs them independently — the chunk pipeline reads volumes directly and never consumes the scraping output. Pranesh's design doc fixes this by having Process 2 read from Process 1's output table, which is the right integration.

3. **Catalog/environment mismatch is real** — Tao flagged that the application layer uses `VGPD`/`VGPP` while data processing writes to `VIUD`/`VAID`. The DS experimentation code writes to `main.gp_services_sdg_poc.*`, not the target catalog objects. Pranesh's design doc uses `vaid/vaiq/vaip` for output tables — need to confirm these are correct for each environment and that the app layer can read from them.

4. **Incremental ingestion is a key concern** — Tao raised that adding new documents to the existing data is hard today. A full re-run of the chunk pipeline takes many hours (20+ hours mentioned). This makes the watermark + `processed` status approach in Pranesh's design even more important — without incremental logic, adding a few FSRs means reprocessing everything.

5. **Multi-ESN handling differs between pipelines** — Tao mentioned the DS team has two index approaches: one focused on a single ESN, another more general. The scraping pipeline and chunk pipeline handle ESNs differently. Pranesh's design doc doesn't explicitly address multi-ESN PDFs — if one PDF covers multiple ESNs, does Process 1 create one row or fan out? This needs to be defined because it affects how chunks inherit metadata downstream.

### Points that surface risks not in the design doc

1. **Long pipeline runtimes** — The full chunk pipeline took 20+ hours in the DS experimentation code. Even with incremental logic, a first-run bootstrap of ~20,000 files will be very long. The design doc should acknowledge expected runtime for the initial load and consider batching or parallelism strategies.

2. **Data quality must come before agent correctness** — Tao's view: the data pipeline problems need to be solved before optimizing agent/retrieval behavior. The risk assessment and agent responses are only as good as the underlying chunks and metadata. This supports prioritizing the pipeline integration (Pranesh's design) over retrieval tuning.

3. **UAT feedback is positive at the high level** — SLE gave good feedback on what they're seeing, but detailed issues exist. This means the pipeline rework doesn't need to change direction, just get more robust.

### Alignment with Pranesh's design

| Topic | Tao's position | Pranesh's design | Status |
|-------|---------------|-----------------|--------|
| Scraping → chunking integration | Must be connected | Process 2 reads Process 1 output | Aligned |
| Incremental ingestion | Critical, full re-runs too expensive | Watermark + `processed` status | Aligned |
| Purposeful vector index | Don't dump everything | Selective metadata in chunk rows | Aligned (needs Vince's top-level column change) |
| Catalog/environment paths | `VIUD`/`VAID` vs `VGPD`/`VGPP` mismatch | Uses `vaid/vaiq/vaip` | Needs confirmation |
| Multi-ESN handling | DS team has two approaches | Not explicitly addressed | Gap |
| Runtime for full pipeline | 20+ hours for chunk pipeline | No runtime estimates | Gap |

---

## Recommended Next Steps

1. **Update chunk table schema** to promote high-value metadata to top-level columns (per Vince's Phase 1 list)
2. **Add field precedence rules** to the design doc — even a simple table of field → primary source
3. **Decide on upsert vs append** for re-uploaded files before implementation
4. **Add a re-materialization mechanism** for Process 2 (reset `processed` on affected rows when metadata changes)
5. **Align with Tao on Monday** — Tao's feedback from Vince may have additional items; merge before finalizing
6. **Keep `document_summary` out of v1** — revisit after the core flow is working
