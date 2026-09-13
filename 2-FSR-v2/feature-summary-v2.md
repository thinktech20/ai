FSR v2 Feature Summary
======================

Status
------

FSR v2 is a redesigned ingestion and retrieval pipeline for Field Service
Reports. It replaces the v1 document-level equipment fan-out model with a
parser-aligned, region-aware pipeline that preserves equipment attribution at
document and chunk level.

The delivered v2 implementation includes:

- **Intelligent report metadata extraction** with deterministic equipment sections
	and attribution, plus a separate equipment mapping table that normalizes the
	relationship between every report and its primary or secondary equipment
- **Improved retrieval and risk-assessment accuracy** through richer metadata,
	including equipment context, section attribution, dates, active status,
	provenance, and reference-data enrichment
- **Reference-data enrichment** through IBAT, Event Vision, and PSOT lookups
- **Region-aware content chunking and embeddings** that keep each part of a
	report tied to its owning equipment, preventing content from one unit from
	being labeled or retrieved as another
- **Persisted parsed documents** so content can be reproduced or re-chunked with a
	different strategy without re-reading the source PDF
- **Equipment-aware report readiness and search results**, including primary and
	secondary equipment identifiers
- **MLflow experiment tracking and retrieval evaluation** support for comparing
	models, strategies, and top-K settings
- **Backfill recovery, validation, and data-correctness validations**
- **Operational safeguards** for large, long-running serverless workloads
- **Separate ingestion jobs** for metadata extraction, chunking and embedding,
	and search-index synchronization, plus a chained workflow used for the daily
	incremental ingestion process after the backfill is complete

The deterministic preprocessor redesign described near the end of this document
is implemented in `common/fsr_v2/preprocessor_v2.py`. It is part of the
delivered FSR v2 ingestion path and has been validated against the known
preprocessor bug corpus. Further accuracy improvements remain follow-up work.


1. Problems addressed from FSR v1
---------------------------------

FSR v1 had two important multi-equipment failure modes.

1. Retrieval miss

An FSR could contain multiple pieces of equipment, such as a Gas Turbine and a
Generator. If the document listed the Gas Turbine ESN first, chunks could be
tagged with that ESN even when the content belonged to the Generator. A query
for the Generator ESN then returned no result.

2. Wrong equipment label

Generator content such as stator, rotor, or field sections could be labeled as
Gas Turbine content. That gave downstream risk assessment the wrong equipment
context and could lead to an incorrect remediation recommendation.

FSR v2 addresses both by preserving section and region context and assigning
equipment metadata at chunk level instead of fanning every chunk out to every
ESN in the document.


2. How the solution works
-------------------------

The solution is organized into modular capabilities that can run independently
or as one end-to-end workflow:

		Report understanding and enrichment
				PDF discovery -> text parsing -> equipment-aware preprocessing
				-> field normalization -> reference-data enrichment
				-> searchable report metadata + equipment mapping

		Content preparation
				completed report metadata -> parser-aligned text
				-> equipment-aware content chunks -> embeddings

		Search indexing
				content chunks -> index creation/synchronization
				-> searchable report content

		Business search and readiness
				equipment-map eligibility -> ESN/date/status filtering
				-> vector retrieval -> post-filtered ranked results

The state is carried primarily on fsr_metadata_v2:

- metadata_status: pending, completed, failed, or date_filtered
- chunk_status: pending, in_progress, completed, or failed
- metadata_retry_count and chunk_retry_count
- scraped_at and chunked_at timestamps
- parser, processor, prompt, model, and pipeline provenance

P2 only claims metadata-completed documents. A document outside the configured
date range is marked date_filtered and is not re-claimed.


3. P1 metadata extraction and enrichment
-----------------------------------------

P1 produces the document-level source of truth in fsr_metadata_v2.

Input and parsing

- Discovers PDFs from configured Unity Catalog volumes.
- Supports targeted document processing through FSR_TARGET_PDF_NAMES.
- Uses the configured v2 parser path and records parser provenance.
- Stores parser-aligned extracted artifacts in a volume when configured, so P2
	can reuse the same text representation.
- Applies a page-one date probe before full processing when date filtering is
	enabled. This avoids fully parsing documents outside the configured range.

Deterministic preprocessing

The preprocessor scans the full document text for structured evidence:

- equipment headers
- equipment labels
- ESN-shaped values
- section and subsection headings
- inactive-equipment markers
- region boundaries
- document-level equipment metadata
- hints for downstream LLM normalization

