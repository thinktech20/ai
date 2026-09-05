# ESN Extractor — proposed approach

> **Status:** 2026-05-26 — **direction simplified, Option C below superseded.**
>
> The final design no longer modifies the DS team's LLM prompt at all. The existing P1 metadata LLM call and the page-1 ESN regex ([`_extract_esn_from_page1_text`](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py)) stay exactly as-is. On top of that, P1 runs the **same ESN regex over the first `N=5` pages** of the PDF (config knob, tunable from Phase 0.3 measurement) to build the intermediate `esn_mentions: {esn: count}` map used by the multi-ESN logic. No new LLM call. No prompt change.
>
> Authoritative wording is in [proposed-multi-ESN-design.md §ESN Extraction Method](proposed-multi-ESN-design.md) and open item **O1**.
>
> Everything below this notice is historical context for how we got here (Options A/B/C exploration). Treat it as background, not the design.

---

> **Earlier status (superseded):** Locked in 2026-05-26 — Option C (single P1 LLM call with `esn_mentions` extension). Here, `esn_mentions` is intermediate extraction output, not a stored field. See [proposed-multi-ESN-design.md §Decisions log items 6–9](proposed-multi-ESN-design.md) for how this fits into the final ESN resolution design.
> **Date opened:** 2026-05-06 · **Decided:** 2026-05-26
> **Related:** [../analysis/ds-code-test-results.md](../analysis/ds-code-test-results.md), [../tracker.md](../tracker.md) ESN-04c → ESN-06
> **Scope:** ESN extraction quality only (sub-problem 2 in [../plan.md](../plan.md)). Cardinality (sub-problem 1) is in [proposed-multi-ESN-design.md](proposed-multi-ESN-design.md).

## 2026-05-26 updates layered on this draft

The extractor shape below is unchanged (option C wins). Decisions that close earlier open items in this doc:

- **`fsr_pdf_ref` role:** hint only, never authoritative. Adds lower-rank `esn_details` entries (`esn_source='fsr_pdf_ref'`) when ref-only; merges as `esn_source='llm+ref'` on agreement with body-text. Doesn't override high-confidence body-text ESN.
- **Low-confidence fallback:** no body-text mention reaches `MIN_ESN_COUNT=1` → fall back to page-1 ESN as single `esn_details` entry (`rank=0, esn_source='page1', esn_count=0`) **plus** write DQ row `check_name='esn_low_confidence'`. If page-1 also fails → `metadata_status='failed'`, UI-18 retry path applies.
- **Scan window:** keep the existing P1 body-text window. Don't widen speculatively. Phase 0.3 corpus measurement gates widening (>5% docs with ESNs outside window → revisit).
- **`esn_count` is persisted.** The qualified counts feed directly into the `esn_details[].esn_count` field on the metadata row. Useful for DQ + re-extract tie-breaking; cheap to carry.
- **MIN_ESN_FRACTION:** keep `0.10` as the DS-aligned default. Knob owned in prod config.

## TL;DR

Extend our existing P1 metadata LLM call to also return a body-text ESN count map (`esn_mentions`). `esn_mentions` is intermediate extraction output, not a stored field. The resolver uses it to populate `primary_esn`, `esns`, and `esn_details[].esn_count`, then picks top-1 by count using DS-style threshold `(min_count=1, min_fraction=0.10)`. Fall back to today's page-1 string if the count map is empty. **One LLM call per doc, one prompt, one code path.** No DS code lifted.

## Why this shape

Three options were on the table:

| Option | LLM calls/doc | Picked? |
|---|---|---|
| A. DS `esn_identifier` as **fallback** when ours returns null/redacted | 1–2 | No |
| B. **Replace** our extractor with two LLM calls (ours for non-ESN + DS for ESN) | 2 | No |
| **C. One LLM call, modified prompt** — extend ours to also return `esn_mentions` from body text | **1** | **Yes** |

Reasoning in [../analysis/ds-code-test-results.md](../analysis/ds-code-test-results.md) "Updated decision direction." Short version:

- A. doesn't fix happy-path cases where ours returns a *plausible but wrong* ESN; adds a second code path.
- B. doubles LLM calls (~18K extra) and our prompt still has to stay for non-ESN fields.
- C. is the smallest change that captures DS's value (count-then-threshold over body text) without splitting the path.

