# Retrieval-Friendly ESN Schema Design (FSR v2)

## Purpose
Define a retrieval schema that supports:
1. Search by any ESN in a document (not only chunk primary_esn).
2. Accurate ESN-to-equipment-type mapping for the selected ESN.
3. Access to associated ESNs across other equipment types in the same document.
4. A single source of truth for attribution, with a stable serving contract for retrieval.

## Current Context
- In v2, chunk primary_esn is chunk-level and can vary by chunk.
- Region attribution in P2 is driven by P1 preprocessor_regions.
- preprocessor_regions is currently the best canonical source for per-region equipment attribution.

## Design Principles
1. One canonical source of truth for equipment attribution.
2. One serving contract for retrieval/index, optimized for filterability.
3. Keep canonical and serving layers separate so future schema growth is safe.
4. Avoid relying on nested/array filter behavior as the primary index contract.

## Logical Keys
Use the following logical keys across layers:
- metadata_table (fsr_metadata_v2): document_id
- chunk_table (fsr_chunks_v2): chunk_id
   - chunk_id derivation: md5(document_id + "_" + chunk_index)
- document_equipment_map: (document_id, esn)

Note:
- These are logical keys used by pipeline MERGE and retrieval contracts.
- Enforced physical PK constraints may vary by platform/runtime configuration.

## Recommended Two-Layer Model

### Layer A: Canonical Attribution (Silver)
Canonical source of truth stays in metadata table via preprocessor_regions.

Canonical fields:
- document_id
- preprocessor_regions (JSON array of regions with metadata)
- inactive_esns
- doc-level anchors: primary_esn, primary_equip_type, gt_esn, gen_esn

Notes:
- gt_esn/gen_esn are doc-level anchors (non-exhaustive if multiple ESNs per type).
- Full attribution fidelity comes from preprocessor_regions, not anchor fields.

### Layer B: Retrieval Serving Model (Gold/Helper)
Materialize a retrieval helper from canonical data.

Table: document_equipment_map (one row per document_id + esn)

Materialization timing and write rule:
- Build in P1 after preprocessor regions are extracted and merged into metadata.
- Write only real attribution rows (no placeholder or speculative rows).
- Re-materialize idempotently on re-ingestion for the same document_id.

Suggested columns:
- document_id STRING
- esn STRING
- equip_type STRING
- technology_code STRING
- is_active BOOLEAN
- is_primary_esn BOOLEAN
- source_region_count INT

Why this shape:
- Supports search by any ESN.
- Gives exact mapping for selected ESN.
- Lets app fetch associated ESNs in same document quickly.

## Chunk Table Serving Contract
Chunk table remains retrieval execution layer for semantic ranking.

Top-level chunk columns to keep for filters:
- primary_esn
- primary_equip_type
- document_id
- pdf_name
- report_date

Add one normalized scalar field for any-ESN lookup:
- all_esns_search STRING

all_esns_search behavior:
- Derived from active ESNs for the document.
- Same value repeated across chunks for that document.
- Used only as retrieval pre-filter for any-ESN queries.

Optional metadata JSON keys (compatibility only):
- esn_details
- gt_esn / gen_esn anchors

Important:
- Do not make metadata JSON the primary filter contract.
- Use top-level scalar fields for predictable index filtering.

## Retrieval Flow (Any ESN + Associated ESNs)

### Step 1: Resolve selected ESN to document and mapping
1. Query document_equipment_map where esn = selected_esn and is_active = true.
2. Join/filter by document chunk readiness (chunk status = completed).
3. Return:
   - candidate document_ids
   - selected_esn -> equip_type mapping

### Step 2: Get associated ESNs per candidate document
1. Query document_equipment_map by candidate document_ids.
2. Build associated_esns list grouped by equip_type.

### Step 3: Run vector retrieval on chunk table
1. Filter chunk retrieval by:
   - document_id in candidate set, and
   - optionally primary_equip_type = selected_esn_equip_type for precision pass.
2. Apply semantic ranking.

### Step 4: Return enriched retrieval context
Return chunk results with:
- selected_esn mapping
- associated ESNs across other equipment types
- per-chunk primary attribution

## Why This Solves the Problem
1. Any-ESN search works even when selected ESN is not chunk primary_esn in all relevant chunks.
2. Mapping accuracy comes from canonical attribution materialized in helper table.
3. Associated ESNs are deterministic from helper, not inferred from sparse chunk results.
4. Extensible to future equipment types without adding type-specific schema columns.

## Extensibility for Future Equipment Types
Avoid hardcoding only GT/Generator logic in serving contracts.

Use entity-style mapping records:
- esn
- equip_type
- technology_code
- active/status flags

This supports:
- additional equipment types
- multiple ESNs per equipment type
- richer retrieval facets without table redesign.

## Indexing Guidance

Recommended vector-index columns to sync:
- chunk_id
- chunk_index
- document_id
- pdf_name
- page_number
- chunk_text
- primary_esn
- primary_equip_type
- report_date
- all_esns_search
- metadata

Array guidance:
- Treat ARRAY<STRING> filters as optional optimization only.
- Do not rely on array filter support as the core retrieval contract unless validated end-to-end in target runtime.

## Normalization Rules
Apply to all ESN-carrying fields in serving layer:
1. Uppercase.
2. Trim whitespace.
3. De-duplicate.
4. Exclude inactive ESNs from active search sets.
5. Use deterministic ordering when serialized.

## Migration Plan
1. Keep current retrieval path working.
2. Introduce document_equipment_map build from preprocessor_regions in P1 (real rows only).
3. Add all_esns_search to chunk serving path.
4. Add readiness gating in retrieval candidate resolution (chunk status = completed).
5. Switch app any-ESN lookup to helper-first flow.
6. Keep metadata JSON compatibility fields during transition.

## Decision Summary
Recommended source of truth:
- preprocessor_regions (canonical)

Recommended retrieval contract:
- document_equipment_map for ESN resolution and associated ESNs
- chunk table for semantic retrieval with scalar top-level filters
- retrieval readiness gate: only documents with chunk status = completed are candidate documents

This gives correctness now and scales for future multi-equipment growth.