The preprocessor is authoritative for equipment identifiers and equipment type
when it has structured evidence. It does not ask the LLM to rediscover ESNs or
equipment types that were already extracted deterministically.

Reference-data enrichment

P1 enriches metadata through deterministic lookups against:

- IBAT for equipment system and class information
- Event Vision for event and equipment-event context
- PSOT for service-report and outage context where configured

These lookups run after the preprocessor and LLM fields are merged. They avoid
using another LLM call for reference-data resolution and preserve the source
table values in the final metadata record.

LLM normalization

The LLM is scoped primarily to cover-page and administrative fields, including:

- customer
- prepared_by and approved_by
- FSR number
- event type
- project and event identifiers
- document name and summary fields

Preprocessor hints are injected as known facts so the LLM is guided by the
deterministic extraction and should not contradict it.

Merge and enrichment

The merge precedence is:

		LLM fields < preprocessor fields < reference-data enrichment

IBAT, Event Vision, and PSOT lookups provide deterministic enrichment where
available. These joins avoid additional LLM calls for reference-data fields.

The resulting metadata row records the extracted values, preprocessor regions,
inactive ESNs, parsed artifact location, dates, retry state, and processing
provenance.


4. Equipment mapping feature
----------------------------

fsr_document_equipment_map_v2 is a serving helper with one row per
(document_id, esn).

It supports:

- primary and secondary ESNs in the same document
- equipment type per ESN
- technology code where available
- is_primary_esn
- is_active derived from inactive_esns
- source_region_count for attribution auditability
- created_at and updated_at timestamps

Map rows are built from real extracted data:

- region-level ESNs from preprocessor_regions
- document-level primary_esn
- gt_esn, gen_esn, and st_esn anchors
- inactive_esns

The implementation seeds a row from document-level fields when no region carries
that ESN. This prevents a valid document-level ESN from disappearing from ESN
lookup merely because the preprocessor had no region-level occurrence.

The map is not populated with placeholder rows before attribution exists.
Retrieval should require chunk_status = completed before serving a document.


5. P2 parser-aligned chunking and embeddings
--------------------------------------------

P2 reads completed metadata and parser-aligned text, then:

1. Loads the persisted parsed artifact where available.
2. Falls back to source-volume parsing when an artifact is unavailable.
3. Splits text region-first with recursive sub-chunking.
4. Preserves character offsets and page attribution.
5. Applies per-chunk metadata precedence.
6. Generates embeddings through LiteLLM.
7. Validates embedding coverage and dimension.
8. MERGEs chunk rows by deterministic chunk_id.
9. Updates chunk_status only after valid chunk rows are written.

P1 and P2 use the same parser-aligned representation. P1 persists the parsed
document, including page text, page offsets, and character positions, and P2
reuses it when available. This prevents P1 region boundaries from being
calculated in one text coordinate system while P2 chunks a differently
extracted document.

The persisted parsed document is also the reproducibility boundary. If a new
chunking strategy, chunk size, overlap, or attribution method is introduced, P2
can regenerate chunks from the same extracted text and offsets without
re-reading or re-parsing the source PDF. That makes strategy comparisons,
re-chunking, and recovery more consistent and less expensive.

Per-chunk metadata precedence is:

		upload metadata < document metadata < section metadata < region metadata

The region is the highest-priority source. A chunk overlapping a Generator
region receives the Generator ESN and equipment type even when the document-level
primary ESN belongs to a Gas Turbine.

Each chunk stores or exposes:

- chunk_id and document_id
- chunk text and page number
- chunk index
- region_primary_esn
- region_primary_equip_type
- active_esns
- report and outage dates
- embedding vector and embedding dimension
- embedding model
- chunk strategy
- merge strategy
- region attribution method
- pipeline and run provenance
- metadata JSON containing doc, region, section, and chunk_context blocks

The deterministic chunk_id is derived from document_id and chunk index, making
reprocessing idempotent. Existing rows are updated in place rather than
duplicated.


3. P3 Vector Search and modular job orchestration
-------------------------------------------------

P3 creates or synchronizes fsr_vs_index_v2 from fsr_chunks_v2 as an independent
job. FSR v2 separates the operational stages into modular jobs:

- P1 Metadata: discovery, parsing, preprocessing, enrichment, and equipment-map
	materialization
- P2 Chunking: parser-aligned chunking and embedding
- P3 Vector Search: index creation or synchronization

