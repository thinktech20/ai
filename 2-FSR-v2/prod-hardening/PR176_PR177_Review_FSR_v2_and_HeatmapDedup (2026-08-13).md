# PR #176 & #177 Review — FSR v2 Redesign + Heatmap Embedding Dedup (Dev → QA)

**Repository:** `GEV-SoX-DataBricks/pw_sdg_ai_ser_repo`
**Reviewed:** 2026-08-13

> Note: reviewed via a local `git` clone + `refs/pull/<N>/head` fetch (GitHub Enterprise web UI requires corporate SSO not reachable from the automated fetch tool). Correct base branches were determined empirically with `git merge-base` since `origin/main` is stale relative to the active `fsr_v2` → `dev` → `qa` line.

---

## PR #176 — "Fsr v2"

**Branch:** `fsr_v2` (head) → `dev`
**Author:** Madhurima Saxena
**PR Head Commit:** `a1d4696e` ("standalone notebook")
**Diffed against:** `origin/dev` (merge-base `3dcb66a`)
**Scope:** 26 files changed, +6077/−1308
**Verdict:** ⚠️ **REQUEST CHANGES** (one SQL-injection gap must be fixed before merge; everything else is solid)

### 1. Scope Summary

| Area | Files | Summary |
|---|---|---|
| Config/DDL | `common/fsr_v2/config.py`, `common/fsr_v2/enums.py`, `databricks.yaml`, `ddls/fsr_v2/nb_sdg_fsr_v2_ddl.py` | New `fsr_run_log_v2` / `fsr_data_quality_log_v2` operational tables; new parse-once `parsed_volume_path`/`parsed_parser_version` columns + `FSR_PARSED_DOC_VOLUME_ROOT` volume; new `PYMUPDF_V1_0` extractor; chunking strategy hardcoded to `region_first:recursive` |
| Core logic | `common/fsr_v2/preprocessor.py` (modified), `common/fsr_v2/preprocessor_v2.py` (**new**, 1659 lines), `silver/src/etl/fsr_v2/metadata_processor_v2.py` | New `_choose_type_anchor_esn()` ESN-anchor selection (title/boundary evidence before alphabetical fallback); new IBAT-backed type-constrained ESN resolution (Phase 3 fallback) |
| Chunking | `gold/src/etl/fsr_v2/chunk_splitter.py` (**new**), `gold/src/etl/fsr_v2/chunking.py`, `gold/src/etl/fsr_v2/text_extraction.py`, `gold/src/etl/nb_sdg_fsr_v2_chunks.py` | Region-first recursive chunking with full P1 provenance |
| Metadata/parsing | `silver/src/etl/fsr_v2/input.py`, `metadata_enrichment.py`, `parsing.py`, `nb_sdg_fsr_v2_metadata.py` | Wiring for new parse-once flow + PyMuPDF extractor |
| Validation/tests | `tests/fsr_v2/test_preprocessor_v2.py` (**new**, 440 lines), `validation/fsr_v2/nb_fsr_v2_retrieval.py` (**new**, replaces 3 deleted notebooks), `validation/fsr_v2/ingest_data/*` (heavily rewritten + new debug notebook), `validation/fsr_v2/preprocessor/run-preprocessor-standalone.ipynb` (**new**) | Consolidated retrieval validation; standalone debug tooling |
| Workflows | `workflows/fsr_v2/pw_sdg_fsr_v2_p1_metadata.yml`, `p2_chunking.yml`, `p4_validation.yml` | Minor param additions for the new tables/volume |

### 2. Findings

#### Issue 1: SQL injection via unescaped `REQUESTED_ESN` widget in the new consolidated retrieval notebook (MEDIUM)

**File:** `validation/fsr_v2/nb_fsr_v2_retrieval.py` (new), ~lines 78–105

```python
REQUESTED_ESN = get_runtime_param("REQUESTED_ESN", "").strip().upper()
...
candidate_rows = spark.sql(f"""
    SELECT DISTINCT d.document_id
    FROM {MAP_TABLE} d
    INNER JOIN {METADATA_TABLE} m ON d.document_id = m.document_id
    WHERE UPPER(d.esn) = '{REQUESTED_ESN}'
      ...
""").collect()
```

`REQUESTED_ESN` is a free-text Databricks widget value that is interpolated directly into a SQL string literal with no quote-escaping or format validation, then reused verbatim in the `data_readiness` query block too. Anyone able to set widget parameters (including via a triggered job run) can break out of the string literal (e.g. `' OR 1=1 --`) and manipulate the query.

This is **not a new regression** — the same unescaped pattern already existed in the three notebooks this PR deletes (`nb_fsr_v2_retrieval_uc1.py`, `uc2_current.py`, `uc2_future.py`), and the historical hardening commit `00da54a` fixed `chunking.py`'s document-id interpolation, the hardcoded LiteLLM key, and `verify=False` — but never touched `REQUESTED_ESN`. Since this PR rewrites the file from scratch, it's the right moment to close the gap.

