# ADR-008: Multi-ESN Filterability — Store Alternate Serials per Document

| Field | Value |
|---|---|
| **Status** | PROPOSED |
| **Date** | 2026-05-04 |
| **Decision owners** | Madhurima, Pranesh, consuming team |
| **Depends on** | ADR-002 (embedding strategy), `fsr_config.py` schema |
| **Driven by** | [UI-03 findings](../../fsr-prod-ops/user-reported-issues/findings/UI-03-multi-serial-per-doc.md) |

---

## Context

The metadata table stores **one** `esn` per document. UI-03 measured chunk text and found:

- **2,837 docs (~16% of corpus)** contain more than one distinct `NNN[A-Z]NNN` serial token in their body. Tail goes to **83 distinct serials** in a single doc.
- In multi-serial docs, the stored `esn` doesn't appear in the text **65%** of the time — usually because it's a project / IBAT id (UI-01 bucket B) or a top-level Steam Turbine `SY…` serial while the body lists sub-component serials.
- Even in single-serial docs, the stored `esn` matches the only in-text token only **50%** of the time.

These multi-serial docs look like **valve / instrument / equipment-roster FSRs** where one report covers many sub-components. Examples (from UI-03):

| pdf_name | Stored `esn` | Distinct serials in text |
|---|---|---:|
| ProjectID_A-1703392_…EVP-516727 | `299244` (project id) | 83 |
| ProjectID_NEX-P-263451_SP-AR-P-263451 | `SY0022800` | 67 |
| ProjectID_NEX-P-257585_SP-10348257 | `SY0106914` | 58 |

Today the consumer can only pre-filter the vector index by the single stored `esn`. A query like `WHERE esn = '242F242'` returns nothing for a doc whose stored `esn` is `299244` — even though the doc is genuinely about `242F242`.

UI-03's count covers only the GT-shaped `NNN[A-Z]NNN` pattern. Steam Turbine (`SY0…`), Generator (`G00…`), Valve (`V0…`) serials in the same docs are **not counted** there — actual multi-serial coverage is higher.

---

## Problem statement

Should we store **multiple ESNs per document** so the consumer can pre-filter by any serial that appears in the doc, not just the LLM-picked primary?

If yes — what schema, where in the pipeline do we extract them, and what's the impact on the vector index?

---

## Options Considered

### Option A: Status quo — single `esn` STRING, no change

Keep one ESN per document; rely on full-text search inside chunks for alternate-serial queries.

**Pros:**
- No schema, no code, no backfill
- Vector index unchanged

**Cons:**
- Consumer has no pre-filter for ~16% of the corpus by sub-component serial
- Forces full vector search + post-filter on chunk text, which is slow and noisy
- UI-03 shows the stored `esn` is wrong 50–65% of the time anyway, so even the single-ESN filter is unreliable

### Option B: Add `esns ARRAY<STRING>` to metadata + chunk tables (selected)

Add an additive column on both tables. Populate via a one-shot regex scan over chunk text. Expose the column to Vector Search as a filterable field.

**Schema delta** ([`pw_sdg_ai_ser_repo/common/fsr_config.py`](../../pw_sdg_ai_ser_repo/common/fsr_config.py)):

```sql
-- biz_metadata_field_service_report
esns                 ARRAY<STRING>            COMMENT 'All distinct serials extracted from doc text (incl. primary esn). Empty array if none found.'
esns_source          STRING                   COMMENT 'How esns was populated: regex_scan / null'

-- vec_field_service_report (denormalized for VS filtering, parallels existing esn column)
esns                 ARRAY<STRING>            COMMENT 'All distinct serials for filterable VS pre-filter'
```

**Population logic** (one notebook, no LLM):

```python
ESN_REGEX = r"(?<![A-Za-z0-9])[0-9]{3}[A-Z][0-9]{3}(?![A-Za-z0-9])"
# Scan chunk_text per document, collect_set distinct matches, MERGE into both tables.
```

**Pros:**
- Additive column — no PK/FK risk, no break for existing consumers
- Cheap to populate — pure regex, no LLM, no embedding
- Resolves multi-serial filterability for the ~16% subset (and grows as we add more equipment-family regexes)
- Leaves the existing single `esn` column alone — primary identity intact
- One new column on each of two tables; one Vector Search index re-publish (no re-embedding)

**Cons:**
- Vector Search index needs to be **re-created** to expose the new field as filterable (DBR VS limitation — additive metadata columns on an existing index typically require a rebuild). Re-publish only — embeddings are reused, no recompute cost.
- Consumer query code must change from `WHERE esn = X` to `WHERE array_contains(esns, X)`.
- Regex is GT-only today; non-GT serials (`SY…`, `G…`, `V0…`) won't be picked up until we add per-family regexes.

### Option C: Explode to one row per (document × serial)

Change the metadata table grain from `document_id` → `(document_id, esn)`. Chunk join key changes accordingly.