## Proposed change to `nb_sdg_fsr_metadata.py`

### Prompt — output schema

Today:
```json
{ "esn": "<page-1 string>", "install_date": "...", "customer": "...", ... }
```

Proposed:
```json
{
  "esn": "<page-1 string, kept as today>",
  "esn_mentions": {"<esn>": <int count>, ...},   // NEW — from body text
  "install_date": "...",
  "customer": "...",
  ...
}
```

### Prompt — input

Today: structured page-1 JSON only.

Proposed: structured page-1 JSON **plus** start+middle+end body-text window (~1000 chars × 3 = 3000 chars, same windowing DS uses in `_prepare_document_text_for_llm`).

### Resolver (replaces L691-721 in `nb_sdg_fsr_metadata.py`)

```python
REDACTED_RE = re.compile(r"^X{4,}$", re.IGNORECASE)
MIN_ESN_COUNT = 1
MIN_ESN_FRACTION = 0.10

def _qualify(counts: dict[str, int]) -> list[str]:
    total = sum(counts.values())
    if total <= 0:
        return []
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [esn for esn, n in ranked
            if n >= MIN_ESN_COUNT and (n / total) >= MIN_ESN_FRACTION]

def resolve_esn(llm_output: dict, page1_esn: str | None) -> str | None:
    counts = llm_output.get("esn_mentions") or {}
    qualified = _qualify(counts)
    for esn in qualified:
        if not REDACTED_RE.match(esn):
            return esn
    if page1_esn and not REDACTED_RE.match(page1_esn):
        return page1_esn
    return None
```

### What this preserves

- All existing metadata fields keep their current shape.
- `esn` field stays as the page-1 string for backwards compat (it just stops being the only signal).
- DS code under `DS-ref-code/` stays untouched as reference.

### What this changes

- One extra output key in the LLM response.
- ~3000 extra chars in the user message (body window).
- Resolver gains ~15 lines (`_qualify` + redaction filter).

## Cardinality (out of scope here, captured for the reader)

This approach surfaces multi-ESN signals naturally — `esn_mentions` is already a count map. The data-shape decision (array column vs join table vs row duplication) is the **other** sub-problem and lives in the cardinality ADR. For the extractor itself, picking top-1 from `esn_mentions` is what gets stored as `esn` today; downstream cardinality work decides what to do with the rest of the ranked list.

## Risks

1. **One prompt does two jobs** — a regression in either field hits the other. Mitigation: validation harness has cohorts for both ESN and full-metadata accuracy; merge gate covers both.
2. **Token budget** — adding ~3000 input chars + one output key. Spot-check on `azure-gpt-5-2`: doc #7 already failed on 4000 output tokens. May need `gemini-3-flash` or 8000-token output.
3. **Hallucination on redacted manuals** — DS recovered `298126`, `0298304`, `297897` on the 4 manual ecrt docs; need spot-check vs PDFs before trusting these as ground truth.
4. **Threshold tuning** — `MIN_ESN_COUNT=1` is *our* choice, not DS-validated. Owns the knob in prod.

## Open items before committing

| # | Item | Blocking? |
|---|---|---|
| 1 | Spot-check 4 recovered ESNs against source PDFs | **Yes** — if hallucinated, approach changes |
| 2 | Reproduce doc #7 with bigger token budget or different model | No, but informs token sizing |
| 3 | Validate approach C on the 14-doc cohort end-to-end | Yes — proof-of-concept before broader |
| 4 | Re-test on a wider sample (~100–200 docs) | Yes — before merge |
| 5 | Decide model: `azure-gpt-5-2` vs `gemini-3-flash` | No, can defer to impl |

## Resume here tomorrow

1. Spot-check `298126` / `0298304` / `297897` against the 4 manual ecrt PDFs (item 1 above).
2. Adapt [../analysis/nb_ds_esn_identifier_smoke_test.ipynb](../analysis/nb_ds_esn_identifier_smoke_test.ipynb) into a new notebook that calls **our** prompt with the proposed `esn_mentions` extension on the same 14-doc cohort.
3. If both pass, promote this draft to an ADR under [../../../internal/adr/](../../../internal/adr/) and move to ESN-05/06/07 in [../tracker.md](../tracker.md).
