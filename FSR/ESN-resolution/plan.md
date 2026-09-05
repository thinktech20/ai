# ESN Resolution — Feature Plan (to go-live)

> **Started:** 2026-05-06
> **ADO:** #665755
> **Branch:** `fix/665755-esn-resolution` (off `dev`)
> **Driver:** UI-15 in [../tracker.md](../tracker.md). Re-open ESN extraction from first principles after the UI-14 row-duplication patch.
> **New input (2026-05-06, Pranesh):** see [esn-todos](esn-todos). Reframes the problem as **many-to-many ESN↔doc** and proposes a **deterministic `document_id` (hash of volume + docid)** + **DS reference code** under [DS-ref-code/](DS-ref-code/) as the starting point for extractor design.
> **Scope of this folder.** Local-only working notes. Code lands in `pw_sdg_ai_ser_repo/`. Nothing here is committed.

---

## Problem statement (one paragraph)

Today FSR stores **one `esn` per document** as a single string column denormalized into 3 places (metadata column + chunk column + chunk JSON). Reality is many-to-many: a single FSR PDF often references multiple equipment serials (multi-ESN-per-doc), and the same physical asset can appear across multiple FSRs (multi-doc-per-ESN). On top of that, the current LLM-only extractor produces wrong / null / OCR-corrupted / template-token / pure-numeric primary ESNs in a measurable share of the corpus (see [../user-reported-issues/findings/esn-quality.md](../user-reported-issues/findings/esn-quality.md)). UI-14 ships a row-duplication side-step using `fsr_pdf_ref` to recover Abhinaya's 12 zero-doc ESNs but does not address extraction quality or model the many-to-many relationship as a first-class concept. UI-15 is the proper fix.

## Two sub-problems (Pranesh framing)

1. **ESN ↔ Doc cardinality.** Model multi-ESN-per-doc and same-ESN-across-docs as a first-class data shape (not a hack via row duplication or array hidden in JSON).
2. **ESN extraction quality.** Stop returning null / redacted / wrong primary ESNs from the extractor. Cover Patterns A (OCR `9→7`), B, C (pure-numeric leakage), and PII template tokens (see findings doc).

## Cross-doc invariants (don't forget)

ESN is denormalized in **3 places** today; any new design must explicitly say what each place becomes:
1. `vaip.ai_sot_field_service_report.biz_metadata_field_service_report.esn` (source of truth)
2. `vaip.ai_std_con_field_service_report.biz_chunks_field_service_report.esn` (top-level chunk column → VS filter)
3. `biz_chunks_field_service_report.metadata` JSON `"esn"` key (VS payload)

ESN resolver lives in **one place** in code: [`nb_sdg_fsr_metadata.py` L677-679](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py).

PKs today: `document_id` (metadata), `chunk_id = md5(document_id + "_" + chunk_index)` (chunks). UI-14 introduced an alt chunk_id shape `md5(doc_id + '_' + chunk_idx + '__' + esn)`.

---

## How this folder is organized

| Path | Purpose |
|---|---|
| `plan.md` (this file) | Cross-session plan — phases, decisions, design open questions, definition of done. |
| `tracker.md` | Live work tracker — `ESN-NN` items with status + next action. |
| `esn-todos` | Raw input from Pranesh discussion (do not edit; original ask). |
| `DS-ref-code/` | DS team reference: `fsr_pipeline_dbr_final/` + `ds-team-docs/` (FSR Scraping POC PDFs). Read-only. |
| `analysis/` | Outputs of investigations — DS-code test results, prod ESN buckets, smoke notebooks. |
| `design/` | Three numbered design docs (split by concern), plus Pranesh's raw flow input + the UI-19 ad-hoc repair design. Promoted to ADR under [../../internal/adr/](../../internal/adr/) after sign-off. |
| `validations/` | (To be created.) Validation harness wire-up + per-phase test outputs (CSV, notebook results). May reuse existing [../user-reported-issues/validations/nb_esn_pr_validation.ipynb](../user-reported-issues/validations/nb_esn_pr_validation.ipynb). |

**`design/` contents:**

| File | Scope |
|---|---|
| [design/1-esn-extractor-method.md](design/1-esn-extractor-method.md) | Sub-problem 2 — ESN extraction quality. One LLM call with modified prompt (option C). |
| [design/2-multiple-esn-design.md](design/2-multiple-esn-design.md) | Sub-problem 1 — cardinality / data model. Row fan-out, identity columns, child-row propagation. |
| [design/3-incremental-ingestion-and-watermark.md](design/3-incremental-ingestion-and-watermark.md) | Pipeline mechanics. Anti-join with `source_doc_id`, P1/P2/P3 work-queue gates, VS sync, DQ dedup, re-extract runbook. |
| [design/Pranesh-multi-ESN-approach.md](design/Pranesh-multi-ESN-approach.md) | Raw flow-chart input from Pranesh (2026-05-06). |
| [design/adhoc-doc-repair-job.md](design/adhoc-doc-repair-job.md) | UI-19 single-doc operator repair (separate stream, same folder). |

