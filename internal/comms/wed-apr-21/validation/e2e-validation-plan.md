# FSR Pipeline — End-to-End Validation Plan

Date: 2026-04-21
Status: **PASSED** — Run 5: 35/35 validation checks green (32 core + 3 schema alignment)
Scope: Run new pipeline on 7 FSRs, compare output against old `field_service_report_gt_litellm` ground truth, write findings.

---

## 1. Ground Truth Baseline

**Old table:** `main.gp_services_sdg_poc.field_service_report_gt_litellm`

The exported CSV has **100 chunk rows** for a single document:

| Field | Value |
|-------|-------|
| pdf_name | `337X393 2022-04-04 Robotic` |
| ESN | `337X393` |
| report_date | `null` (not populated in old pipeline) |
| pages covered | 10–306 (90 unique pages) |
| chunk_id pattern | `{pdf_name}_{index}` (0 to 103, some gaps) |

**Old schema columns:** `chunk_id, pdf_name, page_number, generator_serial, report_date, chunk_text, created_at, uploaded_at, chunk_embedding, metadata`

**Old metadata JSON blob keys:**
`chunk_count, chunk_esns, chunk_index, chunk_size, document_extension, end_page, esn_labels, schema_version, section_1, section_2, section_3, start_page, token_count`

---

## 2. Test FSR Selection (10 documents)

Since the GT CSV only contains 1 document (`337X393 2022-04-04 Robotic`), we select it plus 9 additional FSRs from the ESN list already validated in `fsr_pdf_ref`. Pick a mix of 337X and 290T series for variety.

Run this **in Databricks** to get 10 target document_ids:

```sql
-- Step 1: Find 10 FSRs with known ESNs from our validated set
-- Pick ones with a single ESN mapping for clean comparison
WITH target_esns AS (
  SELECT esn FROM (VALUES
    ('337X393'),   -- ground truth baseline
    ('337X305'),
    ('337X330'),
    ('290T762'),
    ('338X408'),
    ('337X709'),
    ('290T543'),
    ('338X713'),
    ('337X369'),
    ('338X425')
  ) AS t(esn)
),
candidates AS (
  SELECT
    LOWER(regexp_extract(s3_filename, '(.+)\\.pdf$', 1)) AS document_id,
    pdf_name,
    esn,
    ROW_NUMBER() OVER (PARTITION BY esn ORDER BY pdf_name) AS rn
  FROM vgpp.fsr_std_views.fsr_pdf_ref
  WHERE esn IN (SELECT esn FROM target_esns)
)
SELECT document_id, pdf_name, esn
FROM candidates
WHERE rn = 1
ORDER BY esn;
```

Record the 10 `document_id` values — these become the `FSR_TARGET_PDF_NAMES` job parameter.

---

## 3. Test Execution Steps

### 3a. Setup — Create test tables

Use runtime params to point at test tables (avoid touching the real ones):

| Parameter | Value |
|-----------|-------|
| `FSR_METADATA_TABLE` | `main.gp_services_sdg_poc.fsr_metadata_registry_test` |
| `FSR_CHUNK_TABLE` | `main.gp_services_sdg_poc.fsr_chunks_test` |
| `FSR_VS_INDEX` | `main.gp_services_sdg_poc.vs_fsr_chunks_test` |
| `FSR_TARGET_PDF_NAMES` | `94dd97dd-b529-4601-bb4a-8ae93130143d,f2fff7a8-1e70-4640-a7da-e3f979b334b6,b054e5d1-4623-496b-94e5-d14623796bd2,cf563f06-2f4e-4c0b-8443-43986b8cd75b,e6a1c986-ba88-417f-a3cc-d356b98ab79a,8a932cd9-4286-4008-932c-d9428630088f,d5334dce-9d7f-4fa1-b34d-ce9d7f7fa130` |
| `FORCE_RESET` | `true` (first run only — creates tables from scratch) |

**Actual test documents (7):**

| document_id (UUID) | ESN |
|---------------------|-----|
| `94dd97dd-b529-4601-bb4a-8ae93130143d` | 290T543 |
| `f2fff7a8-1e70-4640-a7da-e3f979b334b6` | 290T762 |
| `b054e5d1-4623-496b-94e5-d14623796bd2` | 337X369 |
| `cf563f06-2f4e-4c0b-8443-43986b8cd75b` | 337X709 |
| `e6a1c986-ba88-417f-a3cc-d356b98ab79a` | 338X408 |
| `8a932cd9-4286-4008-932c-d9428630088f` | 338X425 |
| `d5334dce-9d7f-4fa1-b34d-ce9d7f7fa130` | 338X713 |

### 3b. Run order

1. **DDL notebook** — `silver/src/ddl/nb_sdg_fsr_ddl.py`
   - Creates `fsr_metadata_registry_test` and `fsr_chunks_test`
