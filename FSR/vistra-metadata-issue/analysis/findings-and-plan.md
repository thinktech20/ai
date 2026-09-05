# Vistra Generator FSR Tagging — Findings & Plan

**Date:** 2026-06-02
**Trigger:** Escalation reviewed — Jon's gap-finder output, the enriched workbook, and the Vistra solution doc (all in [`../input/`](../input/)).
**Audience:** FSR pipeline owners, D&A, Vistra account team.
**Related design:** [`../../ESN-resolution/design/proposed-multi-ESN-design.md`](../../ESN-resolution/design/proposed-multi-ESN-design.md) — schema + train-sibling rule + open item O8 that Approach 2 in this doc implements.

---

## 1. The issue in one paragraph

FSR metadata is keyed one ESN per PDF. When a Field Service Report covers a train outage, today's pipeline only tags the prime mover (Gas Turbine or Steam Turbine) on the metadata row. The Generator ESN on the same train gets no metadata row and no chunk rows. Any Generator-keyed search returns nothing — even though the FSR demonstrably describes Generator work. Jon's cross-tag gap finder identified **252 Vistra PDFs** with this gap across 51 trains; **47 are confirmed** (≥3 generator-engineering keywords in chunk text) and need tagging this week; **205 are weak matches** deferred for SME triage.

## 2. Why the existing pipeline misses it

The pipeline has three potential ESN sources. Two run during normal ingestion; the third is built but currently dormant. Neither situation would have caught these PDFs.

| Source | Status | Path | Why it misses the Vistra Generator |
|---|---|---|---|
| Page-1 LLM normalization + page-1 regex fallback | Active | [`nb_sdg_fsr_metadata.py`](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) | Page-1 cover names the prime mover (GT/ST), not the generator |
| `fsr_pdf_ref` view join | Active | [`nb_sdg_fsr_metadata.py`](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) (`_pdf_ref_esn_map`) | Ref view only carries the prime-mover ESN for these PDFs |
| Tier-2 full-document LLM frequency analysis | Built but `FSR_ESN_DETECT_ENABLED=false` on daily ingest (only the ESN backfill job [`pw_sdg_fsr_esn_backfill.yml`](../../../pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_esn_backfill.yml) sets it `true`) | [`fsr_esn_identifier.py`](../../../pw_sdg_ai_ser_repo/common/fsr_esn_identifier.py) (invoked from [`nb_sdg_fsr_chunks.py`](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py)) | Even if enabled, it wouldn't catch these PDFs: the LLM only sees a ~3 KB slice of the document (start/middle/end 1 KB each) and the qualifier requires ≥5 mentions and ≥10% share. And when the body never names the generator literally (work described in keywords like "Seal Rings", "MAGIC Inspection"), no body scan can help |

So the gap is structural, not a regression. It would still exist with the daily job running and Tier-2 turned on.

What's **not** consulted by any source: the IBAT train hierarchy (`ibat_equipment_mst.train_sys_id_fk` → sibling ESNs). The pipeline joins IBAT only for single-ESN equipment-field enrichment, never for sibling discovery.

## 3. What exists in the pipeline today

Multi-ESN fan-out infrastructure is already in place — only the **source of additional ESNs** is incomplete.

| Component | File / location | What it does |
|---|---|---|
| `all_esns` JSON column on metadata | [`common/fsr_config.py`](../../../pw_sdg_ai_ser_repo/common/fsr_config.py) | Per-doc list of ESNs |
| `FSR_MULTI_ESN_ENABLED` flag (default `True`) | [`common/fsr_config.py`](../../../pw_sdg_ai_ser_repo/common/fsr_config.py) | Gates fan-out in both P1 and P2 |
| P1 metadata fan-out | [`nb_sdg_fsr_metadata.py`](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) | One row per ESN; secondary rows use `document_id_<ESN>`, `chunk_status=completed` (P2 skips) |
| P2 chunk fan-out | [`nb_sdg_fsr_chunks.py`](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py) | Duplicates each chunk per ESN; `chunk_id = md5(doc_id_ci__esn)`; reuses embedding |
| Tier 2 LLM ESN detector | [`common/fsr_esn_identifier.py`](../../../pw_sdg_ai_ser_repo/common/fsr_esn_identifier.py) | LLM counts ESN mentions on a ~3 KB slice; qualifies by `min_count` + `min_fraction`. **Gated by `FSR_ESN_DETECT_ENABLED` — `false` on daily job, `true` only on the ESN backfill job** |
| Tier 3 backfill (existing docs) | [`nb_sdg_fsr_esn_backfill.py`](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_esn_backfill.py) | Re-runs LLM ESN on completed docs; copies chunks for new ESNs (no re-embed) |
| Auditable repair | [`nb_sdg_fsr_repair_multi_esn.py`](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_repair_multi_esn.py) | Inserts metadata + chunk rows for secondary ESNs from `fsr_pdf_ref`; audit tables for revert |
| Revert | [`nb_sdg_fsr_revert_multi_esn.py`](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_revert_multi_esn.py) | Undoes a repair pass by `RUN_ID` |
| VS sync | [`nb_sdg_fsr_vs_sync.py`](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_vs_sync.py) | Triggers VS index sync after data changes |

