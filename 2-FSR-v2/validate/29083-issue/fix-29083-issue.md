## Findings

### Evidence

- Preprocessor run output: `2-FSR-v2/validate/29083-issue/preprocessor-run.json`
- `all_esns` includes both ESNs for this document.
- Region metadata emits only one ESN (`primary_esn`), and large spans are not region-attributed.

### Current v2 behavior (important)

1. `all_esns` from preprocessor is not part of the v2 serving path.
2. Document-equipment map rows are built from region metadata (`region.metadata.primary_esn`) only.
3. Chunk `active_esns` is built as:
	- union(region `primary_esn`) + doc-level (`primary_esn`, `gt_esn`, `gen_esn`)
	- normalize + deduplicate
	- subtract `inactive_esns`
	- sort

### Root cause pattern

The pipeline is region-first for attribution, but preprocessor region coverage is not guaranteed to be complete. If a valid ESN appears in uncovered spans, that ESN is effectively invisible to map construction and per-chunk region attribution.

---

## Proposed Uniform Fix (all docs)

Implement a two-part fix that is document-agnostic and does not rely on doc-specific heuristics.

### Fix A: Guarantee 100% region coverage in preprocessor output

After normal region detection is complete, add a normalization pass that:

1. Sorts regions by `start`.
2. Merges overlaps / fixes invalid boundaries.
3. Fills every uncovered gap with a fallback region.

Fallback region metadata should use a consistent strategy:

1. `primary_esn`: doc-level `primary_esn` (if available), else empty.
2. `primary_equip_type`: doc-level `primary_equip_type` (if available), else empty.
3. Optional diagnostic flags (recommended):
	- `attribution_source = "fallback_gap_fill"`
	- `attribution_confidence = "low"`

This guarantees chunk attribution never encounters uncovered spans.

### Fix B: Make map materialization resilient to sparse/empty regions

In Stage 5 map building:

1. Build ESNs from region metadata as today.
2. If region-derived ESN set is empty OR clearly incomplete, union with doc-level ESNs:
	- `primary_esn`, `gt_esn`, `gen_esn`, `st_esn` (if present)
3. Apply `inactive_esns` filter before writing map rows.

This prevents docs from being excluded from readiness/retrieval candidate resolution due to region sparsity.

### Fix C (Alternative or additive): Use preprocessor `all_esns` in v2 active ESN derivation

Update FSR v2 implementation to request and process the `all_esns` field from preprocessor output.

Updated `active_esns` calculation:

1. Collect ESNs found in region-level `primary_esn` across all regions.
2. Add all ESNs from preprocessor document-level `all_esns`.
3. Add document-level ESNs:
	- `primary_esn`
	- `gt_esn`
	- `gen_esn`
4. Normalize all ESNs to uppercase.
5. Remove null, empty, or invalid ESN values.
6. Remove duplicate values.
7. Remove ESNs present in `inactive_esns`.
8. Sort remaining ESNs.
9. Store result in `active_esns` array.

Implementation notes:

1. In P1 metadata processors, include `all_esns` in requested preprocessor fields.
2. In chunking (`_build_active_esns`), union region ESNs + doc ESNs + parsed `all_esns`.
3. Keep existing behavior as fallback when `all_esns` is missing.

---

## Why this works uniformly

1. No assumptions about specific section titles or document templates.
2. Works for single-ESN and multi-ESN reports.
3. Preserves current high-confidence region attribution where available.
4. Uses fallback only for uncovered spans, so behavior is stable and deterministic.

---

## Validation Plan

### Unit-level checks

1. Region output coverage test: total covered chars == full_text length.
2. No invalid regions: `0 <= start < end <= len(full_text)`.
3. No uncovered gaps after normalization pass.

### Pipeline-level checks

1. Re-run P1 for a sample set (single ESN, multi ESN, mixed GT/GEN/ST).
2. Validate map rows contain expected active ESNs for each sample.
3. Re-run P2 and confirm chunk `region_primary_esn` is non-empty for previously uncovered spans.

### Retrieval checks

1. UC1 readiness query returns expected docs for all active ESNs in sample set.
2. UC2 retrieval returns attributed chunks without relying on unattributed fallback path.

---

## Rollout Recommendation

1. Add fix behind a config flag (default off in prod).
2. Run on validation corpus and compare:
	- region coverage
	- map ESN recall
	- retrieval precision/recall
3. Enable in prod once metrics are neutral or improved.