2. **Process 1** — `silver/src/etl/nb_sdg_fsr_metadata.py`
   - Discovers the 7 PDFs, creates stubs, scrapes metadata via LLM, enriches from IBAT/EV/PSOT
3. **Process 2** — `gold/src/etl/nb_sdg_fsr_chunks.py`
   - Chunks, embeds, writes to chunk table, syncs to VS index
4. **Validation** — `silver/src/validation/nb_sdg_fsr_validate.py`
   - Automated quality checks

### 3c. Job Configuration

Parameters set as **job-level base parameters** on "PW SDG FSR Ingestion -TEST" job.
All 4 tasks inherit them automatically — no per-notebook widget injection needed.

### 3d. Bugs Found & Fixed

| Run | Step | Error | Fix | Commit |
|-----|------|-------|-----|--------|
| 1 | chunk_ingestion | `KeyError: 'chunk_size'` — log line referenced removed dict key | `c['chunk_size']` → `len(c['chunk_text'])` | `9064b81` |
| 2 | validate | `3.5 pdf_name null` — `success_records` missing `volume_path`, derivation SQL failed silently | Added `volume_path` to success_records | `58f9439` |
| 3 | validate | `3.5 pdf_name null` — enrichment step rebuilds `success_records` via `keep_cols`, which didn't include `volume_path` | Added `volume_path` to `keep_cols` | `a71f712` |

### 3e. Run Results

| Run | DDL | Metadata | Chunks | Validation | Notes |
|-----|-----|----------|--------|------------|-------|
| 1 | pass | pass | **FAIL** | — | `KeyError: 'chunk_size'` |
| 2 | pass | pass | pass (1125 chunks) | 31/32 | pdf_name null (missing volume_path in dict) |
| 3 | pass | pass | pass | 31/32 | pdf_name null (volume_path dropped by keep_cols) |
| 4 | pass | pass | pass (1125 chunks) | **32/32** | All checks green |
| 5 | — | — | — | **35/35** | Validate-only rerun with 3 new schema alignment checks (enrichment score, metadata JSON keys, report_date) |

---

## 4. Comparison Queries

### 4.1 Coverage: Old vs New chunk counts

```sql
-- How many chunks did the old pipeline produce for 337X393?
SELECT pdf_name, COUNT(*) AS old_chunks
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm
GROUP BY pdf_name;

-- How many chunks does the new pipeline produce?
SELECT pdf_name, COUNT(*) AS new_chunks
FROM main.gp_services_sdg_poc.fsr_chunks_test
WHERE pdf_name LIKE '%337X393%' OR esn = '337X393'
GROUP BY pdf_name;
```

### 4.2 Page coverage comparison

```sql
-- Old pipeline: which pages are represented?
SELECT
  MIN(page_number) AS min_page,
  MAX(page_number) AS max_page,
  COUNT(DISTINCT page_number) AS distinct_pages,
  COUNT(*) AS total_chunks
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm;

-- New pipeline: same metrics
SELECT
  MIN(page_number) AS min_page,
  MAX(page_number) AS max_page,
  COUNT(DISTINCT page_number) AS distinct_pages,
  COUNT(*) AS total_chunks
FROM main.gp_services_sdg_poc.fsr_chunks_test
WHERE pdf_name LIKE '%337X393%' OR esn = '337X393';
```

### 4.3 Chunk size distribution

```sql
-- Old
SELECT
  AVG(LENGTH(chunk_text)) AS avg_chars,
  MIN(LENGTH(chunk_text)) AS min_chars,
  MAX(LENGTH(chunk_text)) AS max_chars,
  PERCENTILE(LENGTH(chunk_text), 0.5) AS median_chars
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm;

-- New
SELECT
  AVG(LENGTH(chunk_text)) AS avg_chars,
  MIN(LENGTH(chunk_text)) AS min_chars,
  MAX(LENGTH(chunk_text)) AS max_chars,
  PERCENTILE(LENGTH(chunk_text), 0.5) AS median_chars
FROM main.gp_services_sdg_poc.fsr_chunks_test;
```

### 4.4 Metadata enrichment check (new pipeline only)

```sql
-- Metadata completeness for the 10 test FSRs
SELECT
  document_id,
  pdf_name,
  esn,
  equipment_type,
  event_type,
  report_issued_date,
  outage_type,
  technology_type,
  metadata_status,
  chunk_status,
  CASE WHEN esn IS NOT NULL THEN 1 ELSE 0 END
    + CASE WHEN equipment_type IS NOT NULL THEN 1 ELSE 0 END
    + CASE WHEN event_type IS NOT NULL THEN 1 ELSE 0 END
    + CASE WHEN report_issued_date IS NOT NULL THEN 1 ELSE 0 END
    + CASE WHEN outage_type IS NOT NULL THEN 1 ELSE 0 END
    AS enrichment_score
FROM main.gp_services_sdg_poc.fsr_metadata_registry_test
ORDER BY document_id;
```