**Fix:** either escape it the same way already used elsewhere in this PR (`DEBUG_DOC_ID.replace("'", "''")` pattern in the new dev-debug notebook), or better, validate against the expected ESN shape before use:
```python
if not re.fullmatch(r"[A-Z0-9]{6,10}", REQUESTED_ESN):
    raise ValueError(f"Invalid REQUESTED_ESN format: {REQUESTED_ESN!r}")
```

#### Issue 2: SQL injection via unescaped `equip_type` in the new IBAT resolver (LOW — hardening recommended)

**File:** `silver/src/etl/fsr_v2/metadata_processor_v2.py`, `_make_ibat_resolver()`

```python
rows = spark.sql(f"""
    ...
    WHERE candidate_type = UPPER(TRIM('{equip_type}'))
      AND candidate_esn NOT RLIKE '^SY[0-9]{{7}}$'
""").collect()
```

`equip_type` is f-string-interpolated into the SQL literal rather than parameterized. Traced the call chain (`preprocessor_v2.py::_resolve_span_esn_with_ibat_train` → `span.equipment_type`) back to its source: it is always one of a small closed set (`Gas Turbine` / `Generator` / `Steam Turbine` / `Exciter`) produced by the fixed regex alternation `HEADER = r'(GAS TURBINE|GENERATOR|STEAM TURBINE|EXCITER)\s*\(...'`. So today this is **not practically exploitable** — it's never populated from raw, unconstrained PDF text. However it's still an f-string-built SQL value, which is the exact anti-pattern flagged in the PR #175 review, and this resolver function could be reused elsewhere later with less-constrained input. Recommend hardening now while it's cheap:
```python
WHERE candidate_type = UPPER(TRIM(:equip_type))
```
or at minimum whitelist-check `equip_type` against the known enum before interpolating.

#### Issue 3: `verify=False` retained in dev-only debug/reset notebook (LOW)

**File:** `validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest.py`, VS-index delete step (gated behind `DROP_TABLES_AND_INDEX`)

```python
resp = requests.delete(
    f"{WS_URL}/api/2.0/vector-search/indexes/{VS_INDEX}",
    headers=headers, timeout=30, verify=False,
)
```

Call target is the workspace's own Databricks REST API (not a third-party endpoint), and the file is an explicitly-named dev/debug tool, so exploitability is low. Still worth aligning with the `LLM_VERIFY_SSL` pattern used everywhere else in this PR (default `True`, opt-out via widget) for consistency.

#### Issue 4 (carried over, not new): production `FSR_LLM_VERIFY_SSL` still defaults to `"false"` (INFORMATIONAL)

**File:** `silver/src/etl/nb_sdg_fsr_v2_metadata.py`

```python
LLM_VERIFY_SSL = _parse_verify_ssl("FSR_LLM_VERIFY_SSL", "false")
```

This line is unchanged by PR #176 (pre-existing since before this PR) and was already flagged in the PR #175 review for a sibling notebook. Still outstanding on the production metadata pipeline — not a blocker for this PR specifically, but worth a follow-up ticket since the new consolidated retrieval notebook in this same PR correctly defaults `LLM_VERIFY_SSL` to `"true"`.

#### Observation: no explicit regression test for the "bare Turbine heading" fix

Two commits in this PR are titled "Fix regression: bare Turbine section headings not inheriting equipment type" (`44089b1`, `9f7fe48`), which is precisely the class of bug the user's own `fsr_regression_notebook.py` (`check_bare_turbine`) scans production output for. `tests/fsr_v2/test_preprocessor_v2.py` has good coverage of ESN-resolution precedence and boundary/gap logic (`test_esn_resolution_precedence_local_parent_single_type_ibat`, `test_boundary_path_eligibility_multi_esn_same_type_bug41`, `test_gap_guardrail_large_gap_avoids_neighbor_esn_inheritance`, etc.), but no test is explicitly named/scoped for the bare-Turbine-under-Steam-Turbine-parent scenario. Recommend adding one of the two known-bug fixtures from the regression notebook (`b896cb9f...` Rocksavage / `5b688732...` 316X914) as a permanent unit test so this can't silently regress again.

### 3. Positive Changes

