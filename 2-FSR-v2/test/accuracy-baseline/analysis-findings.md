# FSR v2 Accuracy Baseline Analysis Findings

## Scope
This file captures analysis point-by-point from [prompt.md](2-FSR-v2/test/accuracy-baseline/prompt.md).

---

## Point 1
Question:
- Which preprocessor version is actually being used?
- What are the differences between Vince file and pipeline implementation?

### Findings

1. Runtime selection in P1 notebook
- The P1 orchestrator imports both processors:
  - [nb_sdg_fsr_v2_metadata.py](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py#L44)
  - [nb_sdg_fsr_v2_metadata.py](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py#L45)
- It selects implementation using FSR_V2_METADATA_PROCESSOR_VERSION:
  - [nb_sdg_fsr_v2_metadata.py](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py#L121)
- Allowed values are v1 or v2, default is v1:
  - [nb_sdg_fsr_v2_metadata.py](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py#L89)
  - [nb_sdg_fsr_v2_metadata.py](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py#L110)

2. Both metadata processors call the same shared preprocessor core
- v1 wrapper imports and calls common preprocessor:
  - [metadata_processor.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor.py#L25)
  - [metadata_processor.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor.py#L65)
- v2 wrapper also imports and calls the same common preprocessor:
  - [metadata_processor_v2.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py#L27)
  - [metadata_processor_v2.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py#L201)

3. What v2 wrapper changes
- v2 adds TOC-based document_summary extraction and attaches it to metadata:
  - [metadata_processor_v2.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py#L158)
  - [metadata_processor_v2.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py#L203)
- It does not replace the core ESN/region logic from common preprocessor.

4. Vince file vs common preprocessor core
- Compared files:
  - [preprocessor_v2_final.py](2-FSR-v2/analysis/preprocessor_v2_final.py)
  - [preprocessor.py](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py)
- Observed diff: only one added line in common file:
  - import re at file top
- Functional logic/body otherwise matches.

5. Important clarification
- Comparing Vince file directly against [metadata_processor.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor.py) will naturally show large differences because metadata_processor.py is a wrapper/orchestrator, not the preprocessor logic file.
- Correct code-level comparison is Vince file vs [preprocessor.py](pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py).

### Conclusion for Point 1
- The active core preprocessor logic is aligned with Vince's final processor file: `preprocessor_v2_final.py`.
- In the pipeline, both `metadata_processor.py` (v1 wrapper) and `metadata_processor_v2.py` (v2 wrapper) call the same core preprocessor logic.
- What v2 adds: TOC-based `document_summary` extraction and attachment to metadata; this is additional wrapper behavior, not a change to the core ESN/region preprocessor logic.
- The only code-level difference found between Vince's `preprocessor_v2_final.py` and the active core preprocessor file is an added `import re` line.

### Action Item (Point 1)
- Set `FSR_V2_METADATA_PROCESSOR_VERSION` default to `v2` so the TOC-based `document_summary` enhancement is enabled by default while keeping the same core preprocessor logic.
- Status: ✅ done — `nb_sdg_fsr_v2_metadata.py` default changed from `v1` to `v2`.

---

Stop here for review before moving to Point 2.

---

## Point 2
Question:
- Why does region_count differ between Tao's local DS-Guru verification and DB outputs?
- What specific differences exist between Tao's doc and exported tables?

### Inputs used
- Comparison notes section: `## Deep Dive: ESNs 316X914 and 337X581 — Local Verification (2026-07-22)` in `FSR_Retrieval_Fix_Plan - Local DS-Guru vs DB Verification (2026-07-22).md`.
- Table exports reviewed:
  - `fsr_metadata_v2.csv`
  - `fsr_document_equipment_map_v2.csv`
  - `fsr_chunks_v2.csv`

### How `source_region_count` is calculated in code
- The equipment map builder explodes `preprocessor_regions` and groups by `(document_id, esn)`, then counts rows.
- Reference implementation:
  - `nb_sdg_fsr_v2_document_equipment_map.py` (explode `regions`, extract `r.metadata.primary_esn`, `groupBy(document_id, esn)`, `count(*) -> source_region_count`).
  - Same pattern exists in P1 inline materialization path (`nb_sdg_fsr_v2_metadata.py`, `_build_map_rows`).

### Specific differences: Tao doc vs exported DB tables

1. `5b688732-39f2-48d2-a887-3239f258d28b` (316X914 case)
- Tao local note: 5 regions, all Generator (316X914).
- Exported DB (`fsr_metadata_v2.csv`): preprocessor_regions has 2 regions total:
  - 1 region for 316X914 (Generator)
  - 1 region for 155360 (Gas Turbine)
- Exported DB (`fsr_document_equipment_map_v2.csv`):
  - (155360, Gas Turbine, source_region_count=1)
  - (316X914, Generator, source_region_count=1)
- Difference summary: local vs DB region segmentation and labeling do not match.

2. `fcb1511e-596a-4a56-b151-1e596afa569c` (337X581 case)
- Tao local note: 1 Generator region + 1 GT region (2 total); local primary shown as 337X581.
- Exported DB (`fsr_metadata_v2.csv`): preprocessor_regions has 20 regions total:
  - 10 regions for 337X581 (Generator)
  - 10 regions for 298464 (Gas Turbine)
  - metadata primary_esn=298464, primary_equip_type=shared
- Exported DB (`fsr_document_equipment_map_v2.csv`):
  - (298464, Gas Turbine, source_region_count=10)
  - (337X581, Generator, source_region_count=10)
- Difference summary: both ESNs are detected in both environments, but region granularity and primary assignment differ.

3. `bdd56c7a-ebe5-4bf7-904a-5bb63091ba20` (337X581 gap case)
- Tao local note: GT-only map with 10 regions.
- Exported DB (`fsr_metadata_v2.csv`): preprocessor_regions has 136 regions, all for 298464 (Gas Turbine).
- Exported DB (`fsr_document_equipment_map_v2.csv`):
  - (298464, Gas Turbine, source_region_count=136)
- Difference summary: ESN-detection outcome matches (GT-only), but region count differs sharply (10 local vs 136 DB).

### Chunk-table validation from live DB queries
- Current chunk table snapshot (from your Query 1):
  - row_count = 1535
  - distinct_docs = 15
  - created_at range = 2026-07-22T02:55:20.631Z to 2026-07-22T04:01:05.373Z
- Target docs are present in chunk table (from your Query 2):
  - 5b688732-39f2-48d2-a887-3239f258d28b -> 165 chunks
  - fcb1511e-596a-4a56-b151-1e596afa569c -> 160 chunks
  - bdd56c7a-ebe5-4bf7-904a-5bb63091ba20 -> 53 chunks

### Additional differences visible at chunk level (from your Query 3)

1. `5b688732-39f2-48d2-a887-3239f258d28b`
- Chunk ESN distribution in DB:
  - 155360 (Gas Turbine): 159 chunks
  - 316X914 (Generator): 6 chunks
- This aligns directionally with DB map/metadata (both ESNs present), but not with Tao local note where all regions were Generator.

2. `fcb1511e-596a-4a56-b151-1e596afa569c`
- Chunk ESN/equip distribution in DB:
  - 298464 (Gas Turbine): 28 chunks
  - 298464 (shared): 129 chunks
  - 337X581 (Generator): 3 chunks
- Confirms mixed assignment behavior in chunk table and a strong skew toward 298464/shared in DB vs Tao local's simpler 1 Gen + 1 GT region picture.

3. `bdd56c7a-ebe5-4bf7-904a-5bb63091ba20`
- Chunk ESN/equip distribution in DB:
  - 298464 (Gas Turbine): 53 chunks
- This matches the GT-only outcome noted by Tao, but with different region/chunk granularity counts.

### Conclusion for Point 2
- `source_region_count` differences are real and are directly explained by differences in region segmentation produced upstream (number of region entries in `preprocessor_regions`).
- For the three focus docs, exported DB values are internally consistent between:
  - `fsr_metadata_v2.preprocessor_regions`
  - `fsr_document_equipment_map_v2.source_region_count`
- Live DB chunk queries also confirm the same three docs are present and show chunk-level distributions consistent with DB metadata/map direction, but different from Tao local DS-Guru segmentation/primary assignment patterns.
- The mismatch is between local DS-Guru output and DB run output, not between DB metadata and DB map tables.

### Root Cause Analysis for Point 2 (code-level)

Even if the intended preprocessor logic is "the same", there are multiple code paths that can produce different region counts.

1. Different text extraction stack before preprocessor (major)
- FSR v2 pipeline P1 parsing uses `pdfplumber` and builds:
  - per-page text with `.strip()`
  - `full_text = "\n\n".join(pages)`
- DS-Guru standard ingestion path uses `PyPDF2` (`page.extract_text()`), injects heading markers, and concatenates page text differently.
- DS-Guru page-by-page path uses `PyMuPDF` (`fitz`) for extraction.
- Since preprocessor boundaries are regex/char-offset driven over `full_text`, these extraction differences can change:
  - number of detected boundaries
  - boundary positions
  - merged region segments
  -> directly changing `source_region_count`.

2. DS-Guru executes schema-stored preprocessor code, not repo file directly (major)
- DS-Guru loads preprocessor code from collection metadata (`metadata_schema_db.get_full(namespace)`), then runs that `preproc_code` string.
- This means runtime DS-Guru behavior depends on what is saved in the collection schema at that moment, not only on files under `ds-guru/` repo.
- So "same file in repo" does not guarantee "same code executed" in DS-Guru.

3. Map-count definition itself is sensitive to segmentation granularity (expected behavior)
- `source_region_count` is computed as `count(*)` after exploding regions and grouping by `(document_id, esn)`.
- If one run creates many short alternating regions and another creates fewer large merged regions, counts will differ even when ESN detection direction is similar.

4. Wrapper/version selection can change side behavior (minor for region count)
- In pipeline, `FSR_V2_METADATA_PROCESSOR_VERSION` toggles wrapper (`metadata_processor` vs `metadata_processor_v2`).
- Core preprocessor call is shared, but v2 wrapper adds TOC summary behavior. This is not expected to directly alter region count, but confirms runtime is configuration-driven.

### Most likely primary cause chain for current mismatch
- Primary cause A: different extracted text representation between DS-Guru local run and DB pipeline run.
- Primary cause B: possible DS-Guru collection preprocessor-code drift (saved code not exactly the intended final snippet).
- Combined effect: different boundary detection and region merging -> different `preprocessor_regions` cardinality -> different `source_region_count`.

### Verification checks to close RCA fully
- In DS-Guru, export/print the exact active `preproc_code` for the tested collection and compare to `preprocessor_v2_final.py` text.
- For one target PDF, run both systems with the same raw file bytes and log:
  - extracted `full_text` length
  - number of header matches
  - boundary list count
  - final `regions` count by ESN
- If these intermediate counters differ before map materialization, the root cause is confirmed upstream of DB map logic.

### Verification run results (completed)
Target file used:
- `fcb1511e-596a-4a56-b151-1e596afa569c`

Observed outputs from RCA validation notebook:

1. Preprocessor parity check (same extraction, two preprocessors)
- For each extractor (`fitz`, `pdfplumber`, `pypdf2`), outputs are identical between:
  - `active_shared`
  - `vince_reference`
- This strongly indicates no effective logic drift between those two preprocessor files in this run.

2. Extraction-path sensitivity (same preprocessor family, different extractor)
- `fitz`: `full_text_len=297242`, `boundary_count_est=24`, `region_count=24`, split `12 GT + 12 GEN`, primary=`shared`
- `pdfplumber`: `full_text_len=286142`, `boundary_count_est=20`, `region_count=20`, split `10 GT + 10 GEN`, primary=`shared`
- `pypdf2`: `full_text_len=290756`, `boundary_count_est=22`, `region_count=22`, split `11 GT + 11 GEN`, primary=`Generator`

3. What this proves
- Region and boundary counts move with extraction method (20 vs 22 vs 24) even when preprocessor logic is unchanged.
- `full_text` length also varies by extractor, confirming upstream text representation differences.
- Primary assignment can shift as a downstream effect (`shared` vs `Generator`) depending on extracted text.

### Final RCA status for Point 2
- Verified: extraction stack differences are sufficient to explain the region-count mismatch behavior.
- Not supported by this run: a material code difference between `active_shared` and `vince_reference` preprocessor logic.
- Remaining optional check (only if needed): compare DS-Guru live schema `preproc_code` string vs repo file text to fully close environment-level drift risk.

### Action Items for Point 2

**Goal**: align pipeline extraction with DS-Guru so both systems produce consistent region segmentation and primary equipment assignment.

1. Add `PYPDF2_V1_0` enum value to `ExtractorMethod`
   - File: [common/fsr_v2/enums.py](pw_sdg_ai_ser_repo/common/fsr_v2/enums.py)
   - Added: `PYPDF2_V1_0 = "pypdf2_v1.0"` alongside existing `PDFPLUMBER_V1_0`
   - Status: ✅ done

2. Add `parse_pypdf2()` extraction function to pipeline parsing module
   - File: [silver/src/etl/fsr_v2/parsing.py](pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/parsing.py)
   - Added: `parse_pypdf2(doc)` using `pypdf`/`PyPDF2` `page.extract_text()` — matches DS-Guru standard ingestion extraction path
   - Same `"\n\n".join(pages)` and char-offset logic as existing `parse()` so preprocessor input contract is unchanged
   - Status: ✅ done

3. Wire pypdf2 extractor in P1 orchestrator notebook
   - File: [silver/src/etl/nb_sdg_fsr_v2_metadata.py](pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_v2_metadata.py)
   - Added: `"pypdf2_v1.0"` as valid `FSR_V2_PARSER_VERSION` value
   - Added: `_use_pypdf2` flag for dispatch
   - Changed: Stage 2 dispatch calls `parse_pypdf2(doc)` when `_use_pypdf2`, otherwise existing `parse(doc)`
   - Changed: `extractor_method` now correctly passed to `enrichment.run()` so recorded value matches actual method used
   - Added: `ExtractorMethod` import
   - Status: ✅ done

**Default changed to `pypdf2_v1.0`**: matches DS-Guru/Vince extraction path. To revert to pdfplumber, set `FSR_V2_PARSER_VERSION=pdfplumber_v1.0` as a pipeline parameter.

**Expected outcome after switching**:
- `primary_equip_type` changes from `shared` → `Generator` for Generator-dominant docs (e.g. `fcb1511e`)
- `source_region_count` aligns closer to DS-Guru local results
- `extractor_method` recorded as `pypdf2_v1.0` in metadata table for traceability

---

### Gap: Extraction text representation not fully aligned to DS-Guru

**Root cause doc:** `2-FSR-v2/test/accuracy-baseline/root-cause-region-count.md`

Even with `pypdf2_v1.0` extractor, the pipeline produced 22 regions vs DS-Guru's 2 for `fcb1511e`.
Root cause: DS-Guru applies `_inject_pdf_heading_markers` to each page before passing `full_text`
to the preprocessor. This rewrites numbered section headings (e.g. `1.2 Generator ...`) with
`## ` / `### ` prefix markers, which suppresses the preprocessor's `SUBSEC_GEN`/`SUBSEC_GT`
regex patterns (anchored at `^\d`) — collapsing 22 sub-section boundaries to ~2 coarse regions.

Additionally DS-Guru joins pages with a single `\n` while the pipeline used `\n\n`.

**Action Item (Gap 2b — extraction alignment):**
- File: `silver/src/etl/fsr_v2/parsing.py`
  - Added `_inject_pdf_heading_markers(page_text)` call inside `parse_pypdf2` (same function as DS-Guru `main.py`)
  - Changed page separator from `"\n\n"` → `"\n"` with char offsets updated from `+2` → `+1`
- Status: ✅ done
- Revert notes: see `root-cause-region-count.md` — Decision section

---

Stop here for review before moving to Point 3.

---

## Point 3
Question:
- What fixes are needed to the schema / code based on the metadata-levels analysis in `2-FSR-v2/design/metadata-levels.md`?

### What the metadata-levels doc says (proposed vs current)

Three categories of gaps between current implementation and proposed state:

**Gap 1 — `fsr_chunks_v2.metadata` is missing the `region` block**
- Current: `metadata` JSON contains `doc` block + `chunk_context` block only.
- Proposed: should also contain a `region` block with `primary_esn`, `primary_equip_type`, `primary_technology_code` from region attribution.
- Code evidence: in `chunking.py`, `metadata_json` is assembled with `doc` and `chunk_context` but no `region` key. The region-attributed ESN values go directly to top-level chunk columns (`ch["primary_esn"]`, `ch["primary_equip_type"]`) but are never written into the metadata JSON.
- Impact: downstream consumers querying `metadata.region` to understand which equipment section a chunk belongs to get nothing. Retrieval filters/re-rankers that use metadata region context are blind.

**Gap 2 — `fsr_chunks_v2.primary_esn` and `primary_equip_type` are `mixed (doc/region)`, proposed `region-level`**
- Current: `_resolve_chunk_meta_fields` first sets doc-level default (`row.primary_esn`), then region attribution may override. If no region overlap is found, the doc default persists.
- Proposed: should be purely region-level — if attribution misses, the chunk should reflect that rather than silently inheriting the doc value.
- Code evidence: `chunking.py::_resolve_chunk_meta_fields` Step 2 writes `row.primary_esn` as the default before Step 4 region override.
- Impact: chunks with no region overlap (e.g. introduction pages, appendices) incorrectly report `primary_esn` and `primary_equip_type` as if they were attributed, hiding attribution gaps.

**Gap 3 — `fsr_document_equipment_map_v2.is_primary_esn` and `is_active` proposed for removal**
- Current: both columns are computed and stored in every map row.
- Proposed: remove, since `is_primary_esn` is redundant (consumers can join with `fsr_metadata_v2.primary_esn`) and `is_active` is rarely queried directly from the map table.
- Impact: small — these are serving helpers. Low urgency.

### Action Items for Point 3

**Action Item 1 (Gap 1, high priority): Add `region` block to `fsr_chunks_v2.metadata` JSON**
- File: `gold/src/etl/fsr_v2/chunking.py`
  - In the metadata JSON assembly block, added `"region"` key populated from `ch["primary_esn"]` and `ch["primary_equip_type"]`.
- File: `common/fsr_v2/config.py`
  - Added `"region"` to `CHUNK_METADATA_JSON_OPTIONAL_KEYS` and example.
- Status: ✅ done

**Action Item 2 (Gap 2, medium priority): Make chunk `primary_esn`/`primary_equip_type` purely region-level**
- File: `gold/src/etl/fsr_v2/chunking.py`
  - In `_resolve_chunk_meta_fields`, removed Step 2 doc-level default assignment. `primary_esn` and `primary_equip_type` now start empty; region attribution is the only source.
  - If region attribution returns nothing, chunk correctly shows empty (attribution miss is visible).
- Note: existing chunk rows keep old values until P2 re-run.
- Status: ✅ done

**Action Item 3 (Gap 3, low priority): Remove `is_primary_esn` and `is_active` from map table**
- File: `silver/src/etl/nb_sdg_fsr_v2_metadata.py` (`_build_map_rows`)
  - Remove `is_primary_esn` and `is_active` from the returned row dicts.
- File: DDL / `common/fsr_v2/config.py`
  - Remove the two columns from the DDL definition.
- Note: this requires an `ALTER TABLE DROP COLUMN` migration on the live table, or a full table recreate. Coordinate with any consumer that filters on these columns before dropping.
- Status: ⏳ deferred — requires schema migration on live table before code change is safe.

---

Stop here for review before moving to Point 4.

---

## Point 4a
Question:
- How is `pdf_name` or `title` generated in code? For some docs we see UUIDs — where is the actual PDF name?

### How `document_id` and `pdf_name` are derived in v2

1. `document_id`
   - Derived in `input.py`: `document_id = lowercase(filename_stem)` where stem = filename with `.pdf` stripped if present.
   - For FieldVision source (`fv_field_service_report`): files are stored without extension and the filename IS the UUID.
   - Result: `document_id` = UUID for FieldVision documents.

2. `pdf_name` in v2
   - Set in `metadata_enrichment.py`: `"pdf_name": parsed_doc.filename` where `filename = Path(volume_path).name`.
   - For FieldVision: `volume_path = /Volumes/.../fv_field_service_report/fcb1511e-...`, so `filename = fcb1511e-...` (UUID, no extension).
   - No lookup or contextual derivation — whatever the volume file is named becomes `pdf_name`.
   - Result: `pdf_name` is also a UUID for FieldVision documents.

3. `title`
   - Extracted by LLM in P1-S4. Can have an actual human-readable title if LLM finds it on the cover page.
   - Not always available; LLM may return null.

### What FSR v1 did differently

v1 (`nb_sdg_fsr_metadata.py`) has a three-level `pdf_name` derivation cascade:

| Priority | Source | Logic |
|---|---|---|
| 1 | `fsr_pdf_ref` table | SQL lookup by `document_id` → returns stored human-readable name |
| 2 | Contextual fallback | `_build_contextual_pdf_name()` combines `title + customer + equipment_type + esn + outage_start_date` into a readable string |
| 3 | Volume path stem | `Path(volume_path).stem` — same as v2 current, falls back to UUID |

v1 function:
```python
def _build_contextual_pdf_name(rec):
    parts = [title, customer, equipment_type, esn, outage_start_date]  # sanitized
    return "_".join(parts) if parts else None
```

### Gap and Action Item for 4a

**Gap**: v2 does not implement the v1 `pdf_name` derivation cascade. For FieldVision documents the `pdf_name` column stores the UUID instead of a human-readable name. This affects:
- Display in any UI that shows `pdf_name`
- Retrieval result readability (users see UUIDs in results, not report names)

**Action Item 4a-1: Add `pdf_name` contextual derivation to v2 pipeline**
- File: `silver/src/etl/fsr_v2/metadata_enrichment.py`
  - After `rec` dict is built, derive `pdf_name` via contextual composite: `title + customer + primary_equip_type + primary_esn + outage_start_date` (sanitized, joined with `_`).
  - Falls back to `parsed_doc.filename` (current behaviour) when no fields are available.
- Status: ✅ done

---

## Point 4b
Question:
- FSR v1 chunk table `vec_field_service_report` — does it emit sections in chunk metadata JSON?

### Findings

**Yes, v1 DOES emit section paths in chunk metadata.**

From `nb_sdg_fsr_chunks.py` (v1 chunk pipeline):
- v1 uses `hierarchical_semantic_chunking_from_snapshot()` which returns chunks with a 5-level section hierarchy.
- Each chunk's `metadata` JSON includes:
  - `section_1`, `section_2`, `section_3`, `section_4`, `section_5` — the section path titles at each level
  - `start_page`, `end_page` — page range for the chunk
  - Plus all document-level fields (title, customer, esn, event_type, etc.)

v1 metadata JSON shape (confirmed from code):
```json
{
  "pdf_name": "...",
  "section_1": "GAS TURBINE",
  "section_2": "Inspection Summary",
  "section_3": null,
  "section_4": null,
  "section_5": null,
  "start_page": 5,
  "end_page": 12,
  "title": "...",
  "esn": "298464",
  "equipment_type": "Gas Turbine",
  ...
}
```

**In v2, sections are NOT written to chunk metadata JSON.**

From v2 `chunking.py`:
- The v2 metadata JSON assembly only writes `doc` block + `chunk_context` block.
- The chunker does support section metadata via `chunker.get_section_metadata(start_char, end_char)` and applies `sec_meta` to the chunk's `primary_esn`/`primary_equip_type` fields (for ESN attribution), but section titles are not carried into the metadata JSON.
- Result: `fsr_chunks_v2.metadata` has no `section_1…5` or equivalent section-path information.

### Action Item for 4b

**Action Item 4b-1: Add section path to `fsr_chunks_v2.metadata` JSON**
- File: `gold/src/etl/fsr_v2/chunking.py`
  - In the chunk building loop, call `chunker.get_section_metadata(start_char, end_char)` when strategy is `section` and store result in `ch["section"]`.
  - In metadata JSON assembly, add `"section": ch.get("section") or {}` alongside the `region` block.
- File: `common/fsr_v2/config.py`
  - Added `"section"` to `CHUNK_METADATA_JSON_OPTIONAL_KEYS` and example.
- Status: ✅ done

---

Stop here for review before moving to Point 5.
