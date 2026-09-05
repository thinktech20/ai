# ESN Resolution — Tracker

> **Started:** 2026-05-06
> **ADO:** #665755
> **Branch:** `fix/665755-esn-resolution` (off `dev`)
> **Parent:** UI-15 in [../tracker.md](../tracker.md).
> **Plan:** [plan.md](plan.md). **Input:** [esn-todos](esn-todos).
> One row per work item. Move rows to **Done** when consumer-verifiable.

---

## Open

### Phase 0 — Ground truth + DS-code analysis

| ID | Task | Status | Next action | Owner | Refs |
|---|---|---|---|---|---|
| ESN-01 | Map DS reference code components to our two sub-problems (cardinality vs extraction quality) | Not started | Walk [DS-ref-code/fsr_pipeline_dbr_final/src/](DS-ref-code/fsr_pipeline_dbr_final/) + read the two FSR Scraping POC PDFs in [DS-ref-code/ds-team-docs/](DS-ref-code/ds-team-docs/). Produce `analysis/ds-code-component-map.md` listing each module's role. | me | [esn-todos](esn-todos) §5, [plan.md Phase 0](plan.md) |
| ESN-02 | Inspect Pranesh's reference docs | Not started | Pull both PDFs (`d3b1da8a-03b4-4ea6-aa7b-0482edb532ce` and `3ef8d150-1225-4c62-ac5e-ae9166c73954`), dump page-1 + first-few-pages text, list all serials present. Cross-check against what current pipeline stored as `esn` for each. Output: `analysis/pranesh-ref-docs.md`. | me | [esn-todos](esn-todos) |
| ESN-03 | Corpus-wide cardinality measurement | Not started | Notebook under [../prod-issues/](../prod-issues/) — for the 18K corpus measure: (a) % of docs with ESNs only after page 1, (b) distinct-ESN-per-doc distribution (P50/P90/max), (c) ESNs that appear in >1 doc and how many. Output: `analysis/cardinality-measurement.md` + CSV. | me | [plan.md Phase 0.3](plan.md) |
| ESN-04 | Refresh failure-mode counts (Pattern A/B/C, pure-numeric, template tokens) on latest corpus | Done (2026-05-07) | Prod measurement against `vaip.ai_sot_field_service_report.biz_metadata_field_service_report` (18,029 completed docs). Buckets: 0 redacted, 5 null/empty, 2,904 `NNNANNN` (16.1%), 12,349 numeric 6-7 digits (68.5%, looks-real format), **166 numeric <6 digits (0.92%) — confirmed Pattern C** (e.g. `1083`, `10872`, `17872`), 2 numeric >7 digits, 2,334 other alphanum (12.95%), 269 other (1.49%). 50-doc sample of suspect-numeric shows sequential / multi-doc-duplicate IDs (work-order / project / IBAT leakage). Findings: prod scope much smaller than dev exercise implied — hundreds of clearly-bad ESNs, not thousands. Capture in [analysis/ds-code-test-results.md](analysis/ds-code-test-results.md) pending. | me | [esn-quality.md](../user-reported-issues/findings/esn-quality.md), [validation/nb_02_metadata_check.ipynb](../validation/nb_02_metadata_check.ipynb) §5 |

### Phase 0b — Test DS code as-is (before designing anything)

> Per Pranesh (2026-05-06): plan the new design **after** we've actually run the DS scraping + `esn_identifier` from `fsr_pipeline_dbr_final` against our docs and seen what it produces. The component map (ESN-01) tells us where the code lives; this phase tells us how well it works.