## 4. Two approaches

### Approach 1 — Vistra-specific fix (one-shot, reversible)

Clone the existing `nb_sdg_fsr_repair_multi_esn.py` pattern. Swap the input source: instead of joining `metadata × fsr_pdf_ref`, drive off Jon's 47 confirmed `(document_id, missing_generator_esn)` pairs from a staging table.

**Detailed plan:** [`approach-1-implementation-plan.md`](approach-1-implementation-plan.md) — locked design for the four new files under `gold/src/etl/repairs/` and `gold/src/ddl/repairs/` (DDL, loader, repair, revert), staging-table schema, per-row flow, idempotency rules, agreed dev run scope, and rollout sequence.

**Changes**

- New repair package under `gold/src/etl/repairs/` and `gold/src/ddl/repairs/`:
	- `nb_sdg_fsr_repair_vistra_xtrain_ddl.py`
	- `nb_sdg_fsr_load_vistra_gap_staging.py`
	- `nb_sdg_fsr_repair_vistra_xtrain.py`
	- `nb_sdg_fsr_revert_vistra_xtrain.py`
- Input: staging table (`staging_vistra_gap`) seeded from Jon's enriched workbook, with loader validation against metadata + IBAT before any repair write. For this run, upload [`../input/Vistra Generator Missing Reports 5.31.26 - ENRICHED.xlsx`](../input/Vistra%20Generator%20Missing%20Reports%205.31.26%20-%20ENRICHED.xlsx) and point the loader at that file, using sheet `FSR Tagging Gaps`.
- `esn_source = 'cross_tag_gap_v1'` on inserted rows (free-text value already supported).
- Audit tables `fsr_repair_vistra_chunk_inserts` + `fsr_repair_vistra_metadata_updates` (mirror existing pattern, but kept separate for isolated rollback).
- Sequence: dev → SME ack → prod. In dev, load all 47 confirmed rows, repair the 32 rows already present in dev, and leave the 15 missing PDFs unprocessed in staging. One-shot `nb_sdg_fsr_vs_sync` after each.

**Pros:** Small, isolated, auditable, reversible. Same code patterns already running in prod.
**Cons:** Doesn't fix the underlying ingestion. Next time these PDFs re-ingest (or new Vistra FSRs land), the Generator row drops again. The 205 weak rows + future Vistra FSRs need another batch.

### Approach 2 — Pipeline fix (structural)

Add **IBAT train-sibling expansion** as a fourth source feeding `all_esns`. After an ESN is resolved by the existing three tiers, walk `ibat_equipment_mst → train_sys_id_fk → ibat_equipment_mst` to pull sibling ESNs on the same train, filtered by `equipment_type IN ('Generator','Gas Turbine','Steam Turbine')` and `equipment_status NOT IN ('Scrapped','Never Built (Cancelled)','Retired')`.

**Changes**