---

## Phases (sequential, each with go/no-go gate)

### Phase 0 — Ground truth + DS-code analysis

**Goal:** Understand what DS already built and measure the actual cardinality before we design.

| # | Task | Output | Gate to next phase |
|---|---|---|---|
| 0.1 | Read DS reference code under [DS-ref-code/fsr_pipeline_dbr_final/src/](DS-ref-code/fsr_pipeline_dbr_final/) and the two FSR Scraping POC PDFs in [DS-ref-code/ds-team-docs/](DS-ref-code/ds-team-docs/). Map each component to one of the two sub-problems (cardinality vs extraction quality). | `analysis/ds-code-component-map.md` | Component map peer-reviewable in one read |
| 0.2 | Pull Pranesh's two reference docs (`d3b1da8a-03b4-4ea6-aa7b-0482edb532ce` and `3ef8d150-1225-4c62-ac5e-ae9166c73954`) and inspect what ESNs they actually contain (page 1 vs first few pages vs full text). Cross-check against what current pipeline stored as `esn`. | `analysis/pranesh-ref-docs.md` | Both docs analyzed; "ESNs not on page 1" hypothesis confirmed or rejected |
| 0.3 | Corpus measurement: how many docs have ESNs only after page 1? How many distinct ESNs per doc (P50, P90, max)? How many ESNs span >1 doc? | `analysis/cardinality-measurement.md` (notebook + CSV) | Numbers in hand for the design tradeoffs |
| 0.4 | Re-read [../user-reported-issues/findings/esn-quality.md](../user-reported-issues/findings/esn-quality.md) + UI-14 design notes; confirm Pattern A/B/C counts still match latest corpus. | Short note appended to cardinality-measurement | Failure-mode counts current as of Phase-0 close |

### Phase 0b — Test DS code as-is

> **Pranesh (2026-05-06):** plan the design **after** we've run the DS scraping + `esn_identifier` from `fsr_pipeline_dbr_final` against our docs. Component map (Phase 0.1) tells us where the code is; this phase tells us how well it works on our corpus.

| # | Task | Output | Gate |
|---|---|---|---|
| 0b.1 | Stand up `DS-ref-code/fsr_pipeline_dbr_final` runnable (locally or on dbr). Get scraping + `esn_identifier` executing on a small input. | Working setup, notes on env/config (LiteLLM keys, certs, etc.) | Code runs end-to-end on one sample doc |
| 0b.2 | Run DS code on Pranesh's 2 docs + Abhinaya's 12 zero-doc + 5 UI-03 multi-ESN docs. Capture per-doc: ESNs scraped, ESNs qualified by `esn_identifier`, primary vs all. Compare against current prod `esn` + ground-truth from PDF. | `analysis/ds-code-test-results.md` + CSV | Per-doc table covers all 19 docs |
| 0b.3 | Decide which DS components to lift: scraping only, `esn_identifier` only, both, or hybrid. | Short conclusion in same doc | Recommendation written; gate to Phase 1 |

### Phase 1 — Options comparison + design decision

**Goal:** Pick one design and write it up.

**Update (2026-05-06):** Extractor-side decision draft picked: **one LLM call with modified prompt** (extend our existing P1 metadata prompt to also return `esn_mentions: {esn: count}` from a body-text window; resolver picks top-1 by count with `MIN_ESN_COUNT=1`). Draft in [design/1-esn-extractor-method.md](design/1-esn-extractor-method.md). Pending sign-off after spot-check (ESN-04d) and cohort validation (ESN-04e). Cardinality-side decision drafted in [design/2-multiple-esn-design.md](design/2-multiple-esn-design.md) (row fan-out per Pranesh); pipeline cursor / anti-join / watermark in [design/3-incremental-ingestion-and-watermark.md](design/3-incremental-ingestion-and-watermark.md).

**Update (2026-05-12):** Added [design/proposed-multi-ESN-design](design/proposed-multi-ESN-design) with a production-oriented alternative: **one metadata row per PDF + `esns ARRAY<STRING>`**, stable `document_id`, single chunk materialization per PDF, and status-driven retry/rollback/re-extract. Document also records that the current duplication-oriented patch is a **one-time tactical workaround** and **not a sustainable long-term production design**.

