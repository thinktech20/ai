# Metadata-First FSR Architecture for Monday Discussion

> Status: discussion draft for Monday architect review  
> Scope: metadata architecture as the primary design, with chunking and embedding defined only at workflow level  
> Non-goal: this document does not lock the final chunking algorithm

---

## Recommendation Summary

The right production architecture is a metadata-first, two-step pipeline:

1. Process 1 creates and maintains a canonical document registry for every FSR PDF.
2. Process 2 reads that registry, performs chunking and embedding, materializes selected metadata onto chunk rows, and updates processing status.

This keeps metadata extraction, enrichment, and governance separate from chunk generation. That separation is important because metadata architecture needs to be stable now, while chunking quality will continue to evolve.

Pranesh's draft is directionally correct on workflow separation. The main improvement needed is to make Process 1 a stronger document registry with clearer identifiers, status semantics, precedence rules, and re-materialization support.

This should be presented as a design maturation step, not as a rejection of the current proposal. The workflow split is already the right foundation. The discussion for Monday is mainly about making the metadata layer stronger and more production-ready.

---

## 1. Concrete Metadata Architecture

### 1.1 Core Design

The metadata layer should be the canonical file-level source of truth for FSR ingestion.

It should own:

1. file discovery
2. incremental ingestion
3. metadata extraction and normalization
4. enrichment from reference systems
5. document classification
6. source-of-truth field precedence
7. handoff status to chunking

Chunking should not rediscover or reinterpret this metadata unless there is an explicitly approved fallback.

### 1.2 Target Architecture

```text
Volumes -> Process 1: Document Registry / Metadata Table -> Process 2: Chunk + Embed -> Vector Search / Retrieval
```

Process 1 is the system of record for file-level metadata.  
Process 2 is a downstream consumer of that record.

### 1.2.1 End-to-End Flow: Metadata to Chunking

The intended end-to-end behavior should be explicit, especially around what gets read at each stage.

Important clarification:

1. Process 1 does **not** create chunks.
2. Process 1 reads candidate PDFs only to extract document-level metadata and write one canonical document row.
3. Process 2 runs later, reads selected rows from the metadata table, then loads only those PDFs for chunking.
4. The physical PDF may therefore be touched in both processes, but for different purposes:
   - Process 1: identify and register the document
   - Process 2: generate retrieval chunks from the document

```text
1. Source Volumes
   Input:
   - Candidate PDF files in configured source locations
   Output:
   - File list with path and timestamps

2. Process 1A - Discover Candidate Files
   Input:
   - Configured volume paths
   Output:
   - Candidate PDF file list

3. Process 1B - Filter to New or Updated Files
   Input:
   - Candidate PDF file list
   - Watermark from metadata table
   Output:
   - New or updated files to ingest

4. Process 1C - Extract, Normalize, and Enrich Metadata
   Input:
   - Selected PDF files
   - Reference sources such as IBAT / Event Vision / SOT mappings
   Output:
   - Canonical document-level metadata

5. Canonical Metadata Table
   Output row shape:
   - One row per document
   - volume_path
   - document_type
   - canonical metadata fields
   - chunk_status = pending

6. Process 2A - Select Specific Documents for Chunking
   Input:
   - Metadata table rows
   Filter:
   - document_type = FSR
   - chunk_status in (pending, failed)
   Output:
   - Exact set of documents to chunk

7. Process 2B - Load Physical PDFs Using volume_path
   Input:
   - Selected metadata rows
   Output:
   - Full PDF content only for the selected documents

8. Process 2C - Chunk Text and Materialize Metadata
   Input:
   - PDF content
   - Canonical metadata row
   Output:
   - Retrieval-ready chunk rows

9. Chunk Delta Table
   Output:
   - Chunk rows with text, metadata, and embedding-ready structure

10. Process 2D - Embedding / Vector Search Sync
    Input:
    - Chunk rows
    Output:
    - Searchable chunk index

11. Metadata Status Update
    Input:
    - Chunking and embedding outcome
    Output:
    - chunk_status = completed or failed
    - error fields populated when needed

12. Query / Retrieval Layer
    Input:
    - Searchable chunk index
    Output:
    - Retrieval results for downstream consumers
```

### 1.2.1A Plain-Language Reading of the Flow

The proposal should be read in this order:

1. first register the document
2. then decide whether that document should be chunked
3. then chunk it in a downstream step

In other words:

