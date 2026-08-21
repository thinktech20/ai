# URA FSR v2 Retriever Changes Needed

## Problem

The current URA v2 retrieval filter is:

```json
{
	"region_primary_esn": "<requested_esn>",
	"document_id": ["<eligible_doc_id_1>", "<eligible_doc_id_2>"]
}
```

This excludes regions where:

```text
region_primary_esn = ""
region_primary_equip_type = "shared"
```

Shared regions can contain common evidence such as summaries, findings, and
equipment-wide context. They should be available when retrieving FSR content
for any ESN associated with the eligible document.

## Required Retrieval Behavior

For the v2 index, retrieve chunks that satisfy:

```text
document_id IN eligible_document_ids
AND (
		region_primary_esn = requested_esn
		OR region_primary_equip_type = "shared"
)
```

The `document_id` restriction is required. Shared regions must only be
included from documents that the v2 eligibility query has already confirmed
for the requested ESN. Do not retrieve all shared regions across the index.

## Current Retrieval Flow

1. Query `fsr_document_equipment_map_v2` joined with `fsr_metadata_v2`.
2. Keep active mappings, completed chunks, and documents inside the configured
	 recency window.
3. Collect the eligible `document_id` values.
4. If v2 documents exist, query the v2 multi-ESN index using the ESN-specific
	 plus shared-region filter described above.
5. If no v2 documents exist, preserve the current fallback to the legacy
	 timeboxed index using its existing `esn` filter.
6. Return the merged, de-duplicated, similarity-ranked results limited to
	 `top_k`.

Data Readiness does not need a change. Its mapping-table query already returns
documents where the requested ESN is primary or secondary.

## Implementation Options

### Option A: One Vector Search Request

Use the Databricks Vector Search REST filter syntax for an OR expression:

```json
{
	"document_id": ["<eligible_doc_id_1>", "<eligible_doc_id_2>"],
	"or": [
		{"region_primary_esn": "<requested_esn>"},
		{"region_primary_equip_type": "shared"}
	]
}
```

Validate the exact OR syntax against the target Vector Search endpoint before
shipping. The current code uses simple equality and list filters only.

### Option B: Two Vector Search Requests

If the REST API does not support the required OR syntax:

1. Search eligible documents with `region_primary_esn = requested_esn`.
2. Search the same eligible documents with
	 `region_primary_equip_type = "shared"`.
3. Merge both result sets by `chunk_id`.
4. Sort the combined results by similarity score.
5. Return only `top_k` results.

The two-request approach is more explicit and avoids relying on unsupported
compound-filter behavior. It may require over-fetching from each search so
that shared chunks are not lost before the final ranking step.

## Code Changes

In `retriever_service.py`:

- Add `region_primary_equip_type` to the v2 search columns.
- Replace the current ESN-only v2 filter with the ESN-or-shared filter, or
	implement the two-request merge path.
- Keep the legacy index filter unchanged.
- Preserve the existing v2 document eligibility gate and recency filtering.
- Keep shared-region handling limited to the v2 index.

The v2 result columns should include at least:

```python
[
		"chunk_id",
		"pdf_name",
		"page_number",
		"chunk_text",
		"region_primary_esn",
		"region_primary_equip_type",
]
```

## Tests Needed

Add or update retriever tests to verify:

- ESN-attributed and shared chunks are both eligible for a v2 request.
- Shared chunks from documents outside the eligibility result are excluded.
- Duplicate chunks are removed when combining ESN and shared searches.
- The final response is limited to `top_k` and ranked by similarity.
- A v2 request with no eligible documents still uses the legacy fallback.
- The legacy path continues to use the existing `esn` filter.
- The v2 response includes `region_primary_equip_type` for downstream
	attribution and debugging.

## Acceptance Criteria

- A request for an ESN returns relevant chunks attributed to that ESN.
- The same request can also return relevant `shared` chunks from the ESN's
	eligible FSR documents.
- Unrelated shared chunks are not returned.
- Existing Data Readiness behavior and legacy-index fallback behavior remain
	unchanged.
