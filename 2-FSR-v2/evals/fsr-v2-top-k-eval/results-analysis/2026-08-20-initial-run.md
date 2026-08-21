# FSR v2 Top-k Eval — Initial Run Analysis (2026-08-20)

Source data: [results-top-k-run.csv](./results-top-k-run.csv)

## Runs included

- Probe set: 8 probes from `probe-set.csv` (workbook-derived, 2026-08-19).
- Strategies: `ura_current`, `ura_with_shared_impl`.
- K values: 5, 10, 20, 40.
- 8 successful runs. Two earlier runs with `probes_failed=8` are the failed
  401-auth attempts and are excluded from analysis.

## Aggregate metrics

| Strategy | K | n_returned | doc_recall | cited_page_hit | page_f1 | filter_match | avg_latency_ms | p95_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ura_current          |  5 |  5.0 | 0.938 | 0.000 | 0.000 | 1.000 | 2583 | 4255 |
| ura_current          | 10 | 10.0 | 0.938 | 0.042 | 0.019 | 1.000 | 1712 | 1811 |
| ura_current          | 20 | 10.0 | 0.938 | 0.042 | 0.019 | 1.000 | 1953 | 2774 |
| ura_current          | 40 | 10.0 | 0.938 | 0.042 | 0.019 | 1.000 | 1649 | 1740 |
| ura_with_shared_impl |  5 |  5.0 | 0.938 | 0.000 | 0.000 | 0.850 | 1968 | 2543 |
| ura_with_shared_impl | 10 | 10.0 | 0.938 | 0.042 | 0.019 | 0.925 | 2419 | 4226 |
| ura_with_shared_impl | 20 | 20.0 | 0.938 | 0.042 | 0.011 | 0.963 | 1891 | 2168 |
| ura_with_shared_impl | 40 | 38.9 | 0.938 | 0.042 | 0.006 | 0.981 | 1945 | 2411 |

## Observations

1. **Document coverage is saturated at 15/16 (0.9375) for every run.** One
   probe consistently misses one expected document; the other seven probes
   find all expected documents at every K and for both strategies.
2. **`ura_current` caps at ~10 chunks per probe.** The ESN-only filter yields
   ~10 candidate chunks in the v2 index, so K=10, 20, 40 produce identical
   results. Only K=5 truncates.
3. **`ura_with_shared_impl` scales with K** (5 → 39 chunks) because shared
   chunks are included in addition to ESN chunks. This does not improve
   `doc_recall_at_k` or `cited_doc_page_hit_rate`; the extra chunks are
   additional context only.
4. **`avg_cited_doc_page_hit_rate` is very low (0 to 0.042) for both
   strategies.** This means the retriever finds the right documents most of
   the time but rarely surfaces the labeled evidence page in top-K. This is
   the largest open question for the eval.
5. **Filter fidelity:** `ura_current` is 1.0 at all K. `ura_with_shared_impl`
   trends 0.85 → 0.98 as K grows. Both include chunks that pass the eligible
   ESN + shared filter; the current run’s guard against legacy fallback was
   not yet in effect for these runs.
6. **Latency is comparable** across strategies and K (~1.6–2.6 s average,
   p95 up to 4.2 s). No strong latency preference in either direction.

## Per-probe evidence (K=10, `ura_current`)

Downloaded `per_probe/*.jsonl` for the K=10 `ura_current` run. For each
probe, compared expected cited pages against the actual `page_number` of
the top-10 retrieved chunks in the same document.

| Probe | Expected pages | Retrieved page range (same doc) | Nearest match | Interpretation |
|---|---|---|---|---|
| P-001 Oil ingress                    | 86              | 165, 515, 528, 529, 538, 599, 601, 603, 604, 605 | none within ±20 | Genuine miss: query matched later sections |
| P-002 Oil ingress                    | 9, 86, 98       | same as P-001                                    | none within ±20 | Genuine miss (same query) |
| P-003 FOD                             | 173, 237        | 7, 172, 174, 185, 230, 236, 240, 243, 249, 252   | 172, 174 around 173; 236, 240 around 237 | Off-by-one chunk-page boundary |
| P-004 FOD                             | 173, 237, 240   | same as P-003                                    | 240 exact hit; 173/237 off-by-one | 1 exact hit + off-by-one on others |
| P-005 Reversed fan blades             | 239             | 220, 223, 227, 230, 231, 237, 259, 265, 268      | 237 (off by 2) | Off-by-two chunk-page boundary |
| P-006 FOD                             | 920             | 887, 890, 892, 896, 919, 976, 990                | 919 (off by 1) | Off-by-one chunk-page boundary |
| P-007 FOD                             | 891, 920, and page 8 in a second doc | 887, 890, 892, 896, 919, 976, 990 (doc A only) | 890/892 around 891; 919 near 920 | Off-by-one on doc A; second doc never retrieved (this is the 15/16 gap) |
| P-008 ISSB/OSSB migration             | 891, 924        | 887, 890, 892, 896, 916, 919, 976, 1006, 1022    | 890/892 around 891; none near 924 | Off-by-one on 891; miss on 924 |

