# FSR v2 Data Quality Test Cases

> Tables in scope: `ds_test_fsr_metadata_v2`, `ds_test_fsr_document_equipment_map_v2`, `ds_test_fsr_chunks_v2`, `ds_test_fsr_vs_index_v2`

---

## Metadata Table (`fsr_metadata_v2`)

### Basic Extraction

- Single-equipment FSR: verify `primary_esn` and `primary_equip_type` are extracted correctly
- Multi-equipment FSR (GT + Generator on same doc): verify both ESNs are captured and the correct one is set as `primary_esn`
- FSR where cover page ESN differs from body ESN — check which ESN wins

### `preprocessor_regions` column

- Multi-equipment FSR: verify `preprocessor_regions` contains non-overlapping char-range boundaries with the correct ESN/equip_type per region
- Single-equipment FSR: verify `preprocessor_regions` is either a single region covering the whole doc or null (no phantom regions)
- FSR where Generator section has no explicit ESN in the header — verify the region is still emitted or correctly falls back

### `inactive_esns` column

- FSR that explicitly marks one ESN as inactive/decommissioned — verify it appears in `inactive_esns` and not in active retrieval fields
- FSR with no inactive ESNs — verify `inactive_esns` is empty/null, not a garbage value


## Equipment Map (`fsr_document_equipment_map_v2`)

- Multi-equipment FSR: verify all rows exist — one per ESN
- ESN that appears in `inactive_esns`: verify `is_active = false` for that row
- Primary ESN: verify `is_primary_esn = true` for the correct row

---

## Chunk Table (`fsr_chunks_v2`)

### Region-based attribution (core v2 fix)

- Multi-equipment FSR chunk that falls within the GT char-offset region — verify `primary_esn` and `primary_equip_type` match the GT region, not the Generator
- Multi-equipment FSR chunk that falls within the Generator char-offset region — verify same for Generator
- Chunk at a region boundary (overlaps both regions) — verify it is attributed to the region with maximum character overlap, not the first one
- Chunk that falls in a gap between two regions — verify it falls back to doc-level `primary_esn`/`primary_equip_type` and `primary_esn` is empty or a known fallback value

### Merge priority

- Chunk where region, doc-level, and upload metadata all have `primary_equip_type` — verify region value wins
- Chunk with no region match but with doc-level equip_type — verify doc-level value is used
- Chunk where LLM and preprocessor both set `primary_esn` differently — verify preprocessor value wins

### `metadata` JSON column

- Verify the `doc` block contains doc-level fields shared across all chunks of the same document
- Verify the `region` block contains only the chunk's attributed `primary_esn` and `primary_equip_type`, not the doc-level ESN when they differ
- Verify the `section` block is populated for hierarchical/section chunking strategies
- Verify `chunk_context.chunk_start_char` is present and matches the actual character offset of that chunk in the source text
- Multi-equipment doc: verify that chunks from different regions have different `region` blocks within the same document's chunk rows


