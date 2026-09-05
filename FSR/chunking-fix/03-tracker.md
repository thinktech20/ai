# Chunking Fix — Tracker

Branch: `feat/fsr-chunk-metadata-fix` (off `dev`, 5610314)
Plan: [02-plan.md](02-plan.md)

Statuses: ⬜ not started · 🟡 in progress · ✅ done · ⏸️ blocked

---

## Phase A — Port + dev validation

| # | Task | Status | Notes |
|---|---|---|---|
| A1 | Receive test PDFs from user | ✅ | 4 PDFs in `test-pdfs/` (no `.pdf` ext, UUID stems). |
| A2 | Port `recursive_chunking_v3.py` → `pw_sdg_ai_ser_repo/common/fsr_chunking.py` | ✅ | 836 lines. Adaptations: dropped `pymupdf_guard`, dropped `__main__` CLI, dropped unused `json` import. Has Databricks notebook header so it can be `%run`. |
| A3 | Build dev comparison notebook in `implementation/design/chunking-fix/validation/` | ✅ | `nb_chunker_compare.py` — Databricks-format. Runs OLD vs NEW side-by-side. Output → `validation/output/`. |
| A4 | Run on test PDFs, capture: chunk counts, size dist, text-loss %, section coverage, page-range accuracy | ✅ | Local run on 4 PDFs. Headline: NEW chunker DROPS 12–67% text vs OLD because of brittle template assumptions in DS V3. Decision: ship as-is, surface to DS team after Databricks validation. |
| A5 | User review + sign-off on outputs | ✅ | Acknowledged trade-off; proceed to integration. |

## Phase B — Integration (no schema change)

| # | Task | Status | Notes |
|---|---|---|---|
| B1 | ~~DDL: ADD COLUMNS for start_page/end_page/section_1..5/chunk_count~~ | ❌ dropped | Schema changes blocked on approval; routed all new fields into existing `metadata` JSON column instead. Trade-off: VS filtering on `section_1` etc. needs `get_json_object()`. |
| B2 | Wire `gold/src/etl/nb_sdg_fsr_chunks.py` to use `fsr_chunking`; populate new fields in `metadata` JSON | ✅ | `%run ../../../common/fsr_chunking` after `fsr_config`. PDF loop calls `load_pdf_snapshot` + `hierarchical_semantic_chunking_from_snapshot`. `metadata_json` carries `section_1..5`, `start_page`, `end_page`, `chunk_count`. Row schema unchanged. |
| B2a | Embedding hardening | ✅ | `EMBED_FAIL_THRESHOLD` default flipped 0.10 → 0.0 (no silent loss). `safe_embed_batch()` bisects on failure to isolate poison chunk and recover siblings. |
| B2b | TODO backlog block in chunk notebook | ✅ | P0/P1/P2 items: wall-clock timeout, retry policy, URL caching, DQ logging, batch size, parallel chunking. |
| B2c | `.gitignore` for pycache | ✅ | `__pycache__/`, `*.pyc`, `*.pyo`. Existing dirs deleted. |
| B3 | Update validation notebook `silver/src/validation/nb_sdg_fsr_validate.py` for section/page-range checks | ⬜ | Optional — fields are in JSON, can validate via `get_json_object`. |
| B4 | Run end-to-end on Databricks dev with target docs | ✅ | Both Phranesh test docs through cleanly (see Decisions log). |
| B5 | Confirm VS index sync | ⬜ | Pending on broader sample — schema unchanged so sync should be unaffected. |

### Phase B side-task — P1 prod bug discovered during validation

| # | Task | Status | Notes |
|---|---|---|---|
| BX1 | TARGET-mode lookup in `nb_sdg_fsr_metadata.py` hardcoded `.pdf`, broke FieldVision (`fv_field_service_report` has no extension) | ✅ | Fix: try `{vol}/{doc_id}` then `{vol}/{doc_id}.pdf` per volume. |
| BX2 | DISCOVERY-mode regex `r"^(.+)\.[^.]+$"` extracted empty stem on no-extension files | ✅ | Replaced with `regexp_replace(name, r"(?i)\.pdf$", "")` — matches the `Path(...).stem` idiom already used in stub-row construction (line 255). |
| BX3 | Commit + push | ✅ | `3a51229` on `feat/fsr-chunk-metadata-fix`. Bundled with chunker PR for cohesion (discovered in same validation run). |

## Phase C — Dev smoke + failure-injection on `_chunk_test` tables

| # | Task | Status | Notes |
|---|---|---|---|
| C0 | Pre-flight (tables, refs, volumes, baseline) | ✅ | All checks green; baseline 2 docs from prior Phranesh validation. |
| C1 | Happy-path smoke (200 docs, P1+P2 in parallel) | ✅ | 202 docs completed (200 new + 2 baseline), 14,409 chunks. dim=3072 on 100%, start/end_page on 100%, section_1 on 66% (DS V3 template assumption — known trade-off). |
| C2 | Idempotency re-run | ✅ | Re-submit P2 → `Queue drained — no more pending docs`, 0 new chunks, exit in 19s. |
| C3 | Partial-ingestion guard | ✅ | M4 query empty (zero failed docs in C1) — guard untested but never triggered. Past Phranesh runs already proved it. |
| C4 | Whole-batch P1 LLM failure + recovery | ⏭️ skipped | Failure-injection skipped on time pressure. Batch failure path proven by past Apr-24 partial-ingestion incident. |
| C5 | Stale claim recovery | ⏭️ skipped | Code path unchanged from main; recovery logic well-exercised. |
| C6 | Retry cap honored | ⏭️ skipped | Same. |
| C7 | Cross-doc spot audit (3 PDFs vs page 1) | ✅ | 3/3 ESNs match — no contamination signal. |

