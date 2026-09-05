# PR Review — ER Ingestion (PR #30) & Heatmap Ingestion (PR #29)

**Reviewer:** Madhurima  
**Date:** April 27, 2026 (re-reviewed)  
**PRs:** [#30 — ER Ingestion](https://github.apps.gevernova.net/GEV-SoX-DataBricks/pw_sdg_ai_ser_repo/pull/30) | [#29 — Heatmap Ingestion](https://github.apps.gevernova.net/GEV-SoX-DataBricks/pw_sdg_ai_ser_repo/pull/29)  
**Author:** Binayaka  

---

## Overall Summary

Both PRs introduce new pipelines (ER and Heatmap) that follow the same DDL → ETL → Validate + workflow YAML structure as the FSR ingestion pipeline. Structure is good. One previous blocker (FSR workflows file) has been resolved. One blocker remains (cross-PR file conflicts), plus several medium/minor issues, and a planned post-merge follow-up (shared utils → FSR migration).

---

## 🚨 BLOCKERS

### 1. ~~`pw_sdg_fsr_workflows.yml` — FSR jobs commented out~~ ✅ RESOLVED

**Status: Fixed.** Both PRs no longer touch `pw_sdg_fsr_workflows.yml`. The diff is now clean — only new files added, no modifications to existing FSR files. Good.

---

### 2. `common/sdg_common_utils.py` — shared utils extracted but `fsr_config.py` not updated (post-merge follow-up)

The PR introduces `common/sdg_common_utils.py` with shared helper functions (`get_runtime_param`, `get_runtime_bool`, `parse_runtime_list`, `decode_maybe_base64`, `get_dbr_auth`, `embed_texts_batch`, `trigger_vs_sync`, `check_vs_index_status`). This is the right direction — DRY is good.

Problem: `fsr_config.py` still contains its own private copies of most of these functions (`get_runtime_param`, `get_runtime_bool`, `parse_runtime_list`, `decode_maybe_base64`, `get_dbr_auth`). There are now two diverging implementations of the same logic.

**Critical difference in secret lookup order:**
- `sdg_common_utils.py` → `get_secret(scope, key, env_fallback)` tries **secret scope first**, then widget, then env var
- `fsr_config.py` → `_get_secret(key, env_fallback)` tries **widget first**, then secret scope, then env var (explicitly documented: "Widget-first precedence: the secret scope (fsr-pipeline) is not yet provisioned in all environments")

This order difference is not just cosmetic — it changes which value wins when both a widget param and a scope secret exist for the same key.

📍 **Note:** `common/sdg_common_utils.py` L8-9 currently says "Functions extracted from fsr_config.py (DRY)" but has no TODO or follow-up note.  
📍 **Also note:** `common/sdg_common_utils.py` L53 (`def get_secret`) — scope-first order differs from FSR's widget-first.

**Not blocking these PRs.** `fsr_config.py` should not be touched here — the shared-utils extraction is correctly scoped to ER/Heatmap only. The FSR migration (removing duplicate helpers from `fsr_config.py`, aligning secret-lookup order) will be handled as a separate follow-up PR after these merge.

**Follow-up PR (FSR config refactor — after these PRs merge):** Once `sdg_common_utils.py` lands on `dev`, open a dedicated FSR-only PR to:
1. Add `%run ./sdg_common_utils` at the top of `fsr_config.py`
2. Remove the five duplicate helpers: `get_runtime_param`, `get_runtime_bool`, `parse_runtime_list`, `decode_maybe_base64`, `get_dbr_auth`
3. Align the secret API — FSR's `_get_secret(key, env_fallback)` uses widget-first precedence intentionally (scope not yet provisioned everywhere). The shared `get_secret(scope, key, env_fallback)` uses scope-first. The migration must preserve widget-first for FSR until the scope is fully provisioned, and keep the scope bound to `FSR_SECRET_SCOPE` — not silently drop either behavior.
4. Run a full end-to-end test (DDL → P1 → P2 → Validate) against `_af_test` tables before merging.

Do not leave the divergence implicit — it will cause bugs when one copy gets updated and the other doesn't.

---

### 3. 🚨 NEW — Cross-PR file conflicts: `er_config.py` and `heatmap_config.py` differ between PR #29 and PR #30

Both PRs ship copies of `common/er_config.py` and `common/heatmap_config.py`, but the copies **are not identical**:

**`er_config.py` differences:**
- PR #29 `common/er_config.py` L65-78 has an older `ER_TEXT_FIELDS` list with `u_pac`-style column names (`problem_statement`, `abstract_text`, `corrective_action_text`, etc.) and a simpler DDL (no `er_number`, `opened_at`, `status`, `equipment_id` columns)
- PR #30 `common/er_config.py` L67-79 has the updated `ER_TEXT_FIELDS` with ServiceNow-style columns (`close_notes`, `comments`, `description_`, `short_description`, etc.) and the expanded DDL with all VS filter key columns

**`heatmap_config.py` differences:**
- PR #29 `common/heatmap_config.py` L22 defaults `HEATMAP_SOURCE_VIEW` to `"vgpp.fsr_std_views.fsr_unit_risk_matrix_view"` (hardcoded prod table)
- PR #30 `common/heatmap_config.py` L20 defaults `HEATMAP_SOURCE_VIEW` to `""` (safer, consistent with the `""` pattern used by all other configs)

**Risk:** Whichever PR merges second will create a merge conflict, or worse — silently overwrite the correct version with the stale one if the merge is auto-resolved.

**Required action:** 
1. Merge order: PR #29 (Heatmap) first, then PR #30 (ER). PR #30 has the correct/updated versions of both files, so merging it second means the conflict resolution naturally picks the better values.
2. When PR #30 hits the merge conflict on `er_config.py` and `heatmap_config.py`, resolve by taking PR #30's versions entirely (correct `ER_TEXT_FIELDS`, `""` default for `HEATMAP_SOURCE_VIEW`).
3. The person resolving conflicts on PR #30 should verify both shared files (`sdg_common_utils.py`, `databricks.yaml`, env configs) are identical across PRs — they are today, but confirm at merge time.

---

## PR #30 — ER Ingestion Pipeline

### Files changed
`common/er_config.py` (new), `common/sdg_common_utils.py` (new), `common/heatmap_config.py` (new), `databricks.yaml`, `env/dev/config_sdg.py` (new), `env/prod/config_sdg.py` (new), `silver/src/ddl/nb_sdg_er_ddl.py` (new), `silver/src/etl/nb_sdg_er_ingestion.py` (new), `silver/src/validation/nb_sdg_er_validate.py` (new), `silver/src/workflows/enabled/pw_sdg_er_ingestion.yml` (new), several `.gitkeep` files for folder structure

### What looks good ✅

- Pipeline shape matches FSR: DDL → ETL → Validate, same task dependency order
- `%run ../../../common/er_config` mirrors FSR's `%run ../../../Common/fsr_config`
- All table names parameterized via job parameters, no hardcoded table names in notebooks
- `FORCE_RESET` guard in DDL — correct, drops table AND deletes VS index
- Validation checks are numbered (1.x, 2.x, etc.) and follow the same pattern as `nb_sdg_fsr_validate.py`
- `queue: enabled: true` in workflow
- `run_as: user_name: ${var.run_as_user}` — cleaner than FSR's hardcoded email, FSR should adopt this pattern
- Single-notebook ETL is justified: ER is table-to-table with no PDF volumes, no two-phase P1/P2 split needed
- `databricks.yaml` changes are clean: `run_as_user` variable added, ER/Heatmap workflow includes added in the right place using glob patterns (`pw_sdg_er_*.yml`), permissions for team members added only to dev target
- VS index auto-creation logic in ingestion notebook — if index doesn't exist, creates it with correct DELTA_SYNC spec
- CDF enabled on ER chunk table (`'delta.enableChangeDataFeed' = 'true'`) — required for VS DELTA_SYNC
- DDL verify step confirms table exists with correct column count

### Issues

**Medium — `FORCE_RESET` overwrite in ER ingestion ETL (same as Heatmap issue)**  
📍 `silver/src/etl/nb_sdg_er_ingestion.py` L266-269  
`if FORCE_RESET: df.write.mode("overwrite").saveAsTable(ER_CHUNK_TABLE)`. But `nb_sdg_er_ddl.py` already drops and recreates the table on FORCE_RESET. So the sequence is: DDL drops → DDL creates empty → ingestion overwrites. The overwrite in ingestion is redundant and risky — `mode("overwrite")` can alter the table schema (e.g., nullable flags) to match the DataFrame schema, bypassing the DDL-managed schema. Should always use the MERGE path and let DDL handle the reset.

**Medium — `nb_sdg_er_ddl.py` uses `requests` library for VS index deletion**  
📍 `silver/src/ddl/nb_sdg_er_ddl.py` L19-20 (`import requests`, `import urllib3`) and L39 (`requests.delete(...)`)  
All other VS API calls in the codebase use `httpx` (via `sdg_common_utils`). Using both `requests` and `httpx` is inconsistent. Also imports `urllib3` just to disable warnings. Should use `httpx` here too — `sdg_common_utils` already has it available.

**Medium — ER ingestion has no partial-failure tracking**  
📍 `silver/src/etl/nb_sdg_er_ingestion.py` L205 (`return [c for c in chunks if c["chunk_embedding"] is not None]`)  
FSR P2 tracks `chunk_retry_count` per document so failed docs are retried on the next run. ER's ingestion has no equivalent — if 1,000 records embed successfully but 50 fail, the 50 are silently filtered out and never retried on subsequent runs. For a first version this is acceptable, but worth flagging as a gap before production.

**Minor — Unused import: `ThreadPoolExecutor`, `as_completed`**  
📍 `silver/src/etl/nb_sdg_er_ingestion.py` L27  
`from concurrent.futures import ThreadPoolExecutor, as_completed` — never used anywhere in the notebook. Likely left over from a parallel-embedding approach that was removed. Should be cleaned up.

**Minor — `er_config.py` has `ER_SECRET_SCOPE` hardcoded to `"fsr-pipeline"`**  
📍 `common/er_config.py` L33  
ER is borrowing the FSR secret scope. That's probably intentional (same LiteLLM gateway/keys), but it should have a comment explaining why. If ER ever gets its own secret scope, this is easy to miss.

**Minor — `env/dev/config_sdg.py` header says "Loaded by common/common_utils.py via cluster-tag env detection"**  
📍 `env/dev/config_sdg.py` L6 and `env/prod/config_sdg.py` L6  
No file named `common_utils.py` exists in the repo (only `sdg_common_utils.py`), and no notebook `%run`s these env configs. They're reference documentation, not active config. The header is misleading. Add a comment at the top clarifying they are reference-only constants, not loaded by any pipeline.

**Minor — SQL filter uses string interpolation for serial numbers**  
📍 `silver/src/etl/nb_sdg_er_ingestion.py` L46-47  
`extract_er_records()` builds `WHERE u_serial_number IN ('val1', 'val2')` via f-string interpolation from runtime parameters. In a Databricks Spark SQL context this is low risk (no multi-statement execution, parameters set by team members only), but it's still code hygiene to parameterize. Not blocking.

---

## PR #29 — Heatmap Ingestion Pipeline

### Files changed
`common/heatmap_config.py` (new), `common/sdg_common_utils.py` (new), `common/er_config.py` (new — stale copy, see Blocker #3), `databricks.yaml`, `env/dev/config_sdg.py` (new), `env/prod/config_sdg.py` (new), `silver/src/ddl/nb_sdg_heatmap_ddl.py` (new), `silver/src/etl/nb_sdg_heatmap_ingestion.py` (new), `silver/src/validation/nb_sdg_heatmap_validate.py` (new), `silver/src/workflows/enabled/pw_sdg_heatmap_ingestion.yml` (new), several `.gitkeep` files

### What looks good ✅

- Same DDL → ETL → Validate shape, consistent with FSR and ER
- Heatmap is simpler than ER (no chunking, just embed `issue_prompt` directly) — correctly reflected in the code
- MERGE by `row_id` — correct for idempotent upserts
- `FORCE_RESET` guard in DDL implemented
- Validation follows numbered check pattern
- `run_as: user_name: ${var.run_as_user}` — consistent with ER
- `queue: enabled: true` — correct
- `heatmap_config.py` structure mirrors `er_config.py` — good consistency between new pipelines
- `row_id` generated deterministically from `md5(equipment_type + persona + issue_prompt)` — good for idempotent MERGE
- No VS sync needed for heatmap (no VS index) — correctly omitted

### Issues

**Medium — `FORCE_RESET` in heatmap ingestion does a full overwrite, not just table drop**  
📍 `silver/src/etl/nb_sdg_heatmap_ingestion.py` L152-154  
If `FORCE_RESET=true`, the code calls `df.write.mode("overwrite").saveAsTable(...)`. But `nb_sdg_heatmap_ddl.py` already drops the table when `FORCE_RESET=true`. So on a FORCE_RESET run the sequence is: DDL drops table → DDL creates empty table → ingestion overwrites it. The overwrite in ingestion is redundant and slightly risky (it bypasses the DDL-managed schema). Should use the MERGE path always and let DDL handle the reset. Or at minimum, add a comment explaining the intentional double-drop.  
Compare to FSR: DDL handles `FORCE_RESET` fully; ETL notebooks don't have `FORCE_RESET` logic themselves.

**Medium — Missing `%pip install httpx` in heatmap ingestion**  
📍 `silver/src/etl/nb_sdg_heatmap_ingestion.py` — missing before L14 (`%run ../../../common/heatmap_config`)  
Compare: `silver/src/etl/nb_sdg_er_ingestion.py` L16 has `%pip install httpx --quiet`. Heatmap ingestion does NOT have this. Yet `heatmap_config.py` → `sdg_common_utils.py` → `embed_texts_batch()` imports `httpx` at call time. If `httpx` is not pre-installed on the cluster, the pipeline will fail at the embedding step with `ModuleNotFoundError`. Add `%pip install httpx --quiet` before the config `%run`.

**Medium — `heatmap_config.py` has `HEATMAP_SOURCE_VIEW` with a hardcoded prod default (PR #29 version)**  
📍 `common/heatmap_config.py` L22 (PR #29)  
`get_runtime_param("HEATMAP_SOURCE_VIEW", "vgpp.fsr_std_views.fsr_unit_risk_matrix_view")` — this is the only pipeline config that ships with a hardcoded prod table as default. All FSR and ER configs default to `""` and require parameters to be set. Running the pipeline with no parameters will silently read from prod.  
Note: PR #30's copy of `heatmap_config.py` L20 correctly defaults to `""`. Adopt that version.

**Minor — `nb_sdg_heatmap_ddl.py` does not enable `delta.enableChangeDataFeed`**  
📍 `silver/src/ddl/nb_sdg_heatmap_ddl.py` L36-39 (`CREATE TABLE` block — no `TBLPROPERTIES`)  
Compare: `silver/src/ddl/nb_sdg_er_ddl.py` L55 enables CDF. Heatmap doesn't use VS sync, so CDF is probably not needed, but it should be a conscious decision with a comment if intentionally omitted.

**Minor — `HEATMAP_EMBEDDING_TABLE` is required but Heatmap workflow YAML sets it to `""`**  
📍 `silver/src/workflows/enabled/pw_sdg_heatmap_ingestion.yml` L48  
The workflow YAML passes `HEATMAP_EMBEDDING_TABLE: ""` as the default. The `heatmap_config.py` L80-86 validation will throw a `ValueError` on every run unless overridden. This is the correct fail-safe behavior, but it means the pipeline can't be test-run from the UI without manually overriding the parameter. Add a comment in the YAML pointing to where the table name should be set (e.g., `# Override at run time — target: vaid.ai_sot_field_service_report.heatmap_issue_prompt_embeddings`).

**Minor — `HEATMAP_SECRET_SCOPE` also hardcoded to `"fsr-pipeline"` with no comment**  
📍 `common/heatmap_config.py` L30  
Same issue as ER (`common/er_config.py` L33) — borrowing FSR's scope. Add a brief comment.

---

## Summary Table

| # | File : Line | PR | Severity | Action |
|---|------------|----|----------|--------|
| ~~1~~ | ~~`pw_sdg_fsr_workflows.yml`~~ | ~~#29, #30~~ | ~~Blocker~~ | ~~✅ RESOLVED — file no longer touched~~ |
| 2 | `common/sdg_common_utils.py` L8-9, L53 | #29, #30 | ℹ️ Follow-up | Not blocking — FSR migration (remove duplicate helpers, align secret-lookup order) will be a separate post-merge PR |
| 3 | `common/er_config.py` L65-78 (PR#29 stale), `common/heatmap_config.py` L22 vs L20 | #29 vs #30 | 🚨 Blocker | Merge #29 first, then #30. Resolve conflicts by taking #30's versions (correct ER_TEXT_FIELDS, `""` default for HEATMAP_SOURCE_VIEW) |
| 4 | `silver/src/etl/nb_sdg_er_ingestion.py` L266-269 | #30 | Medium | Remove `FORCE_RESET` overwrite; always use MERGE path |
| 5 | `silver/src/etl/nb_sdg_heatmap_ingestion.py` L152-154 | #29 | Medium | Remove `FORCE_RESET` overwrite; always use MERGE path |
| 6 | `silver/src/ddl/nb_sdg_er_ddl.py` L19-20, L39 | #30 | Medium | Switch `requests` → `httpx` (consistent with rest of codebase) |
| 7 | `silver/src/etl/nb_sdg_heatmap_ingestion.py` (before L14) | #29 | Medium | Add `%pip install httpx --quiet` before config `%run` |
| 8 | `silver/src/etl/nb_sdg_er_ingestion.py` L205 | #30 | Medium | Note as known gap — failed embeddings silently dropped, no retry |
| 9 | `common/heatmap_config.py` L22 | #29 | Medium | Change default to `""`, require as job param |
| 10 | `silver/src/etl/nb_sdg_er_ingestion.py` L27 | #30 | Minor | Remove unused `ThreadPoolExecutor` / `as_completed` import |
| 11 | `common/er_config.py` L33, `common/heatmap_config.py` L30 | #29, #30 | Minor | Add comment explaining shared `fsr-pipeline` scope |
| 12 | `env/dev/config_sdg.py` L6, `env/prod/config_sdg.py` L6 | #29, #30 | Minor | Fix header (no `common_utils.py` exists), add comment: reference-only |
| 13 | `silver/src/ddl/nb_sdg_heatmap_ddl.py` L36-39 | #29 | Minor | Add CDF TBLPROPERTIES or comment why omitted |
| 14 | `silver/src/workflows/enabled/pw_sdg_heatmap_ingestion.yml` L48 | #29 | Minor | Add comment with target table name |
