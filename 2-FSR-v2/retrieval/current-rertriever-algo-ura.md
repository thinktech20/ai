# FSR v2 Retrieval: Current URA Algorithm

This note describes how the URA application currently retrieves FSR data. It
uses two separate paths: SQL for document readiness/listing and hybrid vector
search for evidence retrieval.

## Use Cases

1. **Data Readiness API** — `GET /dataservices/api/v1/equipment/{esn}/data-readiness`
	 Return FSR availability and a report count, alongside other source-readiness
	 results. It does not return report metadata.

2. **FSR Report Listing API** — `GET /dataservices/api/v1/equipment/{esn}/fsr-reports`
	 Return a paginated list of FSR metadata for an ESN.

3. **FSR Retrieval API** — `POST /dataservices/api/v1/retriever/retrieve`
	 Return the most relevant FSR chunks for an ESN and query text, subject to
	 the active retrieval-routing configuration.

## Code References

- URA retrieval service: [retriever_service.py](../../../uai3071390-genai-services-demand-generation-usecase/backend/services/data-service/src/data_service/services/retriever_service.py)
	- `_retrieve_multi_esn_document()` — v2 eligibility lookup.
	- `_retrieve_timeboxed_document()` — legacy index fallback lookup.
	- `retrieve_issue_data()` — index selection, embedding lookup, and hybrid
		vector search request.
- URA Data Readiness/report service: [equipment_service.py](../../../uai3071390-genai-services-demand-generation-usecase/backend/services/data-service/src/data_service/services/equipment_service.py)
	- v2 FSR report listing and report-count queries.
	- Legacy listing and report-count fallback queries.
- URA equipment routes: [equipment.py](../../../uai3071390-genai-services-demand-generation-usecase/backend/services/data-service/src/data_service/routes/equipment.py)
	- `data-readiness` returns source availability counts.
	- `fsr-reports` returns the paginated report metadata list.
- v2 vector-index definition: [vector_index.py](../../pw_sdg_ai_ser_repo/vs/src/etl/fsr_v2/vector_index.py)
	- `columns_to_sync` for `fsr_vs_index_v2`.
- v2 index creation DDL: [nb_sdg_fsr_v2_ddl.py](../../pw_sdg_ai_ser_repo/ddls/fsr_v2/nb_sdg_fsr_v2_ddl.py)
	- Index creation payload and synced columns.
- v2 retrieval validation notebook: [nb_fsr_v2_retrieval.py](../../pw_sdg_ai_ser_repo/validation/fsr_v2/nb_fsr_v2_retrieval.py)
	- Reference Vector Search columns and retrieval filters.
- v2 chunk-table schema: [config.py](../../pw_sdg_ai_ser_repo/common/fsr_v2/config.py)
	- Definitions for `region_primary_esn` and
		`region_primary_equip_type`.

## 1. Data Readiness

The application uses SQL only; Vector Search is not involved. Data readiness
returns the count of eligible FSR reports, not a list of documents.

### Steps

1. Determine whether FSR is enabled for the equipment's workflow configuration.
	 If it is not enabled, readiness returns an FSR count of zero.
2. If `FSR_MULTI_ESN_APPLIED` is enabled, count matching v2 mapping/metadata
	 rows first.
3. Keep only active ESN mappings and documents with completed metadata and
	 chunk processing.
4. Apply the `outage_start_date` lookback only when `FSR_LOOKBACK_SET` is
	 enabled. The number of months is `FSR_LOOKBACK_MONTHS` (default: 120).
5. If the v2 count is zero, use the legacy chunks-to-metadata query instead.

The report-list endpoint applies the same v2 readiness predicates, groups by
document, orders by `report_issued_date` descending, and paginates. The count
and list are separate SQL queries. Both use the legacy fallback when the v2
path produces no matches.

### v2 Query Shape

```sql
SELECT
		COUNT(DISTINCT meta.document_id) AS cnt
FROM fsr_document_equipment_map_v2 AS d
INNER JOIN fsr_metadata_v2 AS meta
		ON d.document_id = meta.document_id
WHERE UPPER(d.esn) = UPPER(:esn)
	AND d.is_active = true
	AND meta.metadata_status = 'completed'
	AND meta.chunk_status = 'completed'
	[AND meta.outage_start_date >= DATE_FORMAT(
		ADD_MONTHS(CURRENT_DATE(), -FSR_LOOKBACK_MONTHS), 'yyyy-MM-dd'
	)] -- only when FSR_LOOKBACK_SET is enabled
```

`is_primary_esn` is not used as a v2 filter. Thus a successful v2 mapping
lookup includes both primary and secondary ESNs. This is conditional: if the
multi-ESN path is disabled or has no matches, the legacy fallback additionally
filters legacy metadata by its `esn` field and does not provide the same
secondary-ESN guarantee.

`from_date` and `to_date` supplied to data readiness or `fsr-reports` are not
applied by the v2 queries. They are applied only by the legacy fallback.

## 2. FSR Retrieval

The main implementation is in [retriever_service.py](../../../uai3071390-genai-services-demand-generation-usecase/backend/services/data-service/src/data_service/services/retriever_service.py).