1. Process 1 answers: what is this file, and what is its canonical metadata?
2. Process 2 answers: how do we turn this file into retrieval-ready chunks?

This means the architecture is **not**:

1. extract metadata and chunks in one combined step
2. write chunk rows immediately during metadata extraction

It **is**:

1. read candidate PDFs for metadata registration
2. write one document-level row per source PDF
3. later read selected metadata rows for chunking
4. load only those selected PDFs and generate chunk rows

### 1.2.2 What Gets Read at Each Stage

This is the recommended operating model.

#### Process 1: Metadata Ingestion

Question: Are we reading all FSR docs, or only particular docs from the volume?

Recommended answer:

1. On the first bootstrap run, Process 1 may scan all candidate PDF files in the configured source volumes.
2. On normal incremental runs, Process 1 should only process files whose `last_modified` is newer than the watermark.
3. Process 1 is not limited to already-known FSRs only. It reads candidate PDF documents from the configured source locations and determines document metadata, including `document_type`.

So the source read pattern is:

1. bootstrap: all candidate PDFs in scope
2. incremental: only new or updated candidate PDFs in scope

#### Process 2: Chunking and Embedding

Question: Is Process 2 reading all documents again from the volume?

Recommended answer:

1. No. Process 2 should not rescan the full volume.
2. Process 2 should read only specific rows from the canonical metadata table.
3. Those rows should be filtered to documents that are ready for chunking, typically `document_type = 'FSR'` and `chunk_status IN ('pending', 'failed')`.
4. Only after selecting those metadata rows should Process 2 load the corresponding physical PDFs using `volume_path`.

So the Process 2 read pattern is:

1. select specific metadata rows first
2. then load only those specific PDFs from the volume

### 1.2.3 Step-by-Step Inputs and Outputs

| Step | Purpose | Input | Output |
|---|---|---|---|
| 1. Source discovery | Identify candidate files in scope | Configured volume paths | Candidate PDF file list with path and file timestamps |
| 2. Incremental filter | Avoid full reprocessing on every run | Candidate file list + watermark from metadata table | New or updated files to process |
| 3. Metadata extraction | Parse document-level metadata | Selected PDFs | Raw extracted metadata, page-1 fields, title, file attributes |
| 4. Normalization and enrichment | Resolve canonical business metadata | Raw extracted metadata + IBAT/Event Vision/reference sources | Canonical document metadata row |
| 5. Metadata write | Persist the source-of-truth document record | Canonical metadata row | Metadata table row with `chunk_status = pending` |
| 6. Chunking selection | Choose exactly which docs need chunking | Metadata table rows | Subset of rows where `document_type = 'FSR'` and `chunk_status` is actionable |
| 7. PDF load for chunking | Load only required physical files | Selected metadata rows with `volume_path` | In-memory PDF document content for those rows |
| 8. Chunk generation | Produce retrieval units | PDF content + chunking implementation | Chunk records with text, page ranges, structural metadata |
| 9. Metadata materialization | Attach governed metadata to chunks | Chunk records + canonical metadata row | Retrieval-ready chunk rows |
| 10. Embedding / index sync | Make chunks searchable | Chunk rows | Vectorized searchable chunk dataset / synced index |
| 11. Status update | Record operational result | Chunking outcome | Metadata rows updated to `completed` or `failed` |

### 1.2.4 Decision Boundary Between the Two Processes

The handoff should be simple:

1. Process 1 decides what the document is and what its canonical metadata should be.
2. Process 2 decides how to turn that document into chunk rows for retrieval.

That means:

1. Process 1 output is document-level truth.
2. Process 2 input is a filtered subset of those document rows.
3. Process 2 should not rediscover business metadata unless there is an explicitly approved exception.

### 1.2.5 Concrete Example: One PDF Through Both Processes

Example file:

- `/Volumes/viud/ing_ud_fieldvision/fv_field_service_report/FSR_100245.pdf`

Process 1 behavior:

1. The discovery step sees `FSR_100245.pdf` in the source volume.
2. The incremental filter decides the file is new or updated because its `last_modified` is newer than the current watermark.
3. Process 1 reads the PDF to extract page-1 and document-level metadata such as title, customer, report dates, FSR number, and candidate ESN.
4. Process 1 enriches that metadata from reference systems such as IBAT or Event Vision.
5. Process 1 writes **one row** to the canonical metadata table, for example:
   - `document_id = <deterministic id>`
   - `pdf_name = FSR_100245.pdf`
   - `volume_path = /Volumes/viud/ing_ud_fieldvision/fv_field_service_report/FSR_100245.pdf`
   - `document_type = FSR`
   - `esn = 338X424`
   - `chunk_status = pending`

