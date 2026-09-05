# Query ER Tool Spec Outline

**REST Tool:** `query_er`
**Spec Owner:** DS team -> **Impl Owner:** DEV team

## Summary

The Query ER tool performs hybrid retrieval (semantic + keyword) over pre-chunked ER (Engineering Record) text stored in a Databricks Vector Search index.

The current `er_vs.py` runtime path now normalizes returned rows to the same core response contract used by the original `er.py` helper, while still preserving Databricks-native traceability fields where available.

ER embeddings are self-managed. They are generated during ingestion with an Azure OpenAI embedding deployment routed through LiteLLM, written into the Delta table that backs the Vector Search index, and indexed by Databricks Vector Search. The tool does not rely on a built-in Databricks embedding model for ER retrieval.

At query time the public API accepts only the user query text plus retrieval parameters. The tool calculates the `query_vector` internally with the same self-managed Azure OpenAI embedding model used during ingestion, then calls the Databricks Vector Search REST query endpoint with both `query_text` and `query_vector`.

The tool is exposed as a REST endpoint only. No MCP endpoint is required under the current architecture decision.

## Implementation References

- SharePoint code package: `<add SharePoint code zip URL>`
- Experimental validation package: `REChainExperiment` (`er_vs.py`, `vector_embeddings.py`)
- Current experiment ER index: `main.gp_services_sdg_poc.vs_engineering_report_chunk_litellm`

## Data Sources

### Raw ER source

- Source view: `vgpp.qlt_std_views.u_pac`
- ER ingestion is expected to chunk and embed the main ER text fields per case. Candidate source fields include:
  - `close_notes`
  - `comments`
  - `comments_and_work_notes`
  - `description_`
  - `short_description`
  - `u_desired_deliverable`
  - `u_resolve_notes`

### Vector Search table / index

- Production target Delta table: to be confirmed
- Production target Vector Search index: to be confirmed
- Current experiment ER index: `main.gp_services_sdg_poc.vs_engineering_report_chunk_litellm`
- Retrieval endpoint pattern: `/api/2.0/vector-search/indexes/{index_name}/query`
- Embedding model: self-managed Azure OpenAI embedding deployment via LiteLLM (current runtime default: `azure-text-embedding-3-large-1`, 3072-dim)
- Embedding persistence:
  - document embeddings are calculated during ingestion
  - document embeddings are stored in the Delta table backing the index
  - query embeddings are calculated by the tool during retrieval

### Current runtime response fields

| Column | Type | Notes |
| --- | --- | --- |
| `er_number` | STRING | Normalized ER identifier exposed by the runtime contract |
| `serial_number` | STRING | Equipment serial filter key |
| `opened_at` | STRING / TIMESTAMP | ER open timestamp if present in the index |
| `status` | STRING | ER status |
| `u_component` | STRING | ER component metadata |
| `u_field_action_taken` | STRING | ER field action metadata |
| `equipment_id` | STRING | Equipment identifier if present in the index |
| `chunk_text` | STRING | Retrieved ER chunk text |
| `chunk_index` | INTEGER | Parsed chunk ordinal when recoverable from `chunk_id` |
| `score` | FLOAT | Databricks Vector Search relevance score |
| `chunk_id` | STRING | Databricks-native chunk identifier preserved for traceability |
| `er_case_number` | STRING | Databricks-native ER case identifier preserved for traceability |
| `embedding` | ARRAY<FLOAT> | Stored in the backing Delta table and used by Vector Search. Not returned to callers. |

## Inputs

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `serial_number` | string | Yes | - | Equipment serial number used to scope ER retrieval |
| `query` | string | Yes | - | Natural-language search query |
| `k` | integer | Yes | - | Number of top results to return |
| `query_type` | string | No | `HYBRID` | Retrieval mode. Current runtime supports `HYBRID` and `ANN`. Public API may keep this fixed to `HYBRID`. |

> The public API does not accept `query_vector`. Callers provide `query` text only. The service computes the vector internally.

## Input Validation

