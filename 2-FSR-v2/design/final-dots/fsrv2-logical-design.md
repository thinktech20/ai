# FSR v2 Pipeline — Logical Design (New Joiner Reference)

Document used throughout: `5b688732-39f2-48d2-a887-3239f258d28b`

---

## 1. How a PDF is extracted

**P1 Stage 2 — `parsing.py → parse_pypdf2(doc)`**

1. Opens the file at `volume_path` using PyPDF2.
2. For each page: extracts raw text, then runs `_inject_pdf_heading_markers()` — rewrites numbered headings like `1.2 Generator` → `## 1.2 Generator`. This suppresses the preprocessor's sub-section boundary patterns (which anchor at `^\d`) so only top-level section boundaries are detected.
3. Pages are joined with `\n` (single newline, matching ds-guru behavior).
4. Returns: `full_text` (full document text), `page_texts` (per-page), `page_offsets` — one `{start, end}` per page marking where that page's text sits inside `full_text`:

```
page 0 text: "Cover page text"       → 15 chars → offset {start: 0,   end: 15}
page 1 text: "Site Personnel..."     → 200 chars → offset {start: 16,  end: 215}
page 2 text: "Generator inspection"  → 180 chars → offset {start: 216, end: 395}
```

These offsets are what let the preprocessor assign regions to exact char ranges, and what let P2 match each chunk back to the right region.

---

## 2. How the text is parsed (preprocessor)

**P1 Stage 3 — `preprocessor_v2_final.py`**

Receives `full_text`, `page_offsets`, and the list of fields to populate. Returns three things:
- `metadata` — doc-level key/value fields
- `regions` — list of `{start, end, metadata}` char-offset spans, where each span covers a contiguous section of `full_text` attributed to one ESN/equipment type.

  Built by first scanning `full_text` for `HEADER` patterns (`GENERATOR (316X914 | SY0490705)`) and section markers (`## 3 GENERATOR`) → produces a `boundaries` list of `(char_pos, equip_type, esn)`. Then:
  - **≥2 distinct equipment types in boundaries** → regions are spans between consecutive boundaries:
    ```
    boundary at char 0     → Generator / 316X914
    boundary at char 15000 → Gas Turbine / 298250
    → region 1: {start: 0,     end: 15000, metadata: {primary_esn: "316X914", primary_equip_type: "Generator"}}
    → region 2: {start: 15000, end: 77774, metadata: {primary_esn: "298250",  primary_equip_type: "Gas Turbine"}}
    ```
  - **<2 distinct types** → boundaries didn't reveal multiple equipment; fall back to page-level assignment using form codes, signature keywords, or ESN mentions. Consecutive pages with the same assignment are merged into one region via `page_offsets`. See section 3 for detail.
- `hints` — plain-text notes for the LLM (e.g. "Turbine ESN is 155360")

The preprocessor is pure Python — no LLM, no I/O. It's a regex + heuristic scan of the text.

---

## 3. Preprocessor regions and metadata levels

### Region definition
A region is a continuous span of text attributed to a specific ESN and equipment type:
```json
{"start": 0, "end": 366, "metadata": {"primary_esn": "316X914", "primary_equip_type": "Generator"}}
```

### How regions are built

1. **Boundary detection (always runs first):** Scans `full_text` for `HEADER` patterns (`GENERATOR (316X914 | SY0490705)`), section markers (`## 3 GENERATOR`), and subsection patterns (`3.1 Generator`). Builds a `boundaries` list of `(char_pos, equip_type, esn)` tuples.

2. **Decision:** Check how many distinct equipment types appear in `boundaries`:
   - **≥2 types → Path A:** Regions are the spans between consecutive boundaries, each tagged with that boundary's ESN/type.
   - **<2 types → Path B:** Boundaries didn't reveal multiple equipment types. Fall back to page-level assignment — each page is classified using form codes, signature keywords, or ESN mentions. Consecutive pages with the same assignment are merged into one region using `page_offsets`.

