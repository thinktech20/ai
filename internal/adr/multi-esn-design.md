# Multi-ESN Filtering — Design Doc (for approval)

| Field | Value |
|---|---|
| **Status** | DRAFT — pending approval |
| **Author** | Madhurima |
| **Reviewers** | Pranesh, Tao |
| **Date** | 2026-05-04 |
| **Supersedes** | [ADR-008](ADR-008-multi-esn-filterability.md) (Option B carried forward; population approach updated based on today's evidence + DS reference review) |
| **Driven by** | Abhinaya's prod heat-map test (12 of 30 ESNs returned zero docs); UI-03 multi-serial findings |

---

## 1. Problem in one paragraph

Today the metadata table stores **one** `esn` per document. Vector Search uses that single value as a hard equality pre-filter. About **2,837 docs (~16% of the 18K corpus)** legitimately discuss multiple serial numbers in one PDF — the LLM picks one, the others are unreachable. This is the root cause behind the 12 zero-doc ESNs Abhinaya flagged on 2026-05-04 — the PDFs exist in the prod source volume, the chunks exist in Delta, but the stored `esn` doesn't match any of the serials a user would search for.

**We need a way to filter Vector Search by any serial that genuinely appears in a document, not just one.**

## 2. Goal

Allow consumer queries of the form:
```
WHERE array_contains(esns, '337X305')
```
to return chunks from any FSR doc that mentions `337X305`, even if the doc's primary stored `esn` is something else.

Non-goal: change the primary single `esn` field. Existing single-ESN consumers keep working unchanged.

## 3. Proposed change

### 3.1 Schema (additive, non-breaking)

| Table | New columns |
|---|---|
| `vaip.ai_sot_field_service_report.biz_metadata_field_service_report` | `esns ARRAY<STRING>`, `esns_source STRING` |
| `vaip.ai_std_con_field_service_report.biz_chunks_field_service_report` | `esns ARRAY<STRING>` (denormalized for VS filterability) |
| Vector Search index | `esns` exposed as a filterable field |

- `esn` (existing, single-value) stays. It becomes the **primary / display** ESN — chosen as the highest-mention-count qualified ESN.
- `esns` (new, array) carries **all qualified** ESNs for the doc. `esn` is always a member of `esns`.
- No PK/FK change. `document_id` remains PK on metadata; `chunk_id` remains PK on chunks.

### 3.2 How `esns` is populated — LLM-count approach (borrowed from DS reference)

We borrow [`poc/fsr-pipeline-dbr-candidate/src/esn_identifier.py`](../../poc/fsr-pipeline-dbr-candidate/src/esn_identifier.py) almost verbatim. Three pieces:

1. **Dedicated ESN-only LLM call** over the full document text (with start/middle/end windowing for long docs — 1000 chars × 3 windows). Returns `{esn: mention_count}`.
2. **Format validation** in code: `^[A-Z0-9]{4,12}$`, reject PII templates `^\{.*\}$`.
3. **Count threshold gating**: keep ESNs where `count >= 5 AND count / total_mentions >= 10%`. Filters out in-passing project / IBAT IDs.

Result: a clean array of `{esn, count}`. The dominant ESN by count → primary `esn`. All qualified ESNs → `esns` array. Tie-break alphabetical.

**Are we deviating from the DS approach?** No — this proposal *is* the DS approach. The only addition vs pure DS is keeping a single `esn` column alongside the new `esns` array, derived as the highest-count qualified ESN, so existing consumer queries (`WHERE esn = X`) keep working. DS itself only stores the array. If we'd rather take pure DS (drop the single `esn` column entirely), the pipeline change is slightly simpler but every existing consumer query must be rewritten on day one — see Section 6 alternatives.

**Why not the regex-scan approach in ADR-008?** Today's data shows the dominant problem is the LLM picking the *wrong* serial when multiple are present, not just missing alternates. Regex scan over chunk text would catch alternates but inherits the same equipment-family blind spots that today's pipeline has (only `NNN[A-Z]NNN` GT shape, misses `SY…`, `G00…`, `V0…`). The DS LLM-count approach handles all serial families uniformly and gives us mention counts for free, which we can also use to fix the primary `esn` selection in the same change.

### 3.3 Cost

- One additional LLM call per document (the existing combined metadata call stays as-is for the other fields). Cost roughly doubles for ESN-only at the gateway.
- At incremental rate (~8–10 new docs/day), additional cost is negligible.
- For the one-time fix of existing ~15K affected docs: at P1's current parallelism, ~30–60 min of LLM time.
- No re-embedding. No re-chunking.

### 3.4 Pipeline integration

- **Phase 1 — code change in `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py`:** add the ESN-only LLM call + qualifier; populate `esn` (primary) and `esns` (array) on every new doc going forward. Same change benefits incremental and backfill paths.
- **Phase 2 — chunk-table denormalization in `nb_sdg_fsr_chunks.py`:** copy `esns` array onto every chunk row; rewrite the `metadata` JSON `"esns"` key. Same 3-place propagation pattern we already use for `esn`.
- **Phase 3 — VS index re-publish:** drop + recreate with `esns` exposed as filterable. Embeddings reused — no recompute.
- **Phase 4 — data-fix workflow (UI-13):** re-run the new extractor over the existing 18K docs, MERGE both `esn` and `esns`, sync VS. Single transition window.

## 4. Consumer-side query change

| Use case | Before | After |
|---|---|---|
| Single ESN — primary | `WHERE esn = '337X305'` | Still works (primary is now count-anchored, more accurate) |
| Single ESN — any mention | not possible today | `WHERE array_contains(esns, '337X305')` |
| Multiple ESN OR | `WHERE esn IN ('A','B')` | `WHERE arrays_overlap(esns, array('A','B'))` |

Consumer can adopt incrementally — the existing single-ESN filter keeps working.

## 5. Migration safety

| Risk | Mitigation |
|---|---|
| Existing single-ESN consumer queries break | Doesn't happen. `esn` column stays single-valued and populated. |
| VS index unavailable during rebuild | Drop+recreate window estimated at the same duration as a full sync. Schedule during low-traffic window; coordinate with D&A. |
| Primary `esn` selection regresses some currently-correct ESNs | Validation harness ([nb_esn_pr_validation.ipynb](../../fsr-prod-ops/user-reported-issues/validations/nb_esn_pr_validation.ipynb)) gates the PR — 30 UAT ESNs + 14 known-bad UUIDs + 100-doc regression sample + new multi-ESN cohort (the 11 zero-doc PDFs from today). Hard merge gate. |
| LLM extracts wrong serials | Count threshold (`>=5` mentions AND `>=10%`) rejects in-passing tokens. In-text presence is a structural property of mention-count (can't have `count >= 5` without being in the text), so no separate validator needed. |
| 3-place denormalization drift | Same risk as today's `esn`. Same mitigation: single ad-hoc notebook does metadata MERGE → chunk column MERGE → chunk JSON rewrite → VS sync, in order, in one transaction-or-strictly-sequential. |

## 6. Why this is the robust path (vs alternatives)

| Alternative | Why not |
|---|---|
| **Status quo** (single `esn` only) | Doesn't fix multi-ESN docs. The 12 zero-doc ESNs stay zero. Abhinaya's report stays open. |
| **Regex scan over chunk text only** (ADR-008 original) | Inherits per-equipment-family blind spots. Doesn't fix the wrong-primary-ESN problem (just adds alternates around a bad primary). |
| **Explode rows — one row per (doc × ESN)** | Breaks PK assumptions consumers rely on. 18K → 100K+ rows. Invasive migration. Rejected in ADR-008. |
| **Side table `(document_id, esn, source)`** | VS filter must be on the chunk table, so we'd still need to denormalize into chunks. Same cost as the proposed approach + an extra table. Rejected in ADR-008. |
| **Pure DS — drop single `esn` column entirely** | Cleanest. Matches DS reference 1:1. But requires every existing consumer query to switch to `array_contains` on day one — coordinated breaking change. Proposed approach keeps single `esn` for backward compat at the cost of one derived column. Open to flipping to this if reviewers prefer. |
| **DS LLM-count approach + keep single `esn` column (proposed)** | Single change fixes both the wrong-primary problem and the missing-alternates problem. Borrows production-grade DS code. Backward-compatible for existing single-ESN queries. |

## 7. What I need from you

1. **Approve the schema delta** — `esns ARRAY<STRING>` + `esns_source` on metadata; `esns ARRAY<STRING>` on chunks. Additive only.
2. **Approve the LLM-count approach** for populating `esns` (vs the regex-scan approach in ADR-008). This adds one LLM call per doc to P1.
3. **Approve VS index rebuild** to expose `esns` as a filterable field. One-time, no re-embed. We'll coordinate timing with D&A.
4. **Confirm consumer alignment** — the consuming team (Abhinaya / app team) will need to switch their VS filter expression from `esn = X` to `array_contains(esns, X)` to take advantage of multi-ESN. Until they do, primary `esn` filtering still works (and will be more accurate post-fix).

## 8. Sequencing

| Order | Step | Owner | Gate |
|---|---|---|---|
| 1 | Approval on this doc | Pranesh, Tao | — |
| 2 | UI-07 Sprint 1 PR (negative-prompt + format regex + in-text check) | Madhurima | Validation harness — 30/30 + 14/14 + zero regression in dev |
| 3 | UI-07 Sprint 2 PR (ESN-only LLM call + count threshold + `esns` array) | Madhurima | Same harness + new multi-ESN cohort |
| 4 | DDL change — add columns; VS index rebuild | Madhurima + D&A | Co-ordinated window |
| 5 | UI-13 data-fix workflow run | Madhurima | Re-run nb_uat30_esn_recheck — expect 12 zero-doc ESNs to drop to ≤2 |
| 6 | Notify consumer of `esns` availability | Madhurima | After step 5 verifies |

## 9. References

- ADR-008 (predecessor, Option B carried forward, regex approach replaced): [ADR-008-multi-esn-filterability.md](ADR-008-multi-esn-filterability.md)
- DS reference implementation: [`poc/fsr-pipeline-dbr-candidate/src/esn_identifier.py`](../../poc/fsr-pipeline-dbr-candidate/src/esn_identifier.py)
- ESN field-quality findings: [esn-quality.md](../../fsr-prod-ops/user-reported-issues/findings/esn-quality.md)
- Multi-serial findings: [UI-03-multi-serial-per-doc.md](../../fsr-prod-ops/user-reported-issues/findings/UI-03-multi-serial-per-doc.md)
- UAT-12 zero-doc source check (today): [nb_uat12_zerodoc_esn_source_check.ipynb](../../fsr-prod-ops/prod-issues/nb_uat12_zerodoc_esn_source_check.ipynb)
- Working plan: [plan.md](../../fsr-prod-ops/plan.md) (UI-07 Sprint 1 / Sprint 2, UI-13)
- Tracker: [tracker.md](../../fsr-prod-ops/tracker.md) (UI-05, UI-07, UI-13)
- ESN denormalization pattern (3 places): [nb_sdg_fsr_chunks.py L246, L428, L459, L494](../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py)
- ESN resolver entry point: [nb_sdg_fsr_metadata.py L687](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py)