- **`_choose_type_anchor_esn()`** is a well-reasoned improvement over the previous "first ESN alphabetically" heuristic — it prefers ESNs seen on the title page, then the most frequently-observed ESN at structural boundaries, and only falls back to alphabetical order as a last resort. This directly targets the ESN-misattribution class of bug the user's regression tooling checks for.
- New `fsr_run_log_v2` / `fsr_data_quality_log_v2` tables add real operational observability (per-run doc counts, failure categories, DQ severities) that didn't exist before.
- Parse-once architecture (`parsed_volume_path`) avoids redundant PDF re-parsing across P1/P2 stages — a legitimate performance/cost improvement.
- IBAT-based type-constrained ESN resolution is a sensible additional disambiguation layer for ambiguous multi-ESN documents, used only as a last-resort fallback after local/parent resolution.
- The new consolidated `nb_fsr_v2_retrieval.py` **correctly preserves** the historical security hardening for the LiteLLM path: `LLM_VERIFY_SSL` defaults to `"true"`, and `LITELLM_API_KEY` has no hardcoded default. No secrets or `verify=False` regressions found anywhere else in this 6000+ line diff (checked via full-diff pattern scan for hardcoded keys, `eval`/`exec`/`pickle`/`shell=True`, and other `verify=False` occurrences).
- Table names in DDL/config remain sourced from deploy-time bundle variables, not runtime/user input — consistent with the already-accepted pattern from PR #175.

---

## PR #177 — "Dev → QA"

**Branch:** `dev` (head is literally identical to `origin/dev`) → `qa`
**Author:** Namruth S P (merging PR #172, `feat/736374_Dedublicate_issue_prompt_embedding`)
**PR Head Commit:** `ff7014b9`
**Diffed against:** `origin/qa` (merge-base `8353bc8`)
**Scope:** 2 files changed, +100/−6
**Verdict:** ✅ **APPROVE**

### 1. Scope Summary

| File | Change Summary |
|---|---|
| `silver/src/etl/nb_sdg_heatmap_ingestion.py` | Deduplicates `issue_prompt` rows before embedding; row_id now derived from `issue_prompt` alone (post-dedup, one row per unique prompt); adds a retry pass for rows that failed embedding on the first attempt; adds a coverage-gap warning |
| `silver/src/validation/nb_sdg_heatmap_validate.py` | New checks: "all source issue_prompts have embeddings" (left-anti join) and "no duplicate issue_prompts in the embedding table" |

### 2. Findings

No security or correctness issues found. This is a small, focused promotion of already-tested `dev` work:

- Dedup key change (`equipment_type|persona|issue_prompt` → `issue_prompt` alone) is intentional and consistent with the new dedup step (`df.drop_duplicates(subset=["issue_prompt"], keep="first")`) — correct, since after dedup there's exactly one row per prompt and the ID should depend only on the text that was actually embedded.
- Retry pass correctly re-derives `row_id` the same way as the main pass, uses the same batch/backoff config vars (`HEATMAP_MAX_RETRIES`, `HEATMAP_EMBEDDING_BATCH_SIZE`), and updates `embedded`/`failed` counters consistently.
- New validation checks (5.1 coverage, 6.1 no-duplicates) are the right complement to the ingestion change and would have caught a regression in either the dedup or retry logic.
- `HEATMAP_SOURCE_VIEW` is interpolated into `spark.sql(f"SELECT DISTINCT issue_prompt FROM {HEATMAP_SOURCE_VIEW}")` but this is a fixed config-sourced view name, not user/runtime input — same low-risk pattern already accepted in prior reviews.

### 3. Positive Changes

- Clear, well-commented rationale for both the dedup key and the row_id change.
- Retry logic is bounded (fixed batch size, `time.sleep(5)` backoff) and doesn't silently swallow persistent failures — final counts and a sample of missing prompts are logged.
- Validation notebook additions give this pipeline meaningfully better regression detection than it had before.

---

## Combined Verdict Summary

| PR | Issue | Severity | Status |
|---|---|---|---|
| #176 | Unescaped `REQUESTED_ESN` interpolated into SQL in new `nb_fsr_v2_retrieval.py` | Medium | ❌ Fix before merge |
| #176 | Unescaped `equip_type` interpolated into SQL in new IBAT resolver (`metadata_processor_v2.py`) | Low | ⚠️ Recommend hardening |
| #176 | `verify=False` retained in dev-only `nb_fsr_v2_dev_ingest.py` VS-index delete call | Low | ⚠️ Recommend fixing for consistency |
| #176 | `FSR_LLM_VERIFY_SSL` still defaults `"false"` in production metadata notebook (pre-existing, not a regression) | Informational | 📝 Track separately |
| #176 | No explicit unit test for the "bare Turbine heading" regression fix | Informational | 📝 Recommend adding |
| #177 | None found | — | ✅ Clean |

**Overall recommendation:** Request changes on **PR #176** to close Issue 1 (SQL injection on `REQUESTED_ESN`) — everything else in that PR is additive and well-tested. **PR #177** is approved as-is.

## Notes for Follow-Up

- Consider extracting a single shared `safe_sql_literal()` / parameterized-query helper for the FSR v2 codebase, since the "escape single quotes manually" pattern is currently duplicated ad hoc across `chunking.py`, the dev-debug notebook, and (still missing) the retrieval notebook.
- File a follow-up ticket for the pre-existing `FSR_LLM_VERIFY_SSL` default in `nb_sdg_fsr_v2_metadata.py` (production pipeline), since it was already flagged in the PR #175 review and remains unresolved.
