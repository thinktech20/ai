# Dev single-ESN smoke test — Vistra cross-train repair

**Goal:** validate the repair end-to-end in dev with **one** row from Jon's enriched workbook before running all 47.
**Branch:** `repair/697310-vistra-cross-train-generator-gap` (in `pw_sdg_ai_ser_repo`).

---

## 0. Prep — pick the test row

From `FSR/vistra-metadata-issue/input/Vistra Generator Missing Reports 5.31.26 - ENRICHED.xlsx`:

1. Open the workbook, filter `Gap Confirmed = YES`.
2. Pick **one** row whose `PDF (stem)` or `PDF Name` resolves cleanly in dev.

   First resolve the base metadata row by `pdf_name`:
   ```sql
    SELECT document_id, pdf_name, esn, metadata_status, chunk_status
    FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
    WHERE LOWER(pdf_name) = LOWER('Field_Service_Report_ProjectID_A-1375356_FSP-293536_C-10349934.pdf');
   ```

   Then run this eligibility check using the returned `document_id` and the missing Generator ESN from the sheet:
   ```sql
   WITH meta_check AS (
     SELECT 'metadata_target' AS check_name, COUNT(*) AS hits
     FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
    WHERE document_id = 'ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f_337X751'

     UNION ALL

     SELECT 'chunk_target_esn' AS check_name, COUNT(*) AS hits
     FROM vaid.ai_std_con_field_service_report.vec_field_service_report
     WHERE document_id LIKE 'ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f%'
          AND UPPER(TRIM(esn)) = UPPER(TRIM('337X751'))

     UNION ALL

     SELECT 'base_metadata_ready' AS check_name, COUNT(*) AS hits
     FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
    WHERE document_id = 'ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f'
       AND LOWER(metadata_status) = 'completed'
       AND LOWER(chunk_status) = 'completed'
   )
   SELECT * FROM meta_check;
   ```

   Use the row only if all of these are true:
   - base metadata row exists and is `completed` / `completed`
   - `metadata_target = 0` (the target `<BASE_DOC_ID>_<MISSING_ESN>` row does not already exist)
   - `chunk_target_esn = 0` (the missing ESN does not already appear in chunk rows for this doc)

   Notes:
   - Existing rows for some **other** ESN are fine.
   - Existing junk like `XXXXXX` in chunk rows is not ideal, but it does not block the test unless the target missing ESN already exists.
3. Record these for the verify queries later:
   - `BASE_DOC_ID`  = `ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f`
   - `BASE_ESN`     = `297603`
   - `MISSING_ESN`  = `337X751`
   - `NEW_DOC_ID`   = `ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f_337X751`
   - `BASE_PDF_NAME`= `Field_Service_Report_ProjectID_A-1375356_FSP-293536_C-10349934.pdf`

    Current chosen dev smoke-test candidate (from latest 47-file validation, exists in both tables):
    - `BASE_PDF_NAME` = `Field_Service_Report_ProjectID_A-1375356_FSP-293536_C-10349934.pdf`
    - Resolved from current dev query output:
       - `BASE_DOC_ID` = `ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f`
       - `BASE_ESN` = `297603`
       - `MISSING_ESN` = `<Missing ESN from xlsx row>`
       - `NEW_DOC_ID` = `<BASE_DOC_ID>_<MISSING_ESN>`

## 1. Build a 1-row test xlsx

Copy the enriched workbook → keep **only header row + the one chosen row** → save as:

```
Vistra_Single_ESN_Test_<your_initials>_<YYYYMMDD>.xlsx
```

Upload to the dev Volumes path:

```
/Volumes/vaid/ai_sot_field_service_report/repair_inputs/Vistra_Single_ESN_Test_MS_20260603.xlsx
```

If the folder doesn't exist, create it via the Catalog UI or:
```sql
CREATE VOLUME IF NOT EXISTS vaid.ai_sot_field_service_report.repair_inputs;
```
then put it under `.../repair_inputs/`.

The loader accepts either a stem-style column (`PDF (stem)`, `PDF Stem`, `pdf_stem`) or a filename-style column (`PDF Name`, `PDF File Name`, `pdf_name`). If you provide the filename form, it strips the trailing `.pdf` automatically before staging.

## 2. Capture before-state

Run these in the dev SQL editor and **save the output** (paste into a scratch tab — needed for compare in §7):

