# Chunking Fix — Plan

> **Status (2026-04-29):** Phase A + B complete. Both Phranesh test docs validated end-to-end on Databricks dev with prod LiteLLM gateway. See [03-tracker.md](03-tracker.md) for current state.

> **Scope decision:** Multi-ESN per PDF is **deferred** (see [01-chunking-strategy-comparison.md §6/§7](01-chunking-strategy-comparison.md)). This plan covers the structural / metadata chunking improvements only.

> **Approach:** Port DS `recursive_chunking_v3.py` into the production pipeline rather than reimplementing. The DS code is mature, has been validated on 230 FSRs, and lives in [ds-code-n-doc/fsr_pipeline_dbr_final/src/recursive_chunking_v3.py](ds-code-n-doc/fsr_pipeline_dbr_final/src/recursive_chunking_v3.py).

> **Schema decision (2026-04-29):** No DDL changes. New fields (`section_1..5`, `start_page`, `end_page`, `chunk_count`) ride in the existing `metadata` JSON column. DDL changes need separate approval; JSON keeps this PR self-contained. Trade-off: VS filtering on these fields requires `get_json_object()`.

---

## 1. What we're changing

| # | Fix | Rationale |
|---|---|---|
| 1 | **TOC detection + skip front-matter** | Avoids dot-leader / underscore-leader noise polluting body chunks. |
| 2 | **Boilerplate filtering** (positional header/footer, lines repeated on ≥20% of pages) | Removes "Page X of Y", legal disclaimers, GE Vernova footers from chunks. |
| 3 | **Header classification** (TOC match + numbering depth + font-size/bold) | Identifies section headers up to 5 levels. |
| 4 | **Per-section recursive split** | Groups body text by section path, then runs `RecursiveCharacterTextSplitter` *per section* — chunks no longer cross section boundaries. |
| 5 | **Section metadata** (`section_1` … `section_5`) on each chunk | Enables section-aware reranking and citation. |
| 6 | **Page range** (`start_page` + `end_page`) instead of single `page_number` | Accurate citations for chunks spanning multiple pages. |
| 7 | **Front Matter + Table of Contents as their own sections** | Cover-page info (customer, dates, ESN context) becomes searchable instead of being silently dropped. |

### What we are NOT changing

- **Splitter, chunk_size, chunk_overlap** — already match DS (`RecursiveCharacterTextSplitter`, 4000 / 200, separators `["\n\n","\n",". "," ",""]`).
- **Small-chunk merging** — not in DS V3 either; only a < 20-char drop filter.
- **PyMuPDF (`fitz`)** — already used.
- **Multi-ESN handling** — deferred.

---

## 2. Implementation strategy

### 2.1 Code organization

Add a new module under `gold/src/etl/` (or a shared lib under `common/`):

```
common/
  fsr_chunking.py        # ported recursive_chunking_v3 (single file, no esn_identifier needed)
gold/src/etl/
  nb_sdg_fsr_chunks.py   # imports & uses fsr_chunking, drops the inline splitter
```

Why a separate file (not inline in the notebook): the V3 code is ~860 lines. Keeping it as a pure-Python module makes it unit-testable and reusable.

### 2.2 What gets ported from `recursive_chunking_v3.py`

- All helpers: `normalize`, `_norm_key`, `_numbering_depth`
- `load_pdf_snapshot`, `page_text_from_snapshot`, `document_text_from_snapshot`
- TOC: `_is_toc_line`, `detect_toc_pages`, `detect_front_matter`, `extract_toc_entries`
- Boilerplate: `compute_repeated_lines`, `is_boilerplate`
- Lines: `extract_lines`
- Classification: `_is_likely_header`, `_header_signature`, `_are_siblings`, `_assign_level_from_metadata`, `classify_lines`
- Hierarchy: `build_hierarchy`
- Splitter wrapper: `semantic_chunk`
- Entry points: `hierarchical_semantic_chunking_from_snapshot`, `hierarchical_semantic_chunking_from_pdf`

### 2.3 What we drop / adapt

- **Drop** `pymupdf_guard` import — needed for DS local multiprocessing; in Databricks notebooks PyMuPDF is single-threaded per cell. Replace `with hold_pymupdf_lock():` with a plain `try/finally`.
- **Drop** ESN-from-snapshot code (`_extract_esn_from_*`) — ESN is resolved in P1 / metadata table; chunk row gets ESN from registry MERGE.
- **Adapt** module-level constants — keep `MAX_LEVELS = 5`, source `chunk_size` / `chunk_overlap` from `CHUNKING_CONFIG`.
- **Adapt** `metadata.document_title` (full path) → keep only `document_id` (UUID stem).

### 2.4 Chunk metadata fields (no schema change)

New fields are written into the existing `metadata` STRING column as JSON keys, not as new columns:

