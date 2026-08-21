# FSR v2 Retrieval: Current URA Algorithm

This note describes how the URA application currently retrieves FSR data. It
uses two separate paths: SQL for document readiness/listing and hybrid vector
search for evidence retrieval.

## Use Cases

1. **Data Readiness API** — `GET /dataservices/api/v1/equipment/{esn}`
	 Return all eligible FSR documents for an ESN, whether the ESN is primary or
	 secondary in the document.

2. **FSR Retrieval API** — `POST /retrieve`
	 Return the most relevant FSR chunks for an ESN and query text, subject to
	 the configured recency window.

## Code References

- URA retrieval service: [retriever_service.py](../../../uai3071390-genai-services-demand-generation-usecase/backend/services/data-service/src/data_service/services/retriever_service.py)
	- `_retrieve_multi_esn_document()` — v2 eligibility lookup.
	- `_retrieve_timeboxed_document()` — legacy index fallback lookup.
	- `retrieve_issue_data()` — index selection, embedding lookup, and hybrid
		vector search request.
- URA Data Readiness/report service: [equipment_service.py](../../../uai3071390-genai-services-demand-generation-usecase/backend/services/data-service/src/data_service/services/equipment_service.py)
	- v2 FSR report listing and report-count queries.
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

The application uses SQL only; vector search is not involved.

### Steps

1. Look up the requested ESN in the v2 document-to-equipment mapping table.
2. Join matching documents to the v2 metadata table.
3. Keep only active ESN mappings and documents with completed metadata and
	 chunk processing.
4. Apply the configured lookback window to `outage_start_date`.
5. Return the document metadata ordered by `report_issued_date` descending.

The same eligibility query is used to count available FSR reports for the
readiness view.

### Query

```sql
SELECT
		meta.title,
		meta.event_type,
		meta.ev_project_id,
		meta.ev_equipment_event_id,
		meta.pdf_name,
		meta.volume_path,
		meta.fsr_number,
		meta.report_issued_date,
		meta.outage_start_date,
		meta.outage_end_date,
		meta.document_summary,
		meta.primary_equip_sys_id AS equipment_sys_id
FROM fsr_document_equipment_map_v2 AS d
INNER JOIN fsr_metadata_v2 AS meta
		ON d.document_id = meta.document_id
WHERE UPPER(d.esn) = UPPER(:esn)
	AND d.is_active = true
	AND meta.metadata_status = 'completed'
	AND meta.chunk_status = 'completed'
	  AND meta.outage_start_date >= DATE_FORMAT(
		  ADD_MONTHS(CURRENT_DATE(), -120), 'yyyy-MM-dd'
	  )
ORDER BY meta.report_issued_date DESC;
```

`is_primary_esn` is not used as a filter here. The mapping table includes both
primary and secondary ESNs, which is what allows the readiness response to
return every FSR associated with the requested equipment.

## 2. FSR Retrieval

The main implementation is in [retriever_service.py](../../../uai3071390-genai-services-demand-generation-usecase/backend/services/data-service/src/data_service/services/retriever_service.py).

The request contains an ESN and one or more issue query texts. Each query is
embedded and sent to Databricks Vector Search using hybrid search.

### Steps

1. **Check v2 eligibility.** Query the multi-ESN mapping table joined to v2
	 metadata and collect eligible `document_id` values for the ESN.
2. **Select the index.**
	 - If v2 documents are found, use the v2 multi-ESN index.
	 - If no v2 documents are found, query the legacy/timeboxed index instead.
	 - If neither path returns eligible documents, skip vector search and return
		 no evidence.
3. **Get the query embedding.** The application reads the stored embedding for
	 the issue prompt from the configured embedding table.
4. **Run hybrid search** with the query text, query embedding, ESN/document
	 filters, and `top_k`.
5. **Return the ranked chunks** and their evidence, document name, page number,
	 report date, and similarity score for each issue.

The index fallback is based on whether eligible documents exist in the v2
mapping table. A zero-hit response from the v2 vector index does **not** cause
the application to issue a second vector-search request against the legacy
index.

### Step 1: v2 eligibility query

```sql
SELECT DISTINCT d.document_id
FROM fsr_document_equipment_map_v2 AS d
INNER JOIN fsr_metadata_v2 AS meta
		ON d.document_id = meta.document_id
WHERE UPPER(d.esn) = UPPER(:esn)
	AND d.is_active = true
	AND meta.chunk_status = 'completed'
	  AND meta.outage_start_date >= DATE_FORMAT(
		  ADD_MONTHS(CURRENT_DATE(), -120), 'yyyy-MM-dd'
	  );
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
		  ADD_MONTHS(CURRENT_DATE(), -120), 'yyyy-MM-dd'
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