```sql
-- A. Base + any existing fan-out rows for this PDF
SELECT document_id, esn, esn_source, equipment_type,
       metadata_status, chunk_status
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
WHERE document_id LIKE 'ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f%'
ORDER BY document_id;

-- B. Chunk row counts per document_id for this PDF
SELECT document_id, esn, COUNT(*) AS chunks
FROM vaid.ai_std_con_field_service_report.vec_field_service_report
WHERE document_id LIKE 'ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f%'
GROUP BY document_id, esn
ORDER BY document_id, esn;

-- B2. Safety check — target missing ESN must not already exist for this doc
SELECT document_id, esn, COUNT(*) AS chunks
FROM vaid.ai_std_con_field_service_report.vec_field_service_report
WHERE document_id LIKE 'ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f%'
   AND UPPER(TRIM(esn)) = UPPER(TRIM('337X751'))
GROUP BY document_id, esn
ORDER BY document_id, esn;

-- C. Confirm MISSING_ESN exists in IBAT
SELECT equip_serial_number, equipment_sys_id,
       equipment_sub_class AS equipment_class_code
FROM vgpd.prm_std_views.ibat_equipment_mst
WHERE UPPER(TRIM(equip_serial_number)) = UPPER(TRIM('337X751'));
```

## 3. Sync notebooks to the dev workspace

Two options — pick whichever's easier.

**Option A — Git folder (recommended, 1 minute):**
1. In dev workspace UI: **Workspace → Repos → Add Repo**.
2. Point at the `pw_sdg_ai_ser_repo` repo, branch `repair/697310-vistra-cross-train-generator-gap`.
3. After clone, the four notebooks are at:
   - `gold/src/ddl/repairs/nb_sdg_fsr_repair_vistra_xtrain_ddl`
   - `gold/src/etl/repairs/nb_sdg_fsr_load_vistra_gap_staging`
   - `gold/src/etl/repairs/nb_sdg_fsr_repair_vistra_xtrain`
   - `gold/src/validation/repairs/nb_sdg_fsr_repair_vistra_xtrain_verify`
4. (Revert notebook lives at `gold/src/etl/repairs/nb_sdg_fsr_revert_vistra_xtrain` — only needed for §8.)

**Option B — manual upload:** open each `.py` locally, copy text, paste into a new notebook in the dev workspace under `/Users/<you>/vistra-test/`. Slower; only use if Repos is unavailable.

## 4. Create the dev job (manual, one-time)

Workflows UI → **Create Job** → name it `MS_Vistra_Xtrain_Repair_Dev_Test`.

If you cloned the branch into a Databricks Repo, the notebook paths will be under:

`/Workspace/Repos/<you>/pw_sdg_ai_ser_repo/`

Replace `<you>` with your Databricks Repo owner folder (usually your email or username as shown in the Repos UI).

Add four tasks in this order (each depends on the previous):

| Task key | Notebook | Timeout |
|---|---|---|
| `ddl_setup`   | `/Workspace/Repos/<you>/pw_sdg_ai_ser_repo/gold/src/ddl/repairs/nb_sdg_fsr_repair_vistra_xtrain_ddl`   | 600s |
| `load_stage`  | `/Workspace/Repos/<you>/pw_sdg_ai_ser_repo/gold/src/etl/repairs/nb_sdg_fsr_load_vistra_gap_staging`    | 1800s |
| `repair`      | `/Workspace/Repos/<you>/pw_sdg_ai_ser_repo/gold/src/etl/repairs/nb_sdg_fsr_repair_vistra_xtrain`       | 3600s |
| `verify`      | `/Workspace/Repos/<you>/pw_sdg_ai_ser_repo/gold/src/validation/repairs/nb_sdg_fsr_repair_vistra_xtrain_verify`| 1800s |

Cluster: any existing dev shared cluster, or use the same instance pool the other FSR jobs use.

**Job parameters** (add all under "Job parameters" so every task sees them):

| Param | Value |
|---|---|
| `jb_env` | `dev` |
| `FSR_METADATA_TABLE` | `vaid.ai_sot_field_service_report.biz_metadata_field_service_report` |
| `FSR_CHUNK_TABLE` | `vaid.ai_std_con_field_service_report.vec_field_service_report` |
| `FSR_RUN_LOG_TABLE` | `vaid.ai_sot_field_service_report.fsr_run_log` |
| `FSR_DQ_LOG_TABLE` | `vaid.ai_sot_field_service_report.fsr_data_quality_log` |
| `FSR_VS_ENDPOINT` | `pw-ser-sdg-vector-search` |
| `FSR_VS_INDEX` | `vaid.ai_std_con_field_service_report.vs_vec_field_service_report` |
| `FSR_CATALOG_VGPP` | `vgpd` |
| `FSR_PDF_REF_VIEW` | `vgpd.fsr_std_views.fsr_pdf_ref` |
| `INPUT_PATH` | `/Volumes/vaid/ai_sot_field_service_report/repair_inputs/Vistra_Single_ESN_Test_MS_20260603.xlsx` |
| `INPUT_SHEET` | `FSR Tagging Gaps` |
| `INPUT_FORMAT` | `auto` |
| `SOURCE_TAG` | `cross_tag_gap_v1` |
| `ENV_TAG` | `dev` |
| `DRY_RUN` | `true`  ← **leave true for the first run** |
| `CONFIDENCE_FILTER` | `confirmed` |
| `REPAIR_RUN_ID` | leave empty (auto-uuid) |