| File | Change |
|---|---|
| `common/fsr_config.py` | New flags: `FSR_TRAIN_SIBLING_EXPANSION` (default `false`), `FSR_TRAIN_SIBLING_TYPES`, `FSR_TRAIN_SIBLING_REQUIRE_TEXT_EVIDENCE`, `FSR_TRAIN_SIBLING_KEYWORD_THRESHOLD` |
| `common/fsr_train_resolver.py` *(new)* | `resolve_train_siblings(esns, ibat_df)` — single broadcast lookup built from IBAT joined on `train_sys_id_fk` |
| `nb_sdg_fsr_metadata.py` (P1) | In the multi-ESN fan-out block, union `all_esns_list` with train siblings; use existing IBAT lookup for per-sibling equipment fields |
| `nb_sdg_fsr_chunks.py` (P2) | In the `all_esns` computation, union with train siblings before fan-out |
| `nb_sdg_fsr_esn_backfill.py` (Tier 3) | Same union — backfills siblings for already-ingested docs |
| `nb_sdg_fsr_validate` | New check: for any doc with a train-sibling Generator, confirm a chunk row exists for that ESN |
| Optional text-evidence gate | When `…REQUIRE_TEXT_EVIDENCE=true`, keep a sibling only if ≥N keywords match (Jon's curated list) |

**Rollout knobs**

1. Turn on in **dev only** → run Tier-3 backfill → measure row inflation and sample SME validation.
2. Flip on in prod after fleet-level review (not just Vistra).

**Pros:** Root-cause fix. Works for every customer, not just Vistra. Closes the gap permanently for re-ingestion + new FSRs. Reuses existing fan-out infra. One config flag to roll back.
**Cons:** Larger blast radius — inflates chunk table fleet-wide (storage + VS index size). IBAT train relationships may be imperfect (siblings on shared shaft never named in the FSR add noise; mitigated by the keyword gate). Needs SME validation beyond Vistra before turn-on. Doesn't solve the Friday account-team commit on its own.

The accompanying design doc [`../../ESN-resolution/design/proposed-multi-ESN-design.md`](../../ESN-resolution/design/proposed-multi-ESN-design.md) was updated 2026-06-02 with:
- New section **"Equipment-hierarchy expansion (train siblings)"** defining `esn_source='train_sibling'` and the optional keyword gate.
- Open item **O8** covering config flags, rollout sequence, fleet-wide row-inflation estimate, keyword-list ownership, and `rank` interaction with O1.

## 5. Recommendation

**Do both, in sequence:**

1. **This week — Approach 1.** In dev, load all 47 confirmed rows from [`../input/Vistra Generator Missing Reports 5.31.26 - ENRICHED.xlsx`](../input/Vistra%20Generator%20Missing%20Reports%205.31.26%20-%20ENRICHED.xlsx) using sheet `FSR Tagging Gaps`, repair the 32 rows already present, and leave the 15 missing PDFs unprocessed there. Promote the same workbook to prod for the full confirmed run once ready. Reversible. No pipeline code change.
2. **Next sprint — Approach 2.** Structural fix; the 205 weak rows + Jon's looser keyword rule (literal ESN hit OR ≥3 keywords) feed Approach 2's optional text-evidence gate.

## 6. Open questions

1. Owner for the Vistra-side SME spot-check (needed by Wednesday to validate dev results before prod promote).
2. Visibility on the 205 weak rows now (deferred annotation in workbook) vs after next-week SME triage.
3. Fleet-wide row-inflation estimate before turning on Approach 2 in prod — needs a quick query against IBAT + the metadata table.
4. Whether the keyword-evidence gate should be on by default in Approach 2, or trust IBAT train membership alone.

## 7. References

- Jon's gap-finder logic — [`../input/FSR_Cross_Tag_Gap_Logic 1.md`](../input/FSR_Cross_Tag_Gap_Logic%201.md)
- Vistra solution write-up + 47-row action plan — [`../input/Vistra_Generator_FSR_Tagging_Solution_2026-05-31.md`](../input/Vistra_Generator_FSR_Tagging_Solution_2026-05-31.md)
- Enriched workbook (47 confirmed + 205 deferred) — [`../input/Vistra Generator Missing Reports 5.31.26 - ENRICHED.xlsx`](../input/Vistra%20Generator%20Missing%20Reports%205.31.26%20-%20ENRICHED.xlsx)
- Gap-finder script — [`../input/fsr_cross_tag_gaps.py`](../input/fsr_cross_tag_gaps.py)
- Multi-ESN design (updated with train-sibling section + O8) — [`../../ESN-resolution/design/proposed-multi-ESN-design.md`](../../ESN-resolution/design/proposed-multi-ESN-design.md)
- Pipeline code — [`../../../pw_sdg_ai_ser_repo/`](../../../pw_sdg_ai_ser_repo/)