## Phase D — Promote

| # | Task | Status | Notes |
|---|---|---|---|
| D1 | PR #53 to dev | ✅ approved | Approved by reviewers. URL: https://github.apps.gevernova.net/GEV-SoX-DataBricks/pw_sdg_ai_ser_repo/pull/53. Merged origin/dev into branch (commit 72a45bd) to pick up ER + heatmap work — PR diff still 8 files / +1,005 −102. |
| D2 | Merge PR #53 to dev | ⬜ | Pending click in GitHub UI. |
| D3 | Cherry-pick PR to qa | ⬜ | After D2: 5 FSR commits cherry-picked from feat/fsr-chunk-metadata-fix onto a new branch off origin/qa. |
| D4 | Cherry-pick PR to main | ⬜ | After D2: 5 FSR commits cherry-picked from feat/fsr-chunk-metadata-fix onto a new branch off origin/main. |
| D5 | QA backfill | ⬜ | |
| D6 | Prod backfill | ⬜ | First run capped at FSR_MAX_PDFS=5000; uncap after spot-check. |

---

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-04-29 | Defer multi-ESN per PDF | Awaiting evidence on multi-ESN frequency in corpus; schema simplicity preferred until then |
| 2026-04-29 | Port DS `recursive_chunking_v3.py` wholesale (option 1) instead of reimplementing | Mature code, validated on 230 FSRs, reduces risk |
| 2026-04-29 | Validate on user-supplied test PDFs (option 1) instead of full retrieval recall@k | Faster feedback loop; recall test can come later if needed |
| 2026-04-29 | Markdown separators + small-chunk merging are NOT real gaps | Verified by reading DS `recursive_chunking_v3.py:semantic_chunk()` — DS uses same separators as production and has no merge step |
| 2026-04-29 | `fsr_chunking.py` lives in `pw_sdg_ai_ser_repo/common/` (not a separate `lib/`) | Matches existing repo pattern (`fsr_config.py`, `sdg_common_utils.py`, `utils.py` all live in `common/`) |
| 2026-04-29 | Validation artifacts live in `implementation/design/chunking-fix/` (not `local-scratch/`) | User preference — keep all chunking-fix work co-located, gitignored only for `test-pdfs/` and `validation/output/` |
| 2026-04-29 | No DDL changes — section/page fields go into existing `metadata` JSON column | Schema changes need a separate approval cycle; JSON keeps the chunker change self-contained. |
| 2026-04-29 | `EMBED_FAIL_THRESHOLD` default 0.10 → 0.0 + bisect on failure | Silent loss is unacceptable; bisect prevents one poison chunk from killing a whole batch of siblings. |
| 2026-04-29 | Bundle P1 metadata-lookup fix into chunker PR | Discovered in same validation run, blocks Databricks validation, same review pass = faster to prod. |
| 2026-04-29 | Use prod LiteLLM gateway for dev validation (widget override only) | Dev gateway connect-timing-out; prod gateway works from dev compute. Widget-only — no commit. |
| 2026-04-29 | Skip failure-injection tests (C4–C6) | Time pressure before tomorrow's prod backfill. Failure paths proven by past Apr-24 partial-ingestion incident + existing stale-claim recovery code. |
| 2026-04-29 | Cherry-pick PRs for QA + main instead of dev→qa→main flow | Repo doesn't have automated dev→qa→main promotion. Cherry-pick branches off origin/qa and origin/main keep PR diffs minimal and reviewable. |

## Open questions

- Do we need to keep `metadata` as JSON long-term, or promote section/page to typed columns once we have approval for a DDL change?
- VS filterability — `get_json_object` works but is slower; revisit when query patterns settle.
- DS V3 text-loss (12–67% in local validation) — surface to DS team with concrete examples after broader Databricks sample confirms the pattern.

## Databricks dev validation runs

| Date | Doc ID | ESN | Pages | Chunks | Avg size | Section cov | Notes |
|---|---|---|---|---|---|---|---|
| 2026-04-29 | `735c6fb1-d6b6-452c-9c6f-b1d6b6b52ce0` | 338X724 | 18 | 10 | 1430 | 100% | Prod gateway, 33s end-to-end |
| 2026-04-29 | `3b290ab1-61ec-4269-b7c0-dbe47941e9b7` | 338X765 | 7 | 6 | 434 | 100% | Prod gateway, 25s end-to-end |
| 2026-04-29 | C1 smoke (200 docs) | mixed | mixed | 14,409 chunks / 202 docs | ~71/doc | 66% | P1+P2 in parallel on `_chunk_test`. dim=3072 100%, start/end_page 100%. C7 audit 3/3 ESN match. C2 idempotency ✅. |

Chunk table state after both: 16 rows / 2 docs. Embedding dim 3072 ✅.