**DECISION (2026-05-26) — Option B picked.** Cardinality model = **one metadata row per PDF + `esn_details` struct array** (per [design/proposed-multi-ESN-design.md](design/proposed-multi-ESN-design.md)). Option A (row fan-out per Pranesh, [design/2-multiple-esn-design.md](design/2-multiple-esn-design.md)) is **not chosen** — do not re-litigate without new evidence. Reasons: (a) stable `document_id` (no downstream churn), (b) per-ESN equipment attributes (`equipment_type`/`equipment_sys_id`/`equipment_class_code`) stay bound to their ESN via struct, (c) chunks materialized once per PDF (storage stays flat), (d) row-local retry/rollback/re-extract, (e) UI-14 row-duplication patch can be cleanly sunset. Trade-off accepted: consumer VS pre-filter shifts from native `esn = 'X'` to `array_contains` or a denormalized helper column — see Open items below.

Extractor decision (one LLM call with modified prompt — option C in [design/1-esn-extractor-method.md](design/1-esn-extractor-method.md)) is **independent** and stays as-is.

**Update (2026-05-26) — design doc finalized + sent for team review.** [design/proposed-multi-ESN-design.md](design/proposed-multi-ESN-design.md) is the authoritative design. Final open items consolidated to **O1–O7** at the bottom of that doc (must be confirmed before implementation). Announced on Slack to DS team + Scope agent stakeholders for input on O1–O7.

**Pending (2026-05-27) — train with multiple ESNs.** A single train asset can carry multiple ESNs. Confirm whether the proposed multi-ESN design handles this via `esn_details` per PDF, or whether an asset-level abstraction (`train_id` / `asset_id` grouping multiple ESNs) is needed. Likely impacts O1 (extraction), O2 (schema), O6 (chunk tagging). Tracked under Intake in [tracker.md](tracker.md).

**Update (2026-05-07) — prod ESN quality measurement (ESN-04 done):** Against `vaip.ai_sot_field_service_report.biz_metadata_field_service_report` (18,029 completed docs):

| bucket | docs | % |
|---|---|---|
| null/empty | 5 | 0.03% |
| redacted (`^X+$`) | **0** | 0% |
| `NNNANNN` alphanum (e.g. `270T434`) | 2,904 | 16.11% |
| numeric 6–7 digits (looks-real, e.g. `297843`) | 12,349 | 68.50% |
| numeric <6 digits (suspect Pattern C) | **166** | 0.92% |
| numeric >7 digits | 2 | 0.01% |
| other alphanum | 2,334 | 12.95% |
| other | 269 | 1.49% |

50-doc sample from the suspect-numeric bucket confirms Pattern C: sequential / multi-doc-duplicate IDs (e.g. `10872`-`10874`, `26888`-`26892`, `17872` across 3 docs), with several rows where both `llm` and `fsr_pdf_ref` agree on the same wrong value — meaning the wrong ID is literally on page 1 of the PDF, not an LLM hallucination.

**Implications:**
- Redaction is dev-only-for-now (zero in prod) — not the rollout driver.
- Pattern C scope in prod is ~166 docs (0.92%), not thousands. Plus possibly some inside the 12,349 6–7 digit bucket — needs spot-check (ESN-04h).
- Approach C still applies and is the right mechanism (body-text count would catch Pattern C the same way it caught redacted ones).
- The argument for approach C shifts from "rescue 12K bad docs" to "tighten a working extractor + unlock multi-ESN signal for cardinality work." Still valid, smaller scope.

| # | Task | Output | Gate |
|---|---|---|---|
| 1.1 | Build option matrix across (a) UI-07 LLM-count extractor as currently on `fix/multiple-esns`, (b) DS `esn_identifier` lifted as-is (informed by Phase 0b results), (c) hybrid using `fsr_pdf_ref` as ground-truth where available, (d) per-equipment-family validators, (e) **deterministic `document_id` + many-to-many rows** (Pranesh proposal). Compare on: cardinality fit, extraction accuracy, PK/FK impact, blast radius, runtime cost, what happens to currently-correct docs. | `analysis/option-matrix.md` | Reviewer can pick from the matrix without re-doing the analysis |
| 1.2 | Decide. Document tradeoffs accepted. | Decision recorded in `analysis/option-matrix.md` + new ADR stub | Decision signed off (you + Pranesh at minimum) |
| 1.3 | Promote the three split design docs ([design/1-esn-extractor-method.md](design/1-esn-extractor-method.md), [design/2-multiple-esn-design.md](design/2-multiple-esn-design.md), [design/3-incremental-ingestion-and-watermark.md](design/3-incremental-ingestion-and-watermark.md)) to a single ADR covering data model, `document_id` strategy, extractor, validation, migration, rollback. | ADR file under [../../internal/adr/](../../internal/adr/) | Design reviewed |

