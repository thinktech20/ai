# Runbook — ad-hoc doc repair (`PW_SDG_FSR_Doc_Repair`)

> **For:** SRE / on-call running an operator-driven correction on a single FSR document.
> **Tool:** [`PW_SDG_FSR_Doc_Repair`](../../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_doc_repair.yml) → notebook [`nb_fsr_doc_repair.py`](../../pw_sdg_ai_ser_repo/gold/src/etl/data_fixes/nb_fsr_doc_repair.py).
> **Design:** [design/adhoc-doc-repair-job.md](design/adhoc-doc-repair-job.md).
> **Ticket:** ADO #667154.

## When to use

A user reports a wrong value for a single field on a single document, and the correct value is known. Examples:
- ESN is `XXXXXX` (redacted) or wrong, and the operator has the correct serial from the PDF or from the user.
- Equipment type / sys_id / class code is wrong on one doc.

**Do NOT use this tool for:**
- Bulk corrections (>1 doc) → use the bulk multi-ESN repair (`PW_SDG_FSR_Repair_Multi_ESN`) or wait for the proper extractor fix (UI-15).
- Adding a second ESN to a doc that already has one → multi-ESN add is refused; use the bulk path.
- Fields not in the whitelist (`customer`, `install_date`, etc.) → not supported in v1.

## Whitelist of patchable fields

| field | what it touches |
|---|---|
| `esn` | `metadata.esn` + `chunks.esn` (column) + `chunks.metadata` JSON `"esn"` key. Also sets `metadata.esn_source = 'manual_repair'`. |
| `equipment_sys_id` | `metadata.equipment_sys_id` + `chunks.metadata` JSON key. |
| `equipment_type` | `metadata.equipment_type` + `chunks.metadata` JSON key. |
| `equipment_class_code` | `metadata.equipment_class_code` + `chunks.metadata` JSON key. |

Anything else is rejected at parameter validation.

## Job parameters

| param | required | example | meaning |
|---|---|---|---|
| `FSR_REPAIR_PATCHES_JSON` | yes (patch mode) | `[{"document_id":"abc","field":"esn","new_value":"297843"}]` | JSON array of patches. v1 cap: one distinct `document_id` per run. Multiple fields on the same doc OK. |
| `FSR_REPAIR_OPERATOR` | yes | `firstname.lastname` | written to backup + audit |
| `FSR_REPAIR_REASON` | yes | `User report ADO #12345 — wrong ESN` | written to backup + audit |
| `FSR_REPAIR_DRY_RUN` | no (default `true`) | `false` | safety gate. Must be `false` to apply writes. |
| `FSR_REPAIR_REVERT_RUN_ID` | no | `4e5c0413-7835-46df-…` | if set, run in **revert mode** (see below) |
| `FSR_METADATA_TABLE`, `FSR_CHUNK_TABLE` | yes | (DAB defaults) | source tables |
| `FSR_RUN_LOG_TABLE`, `FSR_DQ_LOG_TABLE`, `FSR_VS_ENDPOINT`, `FSR_VS_INDEX` | yes | (DAB defaults) | not used by this job; required by `fsr_config` import-time validation |

## Standard procedure (patch)

1. **Confirm the right value** with the user / source PDF. The job does not validate against the PDF.
2. **Dry-run first** (always):
   - `FSR_REPAIR_DRY_RUN=true`, fill operator + reason + patches.
   - Verify the plan summary in the run logs: old value → new value, # metadata rows (always 1), # chunk rows.
   - Note the `run_id` in the exit message — even on dry-run a backup snapshot is captured under that `run_id`.
3. **Apply** with the same params but `FSR_REPAIR_DRY_RUN=false`.
4. **Verify the writes** (replace `<run_id>` with the value from the logs):
   ```sql
   -- audit: one row per (field, target_table)
   SELECT field, target_table, old_value, new_value, applied
   FROM <fsr_metadata_schema>.fsr_doc_repair_audit
   WHERE run_id = '<run_id>';

   -- doc state
   SELECT esn, esn_source, equipment_type, equipment_sys_id, equipment_class_code
   FROM <metadata table>
   WHERE document_id = '<doc>';

   -- chunks (top-level + JSON)
   SELECT chunk_index, esn, SUBSTR(metadata, 1, 200)
   FROM <chunks table>
   WHERE document_id = '<doc>'
   ORDER BY chunk_index;
   ```