The stages can be triggered independently for backfills, recovery, validation,
or controlled QA testing. An optional chained ingestion workflow runs them in
order as P1 -> P2 -> P3 for normal incremental ingestion.

The indexed fields include:

- chunk_id
- document_id
- chunk_text
- chunk_embedding
- primary or region ESN attribution
- equipment type
- active_esns
- report and outage dates
- metadata JSON

Retrieval has two complementary paths.

Data readiness lookup

- Resolves documents through the equipment map.
- Filters to active ESNs.
- Requires metadata and chunk completion states.
- Applies the recency threshold.
- Returns documents ordered by report date.

Vector retrieval

- Validates ESN eligibility through metadata and the equipment map.
- Embeds the query text at request time.
- Queries the vector index using chunk-level ESN filters.
- Applies recency and document eligibility post-filters.
- Deduplicates chunk results.
- Uses an unattributed-chunk fallback only where required by coverage gaps.

The result is equipment-aware retrieval rather than document-wide ESN fan-out.

Experiment-driven retrieval tuning

FSR v2 includes MLflow experiment tracking for pipeline configuration and
evaluation. Retrieval validation can compare query behavior across embedding
models, chunking and attribution strategies, and different top-K values. This
provides an evidence-based way to select a top-K setting rather than choosing
one as a fixed default without measuring retrieval quality and result volume.


7. Operational and resiliency improvements
-------------------------------------------

The QA backfill exposed and resolved several production risks.

Incremental map writes

The equipment map was originally accumulated in memory and written once at the
end of P1. An interruption could leave thousands of completed metadata rows
with no map rows. The map is now written per LLM batch, bounding the loss from a
large run to the in-flight batch.

Failure and DQ durability

Failure rows, date-filter rows, and DQ rows were also previously held until the
end of the notebook. They are now flushed per batch, so retry counts and DQ
records survive a failed or cancelled run.

Driver-memory protection

P1 no longer retains every completed Future and its parsed document text for the
whole run. Futures are released as their results are consumed.

Single-trigger backfill

P1 processes the queue in slices. FSR_V2_P1_SLICE_SIZE bounds the number of
documents submitted to the thread pool at once, but one trigger can continue
through all slices until the queue is drained.

Optional FSR_V2_P1_MAX_RUNTIME_MINUTES provides a clean-boundary runtime cap.
It is checked between slices and writes are flushed before the run stops.

P2 conflict recovery

P2 writes now use shared Delta conflict retry logic with exponential jittered
backoff. This prevents a transient optimistic-concurrency conflict from
crashing the job without retrying.

Stale-claim accounting

When P2 reclaims a stale in_progress document, it increments chunk_retry_count
and records the recovery reason. A poison-pill document therefore cannot be
reclaimed forever without consuming retry budget.

Serverless compatibility

The pipeline is designed for Databricks serverless Python 3.10. Runtime
parameters avoid Python 3.10-incompatible nested f-string syntax. Validation
checks use structured tables and SQL because serverless does not reliably return
driver logs.


8. Validation and correctness checks
-------------------------------------

FSR v2 includes the following validations and correctness checks:

- pulse checks for queue state, throughput, stale claims, failures, run logs,
	DQ logs, and cross-table consistency
- an end-to-end correctness gate that reports PASS, FAIL, or SKIP
- equipment-map repair using persisted metadata without PDF parsing or LLM calls
- snapshot comparison for incremental/idempotent behavior
- MLflow experiment tracking for pipeline and retrieval configuration studies,
	including top-K evaluation
- checks for orphan chunks, duplicate chunk IDs, empty text, embedding dimension,
	duplicate equipment-map pairs, blank ESNs, and primary-ESN consistency

The critical cross-table rule is:

- when P1 is idle, every completed document with a known ESN must have a map row
- while P1 is active, a small temporary gap up to one LLM batch is expected
- a gap that persists while idle, grows across checks, or exceeds the batch
	boundary requires investigation or repair

QA evidence from the backfill included:

- 9,280 map rows rebuilt for 7,363 affected documents in 49 seconds
- zero duplicate document/ESN pairs
- zero blank ESNs
- zero orphan map rows
- zero primary-ESN mismatches
- source region counts matched map counts across 6,807 compared pairs
- per-batch map writes observed live during P1
- date-filter and DQ writes observed live after previously being absent


9. Implemented deterministic preprocessor capabilities
-------------------------------------------------------

