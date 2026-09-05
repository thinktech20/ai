# Ad-hoc doc repair job — design

> **Date:** 2026-05-07
> **Status:** Built + dev-validated. Code on branch `feat/667154-fsr-doc-repair-adhoc` (`pw_sdg_ai_ser_repo`). Runbook: [../runbook-doc-repair.md](../runbook-doc-repair.md).
> **Driver:** prod user-reported ESN/metadata corrections. Need a one-shot operator-driven script (not a pipeline) to fix a named doc end-to-end across metadata + chunks tables.
> **Scope:** ESN + equipment trio (`equipment_sys_id`, `equipment_type`, `equipment_class_code`).

## Intent

Operator says "doc X should have value Y for field F" → script reads current state, patches **only the named field(s)** in metadata + every related chunk row, writes audit, optionally dry-runs.

This is **not** detection. It is **not** re-extraction. It is a targeted MERGE driven by operator-supplied corrections.

The fsr_pdf_ref-driven bulk multi-ESN repair ([nb_sdg_fsr_repair_multi_esn.py](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_repair_multi_esn.py)) already exists for the corpus-wide case and stays as-is.

## Assumptions

1. Operator supplies the right value. We don't validate it against the PDF or any other source.
2. The fix targets a fixed whitelist of denormalized fields. See **Patchable fields** below.
3. ESN is denormalized in **3 places** today: `metadata.esn`, `chunks.esn` (column), `chunks.metadata` (JSON `"esn"` key). All three get patched together. The equipment trio fields are denormalized in 2 places: `metadata.<field>` and `chunks.metadata` (JSON key) — no top-level chunks column.
4. **Multiple chunk rows per (doc, chunk_index) can exist** because the multi-ESN row-duplication path writes one chunk row per (doc, chunk_idx, esn). All matching rows are read, backed up, and patched.
5. The chunk_id formula stays as-is — we don't re-key. **Primary keys (`document_id`, `chunk_id`) are never modified** in either path (patch or revert). The patched `esn` value can drift from the value embedded in the chunk_id MD5 hash; that's the safe, intentional choice — re-keying would break any external reference to chunk_id.
6. VS index sync is not part of this job. Caller triggers VS sync separately if the field being patched is filterable. (Confirm whether `esn` filterable column requires sync after a column update vs row insert.)
7. **Hard cap: 1 document per run.** This is an operator-driven targeted fix, not a backlog tool. The input schema is still a JSON array (so the same code path can be raised later if needed), but v1 rejects any payload with more than one document_id. Bulk corrections go through the existing `nb_sdg_fsr_repair_multi_esn.py`.
8. **One ESN value per patch.** If a doc needs to become multi-ESN, that's a different shape (insert chunk rows) — refuse and route to the bulk repair. v1 patches existing rows only, never inserts.
9. Default `DRY_RUN=true`. Must be explicitly set to `false` to write.
10. **Full-row backup before any write.** Every modified row from both tables is copied verbatim into a backup table (see **Backup + audit tables** below) before the UPDATE runs. Revert = re-MERGE from backup table by `(run_id, document_id)`.
11. **Backup + audit tables live in the same schema as the source tables** (`vaip.ai_sot_field_service_report.*`). No new schema. SRE-only write access.
12. **Backup is kept forever.** Volume is tiny. Every row carries `run_ts` so age is queryable; no TTL job.

## Patchable fields (whitelist)

v1 hard-codes this list. Anything not in the list is rejected at parameter validation.

| field | metadata column | chunks column | chunks.metadata JSON key | notes |
|---|---|---|---|---|
| `esn` | `esn` | `esn` | `"esn"` | also sets `metadata.esn_source = 'manual_repair'` |
| `equipment_sys_id` | `equipment_sys_id` | — | `"equipment_sys_id"` | |
| `equipment_type` | `equipment_type` | — | `"equipment_type"` | |
| `equipment_class_code` | `equipment_class_code` | — | `"equipment_class_code"` | |

Fields explicitly **out of scope for v1** (add later if asked): `customer`, `install_date`, `work_order`, `site`, `unit`, free-text fields, anything that requires re-extraction.

## Backup + audit tables

Two tables, both created idempotently in `nb_sdg_fsr_ddl.py`:

### `fsr_doc_repair_backup`

Full-row snapshot of every row touched, written **before** the UPDATE. This is the rollback source.