| JSON key | Type | Purpose |
|---|---|---|
| `start_page` | int | First page covered by chunk (1-based) |
| `end_page` | int | Last page covered by chunk (1-based) |
| `section_1` | string | L1 section title (e.g. "Background") |
| `section_2` | string | L2 section title |
| `section_3` | string | L3 |
| `section_4` | string | L4 |
| `section_5` | string | L5 |
| `chunk_count` | int | Total chunks in this section group (DS metadata) |

Existing `page_number` column kept and set to `start_page` for backward compat. Chunk row schema, `StructType`, and MERGE logic all unchanged.

Why JSON instead of typed columns: DDL changes require a separate approval cycle and a coordinated VS index sync. Routing into JSON ships the chunker improvement immediately; promoting to typed columns can come later as a follow-up.

### 2.5 Vector Search index

No schema change → no index sync rework needed. Filtering on `section_1`, `start_page`, etc. requires `get_json_object(metadata, '$.section_1')` in VS queries. Acceptable trade-off until query patterns settle.

---

## 3. Phased rollout

### Phase A — Port + dev validation ✅
1. ✅ Ported `recursive_chunking_v3.py` → `common/fsr_chunking.py`.
2. ✅ Dev comparison notebook (`validation/nb_chunker_compare.py`) ran old vs new on 4 PDFs locally.
3. ✅ Sign-off received — known trade-off: DS V3 drops 12–67% text vs old chunker on these 4 docs (template assumptions). Decision to ship and surface to DS team after broader validation.

### Phase B — Integration (no schema change) ✅
1. ✅ New fields routed into `metadata` JSON column (no DDL).
2. ✅ `nb_sdg_fsr_chunks.py` wired to `fsr_chunking` via `%run`.
3. ✅ Embedding hardening: `EMBED_FAIL_THRESHOLD` default → 0.0; `safe_embed_batch()` bisects on failure.
4. ✅ End-to-end validated on 2 Phranesh test docs (see [03-tracker.md](03-tracker.md) Databricks runs table).
5. ✅ Side-task: P1 fix for `nb_sdg_fsr_metadata.py` lookup hardcoding `.pdf` extension (FieldVision Volume has no extension). Bundled into the same PR.

### Phase C — Dev smoke + failure-injection on `_chunk_test` tables (next)

> Goal: prove the `feat/fsr-chunk-metadata-fix` branch runs end-to-end and recovers from realistic failures, before tomorrow's prod backfill. Target: ~1 hour total.
>
> Test tables (dev):
> - `vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test`
> - `vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test`
> - `vaid.ai_sot_field_service_report.fsr_run_log_chunk_test`
> - `vaid.ai_sot_field_service_report.fsr_data_quality_log_chunk_test`
>
> **P1 + P2 can run in parallel.** Stub rows are written at file discovery; P2 only claims docs where `metadata_status='completed'`. Submit P1 (`PW_SDG_FSR_Metadata_Backfill`) and P2 (`PW_SDG_FSR_Chunking_Backfill`) jobs separately so they overlap.
>
> Pull the branch in Databricks UI → use the standalone P1 and P2 jobs (not the combined `PW_SDG_FSR_Ingestion`) → override the parameters listed below per step.
>
> **Note:** schema column names — `metadata_error` and `chunk_error` (not `last_error`).

**Common parameter overrides (apply to every Phase C run unless noted):**

| Parameter | Value |
|---|---|
| `jb_env` | `dev` |
| `FSR_METADATA_TABLE` | `vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test` |
| `FSR_CHUNK_TABLE` | `vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test` |
| `FSR_RUN_LOG_TABLE` | `vaid.ai_sot_field_service_report.fsr_run_log_chunk_test` |
| `FSR_DQ_LOG_TABLE` | `vaid.ai_sot_field_service_report.fsr_data_quality_log_chunk_test` |
| `FSR_VS_INDEX` | `..._chunk_test` (or skip if no test index) |
| `FSR_SOURCE_VOLUME_PATHS` | `/Volumes/viud/ing_ud_fieldvision/fv_field_service_report,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports` |
| `LITELLM_BASE_URL` | `https://prd-gateway.apps.gevernova.net/` *(prod gateway, dev gateway flaky)* |

#### C0 — Pre-flight (5 min)

Run as SQL/notebook cells in dev workspace:

```sql
-- Tables exist + schemas
DESCRIBE TABLE vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test;
DESCRIBE TABLE vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test;
DESCRIBE TABLE vaid.ai_sot_field_service_report.fsr_run_log_chunk_test;
DESCRIBE TABLE vaid.ai_sot_field_service_report.fsr_data_quality_log_chunk_test;

-- Reference tables readable
SELECT COUNT(*) FROM vgpp.prm_std_views.ibat_equipment_mst LIMIT 1;
SELECT COUNT(*) FROM vgpp.fsr_std_views.eventmgmt_event_vision_sot LIMIT 1;
SELECT COUNT(*) FROM vgpp.fsr_std_views.fsr_pdf_ref LIMIT 1;
SELECT COUNT(*) FROM vgpp.fsr_std_views.fsr_field_vision_field_services_report_psot LIMIT 1;
```