At this point:

1. the document is registered
2. no chunk rows exist yet
3. no embeddings exist yet

Process 2 behavior:

1. Process 2 queries the metadata table for rows where `document_type = 'FSR'` and `chunk_status IN ('pending', 'failed')`.
2. It selects the row for `FSR_100245.pdf`.
3. Only then does Process 2 load `/Volumes/viud/ing_ud_fieldvision/fv_field_service_report/FSR_100245.pdf` from the volume.
4. It extracts full text, splits the text into chunks, and creates chunk rows.
5. It copies selected canonical metadata onto each chunk row, such as `document_id`, `esn`, `title`, `customer`, and `report_issued_date`.
6. It generates embeddings for those chunk rows.
7. It writes the chunk rows to the chunk table and syncs the vector index.
8. It updates the metadata row from `chunk_status = pending` to `chunk_status = completed`.

So the same PDF participates in both processes, but the outputs are different:

1. Process 1 output: one document-level metadata row
2. Process 2 output: many chunk rows plus embeddings

### 1.3 Metadata Table Role

Recommended table role:

- One row per source document
- Stable record across re-runs and re-uploads
- Contains both business metadata and operational processing state
- Provides the `volume_path` used by Process 2 to load the physical PDF

Recommended table name pattern:

- `biz_metadata_field_service_report`

### 1.4 Recommended Metadata Schema

At minimum, the metadata table should contain the following columns.

| Column | Type | Why it matters |
|---|---|---|
| `document_id` | STRING | Stable primary key for the document record |
| `pdf_name` | STRING | Source file identifier / compatibility key |
| `volume_path` | STRING | Physical location used by Process 2 |
| `document_type` | STRING | `FSR`, `TIL`, `MANUAL`, `ER`, `UNKNOWN` |
| `title` | STRING | Retrieval context and UI usefulness |
| `customer` | STRING | Important business filter and context |
| `esn` | STRING | Primary resolved ESN |
| `esn_source` | STRING | Makes ESN lineage explicit |
| `equipment_sys_id` | STRING | IBAT linkage |
| `equipment_type` | STRING | Business and retrieval filter |
| `equipment_code` | STRING | Additional equipment subtype |
| `event_type` | STRING | Business and retrieval filter |
| `ev_project_id` | STRING | Event Vision lineage |
| `ev_equipment_event_id` | STRING | Event Vision lineage |
| `ofs_event_id` | STRING | Operational linkage |
| `fsp_project_id` | STRING | Operational linkage |
| `xxx_project_id` | STRING | Preserve source value until clarified |
| `fsr_number` | STRING | Business identifier |
| `report_issued_date` | DATE | Important date dimension |
| `outage_start_date` | DATE | Important date dimension |
| `outage_end_date` | DATE | Important date dimension |
| `prepared_by` | STRING | Useful context field |
| `approved_by` | STRING | Useful context field |
| `page_count` | INT | Debugging and quality checks |
| `chunk_status` | STRING | Contract between Process 1 and Process 2 |
| `chunk_error_code` | STRING | Short failure category |
| `chunk_error_reason` | STRING | Detailed failure message |
| `metadata_version` | INT | Supports re-materialization when enrichment logic changes |
| `metadata_resolved_at` | TIMESTAMP | When the canonical metadata was last resolved |
| `field_source_map` | STRING / JSON | Optional lineage map of which source populated which field |
| `ingestion_timestamp` | TIMESTAMP | Watermark for incremental metadata ingestion |
| `updated_timestamp` | TIMESTAMP | Operational auditability |

### 1.5 Identifier and Upsert Rules

Recommended rules:

1. `document_id` should be deterministic and stable for the active document record.
2. `volume_path` should be the operational uniqueness key for ingestion and re-upload handling.
3. Re-uploaded files should use upsert, not append.

Why:

- Append mode creates stale duplicate records.
- Process 2 should not need to decide which of two metadata rows is current.
- Upsert allows a changed file to reset `chunk_status = 'pending'` and be reprocessed cleanly.

### 1.6 Incremental Metadata Ingestion

Process 1 should use watermark-based ingestion.

Recommended logic:

```text
watermark = MAX(ingestion_timestamp)
new_or_updated_files = files where last_modified > watermark
```

Behavior:

1. empty table means full bootstrap
2. normal runs process only new or updated files
3. `FORCE_RESET` is reserved for full rebuilds only

### 1.7 ESN Resolution Ownership

ESN should be resolved once in Process 1 and carried forward.

Recommended precedence:

1. trusted source-of-truth reference when available
2. normalized extraction result
3. regex or heuristic fallback
4. null

The winning source should be written to `esn_source`.

This matters because the team should not have one ESN rule in metadata extraction, another in chunking, and another in retrieval.

### 1.7.1 Suggested Field Precedence Table

The exact source systems can be finalized with the team, but the architecture should assume explicit precedence rules like the following.

| Field | Preferred source | Fallback | Why |
|---|---|---|---|
| `esn` | trusted reference / SOT mapping | normalized extraction, then heuristic fallback | ESN consistency is critical for retrieval and joins |
| `equipment_type` | IBAT-enriched value | normalized extraction | IBAT is the stronger business source |
| `equipment_code` | IBAT-enriched value | normalized extraction | Better governance and consistency |
| `event_type` | Event Vision-enriched value | normalized extraction | Event systems should win when available |
| `ev_project_id` | Event Vision-enriched value | normalized extraction | Event system identifier |
| `ev_equipment_event_id` | Event Vision-enriched value | normalized extraction | Event system identifier |
| `ofs_event_id` | Event Vision or agreed operational source | normalized extraction | Operational linkage should be deterministic |
| `fsp_project_id` | normalized extraction with enrichment validation | raw extracted value | Preserve report context while allowing cleanup |
| `fsr_number` | normalized extraction | raw extracted value | Usually document-native |
| `report_issued_date` | normalized extraction | raw parsed date | Document-native but needs date normalization |
| `outage_start_date` | normalized extraction | raw parsed date | Document-native but needs date normalization |
| `outage_end_date` | normalized extraction | raw parsed date | Document-native but needs date normalization |
| `title` | extracted and normalized document title | raw page-1 title text | Document-native field |
| `customer` | normalized extraction with enrichment validation when available | raw extracted value | Business context field that may need cleanup |

### 1.8 Document Type Ownership

`document_type` should be decided in Process 1, not in Process 2.

Why:

1. Process 2 can simply filter to `document_type = 'FSR'`
2. the same metadata architecture can later support ERs, manuals, and other document classes
3. type separation is a metadata concern, not a chunking concern

### 1.9 Status Model Between the Two Processes

Prefer `chunk_status` over a generic `processed` field.

Recommended values:

1. `pending`
2. `processing`
3. `completed`
4. `failed`

Why this is better than `yes` / `failed` / null:

1. the state is explicit and self-describing
2. in-flight rows are visible
3. retries and operational dashboards become easier
4. null is no longer overloaded as business meaning

### 1.10 Metadata-to-Chunk Contract

Process 2 should treat the metadata table as the contract boundary.

That means:

1. it reads pending FSR rows from the metadata table
2. it uses `volume_path` to load the PDF
3. it materializes selected metadata fields onto chunk rows
4. it updates `chunk_status` and error columns on completion or failure

This contract should remain stable even if the chunking algorithm changes later.

### 1.11 Re-Materialization Capability

Metadata changes should not always require re-scraping or re-chunking.

Recommended design:

1. bump `metadata_version` when enrichment or precedence logic changes
2. allow a targeted re-materialization job to refresh chunk-row metadata from the canonical metadata table
3. reserve full re-chunking for cases where chunk text itself must change

This is important for production maintainability.

### 1.12 Catalog and Environment Alignment

Before implementation, the team should explicitly confirm:

1. source volume catalogs for DEV, UAT, and PROD
2. target metadata table catalog/schema
3. target chunk table and vector index catalog/schema
4. which application and retrieval services will read from those target objects

This matters because the current discussions reference multiple catalog families such as `VIUD`, `VAID`, `VGPD`, and `VGPP`. The architecture should not move forward with ambiguous environment ownership.

---

## 2. Design Discussion Areas and Suggested Enhancements

Pranesh's draft is good on process separation and workflow clarity. The discussion areas below are best viewed as enhancements that make the design more explicit, more governable, and easier to operate in production.

### 2.1 Add a stable `document_id`

Current issue:

- The draft relies on `pdf_name` and `volume_path`, but does not define a stable document primary key.

Recommended alternative:

- Add `document_id` as the primary key of the metadata table.
- Keep `pdf_name` as a compatibility field, not the canonical identity.