Copy/paste JSON version:

```json
{
   "jb_env": "dev",
   "FSR_METADATA_TABLE": "vaid.ai_sot_field_service_report.biz_metadata_field_service_report",
   "FSR_CHUNK_TABLE": "vaid.ai_std_con_field_service_report.vec_field_service_report",
   "FSR_RUN_LOG_TABLE": "vaid.ai_sot_field_service_report.fsr_run_log",
   "FSR_DQ_LOG_TABLE": "vaid.ai_sot_field_service_report.fsr_data_quality_log",
   "FSR_VS_ENDPOINT": "pw-ser-sdg-vector-search",
   "FSR_VS_INDEX": "vaid.ai_std_con_field_service_report.vs_vec_field_service_report",
   "FSR_CATALOG_VGPP": "vgpd",
   "FSR_PDF_REF_VIEW": "vgpd.fsr_std_views.fsr_pdf_ref",
   "INPUT_PATH": "/Volumes/vaid/ai_sot_field_service_report/repair_inputs/Vistra_Single_ESN_Test_MS_20260603.xlsx",
   "INPUT_SHEET": "FSR Tagging Gaps",
   "INPUT_FORMAT": "auto",
   "SOURCE_TAG": "cross_tag_gap_v1",
   "ENV_TAG": "dev",
   "DRY_RUN": "true",
   "CONFIDENCE_FILTER": "confirmed",
   "REPAIR_RUN_ID": ""
}
```

## 5. First run — DRY_RUN=true

Trigger the job. Expected outcomes:

- **ddl_setup**: creates 3 Delta tables if missing. Logs "Vistra DDL SETUP COMPLETE". Idempotent.
- **load_stage**: reads the 1-row xlsx → MERGEs into `staging_vistra_gap`. Logs row count = 1, `pending` = 1.
- **repair**: with DRY_RUN=true, prints the planned metadata-row count (= 1) and total chunk-row count (= N, the base PDF's chunk count). **No writes.** Staging stays `pending`.
- **verify**: will fail C1 (staging-done count 0 ≠ audit-meta 0 is fine, but with `REPAIR_RUN_ID` empty the notebook picks "latest from audit" — when audit is empty it raises). **Expected.** Disable the verify task for the dry run, or accept the verify failure as a dry-run artifact.

Recommended: for the dry run, **remove the verify task** (or set its run condition to skip). Re-add for the real run.

Inspect:
```sql
-- staging populated, status still pending
SELECT pdf_stem, missing_esn, dev_status, dev_error, confidence
FROM vaid.ai_sot_field_service_report.staging_vistra_gap;
```

## 6. Real run — DRY_RUN=false

1. Set job param `DRY_RUN` to `false`.
2. Re-trigger.
3. Re-add the verify task if removed in §5.

Expected:

- **load_stage**: idempotent re-merge, same 1 row.
- **repair**: inserts 1 metadata row, N chunk rows, 1 metadata audit row, N chunk audit rows. Marks staging `dev_status='done'`, captures `dev_run_id`. Logs "Vistra Repair Summary".
- **verify**: all 4 gates pass. C5 prints chunk distribution. C6 prints sample VS hits (or warns if VS hasn't synced yet — that's fine).

## 7. Post-run validation

Run the same queries as §2 and compare:

```sql
-- A'. Expect 1 new row: document_id = ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f_337X751, esn = 337X751,
-- esn_source = 'cross_tag_gap_v1', equipment_type = 'Generator'.
SELECT document_id, esn, esn_source, equipment_type
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
WHERE document_id LIKE 'ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f%'
ORDER BY document_id;

-- B'. Expect a new group: document_id = ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f_337X751, esn = 337X751,
-- chunks = same N as the base.
SELECT document_id, esn, COUNT(*) AS chunks
FROM vaid.ai_std_con_field_service_report.vec_field_service_report
WHERE document_id LIKE 'ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f%'
GROUP BY document_id, esn
ORDER BY document_id, esn;

-- D. Audit rows for this run
-- Metadata audit lives in ai_sot; chunk audit lives in ai_std_con.
SELECT *
FROM vaid.ai_sot_field_service_report.fsr_repair_vistra_metadata_updates
WHERE repair_run_id = 'dev_single_esn_fix_20260604_07';

SELECT COUNT(*) AS audited_chunks
FROM vaid.ai_std_con_field_service_report.fsr_repair_vistra_chunk_inserts
WHERE repair_run_id = 'dev_single_esn_fix_20260604_07';

-- E. Sample chunk row — confirm metadata JSON has rewritten esn/equipment fields
SELECT chunk_id, document_id, esn, metadata
FROM vaid.ai_std_con_field_service_report.vec_field_service_report
WHERE document_id = 'ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f_337X751';
```

Check the JSON in column `metadata` from query E — keys `esn`, `equipment_sys_id`, `equipment_type` (= `Generator`), `equipment_class_code` should match the IBAT values for `<MISSING_ESN>`, **not** the base row's.

---

## ✅ Smoke test results — 2026-06-04 (PASSED + REVERTED)

**Run ID:** `dev_single_esn_fix_20260604_07`  
**Branch:** `repair/697310-vistra-cross-train-generator-gap`  
**Test candidate:** `Field_Service_Report_ProjectID_A-1375356_FSP-293536_C-10349934.pdf` | base ESN `297603` | missing ESN `337X751`

### A'. Metadata row inserted correctly

| document_id | esn | esn_source | equipment_type |
|---|---|---|---|
| ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f | 297603 | fsr_pdf_ref | Gas Turbine |
| ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f_337X751 | 337X751 | cross_tag_gap_v1 | Generator |

✓ New row present with correct ESN, source, and equipment type.

### B'. Chunk rows cloned correctly

| document_id | esn | chunks |
|---|---|---|
| ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f | 297603 | 162 |
| ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f | XXXXXX | 162 |
| ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f_297603 | 297603 | 162 |
| ecb60ad9-f4dd-47d1-b60a-d9f4dd07d12f_337X751 | 337X751 | 162 |

✓ 162 chunks inserted for new document_id, matching base count.

### D. Audit counts

- Metadata audit rows: **1** ✓
- Chunk audit rows: **162** ✓

### E. Metadata JSON — sample chunk row

```json
{
  "pdf_name": "Field_Service_Report_ProjectID_A-1375356_FSP-293536_C-10349934.pdf",
  "title": "GE Power Power Services Moss Landing HGPI - Unit 2 7FA.03 Hot Gas Path Inspection w Exhaust Casing Replacement Moss Landing",
  "customer": null,
  "esn": "337X751",
  "equipment_sys_id": "SY0072569",
  "equipment_type": "Generator",
  "equipment_class_code": "7FH2",
  "event_type": "Hot Gas Path Inspection (HGPI)",
  "report_issued_date": "2021-05-25",
  "outage_start_date": "2021-03-14"
}
```

✓ `esn`, `equipment_sys_id`, `equipment_type`, `equipment_class_code` all match IBAT values for `337X751` — not the base row's Gas Turbine values.

### Revert (run after validation)

Revert job `MS_Vistra_Xtrain_Revert_Dev_Test` run with `REVERT_RUN_ID = dev_single_esn_fix_20260604_07`.

- Chunks deleted: **162** ✓
- Metadata rows deleted: **1** ✓
- Staging reset to `pending`: **1** ✓

**Post-revert state confirmed clean** — metadata table back to base-only row, chunk table back to pre-test groups, staging `dev_status = pending`.

---

## 8. Revert (only if test fails or you want to clean up)

Create a second job `MS_Vistra_Xtrain_Revert_Dev_Test` with one task pointing at `nb_sdg_fsr_revert_vistra_xtrain`. Same job parameters as the repair job, plus:

| Param | Value |
|---|---|
| `REVERT_RUN_ID` | the `repair_run_id` from §7 query D |

Trigger. It will:
1. Delete the inserted metadata row.
2. Delete the N inserted chunk rows.
3. Reset staging `dev_status` back to `pending`.
4. Print VS sync next steps (the index won't auto-clean; you'd need to trigger a VS resync if you want the deleted chunks gone from the index).

Re-run §7 queries A' and B' — they should match the §2 before-state.

## 9. After the smoke test passes

- Drop the test xlsx, generate the full 47-row xlsx, upload to the same Volumes folder under a different filename.
- Update `INPUT_PATH` job param.
- Re-run with `DRY_RUN=true` first, then `DRY_RUN=false`.
- This is dev step 3–4 in §6 of `analysis/approach-1-implementation-plan.md`.

### Prod pre-flight SQL pack

Before running the full file in prod, use these checks to estimate how many rows are already partially present and may end up as `skipped` instead of `done`.

```sql
-- P1. Target metadata rows already present in prod
SELECT s.pdf_stem,
          s.missing_esn,
          m.document_id,
          m.esn,
          m.esn_source,
          m.equipment_type
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
JOIN vaip.ai_sot_field_service_report.biz_metadata_field_service_report m
   ON m.document_id = CONCAT(s.document_id, '_', s.missing_esn)
WHERE LOWER(s.confidence) = 'confirmed'
ORDER BY s.pdf_stem, s.missing_esn;

-- P2. Target ESNs already present in prod chunk rows for the same document
SELECT s.pdf_stem,
          s.document_id AS base_document_id,
          s.missing_esn,
          c.document_id AS chunk_document_id,
          c.esn,
          COUNT(*) AS chunk_rows
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
JOIN vaip.ai_std_con_field_service_report.vec_field_service_report c
   ON c.document_id LIKE CONCAT(s.document_id, '%')
 AND UPPER(TRIM(c.esn)) = UPPER(TRIM(s.missing_esn))
WHERE LOWER(s.confidence) = 'confirmed'
GROUP BY s.pdf_stem, s.document_id, s.missing_esn, c.document_id, c.esn
ORDER BY s.pdf_stem, s.missing_esn, c.document_id;

-- P3. Confirmed rows that still look clean to process
WITH meta_hits AS (
      SELECT s.pdf_stem, s.missing_esn, COUNT(*) AS meta_hits
      FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
      LEFT JOIN vaip.ai_sot_field_service_report.biz_metadata_field_service_report m
         ON m.document_id = CONCAT(s.document_id, '_', s.missing_esn)
      WHERE LOWER(s.confidence) = 'confirmed'
      GROUP BY s.pdf_stem, s.missing_esn
),
chunk_hits AS (
      SELECT s.pdf_stem, s.missing_esn, COUNT(*) AS chunk_hits
      FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
      LEFT JOIN vaip.ai_std_con_field_service_report.vec_field_service_report c
         ON c.document_id LIKE CONCAT(s.document_id, '%')
       AND UPPER(TRIM(c.esn)) = UPPER(TRIM(s.missing_esn))
      WHERE LOWER(s.confidence) = 'confirmed'
      GROUP BY s.pdf_stem, s.missing_esn
)
SELECT s.pdf_stem,
          s.document_id AS base_document_id,
          s.missing_esn,
          COALESCE(m.meta_hits, 0)  AS meta_hits,
          COALESCE(c.chunk_hits, 0) AS chunk_hits
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
LEFT JOIN meta_hits m
   ON m.pdf_stem = s.pdf_stem AND m.missing_esn = s.missing_esn
LEFT JOIN chunk_hits c
   ON c.pdf_stem = s.pdf_stem AND c.missing_esn = s.missing_esn
WHERE LOWER(s.confidence) = 'confirmed'
   AND COALESCE(m.meta_hits, 0) = 0
   AND COALESCE(c.chunk_hits, 0) = 0
ORDER BY s.pdf_stem, s.missing_esn;
```

How to use this:
- `P1` shows rows where the target metadata doc already exists.
- `P2` shows rows where the target ESN already appears in chunk data for that document.
- `P3` shows the confirmed rows that still look clean to process.
- If `P1` or `P2` returns rows, that is not necessarily a blocker. It means those rows may become `skipped` or may need manual review after the prod run.

## Quick troubleshooting

| Symptom | Likely cause |
|---|---|
| `load_stage` says 0 rows pending | xlsx uploaded but `dev_status` not pending — check `dev_error` column for validation failure (doc_id not found, MISSING_ESN not in IBAT) |
| `repair` skips with "REPAIR_RUN_ID already exists in audit" | Re-running with same explicit `REPAIR_RUN_ID`. Clear the param to auto-uuid |
| `repair` skips a row with "target document_id already complete" | Target metadata + target chunks already exist. This is expected idempotent behavior |
| `verify` C2/C3 fail with empty audit | Repair ran in DRY_RUN mode — no audit rows written. Re-run with DRY_RUN=false |
| `verify` C6 warns "VS returned 0 hits" | VS index hasn't synced the new chunks yet (sync runs on a schedule). Not a real failure |