### For `5b688732`
This is a single-equipment document — only Generator `316X914` is active. Path B runs and creates **358 page-level regions**, each assigned to `316X914 / Generator`. All regions in `preprocessor_regions.json` show the same assignment.

### Metadata levels
| Level | Where stored | What it contains |
|-------|-------------|-----------------|
| Doc-level | `fsr_metadata_v2` columns | `primary_esn`, `primary_equip_type`, `gt_esn`, `gen_esn`, dates, project IDs, etc. |
| Region-level | `fsr_metadata_v2.preprocessor_regions` (JSON) | Per-span `primary_esn`, `primary_equip_type` for chunk attribution |
| Chunk-level | `fsr_chunks_v2.metadata` (JSON) | Full `fsr_v2_chunk_metadata_v2` struct: `doc`, `region`, `section`, `chunk_context` blocks |

---

## 4. Other preprocessor outputs and how they're used

| Output | Where used |
|--------|-----------|
| `hints` | Injected into the LLM extraction prompt as "known facts — do not contradict". Prevents LLM from overriding preprocessor-derived ESN/equipment type values. |
| `inactive_esns` | Stored on metadata row. Used in P2 to exclude ESNs from `active_esns`. Equipment flagged as "not applicable for this outage" near an ESN mention triggers this. |
| `document_summary` | v2 preprocessor only. TOC-based summary stored on the metadata row. |

---

## 5. How specific metadata columns are calculated

### `primary_esn` and `primary_equip_type`

1. **HEADER scan** (full text): finds `GENERATOR (316X914 | SY0490705)` → maps ESN to type.
2. **Label scan** (first 6 pages): `Generator Serial No: 316X914`, `Generator ESN: ...`, etc.
3. **GT label scan**: `Assoc. Turbine: 155360` → maps GT ESN.
4. After building the ESN-to-type map, `_choose_primary()` decides:
   - Single equipment: use it directly.
   - Both GT and Generator present: compare byte-share of detected sections (1.2x ratio threshold). If no clear winner from boundaries, compare signature keyword counts. If still tied: `shared`.

### `gt_esn` / `gen_esn`
First active ESN of each type (sorted alphabetically) from the full ESN-to-type map.

### `event_type`
**LLM-derived only** — preprocessor does not calculate this. The LLM receives the first 6000 chars of the document plus preprocessor hints and extracts `event_type` (e.g. "Call-Out", "Inspection").

### For `5b688732`
- HEADER match: `GENERATOR (316X914 | SY0490705)` → `gen_esn = 316X914`
- GT label match on title pages: "Associated Turbine: 155360" → `gt_esn = 155360`
- Single active Generator → `primary_esn = 316X914`, `primary_equip_type = Generator`
- `event_type = ""` — LLM could not extract it from this document
- `outage_start_date = 2019-11-23` — preprocessor found via `Job Start Date:` pattern

---

## 6. How `primary_esn`, `primary_equip_type`, `active_esns` in `fsr_chunks_v2` are calculated

**P2 — `chunking.py → _resolve_chunk_meta_fields()`**

For each chunk `[chunk_start_char, chunk_end_char]`:

1. Start with `primary_esn = ""`, `primary_equip_type = ""`.
2. Find the region with maximum character overlap with the chunk's range.
3. If a region is found: use its `primary_esn` and `primary_equip_type`.
4. If no region overlaps: stays empty (no doc-level fallback — removed intentionally so cross-equipment contamination is prevented).

**`active_esns`** — computed once per document in `_build_active_esns()`:
- Union of all ESNs from all regions + `doc.primary_esn`, `doc.gt_esn`, `doc.gen_esn`
- Minus any ESNs in `inactive_esns`
- Sorted and pipe-joined: e.g. `"316X914"` or `"298250|338X447"`

**For `5b688732`:** every chunk overlaps a Generator region → `primary_esn = 316X914`, `primary_equip_type = Generator`, `active_esns = "316X914"`.

---

## 7. How the chunk metadata JSON fields are calculated

**Contract version:** `fsr_v2_chunk_metadata_v2`