```python
# Volumes readable
dbutils.fs.ls("/Volumes/viud/ing_ud_fieldvision/fv_field_service_report")[:3]
dbutils.fs.ls("/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports")[:3]
```

Secret scope check is skipped when `LITELLM_API_KEY` is passed as a job parameter (widget wins over scope per [fsr_config.py L161-L177](../../../pw_sdg_ai_ser_repo/common/fsr_config.py)). Verify in the C1 P1 log that `API key set : True`.

```sql
-- Baseline counts
SELECT COUNT(*) AS rows,
       SUM(CASE WHEN metadata_status='completed' THEN 1 ELSE 0 END) AS completed,
       SUM(CASE WHEN metadata_status='pending'   THEN 1 ELSE 0 END) AS pending,
       SUM(CASE WHEN metadata_status='failed'    THEN 1 ELSE 0 END) AS failed
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test;
```

**Gate:** all checks return without error. Note baseline counts.

#### C1 — Happy-path smoke (20 min, P1 + P2 in parallel)

Submit **two jobs separately, in parallel**:

**C1.a — `PW_SDG_FSR_Metadata_Backfill`** (P1) — overrides:

| Param | Value |
|---|---|
| *(all common overrides above)* | |
| `FSR_MAX_PDFS` | `200` |
| `FORCE_RESET` | `false` |
| `FSR_TARGET_PDF_NAMES` | *(empty — DISCOVERY mode)* |

**C1.b — `PW_SDG_FSR_Chunking_Backfill`** (P2) — submit a few minutes after P1 starts (so P1 has committed some `metadata_status=completed` rows). Overrides:

| Param | Value |
|---|---|
| *(all common overrides above except `FSR_MAX_PDFS`)* | |
| `FSR_P2_BATCH_SIZE` | `50` |
| `FSR_P2_MAX_ITERATIONS` | `2` |
| `FSR_VS_ENDPOINT` | `pw-ser-sdg-vector-search_chunk_test` |

P2 will claim whatever P1 has completed at that moment, process up to 100 docs (50 × 2), and exit.

**Watch logs for:**
- Both: `LLM base URL : https://prd-gateway...`
- Both: `API key set : True`
- P1: `Volumes : ['/Volumes/viud/...', '/Volumes/viud/...']`
- P1: per-batch `[B<n>] Sending 4 records to LLM... Got N normalized rows`
- P1: final `Grand total: ok=X, fail=Y` — fail rate <5%
- P2: `[batch ...] N docs claimed`
- P2: `Generated N embeddings in Ms`
- P2: `Embedding failures in 0 documents`
- P2: `Excluding 0 failed docs`

**Verify post-run:**

```sql
-- Run-log row written
SELECT * FROM vaid.ai_sot_field_service_report.fsr_run_log_chunk_test
ORDER BY run_start_ts DESC LIMIT 3;

-- Status distribution
SELECT metadata_status, chunk_status, COUNT(*)
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test
GROUP BY metadata_status, chunk_status;

-- Chunks
SELECT COUNT(*) AS total_chunks, COUNT(DISTINCT document_id) AS docs
FROM vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test;

-- Embedding dim sanity
SELECT size(embedding) AS dim, COUNT(*)
FROM vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test
GROUP BY size(embedding);  -- expect: 3072 only

-- Section metadata populated (chunker fix)
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN get_json_object(metadata,'$.section_1') IS NOT NULL THEN 1 ELSE 0 END) AS with_section,
  SUM(CASE WHEN get_json_object(metadata,'$.start_page') IS NOT NULL THEN 1 ELSE 0 END) AS with_start_page,
  SUM(CASE WHEN get_json_object(metadata,'$.end_page')   IS NOT NULL THEN 1 ELSE 0 END) AS with_end_page
FROM vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test;
```

**Gate:** P1 ≥95% success, P2 ≥95% success, all chunks dim=3072, section_1 coverage ≥90%.

#### C2 — Idempotency (5 min)

Re-submit the **exact same C1 job** (no parameter changes).

**Verify:**
- P1 log: `Existing docs in table: N (will be skipped)`.
- P2 log: claim returns 0 rows.
- Chunk count unchanged from end of C1.

**Gate:** zero new rows written.

#### C3 — Partial-ingestion guard (chunker fix proof, 5 min)

Confirm the integrity fix from `nb_sdg_fsr_chunks.py` works: failed docs must have **zero** chunks in the chunk table.