Summary:

- **5 of 8 probes** have a retrieved chunk within ±2 pages of the expected
  cited page. This is a chunk-page boundary effect: the retrieved chunk
  overlaps the labeled evidence but records the adjacent page number as
  `page_number`.
- **1 of 8 probes** (P-004) has an exact page match on one of three expected
  pages.
- **2 of 8 probes** (P-001, P-002 “Oil ingress” on ESN 338X447) are genuine
  content misses. The retriever returns pages 165–605 for a report whose
  labeled evidence is on pages 9, 86, and 98. The query
  `field service report unit 338X447 Generator Stator Oil ingress` matches
  later sections that mention oil in a different context. Same query, same
  ESN, so both probes miss identically.
- **1 of 8 probes** (P-007) accounts for the 15/16 document-recall gap. The
  probe expects 2 documents; only document A is retrieved. Document B never
  appears in the top-K for this ESN. This is a real retrieval miss, not a
  labeling issue.

## Corrected interpretation of the initial metrics

The strict page-hit metric under-reports true retrieval quality because it
treats an adjacent chunk-page as a miss even when the chunk itself covers
the labeled evidence. A more representative metric on the current chunking
scheme would be one of:

- Cited-page hit within a ±2-page tolerance.
- Chunk-level overlap using explicit `expected_chunk_ids` for a fixed
  `chunk_table_version` (already supported by the scoring spec).

Applying a ±2-page tolerance to today’s 8 probes:

- Effective cited-page hit at the probe level: 6 of 8 probes retrieve the
  labeled evidence (exact or adjacent chunk).
- Genuine retrieval misses remain 2 of 8 (both are the same Oil ingress
  query on ESN 338X447).

## Preliminary top-k selection

Per the plan in [run-instructions.md](./run-instructions.md), the smallest K
that preserves document coverage and does not regress F1:

- `ura_current`: **K = 10**. K > 10 has no effect (pool exhausted); K = 5
  truncates.
- `ura_with_shared_impl`: **K = 10**. Larger K adds context without improving
  doc recall or cited-page hit, and reduces precision.

## Preliminary strategy comparison

At K = 10:

- Document recall: tied at 0.938.
- Cited-page hit rate: tied at 0.042.
- Filter fidelity: `ura_current` 1.0 vs `ura_with_shared_impl` 0.925.
- Latency: `ura_current` 1712 ms vs `ura_with_shared_impl` 2419 ms average.

On this probe set the shared implementation does not improve retrieval
quality and shows a small filter and latency cost. This is a preliminary
signal from 8 probes; a larger probe set is needed before drawing a
production conclusion.

## Open questions to resolve before deciding

1. **Adopt an adjacent-page tolerance in the scoring metric?** The current
   strict page-hit metric penalizes chunk-boundary noise that is not a real
   retrieval quality issue. Adding a ±2-page tolerance (or reporting
   exact-hit and near-hit separately) would materially change the numbers
   above without changing retrieval behavior.
2. **Reword the P-001/P-002 probe** to differentiate the Oil ingress finding
   section from other oil-related mentions, and rerun. This is the only real
   retrieval-quality failure on this set.
3. **Investigate the P-007 second document miss** (`69dfe261`). Check
   whether that document is present in the v2 mapping table for ESN
   `GG10675`, whether it is chunked, and whether its chunks are indexed.
   Likely candidates: mapping row missing, chunk_status not completed, or
   index sync lag.

## Suggested next runs

1. Rerun with the v2-only eligibility guard in place. If any probe would
   trigger legacy fallback, the run raises a clear error naming the ESN
   instead of silently succeeding through the legacy index.
2. After (1), download `per_probe/*.jsonl` for K=10 for each strategy and
   confirm page-number alignment on at least one probe before selecting a
   strategy.
3. Expand the probe set to at least 25–30 probes so K=5 vs K=10 comparisons
   have enough resolution to be meaningful.