| column | type | meaning |
|---|---|---|
| `run_id` | STRING | UUID per repair run — all rows from one invocation share this |
| `run_ts` | TIMESTAMP | when the run started |
| `operator` | STRING | from `FSR_REPAIR_OPERATOR` |
| `reason` | STRING | from `FSR_REPAIR_REASON` |
| `source_table` | STRING | `metadata` or `chunks` |
| `document_id` | STRING | |
| `chunk_id` | STRING | nullable; populated for chunks rows only |
| `row_snapshot` | STRING (JSON) | full row as JSON — every column from the source table |
| `dry_run` | BOOLEAN | snapshot is captured even on dry-run for review |

Written in append mode. Never truncated. Revert workflow reads from here by `run_id`.

### `fsr_doc_repair_audit`

One row per (run, doc, field, table) capturing the change — readable summary, not full snapshot.

| column | type | meaning |
|---|---|---|
| `run_id` | STRING | matches backup table |
| `run_ts` | TIMESTAMP | |
| `operator` | STRING | |
| `reason` | STRING | |
| `document_id` | STRING | |
| `field` | STRING | one of the whitelist fields |
| `target_table` | STRING | `metadata` or `chunks` |
| `chunk_id` | STRING | nullable; for chunks rows |
| `old_value` | STRING | scalar before |
| `new_value` | STRING | scalar after |
| `dry_run` | BOOLEAN | |
| `applied` | BOOLEAN | true if write succeeded; false on dry-run or failure |

## Inputs (workflow parameters)

| param | required | example | meaning |
|---|---|---|---|
| `FSR_REPAIR_PATCHES_JSON` | yes | `[{"document_id":"abc","field":"esn","new_value":"297843"}]` | list of patches; one entry per (doc, field) tuple |
| `FSR_REPAIR_REASON` | yes | `"User report ADO #12345 — wrong ESN"` | written to audit row |
| `FSR_REPAIR_DRY_RUN` | no (default `true`) | `false` | safety gate |
| `FSR_REPAIR_OPERATOR` | yes | `"firstname.lastname"` | written to audit row |
| `FSR_REPAIR_REVERT_RUN_ID` | no | `"3f1c…"` | if set, the job runs in **revert mode** — reads `fsr_doc_repair_backup` for that `run_id` and replays the snapshot back into metadata + chunks. `FSR_REPAIR_PATCHES_JSON` is ignored. A new `run_id` is generated for the revert itself, with `reason = "revert of <original_run_id>"`, and a fresh backup is taken of the *current* state before the revert writes (so a revert can itself be reverted). |

Payload is an array, but v1 rejects anything with more than one distinct `document_id` (see Assumption 7). Multi-ESN additions are also rejected — route those to the bulk repair (see Assumption 8).

## Steps

### Step 0 — Ensure backup + audit tables exist

Run `CREATE TABLE IF NOT EXISTS` for `fsr_doc_repair_backup` and `fsr_doc_repair_audit` at the top of the notebook. Idempotent — no-op when they already exist. Schemas as defined in **Backup + audit tables** above.

### Step 1 — Validate inputs

- Parse `FSR_REPAIR_PATCHES_JSON`; reject any patch whose `field` isn't in the whitelist.
- Reject if more than one distinct `document_id` is present.
- Reject if any `field` appears more than once for that doc (no two competing values for the same field).
- Reject if `FSR_REPAIR_OPERATOR` or `FSR_REPAIR_REASON` empty.
- If `FSR_REPAIR_REVERT_RUN_ID` is set: skip the patches-input checks; instead require that `run_id` exists in `fsr_doc_repair_backup` and resolve the `document_id` from there.
- Generate `run_id = uuid4()` (always a fresh one, even on revert).

### Step 2 — Read current state

For each `document_id` in patch list:
- Pull current row from `biz_metadata_field_service_report` (1 row per doc).
- Pull all current rows from `biz_chunks_field_service_report` (N rows per doc — could be `chunk_count`, or `chunk_count * num_esns` if the multi-ESN row-duplication path ran for this doc).
- Capture `old_*` snapshot for audit.
- If the doc isn't in metadata, fail loudly — don't create a doc that doesn't exist.

### Step 3 — Write full-row backup

Before any UPDATE: serialise every row from Step 2 (metadata + chunks) as JSON and append to `fsr_doc_repair_backup` with `run_id`, `dry_run`, etc. Backup is written even on dry-run — it is the canonical "what existed at the moment of the run" snapshot, used both for revert and for after-the-fact review of what would have changed.