**Pros:**
- Native single-ESN filter still works

**Cons:**
- Table explodes from 18K → 100K+ rows
- `document_id` is no longer unique → breaks every existing consumer query and the chunk-table join
- PK change on metadata table — invasive migration
- Significantly more complex to keep in sync with chunks

Rejected on cost / risk vs Option B.

### Option D: New side table `fsr_doc_serials (document_id, serial, source)`

Keep main tables unchanged; add a long table for (doc, serial) pairs.

**Pros:**
- No schema change to main tables
- Multi-source friendly (LLM, regex, IBAT can each contribute rows)

**Cons:**
- Vector Search can only filter on columns of the **chunk table** — a side table can't be used for VS pre-filter without denormalization
- So we'd still need to copy `esns` into the chunk table → same cost as Option B + an extra table
- More moving parts to keep in sync

Rejected — Option B subsumes it for the VS filter use-case.

---

## Decision (proposed)

**Option B — add `esns ARRAY<STRING>` (+ `esns_source`) to both metadata and chunk tables, populate via regex scan, re-publish VS index with `esns` as a filterable field.**

### Why

1. **Smallest schema delta that solves the consumer's problem.** Additive column, no PK/FK touch, no consumer-breaking changes.
2. **Cheapest fix.** No LLM cost, no re-embed, one regex pass over chunk text. Roughly the cost of running [nb_multi_serial_per_doc.ipynb](../../fsr-prod-ops/prod-issues/nb_multi_serial_per_doc.ipynb) once + one MERGE.
3. **Independent of the primary `esn` correctness work.** UI-01 / UI-02 fixes (re-extract primary ESN) can run in parallel. Once primary ESN is also populated into `esns` (always include it), this column degrades gracefully even if primary is wrong — at least one of the in-text serials is in the array.
4. **Forward-compatible.** Add per-equipment-family regexes (Steam Turbine `SY…`, Generator `G00…`, Valve `V0…`) over time without further schema change.

### Population rule

`esns = array_distinct(array_union([esn], regex_scan(chunk_text)))`

i.e. always include the primary `esn` (even if format-malformed) plus every regex-matched serial from the doc body. Never NULL — empty array `[]` if nothing matches.

### Pipeline integration

- **Phase 1 (one-shot fix):** standalone notebook scans existing chunk table, MERGEs `esns` into both tables. No pipeline change. Re-publish VS index.
- **Phase 2 (steady-state):** add the same regex step to [`pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py`](../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py) so new docs populate `esns` automatically. Mirror in [`silver/src/etl/nb_sdg_fsr_metadata.py`](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) MERGE.

---

## Consequences

**Positive:**
- Consumer can pre-filter VS by any serial in the doc (`array_contains(esns, '242F242')`).
- ~16% of corpus becomes retrievable by sub-component serial.
- Reduces dependency on the primary-ESN extraction quality (UI-01 / UI-02 work continues but isn't a blocker).
- No re-embedding cost.

**Negative / risks:**
- One Vector Search index re-publish required. Need a window when the index is rebuilding (or use a dual-index swap).
- Consumer query code must update — coordinate with the consuming team.
- Regex is GT-only at first cut; multi-format support is follow-on work, not in this ADR.
- A small risk of false positives (any 6-character `NNN[A-Z]NNN` substring in noisy OCR text). Mitigated by the lookaround boundaries; can post-filter against IBAT later.

**Schema migration:**
- `ALTER TABLE biz_metadata_field_service_report ADD COLUMN esns ARRAY<STRING>, ADD COLUMN esns_source STRING` — non-breaking.
- `ALTER TABLE vec_field_service_report ADD COLUMN esns ARRAY<STRING>` — non-breaking.
- VS index drop + recreate with `esns` exposed.

**Backfill:**
- Regex-scan + MERGE all 18K docs. Estimated cheap (UI-03 ran the underlying scan in minutes on serverless).

---

## Open questions for the consuming team

1. Is multi-serial filtering a real query pattern, or is single-ESN sufficient if we fix UI-01 / UI-02?
2. Are non-GT serial formats (`SY…`, `G00…`, `V0…`) in scope for filtering too? (Affects regex scope, not schema.)
3. Acceptable downtime for one VS index rebuild?

## File / code references

- Schema: [`pw_sdg_ai_ser_repo/common/fsr_config.py`](../../pw_sdg_ai_ser_repo/common/fsr_config.py) lines 311–360
- Chunk MERGE: [`pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py`](../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py) line 485
- Metadata MERGE: [`pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py`](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) lines 285, 868, 908
- Companion findings: [esn-quality.md](../../fsr-prod-ops/user-reported-issues/findings/esn-quality.md), [UI-03](../../fsr-prod-ops/user-reported-issues/findings/UI-03-multi-serial-per-doc.md), [equipment-type-quality.md](../../fsr-prod-ops/user-reported-issues/findings/equipment-type-quality.md)
