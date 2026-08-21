# FSR v2 Top-k Eval — Demo Talking Points (2026-08-20)

Source data: [results-top-k-run.csv](./results-top-k-run.csv),
[2026-08-20-initial-run.md](./2026-08-20-initial-run.md).

## Recommendation in one line

For this workload, **top-K = 10** is sufficient. At K = 10 both retrieval
strategies tie on document recall; `ura_current` is slightly better on
filter fidelity and latency. Strategy choice is a separate decision from
top-K and needs a larger probe set before finalizing.

## What to open (in order)

1. [retrieval-scoring-spec.md](../retrieval-scoring-spec.md) — 30 seconds
   of context for the scoring approach.
2. [probe-set.csv](../probe-set.csv) — real ESNs, real expected pages.
3. MLflow experiment `/Users/madhurima.saxena@gevernova.com/fsr_v2_topk_eval`.
4. [2026-08-20-initial-run.md](./2026-08-20-initial-run.md) — the per-probe
   evidence table is the punchline.
5. If asked for detail: open the K=10 `ura_current` run and click into
   `per_probe/*.jsonl`.

## Story (in order)

1. Setup: 8 probes, real ESNs and expected pages. Two strategies,
   four K values, 8 MLflow runs.
2. Headline: retrieval finds the right document about 94% of the time
   (15/16). Six of eight probes retrieve chunks in or adjacent to the
   labeled evidence page.
3. Two failure modes, both actionable:
   - Metric strictness (5 of 8 probes). Retrieved chunks are one or two
     pages off from the labeled page because chunks record the adjacent
     page number. The content is the same. A ±2-page tolerance closes
     the gap without changing retrieval.
   - Query wording (2 of 8 probes). The Oil ingress query on ESN 338X447
     matches later sections of the report; the labeled finding is on
     early pages. Rephrase the probe query.
4. Top-K = 10 for both strategies. Larger K adds noise, smaller K
   truncates coverage.
5. Strategy comparison at K = 10: tied on document recall and adjusted
   evidence recall. `ura_current` slightly better on filter fidelity and
   latency. Shared retrieval does not improve quality on this set; it may
   still be needed for coverage cases not in these 8 probes.
6. Hardening done: probe set versioned in the repo, notebook fails clearly
   on stale/empty inputs, a v2-only guard now prevents silent legacy
   fallback.
7. Next steps: adopt adjacent-page tolerance in the metric, fix the two
   query wording issues, investigate one probe’s missing second document,
   grow the probe set to 25–30.

## Why the MLflow bar chart looks flat

`avg_doc_recall_at_k` is 0.9375 for every one of the 8 successful runs.
Coverage is saturated. That is a finding, not a chart problem. To show
K’s effect, switch the Y-axis to a metric that actually varies with K.

## MLflow charts to show (Bar Chart tab)

Select all 8 successful runs (exclude the two `probes_failed = 8` rows).
Set X-axis to run name (already labeled with strategy and K). Use these
Y-axis metrics one at a time:

1. `avg_n_returned`
   - Purpose: show K’s real effect on candidate volume.
   - Expected: `ura_current` stays flat at ~10 for K = 10, 20, 40 (ESN pool
     exhausted). `ura_with_shared_impl` scales 5 → 10 → 20 → 39.
   - Talking point: “Larger K only adds candidates for the shared strategy.
     Current retrieval hits its ceiling at K = 10.”
2. `avg_precision_at_k` (or `avg_page_precision_at_k`)
   - Purpose: show diminishing returns of larger K.
   - Expected: precision drops as K grows, because true positives stay
     constant while the denominator grows.
   - Talking point: “K > 10 does not add relevant evidence, only noise.”
3. `avg_retrieval_filter_match_rate_at_k`
   - Purpose: show filter fidelity gap between strategies.
   - Expected: `ura_current` = 1.00 at every K. `ura_with_shared_impl`
     climbs from 0.85 at K = 5 to 0.98 at K = 40.
   - Talking point: “Current retrieval is strictly filtered by ESN. Shared
     retrieval trades a small amount of filter fidelity for extra context.”
4. `p95_latency_ms`
   - Purpose: latency profile.
   - Expected: comparable across strategies (~1.7 s to 4.2 s p95). K has
     little effect.
   - Talking point: “Latency is not the deciding factor here. Both
     strategies are in the same range.”
5. `avg_doc_recall_at_k`
   - Purpose: acknowledge the flat bars and use them as the headline.
   - Expected: 0.9375 for every run.
   - Talking point: “All runs find the same 15 of 16 expected documents,
     regardless of strategy or K. Document coverage is not the axis of
     comparison — evidence quality is.”

## If the audience asks “so K = 5 or K = 10?”

Show `avg_n_returned` and `avg_precision_at_k` side by side. K = 5
truncates the candidate pool and misses adjacent-page chunks; K = 10 keeps
full coverage without precision loss for current. That is the K decision.

## If asked “so which strategy?”

The honest answer today: **inconclusive on 8 probes**. Both find the same
documents; current is slightly cheaper and stricter. Shared may still be
needed for edge cases we haven’t sampled. Recommendation: grow the probe
set to 25–30 and re-decide.

## If asked about the cited-page hit metric being low

Walk through the per-probe evidence table in
[2026-08-20-initial-run.md](./2026-08-20-initial-run.md). Point out that
retrieved page numbers are 1–2 off from expected because of chunk-page
boundaries. Six of eight probes are effective hits with a ±2 tolerance.