### Step 4 — Compute the changes

For each patch:
- Field value → `new_value`.
- Other fields on those rows → unchanged.
- For chunks.metadata JSON: regex-replace just the named key, leave the rest of the JSON intact. (Same approach as [nb_sdg_fsr_repair_multi_esn.py L101-114](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_repair_multi_esn.py).)
- If field is `esn`: also set `metadata.esn_source = 'manual_repair'`.

### Step 5 — Plan summary + dry-run gate

Print one block per doc showing:
- doc_id, field, old_value → new_value
- # metadata rows to UPDATE (always 1)
- # chunk rows to UPDATE (variable — depends on whether the doc went through the multi-ESN row-duplication path)
- backup row count written in Step 3

If `DRY_RUN=true` (default) → stop here. Print "no writes performed; backup snapshot still captured under run_id={run_id}."

### Step 6 — Apply (writes)

In one transaction per doc:
- MERGE metadata row (UPDATE only — never INSERT).
- UPDATE chunk rows: top-level column (if applicable for the field) + JSON metadata in one statement. Use `WHERE document_id = :doc AND <field>_old = :old_value` to be safe (don't blanket-update if a chunk row already has the new value from a prior partial fix).

### Step 7 — Audit

For each doc, write one row per (field, target_table) pair to `fsr_doc_repair_audit` with `applied=true` (or `false` on dry-run / failure). Audit references the same `run_id` as the backup.

### Step 8 — Caller-side follow-ups (out of script)

- VS index sync if needed (separate D&A action today).
- Notify the user who reported the issue.

## Revert

Revert is **the same notebook**, not a separate script. Set `FSR_REPAIR_REVERT_RUN_ID` to the `run_id` you want to undo. Job behaviour:

1. Branches early in Step 1: skips the patches-input validation; instead validates that `run_id` exists in `fsr_doc_repair_backup`.
2. Reads the snapshotted rows from `fsr_doc_repair_backup` for that `run_id`.
3. Reads current metadata + chunks rows for the same `document_id` (Step 2 unchanged) and writes them to a **fresh** `fsr_doc_repair_backup` entry under a new `run_id`. This is so the revert is itself revertible.
4. Computes the change as "current row → snapshot row" (Step 4 logic, but the target value comes from the snapshot rather than from `FSR_REPAIR_PATCHES_JSON`).
5. Same dry-run gate, same MERGE, same audit. Audit rows carry `reason = "revert of <original_run_id>"`.

Same primary keys (`document_id`, `chunk_id`) on both sides — no re-keying. Whitelist still applies (revert only touches the same fields the original run touched, since those are the only ones in the snapshot diff).

## Layout

This is a one-off ad-hoc script, not a pipeline. Everything lives in a single notebook — including the `CREATE TABLE IF NOT EXISTS` for the backup and audit tables (run as Step 0 every invocation, idempotent). No edit to the shared DDL notebook.

| path | purpose |
|---|---|
| `pw_sdg_ai_ser_repo/gold/src/etl/data_fixes/nb_fsr_doc_repair.py` | the whole job: DDL, patch path, revert path |
| `pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_doc_repair.yml` | DAB workflow with the params above (workflows live under `silver/` for all FSR jobs) |

## What this is *not*

- Not a detector. Operator names the right value.
- Not a re-extractor. It does not call the LLM.
- Not a pipeline. One-shot, manual trigger.
- Not VS sync. Caller's responsibility.
- Not a replacement for the existing bulk multi-ESN repair (that one stays for fsr_pdf_ref-driven cases).

## Decisions locked in

- **Whitelist:** ESN + equipment trio from day one.
- **Hard cap:** 1 document per run. Input shape stays as JSON array so it can be raised later without a schema change.
- **Multi-ESN add:** refused in v1. Route to bulk repair.
- **Backup + audit table location:** same schema as source tables (`vaip.ai_sot_field_service_report.*`). No new schema.
- **Retention:** keep forever; `run_ts` on every row makes age queryable.

## Open items

1. **VS sync trigger:** does the daily VS sync pick up column updates without a row-level rewrite? Deferred to runbook — operator triggers `PW_SDG_FSR_VS_Sync` after each repair until D&A confirms the sync picks up plain column updates. Conservative default in [../runbook-doc-repair.md](../runbook-doc-repair.md).