```sql
SELECT m.document_id, m.chunk_status, COUNT(c.chunk_id) AS chunks_in_table
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test m
LEFT JOIN vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test c
  ON m.document_id = c.document_id
WHERE m.chunk_status = 'failed'
GROUP BY m.document_id, m.chunk_status;
```

**Gate:** every row shows `chunks_in_table = 0`. (If C1 produced no failed docs, run C4 first then come back.)

#### C4 — Whole-batch P1 LLM failure + recovery (10 min)

Override `LITELLM_BASE_URL` to a deliberately wrong path:

| Param | Value |
|---|---|
| `LITELLM_BASE_URL` | `https://prd-gateway.apps.gevernova.net/wrong-path` |
| `FSR_MAX_PDFS` | `8` |

Pick 8 fresh docs (e.g. via `FSR_TARGET_PDF_NAMES` if needed) so they have no completed history.

**Watch logs:** `[B1] LLM FAILED: ...`, all 8 docs marked `metadata_status='failed'`.

```sql
-- Confirm error message captured
SELECT metadata_status, COUNT(*),
       SUM(CASE WHEN metadata_error IS NULL OR metadata_error='' THEN 1 ELSE 0 END) AS missing_error
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test
WHERE metadata_status='failed'
GROUP BY metadata_status;
-- missing_error should be 0
```

Re-submit with `LITELLM_BASE_URL` reset to `https://prd-gateway.apps.gevernova.net/` (no other change).

**Verify:** all 8 flip to `completed` (within `P1_MAX_RETRIES=3`).

**Gate:** failure path captures error + recovery path heals.

#### C5 — Stale claim recovery (5 min)

Submit the job; as soon as P2 logs `[batch ...] N docs claimed`, **cancel** the run from the UI.

```sql
-- Backdate the claim
UPDATE vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test
SET chunked_at = current_timestamp() - INTERVAL 60 MINUTES
WHERE chunk_status = 'in_progress';
```

Re-submit P2.

**Watch logs for:** `Recovered N stale in_progress claims (>30 min old)`.

**Gate:** stale rows return to `pending` and get processed.

#### C6 — Retry cap honored (5 min)

```sql
-- Force a doc into permanent-fail territory
UPDATE vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test
SET chunk_status='failed', chunk_retry_count=3
WHERE document_id = (
  SELECT document_id
  FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test
  WHERE chunk_status='completed' LIMIT 1
);
```

Submit P2. **Verify:** the targeted doc is **not** re-claimed (claim query filter excludes `chunk_retry_count >= P2_MAX_RETRIES`). Reset row when done.

**Gate:** retry cap prevents infinite loop.

#### C7 — Cross-doc spot audit (5 min)

```sql
SELECT document_id, pdf_name, esn, equipment_sys_id, fsr_number,
       outage_start_date, event_type
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test
WHERE metadata_status='completed'
ORDER BY rand() LIMIT 10;
```

Open 5 of these PDFs in the volume; eyeball that metadata matches page 1.

**Gate:** no obvious mismatches / cross-contamination.

#### Phase C exit criteria → ready for prod

- [ ] C1 pass (happy path)
- [ ] C2 pass (idempotent)
- [ ] C3 pass (no partial chunks for failed docs)
- [ ] C4 pass (batch failure + recovery)
- [ ] C5 pass (stale claim recovery)
- [ ] C6 pass (retry cap)
- [ ] C7 pass (no contamination on spot audit)

### Phase D — Promote
1. Open PR (branch already pushed). Review.
2. QA backfill → prod backfill per existing runbook.

---

## 4. Risks & mitigations

| Risk | Mitigation |
|---|---|
| New chunker drops more text than old (TOC / boilerplate filter too aggressive on some FSR templates) | Phase A side-by-side compares total chars before/after per doc; flag any doc with >10% reduction for manual review. |
| Header classification mis-identifies body as headers on form-style FSRs | DS v3 already has the "demote headers on all-header pages" safeguard (lines 591–613 of `recursive_chunking_v3.py`). Phase A will surface any remaining issues. |
| VS index sync fails on new columns | Test in dev first; rollback path = drop new columns, sync stays on old schema. |
| Per-section split produces many tiny sections (< chunk_size) → chunk count balloons | DS observed 48.5 chunks/report mean at chunk_size=4000. We expect similar. Phase A will confirm. |
| Performance regression in P2 | DS reports 10–20 sec/doc. Current production is similar order. Time on Phase B sample. |

---

## 5. Out of scope (tracked separately)

- Multi-ESN per PDF (deferred — needs Step 1 measurement first; see [01-chunking-strategy-comparison.md §7](01-chunking-strategy-comparison.md)).
- Document-level ESN scan (`esn_identifier.py`) — coupled to multi-ESN work.
- Retrieval / reranking changes — separate workstream.