| Condition | Error |
| --- | --- |
| `serial_number` is empty or missing | `400 Bad Request` - "serial_number is required" |
| `query` is empty or missing | `400 Bad Request` - "query is required" |
| `k` is missing or <= 0 | `400 Bad Request` - "k must be a positive integer" |

## Retrieval Pipeline

### Step 1 - Serial-scoped candidate set

Filter the Vector Search query to only include records matching the provided `serial_number`.

### Step 2 - Generate query vector internally

Embed the request `query` with the configured self-managed Azure OpenAI embedding model. This uses the same embedding family used during ingestion.

### Step 3 - Query Databricks Vector Search

Call the Databricks Vector Search REST endpoint with:

- `query_text`
- `query_vector`
- `num_results`
- `query_type`
- `filters_json = {"serial_number": serial_number}`
- the selected return columns

For `HYBRID` retrieval, Databricks combines:

- dense retrieval against the supplied `query_vector`
- keyword retrieval against the supplied `query_text`

### Step 4 - Return ER chunk results

Return the ER chunks and selected metadata columns from the Vector Search response.

The current runtime adapter in `er_vs.py` converts the raw Vector Search row into the normalized ER retrieval shape expected by downstream callers:

- `er_number`
- `serial_number`
- `opened_at`
- `status`
- `u_component`
- `u_field_action_taken`
- `equipment_id`
- `chunk_text`
- `chunk_index`
- `score`

It also preserves `chunk_id` and `er_case_number` for traceability.

> Optional reranking can be added later if DS and DEV decide it is needed. The current runtime path in `er_vs.py` queries the Vector Search endpoint directly and returns the resulting rows.

## Sample Query Code (Service Internal)

External callers to `query_er` submit only `serial_number`, `query`, and `k`. The service generates `query_vector` internally before calling Vector Search.

```python
import json
import requests

from your_service.vector_embeddings import get_query_vector

serial_number = "290T658"
query_text = "Generator overheating with field action history"
k = 10
query_type = "HYBRID"

query_vector = get_query_vector(query_text)

response = requests.post(
    "https://<workspace-host>/api/2.0/vector-search/indexes/main.gp_services_sdg_poc.vs_engineering_report_chunk_litellm/query",
    headers={
        "Authorization": "Bearer <databricks-token>",
        "Content-Type": "application/json",
    },
    json={
        "query_text": query_text,
        "query_vector": query_vector,
        "columns": [
            "chunk_id",
            "er_case_number",
            "chunk_text",
            "serial_number",
            "opened_at",
            "status",
            "u_component",
            "u_field_action_taken",
            "equipment_id",
        ],
        "num_results": k,
        "query_type": query_type,
        "filters_json": json.dumps({"serial_number": serial_number}),
    },
    timeout=60,
)

response.raise_for_status()
results = response.json()
```

## Expected Output

### Response structure

```json
{
  "results": [
    {
      "er_number": "ER_202446",
      "chunk_index": 3,
      "score": 0.8421,
      "chunk_id": "ER_202446:3",
      "er_case_number": "202446",
      "chunk_text": "Field team observed elevated vibration and documented corrective action...",
      "serial_number": "290T658",
      "opened_at": "2024-09-17T04:00:00Z",
      "status": "Closed",
      "u_component": "Rotor",
      "u_field_action_taken": "Inspection and repair",
      "equipment_id": "EQ-12345"
    }
  ],
  "metadata": {
    "serial_number": "290T658",
    "query": "Generator overheating with field action history",
    "k": 10,
    "query_type": "HYBRID",
    "result_count": 1,
    "duration_ms": 420
  }
}
```

### Output rules

- Blank or null values are returned as `null`
- Literal `"n/a"` remains `"n/a"`
- The response returns the Vector Search result columns listed above, not the raw full `u_pac` row by default

## Raw Source Column Schema (Reference)

The following source columns are relevant to ER ingestion and possible downstream enrichment:

- `number`
- `close_notes`
- `comments`
- `comments_and_work_notes`
- `description_`
- `short_description`
- `u_desired_deliverable`
- `u_component`
- `u_field_action_taken`
- `u_resolve_notes`
- `u_serial_number`
- `u_status`
- `equipment_type`
- `technology_group`
- `technology`
- `component`
- `issue_name`
- `issue_prompt`
- `severity_criteria_0`
- `severity_criteria_1`

Not every raw source column is returned by the current Vector Search retrieval response.

## Current Experiment vs Production Spec

1. **Service shape:** the current repository contains notebook and helper-module code, not a deployed `query_er` REST service.
2. **Embedding model:** the runtime uses self-managed Azure OpenAI embeddings via LiteLLM, not a built-in Databricks embedding model.
3. **Embedding lifecycle:** document embeddings are calculated during ingestion and stored in the Delta table backing the ER Vector Search index.
4. **Query-time behavior:** the tool calculates `query_vector` internally from `query` text and passes both values to the Databricks Vector Search query endpoint.
5. **Index naming:** the current experiment default is `main.gp_services_sdg_poc.vs_engineering_report_chunk_litellm`.
6. **Response contract alignment:** current runtime retrieval in `er_vs.py` now maps Vector Search rows into the same core response shape used by `er.py`, with `chunk_id` and `er_case_number` retained as additional traceability fields.
7. **Reranking:** current runtime retrieval in `er_vs.py` does not apply a separate reranker after the Vector Search call.

## Endpoint

| Endpoint Type | Purpose | Consumer |
| --- | --- | --- |
| REST API | Service-to-service and agent-invoked ER retrieval | Assistants and backend services |

No MCP endpoint is required for this tool under the current architecture decision.

DEV team determines the final URL path, HTTP method (recommended: `POST`), and authentication mechanism.

## Query Logging

Every `query_er` call should log:

| Field | Description |
| --- | --- |
| Timestamp | ISO 8601 request time |
| User | Authenticated identity or calling service name |
| Serial number | `serial_number` provided in the request |
| Query | Search query text |
| k | Requested result count |
| Query type | `HYBRID` or `ANN` if exposed |
| Result count | Actual results returned |
| Duration (ms) | End-to-end latency |
| Errors | Error message on failure, `null` on success |

## Error Responses

| Status | Condition | Body |
| --- | --- | --- |
| `400` | Validation failure | `{ "error": "<message>" }` |
| `404` | No ER chunks found for the serial or filter set | `{ "error": "No ER chunks found for serial {serial_number}", "result_count": 0 }` |
| `500` | Internal retrieval failure | `{ "error": "Internal server error", "detail": "<message>" }` |
| `503` | Vector Search endpoint unavailable | `{ "error": "Vector Search service temporarily unavailable" }` |

## Recent Alignment Update

- `er_vs.py` was updated to align its returned row shape with the original `er.py` interface used by downstream callers.
- The normalized runtime contract now exposes `er_number`, `chunk_text`, `chunk_index`, and `score` directly, while preserving Databricks-native `chunk_id` and `er_case_number` for traceability.
- No change was made to the public retrieval inputs documented here: the Vector Search path still takes `serial_number`, `query`, `k`, and optional `query_type`.

## Acceptance Criteria

- [ ] Tool spec defines inputs and expected output
- [ ] Tool is callable via REST endpoint
- [ ] `serial_number` is mandatory; requests without it return `400`
- [ ] `query` is mandatory; requests without it return `400`
- [ ] `k` is mandatory; requests without it return `400`
- [ ] ER document embeddings are calculated during ingestion with the self-managed Azure OpenAI embedding model
- [ ] ER document embeddings are stored in the Delta table backing the Vector Search index
- [ ] The tool calculates `query_vector` internally at request time
- [ ] The Databricks Vector Search request includes both `query_text` and `query_vector`
- [ ] Serial filtering uses `serial_number`
- [ ] Response returns ER chunk rows and metadata from the Vector Search result set
- [ ] Query logs capture timestamp, user, serial number, query, k, result count, duration, and errors