### Phase 2 — Implementation on a fresh branch

**Goal:** Land code that passes the validation harness as the merge gate.

| # | Task | Where |
|---|---|---|
| 2.1 | Cut a fresh branch off `dev` — `fix/665755-esn-resolution` (ADO #665755) | git |
| 2.2 | DDL changes (additive on dev with `_esn_v2` suffix tables first). | `pw_sdg_ai_ser_repo/silver/src/ddl/nb_sdg_fsr_ddl.py` |
| 2.3 | Extractor implementation (port DS components per Phase-0 map). | `pw_sdg_ai_ser_repo/silver/src/etl/` |
| 2.4 | P1 metadata pipeline integration (open PDF once, run extractor, write new shape). | `nb_sdg_fsr_metadata.py` |
| 2.5 | P2 chunk pipeline integration (new ESN propagation — column + JSON, plus row-duplication if that's the design). | `nb_sdg_fsr_chunks.py` |
| 2.6 | VS index DDL + sync (filterable columns updated). | dev VS endpoint |
| 2.7 | Wire validation harness to new extractor + new cohorts (multi-ESN, many-doc-per-ESN). | [../user-reported-issues/validations/nb_esn_pr_validation.ipynb](../user-reported-issues/validations/nb_esn_pr_validation.ipynb) |
| 2.8 | Generic data-fix job (UI-13 lineage) — repurpose for new extractor as the corpus-wide repair vehicle. | `pw_sdg_ai_ser_repo/silver/src/etl/{nb_sdg_fsr_data_fix.py, data_fixes/nb_esn_v2_fix.py}` |

**Hard merge gate (carried forward from UI-07 plan):** 30/30 UAT + 14/14 known-bad + zero regressions on 100-doc sample + multi-ESN cohort recovers + many-doc-per-ESN cohort behaves per design.

### Phase 3 — Dev validation (sandbox + real dev tables)

| Step | Where | What |
|---|---|---|
| M1 | dev `_esn_v2` tables + index | Smoke test full P1+P2 on small cohort (Pranesh's 2 + Abhinaya's 12 + 5 UI-03 multi-ESN). |
| M2 | dev `_esn_v2` tables | Run data-fix job (targeted mode) against same cohort. Audit-table dry-run → APPLY → VS sync → re-query. |
| M3 | dev real (`vaip_dev.*`) | DDL applied idempotently. VS index registers any new filterable columns. |
| M4 | dev real | Targeted data-fix on the cohort against real dev tables. Confirm Abhinaya heat-map test recovers. |
| M5 | dev real (optional) | Bulk-mode soak test (500-doc slice). Measure runtime, audit volume, VS sync lag. |

### Phase 4 — Prod rollout

| Step | Where | What |
|---|---|---|
| M6 | prod | DDL added (one-time, idempotent). VS index filterable columns registered via D&A ticket. |
| M7 | prod | Targeted data-fix on Abhinaya's 12 (dry-run → APPLY → VS sync → verify). |
| M8 | prod (conditional) | Bulk corpus repair in slices, only if M5 looked good and there's business demand. |

### Phase 5 — Close-out

- [ ] UI-14 sunset plan: confirm row-duplication patch can be reverted (use [../../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_revert_multi_esn.yml](../../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_revert_multi_esn.yml)) once new extractor is live in prod and recovers same docs.
- [ ] Mark UI-15 done in [../tracker.md](../tracker.md). Close UI-05, UI-06, UI-07, UI-13 as folded-in.
- [ ] Move ADR from `design/` to [../../internal/adr/](../../internal/adr/).
- [ ] Update [../../implementation/design/fsr-pipeline-design.md](../../implementation/design/fsr-pipeline-design.md) §1A + §3 + relevant places.

---

## Open items — Option B (post-decision, must answer before ADR sign-off)

Options A/B comparison is **closed** (2026-05-26 — B picked). Items below are the remaining design decisions inside B.

> **Authoritative source for open items: [design/proposed-multi-ESN-design.md §Open items](design/proposed-multi-ESN-design.md#open-items) (O1–O7).** The §1–§14 enumeration below is the original working list from this plan; most items are now decided or folded into O1–O7. Cross-ref:
>
> | This plan | Design doc | Status |
> |---|---|---|
> | §1 VS pre-filter | O5 (FSR index + consumer app change) | Decided B1; FSR-specific wire-up still open under O5 |
> | §2 `esn_details` fields | O2 (field contract) | Field list decided; one schema pass still owed under O2 |
> | §3 chunk-side ESN representation | O6 (chunk-level ESN tagging) | C2 decided; doc-wide vs per-chunk precision still open under O6 |
> | §4 `primary_esn` deprecation | (folded into design) | Decided: keep indefinitely |
> | §5 `document_id` strategy | O3 (cross-volume identity) | Decided: keep uuid; cross-volume identity still open under O3 |
> | §6–§9 extraction sub-items | O1 (ESN extraction method — DS team) | Decided locally; DS confirmation pending under O1 |
> | §10 re-extract trigger | (decided in design — operator-driven) | Closed |
> | §11 backwards-compat window | O4 (v2 tables vs alter) | Folded into O4 |
> | §12 18K corpus migration | O4 (v2 tables vs alter) | Folded into O4; v2 tables recommended |
> | §13 UI-14 sunset path | (decided — retired with v1 sunset at v2 cutover) | Closed |
> | §14 DQ dedup key under B | (decided in design — unchanged) | Closed |

Keeping §1–§14 below for the working notes that fed those decisions — don't re-litigate from this list, work from O1–O7.

**Schema + storage and Extraction sub-items decided 2026-05-26 (this session).** Operational items (§10–14) remain open.

### Schema + storage

1. **VS pre-filter strategy.** **Decided: B1 — derived `esns: ARRAY<STRING>` column on metadata + chunks, synced from `esn_details.esn`.** Internal dev POC evidence is recorded in the tracker. B2 (only `primary_esn` filterable) would miss PDFs where the queried ESN is present but stored as a secondary ESN, so it was rejected. Phase 3 now needs to do the FSR-specific implementation work: (a) expose `esns` on the rebuilt FSR VS index, (b) update the consumer query path to use the right filter shape for that field, and (c) confirm the runtime cost is acceptable on a small dev cohort.
2. **`esn_details` struct field list.** **Decided for now: `esn, equipment_sys_id, equipment_type, equipment_class_code, esn_source, rank, esn_count`.** This covers the current design needs: ESN identity, ESN-bound equipment attributes, and extraction provenance / ordering. Added `esn_count` (body-text mention count — cheap, useful for DQ + audit + re-extract tie-breaking). `extracted_at` is not a current column; it was a candidate per-ESN field considered for the struct and intentionally left out because extraction timing is already covered at the metadata-row level rather than per ESN. Need one explicit schema pass before implementation to confirm whether any extra per-ESN field is truly required.
3. **Chunk-side ESN representation.** **Decided: C2.** Chunk top-level columns: `esns: ARRAY<STRING>` (for VS membership filtering on the array field) **plus** keep existing `esn` STRING (= `primary_esn`, for legacy consumers). Chunk `metadata` JSON payload: full `esn_details` struct array. Equipment attrs don't drive VS filtering at chunk granularity — chunks inherit them from the doc.
4. **`primary_esn` deprecation plan.** **Decided: keep indefinitely as a denormalized convenience column** (= `esn_details[rank=0].esn`). Cost = one extra string column. Consumer docs point at `esns` for filtering, `primary_esn` for display. No sunset date — revisit only if it becomes a maintenance burden. Risk of consumers staying on `primary_esn` filter and missing secondary-ESN docs is solvable via runbook + announcement, not a deprecation gun.
5. **`document_id` strategy.** **Decided: keep uuid (today).** Stability is the whole point of Option B; switching to `hash(volume+docid)` now would self-defeat (downstream cache churn, VS payload ID rekey). Re-ingest idempotency isn't an active pain point. Revisit only if it becomes one.

### Extraction

6. **`esn_count` thresholding policy (no body-text mention reaches `MIN_ESN_COUNT=1`).** **Decided: fall back to page-1 ESN** as 1-element `esn_details` (`rank=0, esn_source='page1', esn_count=0`) + write DQ row `check_name='esn_low_confidence'` (new category, additive). Doc stays searchable; DQ surfaces it. If even page-1 fails: leave `esn_details=NULL`, set `metadata_status='failed'`, existing UI-18 retry path kicks in.
7. **Where the extractor runs.** **Decided: P1 metadata.** Single LLM call extends the existing P1 prompt to also return `esn_mentions: {esn: count}` (per [design/1-esn-extractor-method.md](design/1-esn-extractor-method.md)). No double PDF read — same call produces metadata fields + ESN counts. P2 (chunking) alternative was rejected: would block chunking on extraction, ugly status model (metadata complete without ESN), re-extract requires re-chunking.
8. **`fsr_pdf_ref` role.** **Decided: hint, never authoritative.** Concrete handling: (a) ESNs found in `fsr_pdf_ref` but **not** in body-text counts → add as additional `esn_details` entries with `esn_source='fsr_pdf_ref'` and a lower `rank` than body-text-confirmed entries; (b) ESNs found in **both** → merge into existing entry, set `esn_source='llm+ref'`, keep body-text `esn_count`; (c) never override a high-confidence body-text ESN purely because `fsr_pdf_ref` disagrees. UI-14 (which treated ref as truth) is a tactical patch and gets sunset — see operational item §13.
9. **First-pages scan window.** **Decided: use existing P1 body-text window** (whatever the current metadata prompt sends — don't expand). Phase 0.3 measurement tells us whether widening is needed: if >5% of docs have ESNs only in pages outside the window, revisit. LLM token cost on long docs is real; don't pay it speculatively.

### Operational (still open — address later)

10. **Re-extract trigger.** Confirm operator-only (Section "Lifecycle / Re-extract" in [proposed-multi-ESN-design.md](design/proposed-multi-ESN-design.md)). No auto-replay on mod_time bump.
11. **Backwards compatibility window.** During M3–M7, both old single `esn` column and new `esn_details` coexist. Consumer query path during transition: keep old `esn` populated as `primary_esn` so existing queries don't break.
12. **Migration of existing 18K corpus.** Backfill `esn_details` from existing single `esn` + `equipment_*` columns (one-element struct, `rank=0`, `source='migrated'`)? Or leave `esn_details=NULL` until re-extract touches it? **Default lean: backfill** (one-shot, makes consumer migration uniform).
13. **UI-14 sunset path under B.** UI-14 created duplicated chunk rows. Under B, sunset = delete UI-14-created duplicates (audit table from UI-14 makes this rollback-safe) + ensure those source PDFs now have proper `esn_details`. Document the explicit revert sequence.
14. **DQ dedup key under B.** Stays `(document_id, check_name)` from UI-17 since `document_id` is stable. No change needed (B inherits today's behaviour cleanly — this was an A-specific problem).

### Carried (out-of-scope of A-vs-B decision)

- DS-code component map (ESN-01), Pranesh ref doc inspection (ESN-02), corpus cardinality measurement (ESN-03) — still feed sizing of `esn_details` array (max ESNs per doc).

## Definition of done (go-live)

- [ ] New extractor live in prod P1 (new docs benefit immediately).
- [ ] Existing 18K corpus repaired via UI-13-lineage data-fix job (targeted on consumer-flagged docs at minimum; bulk only if greenlit).
- [ ] VS index reflects new shape; consumer query path returns correct hits for all 30 UAT ESNs + multi-ESN cohort.
- [ ] UI-14 row-duplication patch reverted in prod.
- [ ] SRE runbook updated for the new extractor's failure modes.
- [ ] Findings doc + design doc final, ADR merged under `internal/adr/`.

---

## Conventions

- No emojis in docs unless asked.
- No git commits without explicit ask.
- No temporary patches in `pw_sdg_ai_ser_repo/` — fix root cause.
- Dev tables use `_esn_v2` suffix during development; promotion to real tables only after sandbox passes.
- Validation harness is the merge gate; nothing lands without it green.

## Related

- [../tracker.md](../tracker.md) — UI-15 row, UI-14 row, UI-07/UI-13 (folded), UI-05/UI-06 (superseded).
- [../user-reported-issues/findings/esn-quality.md](../user-reported-issues/findings/esn-quality.md) — failure-mode breakdown.
- [../user-reported-issues/findings/UI-03-multi-serial-per-doc.md](../user-reported-issues/findings/UI-03-multi-serial-per-doc.md) — multi-serial corpus measurement.
- [../../internal/adr/multi-esn-design.md](../../internal/adr/multi-esn-design.md) — prior single-array design (option a in matrix).
- [../user-reported-issues/validations/nb_esn_pr_validation.ipynb](../user-reported-issues/validations/nb_esn_pr_validation.ipynb) — validation harness.

---

## Appendix A — Phase 0b runbook (test DS extractors on dev)

> Concrete steps for ESN-04a / ESN-04b in [tracker.md](tracker.md). Goal: run **both** DS extractors (regex cover-page scraper from `pdf_processor.py` + LLM `esn_identifier.py`) on a small cohort and produce a per-doc comparison CSV. **Read-only — no Delta / VS writes.**

### Cohort (~14 docs, dev catalog `vaip_dev`)

- Pranesh refs: `d3b1da8a-03b4-4ea6-aa7b-0482edb532ce`, `3ef8d150-1225-4c62-ac5e-ae9166c73954`
- 14 known-bad UUIDs from [../prod-issues/nb_uat30_esn_recheck.ipynb](../prod-issues/nb_uat30_esn_recheck.ipynb) `KNOWN_UUIDS` (Pattern A/B/C cohort)
- (Optional) 2-3 multi-ESN samples from [../user-reported-issues/findings/UI-03-multi-serial-per-doc.md](../user-reported-issues/findings/UI-03-multi-serial-per-doc.md)

### Step 1 — Get DS code onto dev

Pick one:
- **(A) Sync dbx as a Repo on dev** → DS code lives at `/Workspace/Repos/<you>/dbx/FSR/ESN-resolution/DS-ref-code/fsr_pipeline_dbr_final/src/`.
- **(B) Upload `DS-ref-code/fsr_pipeline_dbr_final/` as a workspace folder** → e.g. `/Workspace/Users/<you>/ds_esn_test/`.

Note the path; call it `DS_SRC_PATH`. We add it to `sys.path` in the test notebook.

### Step 2 — Confirm LiteLLM credentials reachable on dev

DS `esn_identifier` reads `LITELLM_BASE_URL` + `LITELLM_API_KEY` from the `fsr-pipeline` secret scope (default), with env-var fallback (DS [config.py](DS-ref-code/fsr_pipeline_dbr_final/src/config.py) lines 50-80). Quickest path: pull the same key our `nb_sdg_fsr_metadata.py` job uses from its secret scope (or hardcode for the test).

### Step 3 — Resolve cohort to volume paths

SQL against dev metadata table:

```sql
SELECT document_id, esn AS current_stored_esn, esn_source, volume_path, metadata_status
FROM vaip_dev.ai_sot_field_service_report.biz_metadata_field_service_report
WHERE document_id IN (
  'd3b1da8a-03b4-4ea6-aa7b-0482edb532ce',
  '3ef8d150-1225-4c62-ac5e-ae9166c73954',
  '913433ad-6d19-472f-917c-5048f689a5ed',
  'c020379c-93a4-49f6-b6a9-1388edd59d3a',
  '03d3bef2-db2b-4311-b147-641025e3636b',
  '36de1c13-acee-4633-8b76-8a262f738a20',
  '34bc62b0-573c-4f43-bc62-b0573ccf43e9',
  '348ddaa2-8c32-4646-9f17-c57f33256d82',
  '4b70aab1-e210-4d5b-9cbf-bfe690436861',
  'd5334dce-9d7f-4fa1-b34d-ce9d7f7fa130',
  '090dbba1800f4f5b','090dbba18003a23c','090dbba180100488','090dbba1800b5e28'
)
ORDER BY document_id;
```

Capture any UUID that is missing in dev — that's signal too.

### Step 4 — Test notebook (4 cells)

Drop in a personal workspace folder (don't touch `pw_sdg_ai_ser_repo/`).

**Cell 1 — config + cohort:**

```python
DS_SRC_PATH = "/Workspace/Repos/<you>/dbx/FSR/ESN-resolution/DS-ref-code/fsr_pipeline_dbr_final/src"
LITELLM_BASE_URL_OVERRIDE = "https://dev-gateway.apps.gevernova.net"
LITELLM_API_KEY_OVERRIDE  = dbutils.secrets.get("<our-existing-scope>", "<litellm-key>")

import os, sys
os.environ["LITELLM_BASE_URL"] = LITELLM_BASE_URL_OVERRIDE
os.environ["LITELLM_API_KEY"]  = LITELLM_API_KEY_OVERRIDE
sys.path.insert(0, DS_SRC_PATH)

DOC_IDS = [
    "d3b1da8a-03b4-4ea6-aa7b-0482edb532ce",
    "3ef8d150-1225-4c62-ac5e-ae9166c73954",
    "913433ad-6d19-472f-917c-5048f689a5ed",
    "c020379c-93a4-49f6-b6a9-1388edd59d3a",
    "03d3bef2-db2b-4311-b147-641025e3636b",
    "36de1c13-acee-4633-8b76-8a262f738a20",
    "34bc62b0-573c-4f43-bc62-b0573ccf43e9",
    "348ddaa2-8c32-4646-9f17-c57f33256d82",
    "4b70aab1-e210-4d5b-9cbf-bfe690436861",
    "d5334dce-9d7f-4fa1-b34d-ce9d7f7fa130",
    "090dbba1800f4f5b","090dbba18003a23c","090dbba180100488","090dbba1800b5e28",
]
```

**Cell 2 — pull volume paths from dev metadata:**

```python
from pyspark.sql import functions as F

meta = (
    spark.table("vaip_dev.ai_sot_field_service_report.biz_metadata_field_service_report")
         .filter(F.col("document_id").isin(DOC_IDS))
         .select("document_id", "volume_path", "esn", "esn_source", "metadata_status")
         .toPandas()
         .set_index("document_id")
)
print(f"Resolved {len(meta)}/{len(DOC_IDS)} docs")
print("Missing in dev:", [d for d in DOC_IDS if d not in meta.index])
display(meta)
```

**Cell 3 — run both DS extractors per doc:**

```python
import json, traceback, time
from pdf_processor import _extract_esn_from_pdf
from esn_identifier import (
    load_document_text_for_esn,
    analyze_prepared_document_text_for_esn_counts,
    prepare_document_text_for_esn,
    _qualify_esn_counts,
    MIN_ESN_COUNT, MIN_ESN_FRACTION,
)

results = []
for doc_id, row in meta.iterrows():
    vp = row["volume_path"]
    rec = {
        "document_id": doc_id, "volume_path": vp,
        "current_stored_esn": row["esn"], "current_stored_esn_source": row["esn_source"],
        "regex_esn": None, "llm_raw_counts": None,
        "llm_qualified_esns": None, "llm_primary_esn": None,
        "doc_text_chars": None, "error": None,
    }
    try:
        rec["regex_esn"] = _extract_esn_from_pdf(vp)
        full_text = load_document_text_for_esn(vp)
        rec["doc_text_chars"] = len(full_text)
        prepared = prepare_document_text_for_esn(full_text)
        counts = analyze_prepared_document_text_for_esn_counts(prepared)
        qualified = _qualify_esn_counts(counts, MIN_ESN_COUNT, MIN_ESN_FRACTION)
        rec["llm_raw_counts"]     = json.dumps(counts)
        rec["llm_qualified_esns"] = json.dumps(qualified)
        rec["llm_primary_esn"]    = qualified[0] if qualified else None
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    print(f"{doc_id}: regex={rec['regex_esn']} primary={rec['llm_primary_esn']} qualified={rec['llm_qualified_esns']} stored={rec['current_stored_esn']}")
    results.append(rec)
    time.sleep(0.5)
```

**Cell 4 — comparison + CSV:**

```python
import pandas as pd
df = pd.DataFrame(results)
df["regex_eq_stored"] = (df["regex_esn"] == df["current_stored_esn"])
df["llm_eq_stored"]   = (df["llm_primary_esn"] == df["current_stored_esn"])
df["regex_eq_llm"]    = (df["regex_esn"] == df["llm_primary_esn"])
df["llm_n_qualified"] = df["llm_qualified_esns"].apply(lambda s: 0 if s in (None, "null") else len(json.loads(s)))
display(df)

OUTPUT_DIR = "/Volumes/vaip_dev/.../esn_extractor_test"  # writable Volume; or skip and just display
df.to_csv(f"{OUTPUT_DIR}/esn_extractor_comparison_{int(time.time())}.csv", index=False)
```

### Step 5 — Share results

Paste CSV (or display screenshot) back here. Columns to look at:

| Column | Tells us |
|---|---|
| `regex_esn` vs `current_stored_esn` | Does DS scraper match what we stored? |
| `llm_qualified_esns` | DS LLM's full set of "real" ESNs after thresholds — multi-ESN evidence |
| `llm_primary_esn` vs `current_stored_esn` | Does DS LLM agree with our primary? |
| `llm_n_qualified == 0` | LLM found nothing confident — null/redacted-doc signal |
| `llm_n_qualified > 1` | Multi-ESN doc |

That feeds ESN-04c (decide which DS components to lift).

### Common gotchas

- **`fitz` (PyMuPDF) and `httpx`** must be on the cluster. `%pip install pymupdf httpx` if missing.
- **Cert** — DS `config.py` looks for `GE_Enterprise_Root_CA_2_1.crt` next to `src/`. If syncing via Repos, the file ships with `DS-ref-code/`. Otherwise upload alongside.
- **Volume read perms** — cluster needs read on `viud/...` (dev volumes).
- **Dev catalog** — confirm `vaip_dev` (not `vaip`).
- **DS `EMBEDDINGS_TABLE` default** — points at `main.gp_services_sdg_poc.field_service_report`. We are **NOT calling** any Delta-write function; only the pure extraction helpers. Safe.