### 4.5 Schema diff — old chunk metadata vs new metadata JSON

```sql
-- Old: metadata JSON keys (sample)
SELECT chunk_id, metadata
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm
LIMIT 1;

-- New: metadata JSON keys (sample)
SELECT chunk_id, metadata
FROM main.gp_services_sdg_poc.fsr_chunks_test
LIMIT 1;
```

### 4.6 Embedding dimension check

```sql
-- Old
SELECT chunk_id, SIZE(chunk_embedding) AS embed_dim
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm
LIMIT 1;

-- New
SELECT chunk_id, SIZE(chunk_embedding) AS embed_dim
FROM main.gp_services_sdg_poc.fsr_chunks_test
LIMIT 1;
```

### 4.7 Duplicate detection (new pipeline should have none)

```sql
-- Old pipeline was known to duplicate chunks across ESNs
SELECT chunk_text, COUNT(*) AS dupes
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm
GROUP BY chunk_text
HAVING COUNT(*) > 1;

-- New pipeline: should be zero
SELECT chunk_text, COUNT(*) AS dupes
FROM main.gp_services_sdg_poc.fsr_chunks_test
GROUP BY chunk_text
HAVING COUNT(*) > 1;
```

### 4.8 Content overlap — fuzzy match on 337X393

Compare whether the same text content appears in both old and new chunks for the common document.

```sql
-- Top-level join: how many old chunks have a near-match in new?
SELECT
  old.chunk_id AS old_chunk_id,
  new.chunk_id AS new_chunk_id,
  old.page_number AS old_page,
  new.page_number AS new_page,
  LENGTH(old.chunk_text) AS old_len,
  LENGTH(new.chunk_text) AS new_len,
  SUBSTRING(old.chunk_text, 1, 100) AS old_preview
FROM main.gp_services_sdg_poc.field_service_report_gt_litellm old
LEFT JOIN main.gp_services_sdg_poc.fsr_chunks_test new
  ON new.page_number = old.page_number
  AND new.pdf_name LIKE '%337X393%'
ORDER BY old.page_number, old.chunk_id
LIMIT 20;
```

---

## 5. Findings Template

After running the above, document results in this format:

### 5a. Summary

| Metric | Old Pipeline (GT) | New Pipeline | Notes |
|--------|-------------------|--------------|-------|
| Total chunks (337X393) | 100 | ___ | |
| Distinct pages covered | 90 | ___ | |
| Avg chunk size (chars) | ___ | ___ | |
| Embedding dimension | ___ | 3072 | Old was likely 1536 or 3072 |
| Duplicate chunks | ___ | 0 expected | Old had ESN-based duplication |
| Metadata enrichment score (avg) | N/A | ___/5 | New pipeline only |
| report_date populated | No (null) | ___ | Old was always null |
| Chunk metadata fields | 13 | 23 expected | section headers, equipment info, etc. |

### 5b. Qualitative Assessment

- [ ] Do chunk boundaries look reasonable? (check chunk_text previews)
- [ ] Are section headers captured in metadata JSON?
- [ ] Does page_number assignment look correct? (single page, not span)
- [ ] Is the ESN resolved correctly for all 10 FSRs?
- [ ] Are outage_type / technology_type populated from PSOT?
- [ ] Are event dates (report_issued_date, outage_start/end) parsed correctly?

### 5c. Known Differences (Expected)

| Aspect | Old Pipeline | New Pipeline |
|--------|-------------|--------------|
| chunk_id format | `{pdf_name}_{index}` | `md5(pdf_name + "_" + index)` |
| pdf_name | human-readable filename | UUID stem (document_id) |
| page_number | single page | single page |
| metadata location | JSON blob in `metadata` col | JSON blob in `metadata` col |
| metadata content | section headers, chunk metrics | section headers + all enrichment fields (23 keys) |
| report_date | always null | DATE from report_issued_date |
| ESN duplication | chunks duplicated per ESN | no duplication, single ESN per row |
| Embedding model | unknown (old) | azure-text-embedding-3-large-1 (3072d) |

### 5d. Issues Found

_To be filled after test run_

---

## 6. Prerequisite Checklist

- [ ] Pull `feature/fsr-pipelines` branch in Databricks Repos
- [ ] Verify PAT is configured for Git credentials
- [ ] Confirm `viud` volumes are accessible (PDF source)
- [ ] Confirm `vgpp` reference tables are accessible (IBAT, EV, fsr_pdf_ref, PSOT)
- [ ] Confirm LiteLLM gateway is reachable from cluster
- [ ] Confirm embedding model endpoint is available
- [ ] Note cluster/runtime version used for reproducibility