Example (from prompt):
```json
{
  "metadata_contract_version": "fsr_v2_chunk_metadata_v2",
  "doc": {
    "title": "5b688732-39f2-48d2-a887-3239f258d28b",
    "customer": "",
    "event_type": "",
    "fsp_project_id": "FSP-261874",
    "xxx_project_id": "C-10329409",
    "outage_start_date": "2019-11-23",
    "inactive_esns": []
  },
  "region": {"primary_esn": "", "primary_equip_type": ""},
  "section": {"section_title": "Site Personnel", "section_level": 2, "section_path": ["Dec 2011", "Site Personnel"]},
  "chunk_context": {"chunk_start_char": 0}
}
```

| Block | Source | Notes |
|-------|--------|-------|
| `doc.*` | Preprocessor doc-level + LLM extraction, merged in P1 Stage 4 | `title` is document UUID (preprocessor-authoritative). `fsp_project_id`, `xxx_project_id` = LLM-extracted. `outage_start_date` = preprocessor date regex. |
| `region.*` | Char-offset region attribution in P2 | Empty here because this chunk was ingested in an earlier run before the current attribution logic. In current runs: populated from the region overlapping the chunk. |
| `section.*` | `v1_hierarchical` chunker — reads heading structure from raw chunk metadata (`section_1..section_5` fields). Stores title, level, path. | `["Dec 2011", "Site Personnel"]` = level-1 / level-2 heading path at char 0. |
| `chunk_context.chunk_start_char` | Chunk's `start_char` in `full_text` — same coordinate space as `page_offsets` and `preprocessor_regions`. All three are offsets in the same joined document string. Example: | |

```
full_text (one long string of all pages joined)
│
├── page_offsets:         page 0 → {start: 0,   end: 366}
│                         page 1 → {start: 367,  end: 1084}
│                         ...
│
├── preprocessor_regions: region 0 → {start: 0,   end: 366,  metadata: {primary_esn: "316X914"}}
│                         region 1 → {start: 367,  end: 1084, metadata: {primary_esn: "316X914"}}
│                         ...
│
└── chunk:                chunk_start_char = 0, chunk_end_char = ~4000
                          → overlaps region 0 (and possibly 1, 2...)
                          → region with max overlap wins for attribution
```

⚠️ **Known issue — `v1_hierarchical` coordinate mismatch:** The `v1_hierarchical` chunker internally uses PyMuPDF to extract text, so its `chunk_start_char` is a position in PyMuPDF text space. But `preprocessor_regions` offsets are in pypdf2 text space (P1 extractor). These two strings differ in length and whitespace, so chunk offsets can exceed the last region end → region attribution returns empty. This is why `region: {primary_esn: "", primary_equip_type: ""}` appears in chunk metadata for this strategy. Fix: align the `v1_hierarchical` adapter to pypdf2 offsets (not pdfplumber, which was the previous target). |

---

## 8. How `fsr_document_equipment_map_v2` columns are calculated

Built in P1 Stage 5 via `_build_map_rows()` — runs in-memory after Stage 4 completes, before any SQL read-back.

| Column | How calculated |
|--------|---------------|
| `esn` | All unique ESN values from `preprocessor_regions[].metadata.primary_esn` |
| `equip_type` | First non-null `primary_equip_type` seen for that ESN across regions |
| `is_primary_esn` | `esn == rec["primary_esn"]` (post-enrichment doc-level primary) |
| `is_active` | ESN not in the `inactive_esns` set |
| `source_region_count` | Count of regions in which this ESN appears |

One row per `(document_id, esn)`. Written via MERGE — stale rows for docs in the current batch are deleted first.

**For `5b688732`:**

| document_id | esn | equip_type | is_primary_esn | is_active | source_region_count |
|-------------|-----|-----------|---------------|-----------|-------------------|
| 5b688732-... | 316X914 | Generator | true | true | 358 |

Single row — only one ESN across all 358 page-level regions. `gt_esn = 155360` does NOT appear in the regions (it was never a region-level ESN in this doc, only a doc-level label), so it doesn't get a map row.