The request contains an ESN and one or more issue query texts. Each query is
embedded and sent to Databricks Vector Search using hybrid search.

### Steps

1. **Choose the document filter and index.**
	- Explicit `document_ids` bypass SQL eligibility and use the v2 index only
		when `FSR_MULTI_ESN_APPLIED` is enabled.
	- When `FSR_LOOKBACK_SET` and `FSR_MULTI_ESN_APPLIED` are both enabled, query
		the v2 mapping/metadata tables for eligible document IDs.
	- If that v2 query has no documents, query the legacy/timeboxed tables and
		use the legacy index.
	- When `FSR_LOOKBACK_SET` is disabled, use the legacy index with an ESN-only
		filter; no SQL document-eligibility lookup occurs.
	- If a required eligibility query returns no documents, skip Vector Search
		and return no evidence.
2. **Get the query embedding.** Standard callers read stored issue-prompt
	 embeddings from the configured embedding table. Calls from `qna-agent`
	 generate a fresh embedding for each prompt.
3. **Run hybrid search** with the query text, query embedding, ESN/document
	 filters, and `top_k`.
4. **Return the ranked chunks** and their evidence, document name, page number,
	 report date, and similarity score for each issue.

When the lookback and multi-ESN flags are enabled, index fallback is based on
whether eligible documents exist in the v2 mapping table. A zero-hit response
from the v2 vector index does **not** cause the application to issue a second
vector-search request against the legacy index.

### Step 1: v2 eligibility query

```sql
SELECT DISTINCT d.document_id
FROM fsr_document_equipment_map_v2 AS d
INNER JOIN fsr_metadata_v2 AS meta
		ON d.document_id = meta.document_id
WHERE UPPER(d.esn) = UPPER(:esn)
	AND d.is_active = true
	AND meta.metadata_status = 'completed'
	AND meta.chunk_status = 'completed'
	[AND meta.outage_start_date >= DATE_FORMAT(
		ADD_MONTHS(CURRENT_DATE(), -FSR_LOOKBACK_MONTHS), 'yyyy-MM-dd'
	)]; -- only when FSR_LOOKBACK_SET is enabled
```

The legacy fallback uses the older chunk-to-document relationship:

```sql
SELECT DISTINCT c.document_id
FROM fsr_metadata AS meta
INNER JOIN (
		SELECT DISTINCT document_id
		FROM fsr_chunks
		WHERE esn = :esn
) AS c
		ON meta.document_id = c.document_id
WHERE meta.document_id IS NOT NULL
	  AND meta.outage_start_date >= DATE_FORMAT(
		  ADD_MONTHS(CURRENT_DATE(), -FSR_LOOKBACK_MONTHS), 'yyyy-MM-dd'
	  );
```

### Step 2: current vector-search filters

For a v2 match, URA queries the multi-ESN index and filters at chunk level:

```json
{
	"region_primary_esn": "<requested_esn>",
	"document_id": ["<eligible_doc_id_1>", "<eligible_doc_id_2>"]
}
```

For the legacy fallback, it queries the configured old index:

```json
{
	"esn": "<requested_esn>",
	"document_id": ["<eligible_doc_id_1>", "<eligible_doc_id_2>"]
}
```

The request is sent as a Databricks Vector Search `HYBRID` query with:

```json
{
	"query_text": "<issue_query>",
	"query_vector": "<stored_issue_prompt_embedding>",
	"filters_json": "<one_of_the_filters_above>",
	"num_results": "<top_k>",
	"query_type": "HYBRID"
}
```

The v2 filter uses `region_primary_esn`, the chunk-level attribution produced
by the FSR v2 pipeline. This prevents a multi-equipment document from returning
chunks belonging to another equipment section. The legacy filter uses the old
`esn` field because it queries the old index.

### Current deduplication and ranking

After Vector Search returns results for an issue, the application formats the
rows in the order returned by the service.

- Deduplication key: `chunk_id`.
- Duplicate handling: keep the first occurrence returned by Vector Search and
  discard later rows with the same `chunk_id`.
- Processing limit: process at most the first 10 returned rows.
- Ranking: preserve the Vector Search ranking order; the application does not
  re-rank results or select the duplicate with the highest similarity score.
- Final output: return the de-duplicated rows that remain after this pass.

The current implementation makes one Vector Search request per issue and does
not merge ESN-specific and shared-region result sets. It also does not
overfetch candidates before deduplication, so duplicate removal can reduce the
number of returned rows below the requested `top_k`.

## Current Boundaries

- The app-side implementation does not perform the archived Step 2b fallback
	for chunks with empty `primary_esn`.
- The v2-to-legacy fallback is document-availability routing, not a merge of
	results from both indexes.
- The current v2 filter is ESN-only; shared-region inclusion is proposed in
	`2-FSR-v2/retrieval/retriver-changes-needed.md` and is not yet implemented.
- Query embeddings must match the embedding model used by the selected index.
- SQL values such as `esn` are passed as parameters in the retrieval service.
- The readiness/report-list service escapes ESN values with `sql_literal`
	 rather than using a bound SQL parameter.