| ID | Task | Status | Next action | Owner | Refs |
|---|---|---|---|---|---|
| ESN-04a | Stand up DS `fsr_pipeline_dbr_final` runnable on dbr | Done (2026-05-06) | — | me | self-contained smoke notebook |
| ESN-04b | Run DS `esn_identifier` on 14-doc cohort (Pranesh 2 + Abhinaya 8 + manual ecrt 4) | Done (2026-05-06) | Results captured in [analysis/ds-code-test-results.md](analysis/ds-code-test-results.md). Top-1 match 9/9 UUID succeeded; manual ecrt produced real ESNs vs `XXXXXX` placeholders. | me | [smoke notebook](analysis/nb_ds_esn_identifier_smoke_test.ipynb) |
| ESN-04c | Decide which DS components to lift | In progress | Decision (2026-05-06): **don't lift DS code; one LLM call with modified prompt** — extend our existing P1 metadata prompt to also return `esn_mentions: {esn: count}` from a body-text window, resolver picks top-1 with `MIN_ESN_COUNT=1`. Draft in [analysis/ds-code-test-results.md](analysis/ds-code-test-results.md) + [design/1-esn-extractor-method.md](design/1-esn-extractor-method.md). Open: spot-check 4 recovered ESNs against PDFs (blocking); validate approach on 14-doc cohort with our prompt; re-run doc #7 with bigger token budget. | me | [nb_sdg_fsr_metadata.py L691-721](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) |
| ESN-04d | Spot-check 4 recovered ESNs (`298126`, `0298304`, `297897`) against source PDFs | Not started | Open the 4 manual ecrt PDFs (`090dbba1800f4f5b`, `090dbba18003a23c`, `090dbba180100488`, `090dbba1800b5e28`) and confirm the DS-extracted ESNs are real, not hallucinated. Blocking for ESN-04c sign-off. | me | [analysis/ds-code-test-results.md](analysis/ds-code-test-results.md) |
| ESN-04e | Validate approach C (modified prompt) on 14-doc dev cohort | Blocked on ESN-04d | Adapt [smoke notebook](analysis/nb_ds_esn_identifier_smoke_test.ipynb) into a new notebook that calls **our** prompt with the proposed `esn_mentions` extension on the same cohort. Compare top-1 from our extended prompt vs DS top-1 vs current stored. | me | [design/1-esn-extractor-method.md](design/1-esn-extractor-method.md) |
| ESN-04f | Repro doc #7 (`34bc62b0…`) with larger token budget | Not started | Re-run with `max_completion_tokens=8000` on `azure-gpt-5-2` and once on `gemini-3-flash` to disambiguate token-budget vs content-filter. Non-blocking. | me | [smoke notebook](analysis/nb_ds_esn_identifier_smoke_test.ipynb) |
| ESN-04g | Validate approach C on prod Pattern C cohort (10 docs from the 166 suspect-numeric) | Not started | Pick ~10 docs from the 166 `<6-digit` bucket, mixing: (a) sequential cluster (e.g. `10872`, `10873`, `10874`, `26888`-`26892`); (b) multi-doc duplicates (e.g. `5928`, `13933`, `17872`, `19430`); (c) dual-source agreement rows (`1083`, `10856`, `43561` — stored under both `llm` AND `fsr_pdf_ref`). Run smoke notebook with `MIN_ESN_COUNT=1` and check whether DS body-text extraction returns a different (real) ESN with high count. This is the cleanest "approach C catches Pattern C in prod" evidence. | me | [analysis/ds-code-test-results.md](analysis/ds-code-test-results.md), prod query results 2026-05-07 |
| ESN-04h | Spot-check 6-7 digit numeric bucket (the 12,349 “mostly fine” majority) | Not started | Random sample 20 docs from `esn RLIKE '^[0-9]{6,7}$'` in prod; manually verify against PDFs that the stored ESN is on the page-1 ESN field. Goal: confirm the 68.5% headline isn't masking widespread Pattern C in the 6-7 digit range. Non-blocking unless ESN-04g shows the failure mode is broader than `<6` digits. | me | prod query results 2026-05-07 |
| ESN-04i | Investigate `2_V1.0.pdf` / `3_V1.0.pdf` template docs in manual ecrt | Not started | Three rows in the suspect-numeric sample have document_ids that look like template files (`2_v1.0`, `3_v1.0`, `090dbba1800f08e2`). Confirm whether these are sample/test PDFs that shouldn't be in prod at all. Hygiene issue, separate from extraction quality. | me | prod query results 2026-05-07 |

### Phase 1 — Options + design

