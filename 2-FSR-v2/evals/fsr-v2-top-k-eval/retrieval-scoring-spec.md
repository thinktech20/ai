# FSR v2 Retrieval Scoring Spec (Draft)

Last updated: 2026-08-12

## Table of contents

- [Scope](#scope)
- [Evaluation strategy and baseline](#evaluation-strategy-and-baseline)
	- [Baseline retrieval behavior](#baseline-retrieval-behavior)
	- [Retriever strategy implementations](#retriever-strategy-implementations)
	- [Knob-based comparisons](#knob-based-comparisons)
	- [Measurements for every run](#measurements-for-every-run)
- [Inputs](#inputs)
	- [Probe-set workflow](#probe-set-workflow)
	- [probe-set-template.csv (DS team input)](#probe-set-templatecsv-ds-team-input)
	- [probe-set-resolved.csv (build artifact, used by eval runner)](#probe-set-resolvedcsv-build-artifact-used-by-eval-runner)
	- [Probe template column definitions](#probe-template-column-definitions)
- [Metric 1: returned_doc_ids_vs_expected](#metric-1-returned_doc_ids_vs_expected)
- [Metric 2: cited_doc_page_hit_at_k](#metric-2-cited_doc_page_hit_at_k)
- [Metric 3: chunk_recall_at_k](#metric-3-chunk_recall_at_k)
- [Metric 4: chunk_precision_at_k](#metric-4-chunk_precision_at_k)
- [Metric 5: chunk_f1_at_k](#metric-5-chunk_f1_at_k)
- [Ground-truth levels](#ground-truth-levels)
- [Probe and label validation rules](#probe-and-label-validation-rules)
- [Optional guard metric: esn/equipment filter fidelity](#optional-guard-metric-esnequipment-filter-fidelity)
- [Required per-probe output fields](#required-per-probe-output-fields)
- [Pass/Fail thresholds (initial)](#passfail-thresholds-initial)
- [Experiment comparison report](#experiment-comparison-report)
- [Notes](#notes)
- [Terminology: probe set vs gold set](#terminology-probe-set-vs-gold-set)
- [Implementation note](#implementation-note)

## Scope

This spec defines scoring for probe-based retrieval evals using FSR v2 chunks.

- Retrieval output unit: chunk
- Weak-label target unit: document
- Experiment approach: fixed baseline implementation with controlled knob changes

## Evaluation strategy and baseline

The evaluation is intended to guide the URA app team's retrieval implementation.
We start from the retrieval behavior currently implemented by URA, incorporate
the latest proposed shared-region change, and then compare controlled changes
to individual retrieval knobs.

### Baseline retrieval behavior

The baseline implementation must be aligned with these two design notes:

- `2-FSR-v2/retrieval/current-rertriever-algo-ura.md`
- `2-FSR-v2/retrieval/retriver-changes-needed.md`

The baseline flow is:

1. Use the v2 SQL eligibility query to find active, processed documents for the
	requested ESN within the configured recency window.
2. If eligible v2 documents exist, search the v2 multi-ESN index with hybrid
	retrieval and restrict results to those document IDs.
3. Include chunks where `region_primary_esn = requested_esn` or
	`region_primary_equip_type = shared`.
4. If no eligible v2 documents exist, preserve the legacy timeboxed-index
	fallback and its existing ESN filter.
5. De-duplicate results, rank by similarity, and return only `top_k` chunks.

The evaluation retriever should be implemented in `retriever.py` using this
baseline behavior before running comparison experiments. The implementation
should expose the retrieval controls as configuration rather than embedding
them in individual probes.

### Retriever strategy implementations

Use one experiment interface with two interchangeable retriever strategies:

| Strategy | Purpose | Behavior |
|---|---|---|
| `ura_current` | Reproduce the current URA app behavior. | SQL eligibility gate, current ESN-only v2 filter, one hybrid Vector Search request, current de-duplication, and current Vector Search ranking order. |
| `ura_with_shared_impl` | Evaluate the proposed URA behavior. | Same eligibility gate and legacy fallback, plus ESN-or-shared v2 filtering, candidate merge, de-duplication by `chunk_id`, similarity ranking, and final `top_k` selection. |

The experiment runner passes a strategy name and configuration to the same
interface, for example:

```python
retriever = create_retriever(strategy="ura_current", config=config)
rows = retriever.retrieve(probe)
```

Suggested module layout:
- `retriever_service_ura_current.py` — current-app reference implementation.
- `retriever_service_ura_with_shared_impl.py` — proposed shared-region implementation.
- `retriever_service.py` — common protocol, factory, and shared result types.

Keep the two implementations separate so a change to the proposed shared
retrieval path cannot silently change the current-app reference. Keep shared
SQL, response parsing, normalization, and metric code outside the strategies.
The strategy name, implementation version, and configuration must be recorded
in every run.

### Knob-based comparisons

The retrieval implementation is fixed to the baseline above. Experiments
change configurable retrieval parameters, one at a time, using the same
resolved probe set, ESNs, query prompts, index data, and evaluation conditions.
Record the complete configuration for every run.

Initial tunable knobs:

| Knob | Plain-English explanation | Business problem it helps solve or test |
|---|---|---|
| `top_k` | How many chunks the retriever returns for each issue. Test values such as 5, 10, 20, and 40. | Should the user receive a short, focused set of evidence, or more evidence for complex issues? More chunks may improve coverage but can add noise, processing cost, and response time. |
| `overfetch_k` | How many candidate chunks the retriever collects before it removes duplicates, applies final processing, and selects the final `top_k`. | Are useful chunks being lost because duplicate or filtered results use up the candidate slots? This is especially relevant when ESN-specific and shared-region results are combined. |
| `recency_window_months` | How far back in time the retriever is allowed to search eligible FSR documents. | What is the right balance between recent, operationally relevant reports and older reports that may contain useful historical evidence? A wider window may improve coverage but increase noise and search cost. |
| `query_type` | How the search matches the issue prompt. `HYBRID` uses keyword and semantic matching; vector-only search uses semantic similarity. | Does the current search approach find the evidence users need, including both exact technical terms and conceptually similar language? This is an optional experiment, not a change to the baseline implementation. |

The following are implementation details of the baseline, not experiment
knobs: the SQL eligibility gate, the ESN-or-shared v2 filter, the choice of one
request or two-request merge for shared regions, the v2/legacy routing logic,
and the final de-duplication/ranking behavior. They should change only as an
explicit implementation revision, with its own comparison against the
baseline.

### Measurements for every run

For every knob configuration and every value of K, measure:

| Metric | Category | Value means / definition | Question it answers |
|---|---|---|---|
| `avg_recall_at_k` | Page/evidence retrieval quality | By default, fraction of expected `(document_id, page_number)` evidence pairs retrieved. `1.0` means all expected evidence pages were found. | Of all the evidence pages we expected, how many did the retriever find? |
| `avg_precision_at_k` | Page/evidence retrieval quality | By default, fraction of returned chunks whose `(document_id, page_number)` belongs to an expected evidence pair. `1.0` means every returned chunk points to expected evidence. | Of the evidence returned, how much was relevant? |
| `avg_f1_at_k` | Page/evidence retrieval quality | By default, combined score for page-level recall and precision. Higher is better; `1.0` means both are perfect. | How well does the retriever balance finding expected evidence and avoiding irrelevant evidence? |
| `avg_doc_recall_at_k` | Document coverage | Fraction of expected documents represented in the results. | Of all the expected documents, how many appeared in the results? |
| `avg_cited_doc_page_hit_rate` | Evidence coverage | Fraction of expected evidence pages retrieved. | Of all the expected evidence pages, how many appeared in the results? |
| `retrieval_filter_match_rate_at_k` | Filtering correctness | Fraction of returned chunks that are either attributed to the requested ESN or are `shared` chunks from an eligible document. | Did the retriever return only chunks allowed by the ESN and shared-region filter? |
| `p95_latency_ms` | Performance | Response time in milliseconds under which 95% of requests completed. Lower is better. | How long did retrieval take for almost all requests? |

Compare each configuration with the fixed baseline using metric deltas. Do not
change multiple knobs in one comparison unless the experiment explicitly tests
an interaction.

## Inputs

### Probe-set workflow

```
probe-set-template.csv          Heat Map.xlsx
(DS team fills this)            (existing, owned by DS)
        |                               |
        └──────── build script ─────────┘
                       |
               probe-set-resolved.csv
               (frozen, used by eval runner)
```

### probe-set-template.csv (DS team input)

Probe file columns used:
- probe_id
- esn
- equip_type
- persona
- component
- issue_name
- expected_document_ids
- expected_cited_doc_pages
- expected_chunk_ids
- chunk_table_version

Note on DS team responsibility:
- `issue_prompt` is NOT in this file; DS team fills only the heatmap-key columns + expected_* weak labels
- `expected_cited_doc_pages` = pipe-delimited (document_id, page_number) pairs from the source documents that answer the probe's issue
- `expected_chunk_ids` is optional. DS team provides it only when exact chunk-level scoring is required for a specific `chunk_table_version`.
- DS team uses the chunk table structure (`chunk_id`, `document_id`, `page_number`, `chunk_text`, ...) to identify relevant chunks and pages.
- `expected_cited_doc_pages` remains the stable label for page/evidence scoring; `expected_chunk_ids` is tied to a specific chunk-table version and can change across chunking variants.
- `chunk_table_version` identifies the chunk-table snapshot used to label `expected_chunk_ids`; it is required when `expected_chunk_ids` is populated.
- The prompt is resolved in the build step below.

### probe-set-resolved.csv (build artifact, used by eval runner)

Generated by joining `probe-set-template.csv` with `Heat Map.xlsx` on `(equip_type, component, persona, issue_name)`.
Adds the `issue_prompt` column with the frozen query string for each probe.
This file is what the eval runner reads — do not hand-edit it.

Build step:
- Input: probe-set-template.csv + Heat Map.xlsx
- Join key: (equip_type, component, persona, issue_name)
- Output: probe-set-resolved.csv with issue_prompt frozen
- Re-run the build script whenever probe-set-template.csv or Heat Map.xlsx changes.
- Commit probe-set-resolved.csv alongside each eval run snapshot for traceability.

Reference files:
- 2-FSR-v2/evals/fsr-v2-top-k-eval/probe-set-template.csv
- 2-FSR-v2/evals/fsr-v2-top-k-eval/Heat Map.xlsx
- 2-FSR-v2/evals/fsr-v2-top-k-eval/probe-set-resolved.csv

Retrieved row fields used:
- chunk_id
- document_id
- page_number
- chunk_text
- region_primary_esn
- region_primary_equip_type
- similarity_score

## Probe template column definitions

Reference file:
- 2-FSR-v2/evals/fsr-v2-top-k-eval/probe-set-template.csv

Column definitions:
- probe_id
	- Unique probe identifier (example: P-001).
	- Must be stable across runs so comparisons are deterministic.

- esn
	- Target equipment serial number for retrieval filtering.
	- Use normalized format (uppercase; no extra spaces).

- equip_type
	- Equipment type scope for the probe (example: generator, gas_turbine).
	- Used for slice-level reporting and optional filter checks.

- persona
	- User persona/source role for prompt shaping (example: reliability_engineer).
	- Optional metadata for analysis slices.

- component
	- Equipment component in focus (example: bearing, combustor, seal oil system).
	- Used with persona/issue_name for traceability to source sheet.

- issue_name
	- Short issue label (example: high vibration).
	- Used with component/persona for traceability to source sheet.
	- Join key into Heat Map to resolve issue_prompt at build time.

- expected_document_ids
	- Weak-label expected source documents for this probe.
	- Pipe-delimited list (example: FSR-10021|FSR-10455|FSR-11002).
	- Purpose: verify retrieval pool coverage and mismatches (missing/extra docs).

- expected_cited_doc_pages
	- Pipe-delimited cited targets in document_id,page format.
	- Example: FSR-10021,42|FSR-10021,324.
	- Purpose: verify the exact cited evidence pages appear in top-k chunks.
	- A probe can include multiple cited pages and multiple documents.

- expected_chunk_ids
	- Optional pipe-delimited exact chunk IDs that contain relevant evidence.
	- Use only with the declared `chunk_table_version`.
	- Enables exact chunk-level precision, recall, and F1; it is not required for page-level scoring.

- chunk_table_version
	- Version or run ID of the chunk table used to label `expected_chunk_ids`.
	- Required when `expected_chunk_ids` is populated; blank when chunk IDs are not provided.

- label_source
	- Provenance of weak labels.
	- Recommended controlled values: document_equipment_map, prior_retrieval_run, heuristic_mapping, sme_confirmed.

- confidence
	- Label confidence for prioritization and review.
	- Recommended values: high, medium, low.

- notes
	- Free-text context for reviewers (assumptions, caveats, follow-ups).

Formatting rules:
- Use pipe as multi-value delimiter for expected_document_ids and expected_cited_doc_pages.
- Avoid commas inside multi-value fields unless the entire field is quoted.
- Keep one probe per row.
- Do not use chunk_id as ground truth in this template; chunk IDs can change across chunking variants.

## Metric 1: returned_doc_ids_vs_expected

Definition:
- For each probe, look at top-k retrieved chunks.
- Extract unique document_id values from those chunks.
- Compare with probe expected_document_ids.

Per-probe values:
- expected_doc_count = count(expected_document_ids)
- hit_doc_count = count(intersection(retrieved_doc_ids, expected_document_ids))
- missing_expected_doc_ids = expected_document_ids - retrieved_doc_ids
- additional_doc_ids = retrieved_doc_ids - expected_document_ids
- doc_ids_exact_match = 1 if both sets are equal else 0
- doc_ids_not_same_flag = 1 if sets differ else 0
- doc_recall_at_k = hit_doc_count / max(expected_doc_count, 1)

Aggregate values:
- avg_doc_recall_at_k = mean(doc_recall_at_k)
- avg_doc_ids_exact_match = mean(doc_ids_exact_match)
- avg_doc_ids_not_same_flag = mean(doc_ids_not_same_flag)

## Metric 2: cited_doc_page_hit_at_k

Definition:
- For each probe, parse expected_cited_doc_pages as (document_id, page) pairs.
- Normalize retrieved rows to comparable (document_id, page) pairs.
- Mark each expected pair as hit or miss based on presence in top-k.

Per-probe values:
- expected_cited_pairs_count = count(expected cited pairs)
- matched_cited_pairs_count = count(expected cited pairs present in top-k)
- cited_doc_page_hit_rate = matched_cited_pairs_count / max(expected_cited_pairs_count, 1)
- cited_doc_page_all_hit = 1 if matched_cited_pairs_count == expected_cited_pairs_count else 0
- cited_doc_page_hit_flags = list of yes/no by expected pair

Aggregate values:
- avg_cited_doc_page_hit_rate = mean(cited_doc_page_hit_rate)
- avg_cited_doc_page_all_hit = mean(cited_doc_page_all_hit)

Default aggregate quality metrics use these page/evidence matches:
- `recall_at_k` = unique matched expected page pairs / unique expected page pairs
- `precision_at_k` = retrieved chunks whose page pair is expected / retrieved chunks
- `f1_at_k` = harmonic mean of page-level precision and recall
- `avg_recall_at_k`, `avg_precision_at_k`, and `avg_f1_at_k` are the means of
	those per-probe values.

When `expected_chunk_ids` is populated, the same metric names may additionally
be reported at exact chunk level as `avg_chunk_recall_at_k`,
`avg_chunk_precision_at_k`, and `avg_chunk_f1_at_k`.

## Metric 3: chunk_recall_at_k (optional exact chunk metric)

**Definition:**

The primary retrieval quality metric. For each issue prompt (user query), measures what fraction of the expected chunks — as listed in the probeset template — were successfully retrieved in top-K.

- issue prompt = user query derived from (persona, component, issue_name)
- expected chunks = `expected_chunk_ids`, when provided for the matching `chunk_table_version`
- retrieved chunks = the `chunk_id` values present in top-K results
- If `expected_chunk_ids` is blank, do not report this metric; report the page-level metrics instead.

Per-probe values:
- expected_chunks_count = count of expected_chunk_ids
- retrieved_matching_chunks_count = count of expected_chunk_ids found in top-K results
- recall_at_k = retrieved_matching_chunks_count / max(expected_chunks_count, 1)
- missing_chunks = expected (document_id, page) pairs not found in top-K

Aggregate values:
- avg_chunk_recall_at_k = mean(chunk_recall_at_k) across valid chunk-labeled probes

Relationship to Metric 2:
- Metric 2 (`cited_doc_page_hit_rate`) reports the same underlying hit counts with per-pair hit flags for deep-dive inspection.
- Exact chunk metrics are supplemental; the page/evidence metrics are the
	canonical quality metrics when DS provides page labels only.

## Metric 4: chunk_precision_at_k (optional exact chunk metric)

**Definition:**

For each issue prompt with `expected_chunk_ids`, measures what fraction of the top-k retrieved chunks matched the expected chunk IDs.

Per-probe values:
- total_retrieved_chunks = number of chunks in top-k results
- matched_retrieved_chunks = count of top-k chunk IDs that are in expected_chunk_ids
- precision_at_k = matched_retrieved_chunks / max(total_retrieved_chunks, 1)

Aggregate values:
- avg_chunk_precision_at_k = mean(chunk_precision_at_k) across valid chunk-labeled probes

Interpretation:
- High recall + low precision = missing many relevant chunks in top-k (coverage gap)
- High precision + low recall = returning mostly correct chunks but not enough (rank quality issue)
- Use both together to diagnose retrieval bottlenecks.

## Metric 5: chunk_f1_at_k (optional exact chunk metric)

**Definition:**

Harmonic mean of precision and recall. Balances both dimensions for a single holistic quality score.

Per-probe values:
- chunk_f1_at_k = 2 * (chunk_precision_at_k * chunk_recall_at_k) / max(chunk_precision_at_k + chunk_recall_at_k, eps)
- chunk_f1_at_k = 0 if both chunk precision and chunk recall are 0

Aggregate values:
- avg_chunk_f1_at_k = mean(chunk_f1_at_k) across valid chunk-labeled probes

## Ground-truth levels

The evaluation reports different measures at different levels. They answer
different questions and should not be treated as interchangeable:

| Level | Ground truth supplied by DS | Measures | Use |
|---|---|---|---|
| Document | `expected_document_ids` | Document recall and document set differences | Did retrieval search the right source reports? |
| Page/evidence | `expected_cited_doc_pages` | Page recall, page precision, and page hit flags | Did retrieval return the pages containing the cited evidence? This is the default quality level. |
| Chunk | Optional `expected_chunk_ids` plus `chunk_table_version` | Exact chunk recall, precision, and F1 | Did this exact chunking/index version return the labeled chunks? Use for chunking experiments, not as a portable label across versions. |

Recommendation: ask DS for document IDs and cited document/page pairs as the
required labels. Ask for chunk IDs as an optional enrichment when exact
chunk-level analysis is needed. Do not maintain two independent probe
templates; one template keeps the query, document, page, and optional chunk
labels aligned. A separate generated artifact may be used for labels expanded
from page pairs to chunk IDs.

## Probe and label validation rules

Keep these rules isolated from retriever code and the experiment runner so DS
labeling decisions can change without changing retrieval implementation:

1. Normalize ESNs, document IDs, chunk IDs, and page values by trimming
	whitespace; normalize ESNs and document IDs to the agreed case.
2. Require exactly one Heat Map match for each probe join key after
	normalization. Zero matches and multiple matches fail probe resolution.
3. Require every `expected_cited_doc_pages` pair to contain a document ID and a
	valid page number. Reject blank, non-numeric, or negative page values unless
	the source system explicitly defines them.
4. Reject duplicate values within `expected_document_ids`,
	`expected_cited_doc_pages`, or `expected_chunk_ids`.
5. Require `chunk_table_version` whenever `expected_chunk_ids` is populated.
6. Validate every expected chunk ID against the declared chunk-table snapshot
	and verify its document ID and page number agree with the supplied page
	label.
7. A probe with no document or page ground truth is invalid and is excluded
	from averages with an explicit exclusion reason.
8. Record `valid_probe_count` and `excluded_probe_count` for every run.

## Optional guard metric: esn/equipment filter fidelity

Definition:
- For each top-k row, verify region_primary_esn == probe.esn.
- If equip_type filter is used, verify region_primary_equip_type == probe.equip_type.

Aggregate values:
- retrieval_filter_match_rate_at_k = allowed_rows / total_rows
- equip_type_match_rate_at_k = matched_rows / total_rows

## Required per-probe output fields

Each probe row output should include:
- chunk_id list for top-k rows (for deep-dive traceability)
- top-k returned document_ids
- retrieved document/page pairs
- recall_at_k, precision_at_k, and f1_at_k at the default page/evidence level
- chunk-level metrics only when expected_chunk_ids are available
- missing evidence page pairs
- missing_expected_doc_ids and additional_doc_ids
- doc_ids_not_same_flag
- cited_doc_page_hit_flags (yes/no per expected pair)
- retrieval_filter_match_rate_at_k
- similarity scores, region_primary_esn, and region_primary_equip_type for each row
- retrieval_status and latency_ms

## Pass/Fail thresholds (initial)

Use these as initial gates (tune after first baseline run):
- avg_recall_at_k >= 0.75 (primary gate: coverage)
- avg_precision_at_k >= 0.70 (secondary gate: rank quality)
- avg_f1_at_k >= 0.72 (holistic balance)
- avg_doc_recall_at_k >= 0.80
- avg_cited_doc_page_hit_rate >= 0.75
- retrieval_filter_match_rate_at_k >= 0.95
- no critical slice drops > 0.05 vs baseline

## Experiment comparison report

For each knob configuration and each k in {5, 10, 20, 40}, run the same probe
set and compare the result with the fixed baseline.

Comparison table columns:
- run_id
- strategy
- implementation_version
- configuration_id
- changed_knob
- changed_value
- k
- avg_recall_at_k
- avg_precision_at_k
- avg_f1_at_k
- avg_doc_recall_at_k
- avg_doc_ids_not_same_flag
- avg_cited_doc_page_hit_rate
- avg_cited_doc_page_all_hit
- retrieval_filter_match_rate_at_k
- p95_latency_ms

Delta report fields:
- delta_recall_at_k = experiment - baseline
- delta_precision_at_k = experiment - baseline
- delta_f1_at_k = experiment - baseline
- delta_doc_recall = experiment - baseline
- delta_doc_ids_not_same_flag = experiment - baseline
- delta_cited_doc_page_hit_rate = experiment - baseline
- delta_latency = experiment - baseline

Decision rule (initial):
- Prefer the configuration with higher doc/evidence metrics if latency
	regression <= 20%.
- If quality gain < 0.02 and latency is worse, keep the baseline
	configuration.

## Notes

- This is weak-label scoring for retrieval tuning, not final gold evaluation.
- Gold labels are required for ESN/equipment mapping correctness (separate eval track).

## Terminology: probe set vs gold set

- **Probe set** (this file): test queries with weak labels — heuristic,
  auto-generated, or low-to-medium confidence. Used for retrieval tuning,
  regression checks, and controlled knob comparisons. Labels may be incomplete
  or unverified.
- **Gold set**: a high-confidence, human-verified subset of probes where `label_source = sme_confirmed` and `confidence = high`. Used for final evaluation and reporting. Calling a probe set a gold set would overstate label quality.
- Promotion path: probes graduate from probe set → gold set after SME review and confidence upgrade.

## Implementation note

The implementation repository for this evaluation is `sdg-evals`. The existing
`sdg-evals/fsr/retriever.py` is an earlier scratch implementation, not the URA
app retriever. It may be deleted or overwritten. Start the implementation from
scratch using the strategies and contracts defined in this specification:
`ura_current` and `ura_with_shared_impl`.