5. **Trigger VS sync.** Run `PW_SDG_FSR_VS_Sync` after each repair until D&A confirms the daily sync picks up plain column updates. Conservative default. (Open item — see design doc.)
6. **Notify the user** who reported the issue.

## Revert procedure

Same notebook. Set `FSR_REPAIR_REVERT_RUN_ID` to the `run_id` you want to undo:

| param | value |
|---|---|
| `FSR_REPAIR_PATCHES_JSON` | *(blank — ignored)* |
| `FSR_REPAIR_OPERATOR` | your name |
| `FSR_REPAIR_REASON` | `revert of <run_id>` |
| `FSR_REPAIR_DRY_RUN` | `true` (then `false` once dry-run looks right) |
| `FSR_REPAIR_REVERT_RUN_ID` | the original `run_id` |

The job:
- Reads the original snapshot from `fsr_doc_repair_backup`.
- Compares against current state, replays only fields that drifted.
- Takes a fresh backup of current state under a new `run_id` first (so a revert is itself revertible).
- Writes audit rows tagged `mode='revert'`.

If the doc has not drifted from the snapshot (rare — usually means somebody already reverted), the job exits cleanly as `NO-OP`.

## Backup + audit tables

Both live in the same schema as the metadata table:

- `fsr_doc_repair_backup` — full-row JSON snapshot of every metadata + chunk row touched, written **before** the UPDATE. Append-only, never truncated. This is the rollback source.
- `fsr_doc_repair_audit` — readable summary, one row per (run, doc, field, target_table). Contains old/new values, mode (`patch` or `revert`), operator, reason, dry_run, applied.

Useful queries:

```sql
-- recent repairs (any doc)
SELECT run_id, run_ts, mode, operator, document_id, field, old_value, new_value, applied
FROM <schema>.fsr_doc_repair_audit
ORDER BY run_ts DESC
LIMIT 20;

-- repair history for one doc
SELECT run_id, run_ts, mode, operator, reason, field, old_value, new_value, applied
FROM <schema>.fsr_doc_repair_audit
WHERE document_id = '<doc>'
ORDER BY run_ts DESC;

-- snapshot rows for a given run (revert source)
SELECT source_table, chunk_id, row_snapshot
FROM <schema>.fsr_doc_repair_backup
WHERE run_id = '<run_id>';
```

## Common errors

| message | cause | fix |
|---|---|---|
| `MISSING REQUIRED JOB PARAMETERS: FSR_…` | one of the six fsr_config params not passed | fill them in (DAB defaults cover dev/prod). |
| `FSR_REPAIR_OPERATOR is required` | empty operator | fill it. |
| `field='customer' is not in the whitelist` | trying to patch a non-whitelisted field | not supported in v1. |
| `field='esn' appears more than once for the same doc` | two entries for the same field on the same doc | pick one value. |
| `v1 cap: one distinct document_id per run` | tried to bulk-patch | use the bulk repair path. |
| `document_id='…' not found in <metadata table>` | typo or doc never ingested | verify the document_id. |
| `FSR_REPAIR_REVERT_RUN_ID='…' not found in fsr_doc_repair_backup` | typo or wrong env | check the run_id matches the env's backup table. |
| `Revert: no whitelisted fields differ from snapshot` | doc already matches snapshot | nothing to revert; no error. |

## What this is NOT

- Not a detector — operator names the right value.
- Not a re-extractor — it does not call the LLM.
- Not VS sync — caller's responsibility (see step 5).
- Not a replacement for the bulk multi-ESN repair (UI-14 / `PW_SDG_FSR_Repair_Multi_ESN`).
- Not a long-term fix — proper extractor work is UI-15.