| ID | Task | Status | Next action | Owner | Refs |
|---|---|---|---|---|---|
| ESN-05 | Build option matrix (5 candidates) | Partially done | Three options for the **extractor** worked through in [design/1-esn-extractor-method.md](design/1-esn-extractor-method.md): A. fallback, B. two LLM calls, **C. one call + modified prompt (picked)**. Cardinality option matrix (data-shape: array vs join table vs row dup) covered in [design/2-multiple-esn-design.md](design/2-multiple-esn-design.md); pipeline cursor / anti-join in [design/3-incremental-ingestion-and-watermark.md](design/3-incremental-ingestion-and-watermark.md). | me | [design/1-esn-extractor-method.md](design/1-esn-extractor-method.md) |
| ESN-06 | Cardinality model decision (A row fan-out vs B `esn_details` struct array) | **Done (2026-05-26) — Option B picked.** | Decision: one metadata row per PDF + `esn_details: ARRAY<STRUCT>` (per [design/proposed-multi-ESN-design.md](design/proposed-multi-ESN-design.md)). Stable `document_id`, per-ESN equipment attrs preserved, chunks materialized once, UI-14 sunsettable. Option A archived in [design/2-multiple-esn-design.md](design/2-multiple-esn-design.md) (do not re-litigate). Extractor decision (option C, one LLM call) remains independent and unchanged. | me | [plan.md “Open items — Option B”](plan.md) |
| ESN-06a | Option B — VS pre-filter strategy (B1 derived `esns ARRAY<STRING>` vs B2 `primary_esn` only) | **Done (2026-05-26)** | Decided B1: derived `esns: ARRAY<STRING>` column on metadata + chunks for VS membership filtering on the array field. B2 rejected (re-introduces UI-14 secondary-ESN invisible problem). Internal dev POC completed 2026-05-26 against temp table/index `vaid.ai_sot_field_service_report._tmp_vs_arrayfilter_test` / `_tmp_vs_arrayfilter_test_idx`: VS query API returned only `doc3`, `doc1`, `doc4` for filter JSON `{"esn_list":"ESN-001"}`, confirming array-membership filtering works at platform level. FSR-specific index exposure, consumer app change, and perf confirmation remain Phase 3 work. | me | [plan.md §1](plan.md) |
| ESN-06b | Option B — `esn_details` struct field list final | **Done (2026-05-26)** | Decided: `esn, equipment_sys_id, equipment_type, equipment_class_code, esn_source, rank, esn_count`. Added `esn_count` (DQ + audit). Dropped `confidence` (derivable from count) and `extracted_at` (row-level timestamps cover it). | me | [plan.md §2](plan.md) |
| ESN-06c | Option B — chunk-side ESN representation (C1 full struct vs C2 `esns ARRAY<STRING>` + JSON) | **Done (2026-05-26)** | Decided C2: chunk top-level = `esns ARRAY<STRING>` + legacy `esn` STRING (= `primary_esn`); full `esn_details` in chunk `metadata` JSON payload. Equipment attrs don't drive VS filter at chunk granularity. | me | [plan.md §3](plan.md) |
| ESN-06d | Option B — `primary_esn` deprecation plan + migration of existing 18K corpus | **Done (2026-05-26)** | Deprecation decided: **keep `primary_esn` indefinitely** as denormalized convenience column. Migration of 18K corpus folded into design doc open item [O4](design/proposed-multi-ESN-design.md#open-items) (v2 tables vs alter) — recommendation is v2 tables, which means re-running metadata extraction + chunking into `metadata_v2`/`chunks_v2` rather than backfilling in place. | me | [design/proposed-multi-ESN-design.md §Open items O4](design/proposed-multi-ESN-design.md#open-items) |
| ESN-06e | Option B — UI-14 sunset path (delete duplicated chunk rows, restore single-row chunks per source PDF) | **Done (2026-05-26)** | Folded into v2 cutover ([O4](design/proposed-multi-ESN-design.md#open-items)): v1 tables + UI-14 patch retire together when consumers cut over to `metadata_v2`/`chunks_v2`. No separate revert sequence needed. | me | [design/proposed-multi-ESN-design.md §Open items O4](design/proposed-multi-ESN-design.md#open-items), [pw_sdg_fsr_revert_multi_esn.yml](../../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_revert_multi_esn.yml) |
| ESN-06f | Option B — extraction sub-decisions (count threshold, P1 vs P2, fsr_pdf_ref role, scan window) | **Done (2026-05-26)** | Decided: (a) fallback to page-1 ESN + DQ row `esn_low_confidence` when no body-text mention; (b) extractor runs in P1 via single LLM call with `esn_mentions` extension; (c) `fsr_pdf_ref` = hint only, never overrides high-confidence body-text ESN; (d) use existing P1 body-text window, widen only if Phase 0.3 measurement shows >5% ESNs hidden beyond it. | me | [plan.md §6–9](plan.md), [design/1-esn-extractor-method.md](design/1-esn-extractor-method.md) |
| ESN-06g | Option B — `document_id` strategy (keep uuid vs hash(volume+docid)) | **Done (2026-05-26)** | Decided: **keep uuid**. Stability is the whole point of Option B; switching now self-defeats. Revisit only if re-ingest idempotency becomes an actual pain point. | me | [plan.md §5](plan.md) |
| ESN-07 | Write ADR (data model = Option B, document_id strategy, extractor, validation, migration, rollback) | **In review (2026-05-26)** | Design doc [design/proposed-multi-ESN-design.md](design/proposed-multi-ESN-design.md) finalized and sent to DS team + Scope agent stakeholders on Slack for input on open items [O1–O7](design/proposed-multi-ESN-design.md#open-items). Promote to ADR under [../../internal/adr/](../../internal/adr/) once O1 (DS extraction method) and O4 (v2 tables vs alter) are confirmed. | me | [design/proposed-multi-ESN-design.md](design/proposed-multi-ESN-design.md), [plan.md Phase 1.3](plan.md) |
| ESN-07a | Decide handling of ESN-specific equipment attributes | **Done (2026-05-26)** | Resolved by Option B: per-ESN `equipment_sys_id`/`equipment_type`/`equipment_class_code` live inside the `esn_details` struct, bound to their ESN. No separate child table needed. | me | [design/proposed-multi-ESN-design.md](design/proposed-multi-ESN-design.md) |
| ESN-28 | Train-level retrieval expansion — materialize `train_sys_id_fk` in metadata + `train_ids ARRAY<STRING>` in chunks (Path 2) | **Open — needs stakeholder discussion (2026-05-27)** | Driver: [train/FSR_IBAT_Investigation_2026-05-26.md](train/FSR_IBAT_Investigation_2026-05-26.md) shows FSRs are filed against one ESN but the natural retrieval unit is the **train** (GT+Gen+ST+ECS share `train_sys_id_fk` in `vgpp.fdc_std_views.eu_ibat`). System-wide skew: 15,912 GT-tagged FSRs vs 235 Gen-tagged; 458 GT FSRs have strong generator content; train expansion rescued 17% of zero-result GT ESNs (+544 FSRs across a 500-sample). Three paths considered: (1) query-time IBAT join in consumer app — no schema change; (2) **materialize `train_sys_id_fk` per ESN in `esn_details` + denormalized `train_ids ARRAY<STRING>` on metadata & chunks for direct VS filtering — recommended**; (3) hybrid (store train_id in `esn_details` only, expansion still in consumer). Path 2 picked tentatively; keeping out of the design doc until discussed with DS team + Scope agent + consumer app owners. Discussion points: (a) train membership in IBAT can change over time → staleness vs runtime-join trade-off; (b) does VS filter on `train_ids` belong alongside `esns` or replace it for train-aware queries; (c) who maintains the IBAT snapshot used at extraction time; (d) DQ side-track — 458 mis-tagged GT FSRs need DS-side relabel, independent of this. **Next action:** raise on next sync with DS + Scope owners, capture decision, then either promote to design doc as O8 or close as "deferred to consumer-app expansion". | me | [train/FSR_IBAT_Investigation_2026-05-26.md](train/FSR_IBAT_Investigation_2026-05-26.md), [design/proposed-multi-ESN-design.md](design/proposed-multi-ESN-design.md) |

### Phase 2 — Implementation

| ID | Task | Status | Next action | Owner | Refs |
|---|---|---|---|---|---|
| ESN-08 | Cut implementation branch off `dev` | Blocked on ESN-07 | Branch: `fix/665755-esn-resolution` (ADO #665755). Old `fix/multiple-esns` work informs but does not necessarily carry forward. | me | — |
| ESN-09 | DDL changes (additive, on dev `_esn_v2` suffix tables) | Blocked on ESN-07 | Update `pw_sdg_ai_ser_repo/silver/src/ddl/nb_sdg_fsr_ddl.py`. Idempotent ALTER. | me | — |
| ESN-10 | New extractor (port DS components per ESN-01 map) | Blocked on ESN-07 | Create `pw_sdg_ai_ser_repo/silver/src/etl/esn_identifier.py` (or named per design). Pure-text input, no PDF I/O if possible. | me | DS reference code |
| ESN-11 | P1 metadata pipeline integration | Blocked on ESN-10 | Wire extractor into [`nb_sdg_fsr_metadata.py`](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py). Update L677-679 resolver. | me | — |
| ESN-12 | P2 chunk pipeline integration (3-place propagation per design) | Blocked on ESN-11 | Wire into [`nb_sdg_fsr_chunks.py`](../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py). Touch L246/L494 (column) + L428/L459 (JSON). | me | — |
| ESN-13 | VS index DDL + dev sync | Blocked on ESN-09 | Rebuild dev VS index `_esn_v2` suffix; expose any new filterable columns per design. | me | — |
| ESN-14 | Wire validation harness to new extractor + add cohorts | Blocked on ESN-10 | Replace stub in [`nb_esn_pr_validation.ipynb`](../user-reported-issues/validations/nb_esn_pr_validation.ipynb). Add many-doc-per-ESN cohort. | me | — |
| ESN-15 | Generic data-fix job (UI-13 lineage) for new extractor | Blocked on ESN-10 | Repurpose dispatcher under `pw_sdg_ai_ser_repo/silver/src/etl/data_fixes/`. Audit table + selective-overwrite policy carries forward. | me | UI-13 in [../tracker.md](../tracker.md) |

### Phase 3 — Dev validation (M1-M5)

| ID | Task | Status | Next action | Owner |
|---|---|---|---|---|
| ESN-16 | M1 — sandbox smoke test on small cohort | Blocked on ESN-08..15 | Pranesh's 2 + Abhinaya's 12 + 5 UI-03. End-to-end P1+P2 on `_esn_v2` tables. | me |
| ESN-17 | M2 — data-fix job sandbox run | Blocked on ESN-16 | Targeted dry-run → APPLY → VS sync → re-query. | me |
| ESN-18 | M3 — DDL on dev real tables (`vaip_dev.*`) | Blocked on ESN-17 | Idempotent ALTER. VS index registers new filterable columns. | me + D&A |
| ESN-19 | M4 — targeted data-fix on real dev tables | Blocked on ESN-18 | Same cohort. Confirm Abhinaya heat-map test recovers on real dev tables. | me |
| ESN-20 | M5 (optional) — bulk-mode soak test (500-doc slice) | Blocked on ESN-19 | Measure runtime, audit volume, VS sync lag. Greenlight required for bulk in prod. | me |

### Phase 4 — Prod rollout (M6-M8)

| ID | Task | Status | Next action | Owner |
|---|---|---|---|---|
| ESN-21 | M6 — DDL on prod | Blocked on ESN-19 (M5 optional) | Idempotent ALTER. VS index filterable columns via D&A ticket. | me + D&A |
| ESN-22 | M7 — targeted prod data-fix on Abhinaya's 12 | Blocked on ESN-21 | Dry-run → APPLY → VS sync → verify with consumer. | me |
| ESN-23 | M8 (conditional) — bulk corpus repair in slices | Blocked on ESN-22 + ESN-20 | Only if M5 was clean and there's business demand. | me |

### Phase 5 — Close-out

| ID | Task | Status | Next action | Owner |
|---|---|---|---|---|
| ESN-24 | Sunset UI-14 row-duplication patch | Blocked on ESN-22 | Run [`pw_sdg_fsr_revert_multi_esn.yml`](../../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_revert_multi_esn.yml) once new extractor recovers same docs in prod. | me |
| ESN-25 | Update parent tracker — close UI-15, UI-05, UI-06, UI-07, UI-13 | Blocked on ESN-22 | Edit [../tracker.md](../tracker.md). Update [../plan.md](../plan.md) ESN section. | me |
| ESN-26 | Move ADR to `internal/adr/`, update pipeline design doc | Blocked on ESN-25 | Final ADR home: [../../internal/adr/](../../internal/adr/). Touch [../../implementation/design/fsr-pipeline-design.md](../../implementation/design/fsr-pipeline-design.md) §1A/§3. | me |
| ESN-27 | SRE runbook update for new extractor failure modes | Blocked on ESN-22 | Add to runbook started under UI-17/UI-18. | me |

---

## Done

| ID | Task | Closed | Resolution |
|---|---|---|---|
| ESN-AdHoc | Ad-hoc operator-driven single-doc repair tooling (#667154) | 2026-05-07 | Side-task driven from prod ESN repair work. Whitelist patch + same-notebook revert across metadata + chunks for ESN + equipment trio. Built + dev-validated on `feat/667154-fsr-doc-repair-adhoc`. Tracked in parent as UI-19. See [design/adhoc-doc-repair-job.md](design/adhoc-doc-repair-job.md), [runbook-doc-repair.md](runbook-doc-repair.md). |
| — | (none yet) | — | — |

---

## Intake

Drop new ESN-related asks here as one-liners; promote to `ESN-NN` when picked up.

- ~~**Train with multiple ESNs** (2026-05-27)~~ → promoted to **ESN-28** (Path 2 = materialize `train_sys_id_fk` in metadata + `train_ids` array on chunks; pending stakeholder discussion before adding to design doc).
