# Preprocessor Knobs & Layer Impact

## Table of Contents

1. [The Problem (Current FSR prod pipeline)](#the-problem-current-fsr-prod-pipeline)
2. [FSR v2 Pipeline Architecture (Context)](#fsr-v2-pipeline-architecture-context)
3. [FSR v2 Pipeline Architecture (Detailed)](#fsr-v2-pipeline-architecture-detailed)
4. [Metadata Table Schema Changes](#metadata-table-schema-changes)
5. [Chunk Table metadata JSON (compatibility during transition)](#chunk-table-metadata-json-compatibility-during-transition)
6. [Future Improvements / Knobs](#future-improvements--knobs)
7. [Per-Chunk ESN Attribution Example (v1 vs v2)](#per-chunk-esn-attribution-example-v1-vs-v2)
8. [Two-Phase Implementation Approach (Rollout Plan)](#two-phase-implementation-approach-rollout-plan)
9. [Refrences](#refrences)

---

## The Problem (Current FSR prod pipeline)

Multi-equipment FSRs (Gas Turbine + Generator on same document) have **two failure modes**:

1. **Retrieval miss** — User queries Generator ESN (e.g., `338X447`), but chunks are tagged with GT ESN → zero results. Affects ~17% of cross-ESN queries.

2. **Wrong label** — Generator content (stator, rotor, field) is labeled "Gas Turbine" because the FSR listed the GT ESN first → LLM risk assessment confuses equipment type → wrong remediation recommendation.

---

## FSR v2 Pipeline Architecture (Context)

### Core Pipeline (Simplified)

```
┌─ P1: METADATA EXTRACTION (nb_sdg_fsr_v2_metadata.py) ─────────────────────────────────────┐
│                                                                                            │
│  Extract Text (pdf parser)                                                                 │
│      knob: FSR_V2_PARSER_VERSION (pypdf2_v1.0 default | pdfplumber_v1.0 | v1)            │
│             pypdf2_v1.0 applies heading marker injection before preprocessor              │
│                                                                                            │
│  → Preprocess (regions + hints + doc metadata)                                             │
│      knob: FSR_V2_METADATA_PROCESSOR_VERSION (v1 baseline / v2 TOC-summary variant)       │
│                                                                                            │
│  → LLM Normalization (cover-page/admin fields)                                             │
│      knob: FSR_LLM_EXTRACTION_PROMPT_VERSION (v2_with_hints default) + model + api-key   │
│                                                                                            │
│  → Document Merge & Enrich (preproc + llm fields, then IBAT/EV/PSOT lookups)             │
│      knob: precedence/merge policy + reference-table availability                          │
│                                                                                            │
│  → Store (metadata_table_v2 row)                                                           │
│                                                                                            │
│  → Stage 5: Materialize document_equipment_map_v2 (batch-scoped MERGE)                    │
│      scope:  success_ids from this P1 run only (not a full-table rebuild)                  │
│      source: map_rows built in-memory during loop via _build_map_rows()                    │
│              (processor_output.regions + post-enrichment rec — no SQL read-back)           │
│      active: is_active derived from inactive_esns list                                     │
│      cleanup: DELETE stale rows for docs in this batch that no longer have map entries     │
└────────────────────────────────────────────────────────────────────────────────────────────┘
                                         ↓
┌─ P2: CHUNKING (nb_sdg_fsr_v2_chunks.py / gold stage) ─────────────────────────────────────┐
│                                                                                            │
│  Read metadata + regions                                                                   │
│  → Merge (upload/doc/section/region precedence)                                            │
│      knob: FSR_MERGE_STRATEGY (v2_4level_cascade default)                                 │
│             FSR_REGION_ATTRIBUTION_METHOD (char_offset_max_overlap default)               │
│  → Chunk                                                                                   │
│      knob: FSR_CHUNKING_STRATEGY (default: v1_hierarchical)                                │
│  → Embed                                                                                   │
│      knob: FSR_EMBEDDING_MODEL + FSR_EMBEDDING_DIMENSION (default: 3072)                  │
│  → Store (chunk_table_v2 rows)                                                             │
└────────────────────────────────────────────────────────────────────────────────────────────┘
                                         ↓
┌─ P3: VECTOR INDEX (separate step) ─────────────────────────────────────────────────────────┐
│                                                                                            │
│  Create / Update index schema                                                              │
│      knob: index name, FSR_EMBEDDING_DIMENSION (default: 3072), schema fields             │
│  → Sync index from chunk_table_v2                                                          │
│      knob: INDEX_MODE (create | sync)                                                      │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key FSR v2 Data Assets

- `fsr_metadata_v2` (document-level source of truth)
    - key columns: `document_id`, `pdf_name`, `primary_esn`, `primary_equip_type`, `preprocessor_regions`, `inactive_esns`, `chunk_status`
    - `pdf_name` derivation: contextual composite `customer_equip_type_esn_outage_date` (from LLM/preprocessor-extracted fields); falls back to volume filename when fields are blank. No `fsr_pdf_ref` lookup (v1 used a curated reference table as the primary source; v2 does not).
    - `title` column: set from LLM-extracted `document_name` (the preprocessor maps this to `ctx.filename`, i.e. the volume filename). Not extracted from PDF cover-page text as in v1.
- `fsr_chunks_v2` (chunk-level retrieval dataset)
    - key columns: `chunk_id`, `document_id`, `chunk_text`, `primary_esn`, `primary_equip_type`, `report_date`, `outage_start_date`, `chunk_embedding`, `metadata`
- `fsr_document_equipment_map_v2` (helper map for document-to-ESN lookup)
    - key columns: `document_id`, `esn`, `equip_type`, `is_primary_esn`, `is_active`
- `fsr_vs_index_v2` (vector index synced from chunks)
    - key fields synced from chunks: `chunk_id`, `chunk_text`, `primary_esn`, `primary_equip_type`, `active_esns`, `report_date`, `outage_start_date`, `metadata`

What goes into each chunk row `metadata` JSON:

- `doc` block: doc-level fields (shared across chunks in the same doc)
- `region` block: only that chunk's attributed `primary_esn` and `primary_equip_type`
- `section` block: section info for that chunk
- `chunk_context`: includes `chunk_start_char` for that chunk
- plus any `upload_meta` baseline fields if provided

### Knob Wiring Reality (Code)

- Yes, major knobs are separately selectable and wired through notebook/config runtime parameters.
- Some knobs are file/module swaps (for example Stage 3 processor v1 vs v2), and others are parameter-only (model, strategy, table paths).
- Stage 3 processor version switch is already wired in metadata notebook runtime params.

#### P1 (Metadata Extraction)
| Step | Input | Output |
|------|-------|--------|
| Extract Text | PDF | Raw text (via `FSR_V2_PARSER_VERSION`; pypdf2_v1.0 default with heading marker injection) |
| Preprocess | Raw text | metadata, preprocessor_regions (char ranges), hints |
| LLM Extraction | Page-1 text + hints | LLM fields (customer, event_type, etc.) |
| Document Merge & Enrich | Preprocessor metadata + LLM fields | One final document row (preprocessor > LLM, then IBAT/EV/PSOT enrichment) |
| Derive `pdf_name` | Merged record (`customer`, `primary_equip_type`, `primary_esn`, `outage_start_date`) | Contextual composite name; falls back to volume filename if all fields blank. v1 additionally tried `fsr_pdf_ref` curated table first — v2 does not. |
| Store | Merged metadata | metadata_table row |
| Materialize ESN Map | metadata_table row with extracted attribution | document_equipment_map_v2 rows (one row per document_id + esn) |

**P1 Overall:** Input = PDF | Output = metadata_table (doc-level metadata + preprocessor_regions + LLM fields) + document_equipment_map_v2 (serving helper rows built from real extracted data)

---

#### P2 (Chunking)
| Step | Input | Output |
|------|-------|--------|
| Read Metadata | metadata_table row | Doc-level metadata + preprocessor_regions |
| Merge (per chunk) | Upload meta + doc meta + section meta + regions | Per-chunk metadata (4-level cascade) |
| Split Chunks | Raw text + strategy | Chunks with char offsets |
| Embed | Chunks | Embeddings + dimension |
| Store (Chunks) | Chunks + metadata | chunk_table row |

**P2 Overall:** Input = metadata_table rows | Output = chunk_table (chunks + merged metadata + embeddings + run tracking)

---

#### P3 (Vector Index Creation & Sync)
| Step | Input | Output |
|------|-------|--------|
| Create/Update Index | chunk_table schema + index config | Vector index definition |
| Sync Index | chunk_table rows (embeddings + metadata) | Search-ready index |

**P3 Overall:** Input = chunk_table rows | Output = synced vector index

Note:
- document_equipment_map_v2 materialization belongs to P1, and is created only when real attribution data is available.
- No placeholder rows are written before attribution exists.
- Retrieval candidate resolution should gate to documents with chunk status = completed.

### Merge Step Breakdown (Per-Chunk Attribution)

**Input:**
- Upload metadata (optional: doc_type, priority, file_path) — **baseline**
- Doc-level metadata (preprocessor + LLM combined)
- Section metadata (only if using section strategy)
- Preprocessor regions (char-offset boundaries with per-region metadata)
- Chunk offsets (start_char, end_char in original PDF text)

**Merge Priority (applied in order; later overwrites earlier):**
1. Upload-level metadata (lowest priority) — `{doc_type, priority, file_path, ...}`
2. Doc-level metadata — `{**upload_meta, **preproc_meta, **llm_meta}` (preprocessor > LLM)
3. Section metadata (if strategy=='section') — applies to whole chunk
4. Region metadata (HIGHEST priority) — from best-overlapping region in preprocessor_regions

**Output:**
- Per-chunk metadata JSON with final primary_esn, primary_equip_type, inactive_esns, etc.

**Example:**
```
Doc says: primary_esn=338X447 (from preprocessor doc-level)
Chunk at char 20,000 overlaps region [15,000-28,000] with primary_esn=298250
→ Final chunk metadata: primary_esn=298250 (region wins)
```

### Scope Limitations (v2 Phase 1)

- **Char-offset regions only** — standard ingest path; page-by-page ingest deferred
- **No re-ingestion conflict logic** — if same doc is re-processed, regions are re-attributed but merge precedence is not re-ordered
- **Embedding dimension** — tracked per-chunk in metadata JSON (`embedding_dimension`) and required for P3 index creation (`FSR_EMBEDDING_DIMENSION`, default: 3072)

### Preprocessor Hints Usage

**P1 (Metadata Extraction):**
- Preprocessor outputs `hints` alongside `metadata` and `regions`
- Hints are **injected into LLM extraction prompt** as "known facts — do not contradict"
- Example: `"Turbine ESN is 298250 (from section header)"`

**P2 (Chunking / Merge):**
- Hints are not used in P2 merge; they are P1-only (guide LLM, not chunk merge)

### Replacement & Audit

**On Re-Ingestion of Same Document:**
- **Detection:** MERGE INTO uses chunk_id (derived from doc_id + chunk_index)
- **Behavior:** Old chunks are updated in-place; use `replaced=true` flag in logs
- **Audit trail:** Store in metadata_table.chunk_status transition logs (pending → in_progress → completed)

---

## FSR v2 Pipeline Architecture (Detailed)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        FSR INGESTION PIPELINE                               │
└──────────────────────────────────────────────────────────────────────────────┘

STEP 1: METADATA EXTRACTION (P1 — nb_sdg_fsr_v2_metadata.py)
├─ Discovers new PDFs from:
│  • /Volumes/viud/ing_ud_fieldvision/fv_field_service_report
│  • /Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports
├─ Extracts text via configurable parser (`FSR_V2_PARSER_VERSION`; default: **pypdf2_v1.0** with heading marker injection)
├─ Calls preprocessor on full PDF text + page_offsets
├─ Stores preprocessor outputs in metadata_table
│  • doc-level metadata
│  • preprocessor_regions (char ranges)
│  • inactive_esns
├─ LLM extraction — ds-guru pattern (cover-page admin fields only)
│  • Raw page-1 text slice (first 6000 chars) + schema-driven field spec sent to LLM
│  • Scoped to admin fields: customer, prepared_by, approved_by, fsr_number, event_type, project IDs
│  • ESN, equipment type, and dates are NOT asked of the LLM — preprocessor is authoritative for these
│  • Preprocessor hints injected as authoritative context ("known facts — do not contradict")
│  • LLM returns field names directly; no column mapping or pre-parsing of key:value pairs
├─ Merge precedence: {**llm_meta, **preproc_non_empty} — preprocessor overrides LLM
│  • preprocessor doc-level values win over LLM output for any overlapping fields
│  • per-chunk region attribution (P2) applies on top: region tag > preprocessor-doc > LLM output
├─ Enriches with IBAT + Event Vision
│  • Deterministic table joins on primary_esn — no additional LLM call
│
├─ ┌─ NESTED: PRE-PARSING ENRICHMENT (preprocessor_v2_final.py — runs inside P1)
│  │  ├─ Sandboxed execution (child process, no imports, no I/O)
│  │  ├─ Scans full PDF text for section headers, TOC headers, form numbers, keyword signals, inactive markers,
│  │  │  full-text header re-scan, and nested subsection patterns
│  │  ├─ Outputs:
│  │  │  • metadata (doc-level)
│  │  │  • hints (for LLM normalization)
│  │  │  • regions (start/end with metadata_per_region)
│  │  └─ Runtime: < 1 sec per document
│  └─
│
└─ Outputs → metadata_table + document_equipment_map_v2:
    ├─ Existing columns: esn, equipment_type, equipment_sys_id, equipment_class_code, and related fields
    ├─ LEGACY column: all_esns (deprecated; compatibility only)
    ├─ NEW columns: preprocessor_regions (JSON), inactive_esns (string/array) [PHASE 1 foundation]
    └─ Stage 5: document_equipment_map_v2 rows (batch-scoped MERGE from in-memory map_rows)
        • one row per (document_id, esn) — covers primary and secondary ESNs
        • is_active derived from inactive_esns list
        • DELETE stale rows for docs in this batch that no longer have map entries

STEP 2: CHUNKING (P2 — nb_sdg_fsr_v2_chunks.py)
├─ Change note (2026-07-16):
│  • Originally, full re-chunk/re-embed was positioned as Phase 2.
│  • During implementation, we found parser-aligned chunk attribution is required for v2 correctness.
│  • Therefore, the v2 path now runs parser-aligned chunking + embedding for selected docs in current scope.
├─ Reads completed metadata from metadata_table
│
├─ ┌─ NESTED: MERGE — PER-CHUNK METADATA ATTRIBUTION
│  │  Purpose: Apply region-based metadata to each chunk, ensuring multi-ESN docs don't cross-contaminate chunks.
│  │
│  │  Input:
│  │   • upload_meta = optional upload-level metadata (doc_type, priority, file_path, ...)
│  │   • doc_metadata = document-level metadata from P1 (esn, equipment_type, llm_fields, ...)
│  │   • preprocessor_regions = array from metadata_table: [{start, end, metadata}, ...]
│  │   • chunk = (chunk_text, chunk_start_pos, chunk_end_pos)  [character offsets in original PDF text]
│  │   • section_metadata = optional, from chunker if strategy=='section'
│  │
│  │  Merge Algorithm (per chunk):
│  │   1. Start with base_metadata = {**upload_meta}  [upload-level baseline]
│  │   2. Add: {**base_metadata, **doc_metadata}  [doc values override upload]
│  │      Note: Within doc_metadata, preproc_meta > llm_meta (preprocessor authoritative)
│  │   3. If strategy=='section': get section_metadata for chunk, then:
│  │      {**base_metadata, **section_metadata}  [section values override doc-level]
│  │   4. Find best-overlapping region = region where (overlap between [chunk_start_pos, chunk_end_pos] 
│  │      and [region_start, region_end]) is maximum
│  │   5. If best_overlapping_region exists:
│  │      final_chunk_metadata = {**base_metadata, **region_meta}  [region wins ALL]
│  │   6. Example: doc says primary_esn=338X447 but chunk overlaps region with primary_esn=298250 
│  │      → use 298250
│  │
│  │  Merge Priority (final order):
│  │      upload-level (lowest) < doc-level < section < region (highest)
│  │
│  │  Output per chunk:
│  │   chunk_metadata = {
│  │     "primary_esn": <from best region or doc-level>,
│  │     "primary_equip_type": <from best region or doc-level>,
│  │     "primary_technology_code": <from best region or doc-level>,
│  │     "gt_esn": <from best region if applicable>,
│  │     "gen_esn": <from best region if applicable>,
│  │     "inactive_esns": <from best region or doc-level>,
│  │     "chunk_index": <chunk sequence>,
│  │     "chunk_size": <length in chars>,
│  │     "chunk_strategy": <strategy name>,
│  │     "embedding_model": <model name>,
│  │     "embedding_dimension": <dimension>,
│  │     ... other fields inherited from upload/doc level
│  │   }
│  │
│  │  Pattern: Mirrors ds-guru/app/rag.py _region_metadata_for() — battle-tested production code.
│  └─
│
├─ For existing chunk rows, attach enriched metadata where current chunk anchors / join strategy allow it [PHASE 1]
│  • Goal: improve retrieval filters and enable QA validation without re-chunking or re-embedding
│  • Candidate updates: corrected primary_equip_type, esn_details, related per-ESN metadata
├─ For re-derived chunks [ORIGINAL PHASE 2; NOW REQUIRED FOR V2 CORRECTNESS]
│  • parser alignment + chunking
│  • merge step (per-chunk region attribution — see above)
│  • full per-chunk attribution and embedding
├─ Writes to chunk_table (Gold zone)
│  • PHASE 1 for metadata-only updates on existing rows
│  • PHASE 2 for re-derived chunks (includes merged metadata)
└─ Triggers Vector Search index sync
    • PHASE 1 after metadata updates
    • PHASE 2 after re-derived chunks

STEP 3: INDEXING & STORAGE (Vector Search — fsr_vs_index_v2)
├─ Syncs from fsr_chunks_v2 via Delta Sync index
├─ Key fields indexed:
│  • chunk_id, document_id, pdf_name, chunk_text (for retrieval)
│  • chunk_embedding ARRAY<DOUBLE> (3072-dim, self-managed — caller embeds at query time)
│  • primary_esn, primary_equip_type (chunk-level attribution — the core v2 fix)
│  • outage_start_date, active_esns (recency + doc-scope filters)
│  • metadata (JSON blob with doc/region/section context)
└─ Endpoint: pw-ser-sdg-vector-search

STEP 4: RETRIEVAL — DATA READINESS API (UC1: GET /equipment/{esn})
├─ Input: requested_esn
├─ SQL query on fsr_document_equipment_map_v2 ⨝ fsr_metadata_v2
│  • WHERE UPPER(d.esn) = requested_esn
│  •   AND d.is_active = true
│  •   AND m.metadata_status = 'completed'
│  •   AND m.chunk_status = 'completed'
│  •   AND m.outage_start_date >= recency_threshold (default: 120 months)
│  • fsr_document_equipment_map_v2.esn covers all ESNs in a doc (primary and secondary)
│    → both GT ESN and Generator ESN return this doc if either was the requested ESN
└─ Output: document list ordered by report_issued_date DESC

STEP 5: RETRIEVAL — FSR RETRIEVAL API (UC2: POST /retrieve)
├─ Input: requested_esn + query_text + top_k (default: 5)
│
├─ Step 1 — SQL eligibility gate (same tables as UC1, without metadata_status filter)
│  • Returns candidate_doc_ids for this ESN (is_active=true, chunk_status=completed, recency)
│  • If no eligible docs → return empty immediately (no VS call)
│
├─ Embed query_text via LiteLLM → query_vector (3072-dim, azure-text-embedding-3-large-1)
│  • Self-managed embeddings: VS does NOT auto-embed at query time — caller must embed
│
├─ Step 2a — VS REST API query (high precision path)
│  • POST /api/2.0/vector-search/indexes/{index}/query
│  • filters_json: {"primary_esn": requested_esn}  ← chunk-level attribution, the core v2 fix
│  • num_results: top_k × 3  (over-fetch for post-filter headroom)
│  • Python post-filters:
│    1. outage_start_date >= recency_threshold  (VS REST API rejects nested {"gte": val} filters)
│    2. document_id IN candidate_doc_ids         (enforce is_active=true from Step 1)
│  • Take [:top_k]
│
├─ Step 2b — Fallback VS query (only if len(Step 2a results) < 3)
│  • Targets unattributed chunks (primary_esn = '') from eligible docs
│  • filters_json: {"document_id": candidate_doc_ids}  (VS rejects empty string filter)
│  • Python post-filters: date recency + primary_esn == ''
│  • Merges with Step 2a results (Step 2a ranked first), dedup by chunk_id
│  • Step 2b exists because P1 preprocessor has coverage gaps — some boundary/intro
│    chunks land in unattributed spans (primary_esn = ''). Once P1 emits fallback
│    regions covering all char spans, Step 2b can be removed.
│
└─ Output: top_k ranked chunks with chunk_text + metadata (section_title, equip_type, etc.)

Why the preprocessor matters for retrieval:
- Without fix: multi-ESN docs return mixed Gen+GT chunks labeled with wrong equipment type; LLM gets confused data and risks are wrong
- With fix: each chunk is labeled with its actual equipment type; LLM gets clean equipment-specific data and risks are accurate
```

---

## Metadata Table Schema Changes

Scope note: this section is only for METADATA_TABLE columns and lifecycle.

### Existing Columns (no change)
- equipment_sys_id, equipment_class_code, report_issued_date, outage dates, and related fields

### LEGACY Columns (deprecated)

**Column: esn** (STRING, deprecated)
- Legacy single-ESN compatibility field from current extraction flow.
- No further format evolution is planned.
- Drop esn later once confirmed unused by downstream consumers.

**Column: equipment_type** (STRING, deprecated)
- Legacy doc-level compatibility field from LLM extraction.
- Chunk-level `primary_equip_type` is the retrieval-facing field.
- Drop equipment_type later once confirmed unused by downstream consumers.

**Column: all_esns** (STRING, deprecated)
- Legacy compatibility field only.
- No further format evolution is planned.
- Drop all_esns later once confirmed unused.

### NEW Columns (added for preprocessor integration in METADATA_TABLE)

**preprocessor_regions** (STRING, nullable)
- JSON array of boundaries with per-region metadata.
- Used by chunk attribution logic.

**esn_details** (STRING, nullable)
- Not emitted directly by `preprocessor_v2_final.py`.
- If present, JSON array materialized downstream (P2/retriever) from preprocessor outputs (for example regions + doc-level ESN fields).
- Used as optional retrieval helper during transition.
- Example payload: [{"esn":"338X447","equip_type":"Generator","technology_code":"7FH2","is_primary":true}, ...]

**inactive_esns** (STRING, nullable)
- Comma-separated list or JSON array.
- Used to exclude inactive ESNs from chunk emission and retrieval targeting.

## Chunk Table metadata JSON (compatibility during transition)

Scope note: this section is for CHUNK_TABLE metadata payload compatibility only.

Current state: `fsr_v2_chunk_metadata_v2` schema — assembled in P2 and stored as JSON string in `fsr_chunks_v2.metadata`.
- `doc` block — document-level fields not promoted to first-class chunk columns
- `region` block — ESN/equipment attribution resolved from `preprocessor_regions` char-offset overlap (optional; empty if no region covers the chunk)
- `section` block — section title/path from chunker (optional; populated for `section` and `v1_hierarchical` strategies)
- `chunk_context` block — chunk-only helper fields (e.g. `chunk_start_char`)

Example payload:
```json
{
    "metadata_contract_version": "fsr_v2_chunk_metadata_v2",
    "doc": {
        "title": "Outage report",
        "customer": "site-a",
        "event_type": "Call-Out",
        "outage_start_date": "2026-07-01",
        "outage_end_date": "2026-07-05",
        "inactive_esns": ["ABC123"]
    },
    "region": {
        "primary_esn": "338X447",
        "primary_equip_type": "Generator"
    },
    "section": {
        "section_title": "GENERATOR"
    },
    "chunk_context": {
        "chunk_start_char": 18240
    }
}
```

Contract version is `fsr_v2_chunk_metadata_v2` (see `common/fsr_v2/config.py`).

---

## Future Improvements / Knobs

This section captures candidate knobs for later iterations. These are intentionally non-committal and require validation before adoption.

### TODOs / Known Gaps

- Sub-section header handling: when a lower-level section header indicates a different equipment type but does not include an ESN, first check whether there is exactly one active ESN for that equipment type and tag it; if there are multiple active ESNs, use the higher-level section ESN and match to the correct equipment type using IBAT train mapping.
- ESN extraction + validation: adopt wider ESN candidate extraction (from regex or LLM), then validate against Event SOT and keep only ESNs that exist in Event SOT.
- Cover page + TOC normalization: include cover page and table-of-contents pages in normalization scope, or run a focused LLM judgment step on these smaller page ranges.
- Document summary extraction consistency: keep `document_summary` tied to the same parser-aligned metadata extraction path as other document-level fields, and avoid coupling it to v1 hierarchical chunking behavior so summaries remain consistent across chunking strategies.
- Embedding dimension guardrail: keep tracking `embedding_dimension` in chunk rows and add a run-time validation check that all vectors in a run have the same dimension and match the expected model dimension; log mismatch counts and fail fast when configured.
- Metadata completeness guardrail: when P1 finishes with blank `primary_esn` and/or blank `primary_equip_type`, record an explicit warning status/counter and expose these docs for review before P2 (for example, fail-fast by threshold or mark as completed_with_warnings).

## Per-Chunk ESN Attribution Example (v1 vs v2)

This illustrates how the **MERGE step** in STEP 2 (above) uses `preprocessor_regions` to enable 
per-chunk ESN attribution in v2, replacing the doc-level fan-out in v1.

**Document:** FSR with Gas Turbine (pages 1–12) + Generator (pages 13–22)

**`preprocessor_regions`** stored in `fsr_metadata_v2` (produced by P1):
```json
[
  {"start": 0,     "end": 15000, "metadata": {"primary_esn": "298250",  "primary_equip_type": "Gas Turbine"}},
  {"start": 15000, "end": 28000, "metadata": {"primary_esn": "338X447", "primary_equip_type": "Generator"}}
]
```

**MERGE Algorithm in P2:** During chunking, for each chunk at [chunk_start, chunk_end]:
1. Find best-overlapping region (most overlap wins)
2. Apply region metadata, overriding doc-level metadata
3. Example: chunk at char 20,000 overlaps region [15,000–28,000] → use Generator region metadata

**v1 P2 — fan-out (wrong):** every chunk produces one row per ESN, regardless of content:
```
chunk_id=abc  doc_id=docX          esn=298250  text="combustion liner..."  ← correct
chunk_id=def  doc_id=docX_338X447  esn=338X447 text="combustion liner..."  ← WRONG (GT chunk tagged as Generator)
```

**v2 P2 — region attribution (correct):** each chunk gets one ESN based on which region its char offset falls in:
```
Chunk at char  5,000 → region [0–15,000]    → esn=298250,  equip_type=Gas Turbine
Chunk at char 20,000 → region [15,000–28,000] → esn=338X447, equip_type=Generator
```

`metadata_json` in `fsr_chunks_v2` is **different per chunk**:
```json
// Chunk at char 5,000
{"primary_esn": "298250",  "primary_equip_type": "Gas Turbine", "pdf_name": "...", ...}

// Chunk at char 20,000
{"primary_esn": "338X447", "primary_equip_type": "Generator",   "pdf_name": "...", ...}
```

This is the core v2 fix — ESN attribution is per-chunk by char offset, not a doc-level fan-out.

---

## Two-Phase Implementation Approach (Rollout Plan)

**Phase 1 (Immediate - In Progress):** Metadata UPDATE on existing chunks
- **What:** Run preprocessor on all 458 multi-equipment FSRs.
- **Output:** Page-range accuracy (82.6% to 86.7%+) via page-range scorer and SAGE smoke tests.
- **Deployment:** SQL UPDATE statement on chunk_table metadata fields (for example, primary_equip_type, esn_details, and related retrieval metadata as finalized) with no re-chunking or re-ingestion.
- **Timeline:** Days (reversible, low risk).
- **Reference:** FSR_Retrieval_Fix_Plan.md

**Phase 2 (Long-term - Pipeline Integration):** Preprocessor integrated into production pipeline for new documents
- **What:** Integrate preprocessor into STEP 1, store per-region boundaries, and use char-offset matching in STEP 2.
- **Implementation:** Preprocessor called in P1, per-chunk equipment attribution via char-offset matching in P2 (requires parser alignment).
- **Benefit:** No retrospective fixing needed; forward-going documents are correct by design.
- **Timeline:** Weeks (full pipeline refactor and testing).

### Implementation Delta (Realized During Stage 5, 2026-07-16)

This note is added to preserve traceability between the original shared design and what we learned during implementation.

- Original assumption in this doc:
    - metadata-only updates on existing chunks could be enough for Phase 1
    - parser replacement / re-chunk / re-embed could stay in Phase 2
- What we realized while implementing v2 chunking:
    - per-chunk attribution depends on `preprocessor_regions` char offsets from the P1 text representation
    - if P2 uses a different extraction/chunking representation, chunk-to-region attribution becomes unreliable
    - for v2 correctness, parser-aligned chunking plus embedding is required for the target v2 docs
- Current execution approach:
    - use the new v2 chunking + embedding path for selected v2 docs
    - validate on a bounded SME-reviewed sample first, then ingest only required docs

This is treated as an implementation-time change in sequencing, not a rewrite of the original proposal history.

---

## Refrences

See [fsr-v2-implementation.md](fsr-v2-implementation.md) for:
- implementation comparison
- knobs and behavior details
- layer-by-layer implementation mapping
- expected accuracy and validation criteria
- parser-alignment implementation notes
- reference/code-location mapping