### 2.2 Strengthen `processed` into a clearer status model

Current issue:

- `processed` mixes state and meaning, and `null` means “not yet chunked.”

Recommended alternative:

- Replace `processed` with `chunk_status` using explicit values: `pending`, `processing`, `completed`, `failed`.
- Keep `chunk_error_code` and `chunk_error_reason` separately.

### 2.3 Make ESN precedence and lineage explicit

Current issue:

- The draft includes `esn` but does not define how conflicting sources are resolved.

Recommended alternative:

- Define ESN precedence in Process 1.
- Add `esn_source` so later consumers know why that value was selected.

### 2.4 Add `document_type` now

Current issue:

- The draft assumes FSR scope but does not create a field that allows the architecture to scale to adjacent document classes.

Recommended alternative:

- Add `document_type` now.
- Filter Process 2 to `document_type = 'FSR'`.

### 2.5 Resolve re-upload handling explicitly

Current issue:

- The draft leaves append vs upsert unresolved.

Recommended alternative:

- Standardize on upsert by `volume_path`.
- On update, reset `chunk_status = 'pending'`, clear chunk errors, and refresh metadata.

### 2.6 Add a re-materialization path

Current issue:

- The draft assumes metadata changes are handled only through normal reprocessing.

Recommended alternative:

- Add `metadata_version` and support targeted metadata refresh to chunk rows.

### 2.7 Add lineage and provenance fields on the canonical metadata row

Current issue:

- The draft does not capture when metadata was last resolved or which source contributed specific values.

Recommended alternative:

- Add `metadata_resolved_at`.
- Keep `metadata_version` as the current resolution logic version.
- Add `field_source_map` as an optional later-phase lineage field if full provenance is needed.

### 2.8 Move date fields toward target-state business types

Current issue:

- The draft uses string dates, even though it requires normalized date format.

Recommended alternative:

- Normalize to ISO format during extraction, but store target-state date columns as `DATE` in the production model.

### 2.9 Move chunk-row metadata away from JSON-only for critical fields

Current issue:

- The draft pushes all chunk metadata into one JSON field.

Recommended alternative:

- Promote retrieval-critical fields to top-level chunk columns.
- Keep JSON only for secondary structural and diagnostic metadata.

Why this matters:

1. filtering is easier
2. SQL is simpler
3. indexing and operational inspection are cleaner

### 2.10 Explicitly frame Process 1 as the canonical registry

Current issue:

- The draft is operationally sound but does not fully state that Process 1 is the system of record.

Recommended alternative:

- Explicitly frame Process 1 output as the canonical document registry for all downstream consumers.

### 2.11 Make catalog and environment mapping explicit

Current issue:

- The draft names target locations, but it does not explicitly resolve the environment and catalog mapping across data processing and application layers.

Recommended alternative:

- Add a short deployment mapping section that identifies the source and target catalogs per environment and confirms what the application layer is expected to read.

---

## 3. Basic Workflow for Chunking and Embedding

This section intentionally defines only the workflow. It does not lock the final chunking algorithm.

### 3.1 Workflow Objective

Process 2 should do one thing well:

- convert canonical document records from Process 1 into retrieval-ready chunk rows and embeddings

### 3.2 Recommended Workflow

```text
Read pending FSR rows -> Load PDF from volume_path -> Chunk document text -> Materialize selected metadata -> Generate embeddings -> Write chunk rows -> Sync Vector Search -> Update chunk_status
```

### 3.3 Recommended Runtime Steps

1. Query metadata table for rows where `chunk_status IN ('pending', 'failed')` and `document_type = 'FSR'`.
2. Mark those rows as `processing` when work begins.
3. Load the PDF using `volume_path`.
4. Extract full text and run the current chunking implementation.
5. Generate one or more chunk rows for the document.
6. Materialize selected metadata columns from Process 1 onto each chunk row.
7. Generate embeddings for each chunk.
8. Write chunk rows to the chunk Delta table.
9. Sync or refresh the Vector Search index.
10. On success, update the source document row to `completed`.
11. On failure, update the source document row to `failed` and record the error.

### 3.4 Minimum Chunk Table Shape

At workflow level, the chunk table should support:

| Column | Why it exists |
|---|---|
| `chunk_id` | Stable primary key |
| `document_id` | Link back to canonical metadata row |
| `pdf_name` | Compatibility and debugging |
| `chunk_text` | Retrieval text |
| `embedding` or managed embedding source | Search vectorization |
| `page_start` | Traceability |
| `page_end` | Traceability |
| `esn` | Common retrieval filter |
| `equipment_type` | Common retrieval filter |
| `event_type` | Common retrieval filter |
| `title` | Response context |
| `customer` | Response context |
| `report_issued_date` | Filter/context |
| `document_type` | Type-level filtering |
| `metadata_version` | Re-materialization support |
| `chunk_metadata` | Secondary structure/diagnostics |

If the implementation needs a transition phase, JSON metadata can exist temporarily, but the target architecture should expose key retrieval fields as columns.

### 3.5 Multi-ESN Handling at Workflow Level

At workflow level, the design should allow one chunk row per ESN when a document legitimately applies to multiple units.

Recommended ownership:

1. Process 1 keeps one canonical document row and resolves the primary ESN plus lineage.
2. Process 2 applies deterministic fan-out rules when multi-ESN retrieval rows are actually needed.

The exact ESN fan-out logic does not need to be finalized in this document. The important point is that Process 2 should consume the canonical ESN decision from Process 1 and apply a clear, deterministic rule.

### 3.6 Purposeful Chunk Table and Vector Index

The team should not treat the chunk table or vector index as a place to dump every possible field.

Recommended principle:

1. promote only retrieval-critical metadata to top-level chunk columns
2. keep secondary fields in `chunk_metadata` only when truly needed
3. keep the canonical document registry as the richer source of record

This keeps Process 2 purposeful and prevents the search layer from becoming a copy of every upstream table.

### 3.7 Runtime and Bootstrap Considerations

The first full load will be materially more expensive than incremental runs.

For Monday, it is enough to state:

1. bootstrap processing of the full corpus will likely require batching and checkpointing
2. incremental runs should be driven by `chunk_status` and only process new or failed documents
3. runtime expectations for the full initial load should be called out explicitly during planning

---

## 4. Chunking Algorithm Improvement: What We Should Say Now

The chunking algorithm should be treated as a separate design track.

This document should not attempt to finalize:

1. section boundary logic
2. TOC handling
3. front matter policy
4. header and footer removal rules
5. chunk size and overlap tuning
6. table extraction strategy
7. multi-ESN evidence assignment inside chunk text

### 4.1 What We Can Safely Say Now

For Monday, the position can be:

1. the current recursive chunking approach is good enough as an interim workflow implementation
2. the chunking algorithm is not yet the final production design
3. metadata architecture should be approved independently of final chunking logic
4. Process 2 only needs a stable contract from Process 1 to move forward

### 4.2 Basic Issues to Call Out Without Going Into Design Detail

The current or expected chunking improvement areas are:

1. better separation of real content from front matter, TOC, repeated headers, and footers
2. more reliable section-aware chunk boundaries for long technical PDFs
3. better page range and section metadata on each chunk
4. better handling of tables, appendices, and form-like repeated content
5. consistent strategy for multi-ESN documents
6. better evaluation of chunking quality against retrieval outcomes

These are valid reasons to keep chunking design separate from metadata architecture.

### 4.3 Suggested Monday Position

Recommended message for the discussion:

- We should approve the metadata-first, two-process architecture now.
- We should define Process 2 workflow now.
- We should not block metadata architecture on final chunking algorithm design.
- We should take chunking improvements as a separate focused workstream.

---

## 5. Collaborative Discussion Framing

If this is discussed with Pranesh and the architects, the tone should be collaborative:

1. the current draft already has the right two-process separation
2. the main goal is to make the metadata layer more explicit and more production-friendly
3. these changes are refinements to strengthen the design, not a rewrite of the core direction

Suggested framing language:

- The current design has the right shape. The main opportunity is to make Process 1 a more explicit canonical metadata registry.
- We can lock the metadata architecture now without needing to finalize the chunking algorithm.
- The goal for Monday is to agree on ownership, contract, and status semantics between the two processes.
- If we align on the metadata contract now, chunking improvements can proceed as a separate stream without blocking architecture decisions.

---

## Final Recommendation

For Monday, the strongest position is:

1. adopt Pranesh's two-step workflow separation
2. strengthen Process 1 into a canonical metadata registry
3. make Process 2 a status-driven consumer of that registry
4. expose key metadata as governed fields, not only as JSON blobs
5. keep chunking defined only at workflow level in this discussion
6. treat final chunking algorithm design as a separate document and workstream

This gives the team a production-worthy metadata architecture now without pretending that chunking design is already final.