The deterministic preprocessor is the major foundation that was not present in
FSR v1. The following capabilities are implemented in the v2 preprocessor.

Unnumbered equipment headings

Detect standalone headings such as GAS TURBINE, GENERATOR, STEAM TURBINE, and
EXCITER using anchored patterns. Do not match the same words inside paragraph
text. Emit an equipment-block boundary with source and confidence metadata.

Hierarchical parent/child sections

Represent equipment blocks, numbered sections, and subsections as a hierarchy
with levels and parent context. Section numbering is a hint, not an authority;
nearby explicit hierarchy and heading evidence take precedence.

Parent-context restoration

Give every span an explicit end. A child ends at the next heading of the same or
higher level, while an equipment block ends only at the next equipment-block
heading. When a Generator subsection ends, the following content resumes its
parent Gas Turbine context automatically.

Local ESN assignment

Resolve each section in deterministic order:

1. explicit ESN in the heading
2. resolved ESN inherited from the parent
3. unique active ESN for the equipment type
4. constrained IBAT lookup
5. unresolved/ambiguous state without guessing

This replaces the global single-ESN anchor per equipment type and supports
multiple ESNs of the same equipment type in one document.

Unified TOC and body model

Use TOC entries as summary and coarse-boundary evidence, then refine their
locations against full document text. One section-span model feeds both region
attribution and document-summary extraction instead of maintaining disconnected
TOC and body models.

Attribution provenance

Record esn_source, esn_confidence, region_source, equip_type_source, and the
fallback_chain. Downstream systems can distinguish a local heading assignment
from parent inheritance, an IBAT fallback, a neighbor fallback, or no
assignment.

Full character coverage

Emit explicit front_matter, gap_fallback, trailing, and shared regions so every
character belongs to exactly one contiguous, non-overlapping region. Unattributed
text remains explicit rather than silently disappearing or being assigned to the
document primary ESN.

Ambiguous ESN handling

When deterministic evidence leaves zero or multiple candidates, do not force an
ESN. Emit an equipment-type-only region where justified and mark
esn_confidence = none. These regions become explicit inputs for any optional
later LLM enrichment rather than silent errors.


10. Implemented preprocessor data contract
------------------------------------------

Internal SectionSpan fields:

- start and end
- level, where -1 is an equipment block
- heading_text and heading_type
- equipment_type
- local_esn and resolved_esn
- esn_confidence and esn_source
- parent_idx
- is_summary

Region metadata fields:

- primary_esn when resolved
- primary_equip_type when resolved
- primary_technology_code when available
- esn_confidence
- esn_source
- equip_type_source
- region_source
- fallback_chain

These fields preserve backward compatibility for existing primary ESN and
equipment-type consumers while exposing provenance for validation and retrieval
improvements.


11. Explicit limitations and follow-up work
--------------------------------------------

The deterministic preprocessor cannot solve every case.

- If a Generator section has no Generator ESN, no Generator vocabulary, and no
	reference-data evidence, the ESN remains unresolved.
- If a second ESN is never written anywhere in the document, rule-based logic
	cannot discover it.
- Ambiguous IBAT candidates must remain ambiguous unless a validated train-link
	filter is available.
- Exciter and Generator may currently share a bucket; a dedicated exciter_esn
	field is a follow-up.
- Page-by-page ingest and some appendix-heavy TOC patterns remain future work.
- Embedding dimension checks, metadata completeness warnings, and unresolved-ESN
	review thresholds should remain explicit validation gates.
- A robust P1 claim mechanism for cross-job concurrency is still a separate
	operational hardening item. Standalone P1 and chained ingestion must not run
	simultaneously until that is implemented.


12. Summary
-----------

FSR v2 delivered the architecture needed to make FSR retrieval equipment-aware:
parser-aligned text, deterministic preprocessing, region-based chunk
attribution, multi-ESN mapping, embeddings, vector indexing, and explicit
validation contracts.

The deterministic preprocessor is the key difference from FSR v1. Instead of
leaving section boundaries and equipment attribution implicit or asking the LLM
to infer them, v2 can represent hierarchy, local ESN evidence, parent context,
confidence, provenance, and unresolved cases explicitly.

The implemented redesign extends that foundation to difficult documents with
unnumbered headings, same-type multiple ESNs, nested subsections, TOC/body
alignment, and complete region coverage. Future changes should be incremental
and validated against the known bug corpus before changing the active index.
