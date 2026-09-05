# DS `esn_identifier` smoke-test — results

> **Date:** 2026-05-06
> **Notebook:** [nb_ds_esn_identifier_smoke_test.ipynb](nb_ds_esn_identifier_smoke_test.ipynb)
> **Cohort:** 14 docs (Pranesh 2 + Abhinaya zero-doc 8 + manual ecrt 4)
> **Model:** `azure-gpt-5-2` (via dev litellm gateway, prod key)
> **DS code:** `FSR/ESN-resolution/DS-ref-code/fsr_pipeline_dbr_final/src/esn_identifier.py` — inlined as-is, no edits.

## Headline

### Run A — DS as-shipped (`MIN_ESN_COUNT=5`, `MIN_ESN_FRACTION=0.10`)

| metric | value |
|---|---|
| docs run | 14 |
| LLM call succeeded | 13 / 14 (1 transient empty-content on `34bc62b0…`) |
| `llm_eq_stored` (DS qualified primary == stored) | **1 / 14** (`4b70aab1` only) |
| qualified primary on UUID docs | 1 / 9 — 8 nulls because DS requires `count≥5` and the 3000-char window rarely shows that |
| qualified primary on redacted manual ecrt docs | 3 / 4 (`298126`, `0298304`, `0298304`) — real ESNs in place of `XXXXXX` placeholders |
| top-1 by raw count vs stored (pre-threshold) | matches stored on every successful UUID doc |

**Read-out:** DS-as-shipped is **worse than ours on UUID docs** (8/9 nulls) but **better on redacted manuals** (3/4 recoveries). The LLM output itself is good — the count-≥5 threshold is what blocks the signal. See raw counts in `llm_raw_counts` column of the smoke-test CSV.

### Run B — DS with tuned threshold (`MIN_ESN_COUNT=1`, `MIN_ESN_FRACTION=0.10`)

| metric | value |
|---|---|
| docs run | 14 |
| LLM call succeeded | 13 / 14 (same `34bc62b0…` error) |
| `llm_eq_stored` (DS qualified primary == stored) | **8 / 14** rows; 4 redacted-manual rows are `False` because stored is `XXXXXX` (good outcome, not regression) |
| qualified primary on UUID docs | 8 / 9 — only `d3b1da8a` misses (alpha tiebreak on count-3 vs count-3) |
| qualified primary on redacted manual ecrt docs | 4 / 4 (`298126`, `0298304`, `0298304`, `297897`) |
| `llm_qualified_esns` list size | now noisy — 4-element lists dominated by `SY*` serial numbers and OCR-variant siblings (e.g. `270T434` vs `290T434`) |

**Read-out:** Tuning to `count=1` recovers the happy-path signal that DS-as-shipped throws away. Top-1-by-count is now reliable as a primary ESN. The qualified *list* itself is no longer a clean multi-ESN signal — it accepts everything the LLM saw once. See full numbers below.

## Read-out

The DS LLM **output quality is good** even when DS thresholds reject everything. On every UUID doc that completed, the *top-frequency* ESN in the raw count dict matched the currently-stored ESN. The DS-as-shipped post-filter (`_qualify_esn_counts` with `count≥5`) discards most of that signal because the LLM only sees a 3010-char prepared window where most ESNs appear 1-2 times.

For redacted manual ecrt docs, the DS LLM extracted what look like real ESNs in place of the `XXXXXX` placeholders — directly addresses the redacted-ESN failure mode if confirmed.

## Per-doc detail

### Run B — `MIN_ESN_COUNT=1`, `MIN_ESN_FRACTION=0.10` (the tuned run, used as basis for approach C)

| # | doc | stored | DS top-1 (qualified primary) | DS qualified list | `llm_eq_stored` | notes |
|---|---|---|---|---|---|---|
| 1 | d3b1da8a… | 336X233 | **335X281** | [335X281, 336X233, 335X238] | ✗ | tie at count 3 — alpha tiebreak picks wrong; stored is in the list at #2 |
| 2 | 3ef8d150… | 297843 (fsr_pdf_ref) | **297843** | [297843, 338X427, SY0070003, SY0071760] | ✓ | qualified list noisy with `SY*` serials |
| 3 | 913433ad… | 270T434 | **270T434** | [270T434, 290T434, SY0072675, SY0073345] | ✓ | OCR-sibling `290T434` in list |
| 4 | c020379c… | 270T577 | **270T577** | [270T577, 290T577, SY0073404, SY0525301] | ✓ | |
| 5 | 03d3bef2… | 270T658 | **270T658** | [270T658, 290T658, SY0097043, SY0528010] | ✓ | |
| 6 | 36de1c13… | 297905 | **297905** | [297905, 337X233, SY0071425, SY0073079] | ✓ | |
| 7 | 34bc62b0… | 297843 | — | — | error | empty `message.content` (token budget on `azure-gpt-5-2`) |
| 8 | 348ddaa2… | 297898 | **297898** | [297898, 338X714, SY0048123, SY0097358] | ✓ | |
| 9 | 4b70aab1… | 298374 (fsr_pdf_ref) | **298374** | [298374, 761X004] | ✓ | genuine multi-ESN, both count 5 |
| 10 | d5334dce… | 297897 (fsr_pdf_ref) | **297897** | [297897, 338X713] | ✓ | tied at count 2, alpha tiebreak lands on stored |
| 11 | 090dbba1800f4f5b | XXXXXX | **298126** | [298126, 270T6, 337X305] | ✗ (good) | redacted in store, real ESN extracted |
| 12 | 090dbba18003a23c | XXXXXXX | **0298304** | [0298304] | ✗ (good) | |
| 13 | 090dbba180100488 | XXXXXXX | **0298304** | [0298304] | ✗ (good) | |
| 14 | 090dbba1800b5e28 | XXXXXX | **297897** | [297897, 338X713] | ✗ (good) | |

**Summary:** primary == stored on **8/9** UUID docs (only `d3b1da8a` lost on alpha tiebreak); plausible real ESN recovered on **4/4** redacted manuals.

### Run A — `MIN_ESN_COUNT=5`, `MIN_ESN_FRACTION=0.10` (DS as shipped, kept for reference)

Same raw counts, stricter threshold. Most rows show `qualified=[]` and `primary=null`.

| # | doc | stored | raw top-1 | DS qualified | match (top-1) | notes |
|---|---|---|---|---|---|---|
| 1 | d3b1da8a… | 336X233 | **336X233** | [] | ✓ (raw) | 10 candidates, top tied 3-3 |
| 2 | 3ef8d150… | 297843 | **297843** | [] | ✓ (raw) | |
| 3 | 913433ad… | 270T434 | **270T434** | [] | ✓ (raw) | |
| 4 | c020379c… | 270T577 | **270T577** | [] | ✓ (raw) | |
| 5 | 03d3bef2… | 270T658 | **270T658** | [] | ✓ (raw) | |
| 6 | 36de1c13… | 297905 | **297905** | [] | ✓ (raw) | |
| 7 | 34bc62b0… | 297843 | — | — | error | empty `message.content`, token budget |
| 8 | 348ddaa2… | 297898 | **297898** | [] | ✓ (raw) | |
| 9 | 4b70aab1… | 298374 | **298374** | [298374, 761X004] | ✓ | genuine multi-ESN signal |
| 10 | d5334dce… | 297897 | **297897** | [] | ✓ (raw) | tied 2-2 with 338X713 |
| 11 | 090dbba1800f4f5b | XXXXXX | **298126** | [298126] | placeholder vs real | redacted in store, real in DS |
| 12 | 090dbba18003a23c | XXXXXXX | **0298304** | [0298304] | placeholder vs real | |
| 13 | 090dbba180100488 | XXXXXXX | **0298304** | [0298304] | placeholder vs real | |
| 14 | 090dbba1800b5e28 | XXXXXX | **297897** | [] | placeholder vs real | |

## Decision (ESN-04c)

**Do not modify the DS code.** Use it as a black-box reference to compare against our own extractor.

### Next step — compare DS LLM output vs our UI-07 LLM-count extractor on the same cohort

Goal: see whether **our existing extractor** ([pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) — `SYSTEM_PROMPT` L370-410 + `_extract_esn_from_page1_text` regex L449-462 + resolver L691-721) already produces the correct ESN on these 14 docs, or whether it suffers the same null/redacted failures.

Two sub-questions to answer:
1. **Does our prompt + regex resolver recover the correct ESN on the 9 succeeded UUID docs?** (DS code did — top-1 match 9/9.)
2. **Does our resolver correctly suppress `XXXXXX`/`XXXXXXX` and fall back to a real ESN on the 4 manual ecrt docs?** Today it doesn't — see L694: `resolved_esn = llm_esn or page1_esn`, with no redaction filter; any non-empty LLM string wins. Need to confirm what our LLM actually returns on those 4 docs.

If our extractor matches DS quality on the 9 UUID docs but fails on the 4 redacted manuals, the fix becomes a tiny resolver patch (treat `^X{4,}$` as null → fall through to page1/IBAT) — no need to lift any DS module.

If our extractor is significantly worse than DS on UUID docs, then we lift the DS LLM call and counts logic.

### Open question for doc #7 (`34bc62b0…`)

Reproducible empty-content on `azure-gpt-5-2`. Worth one repro with `max_completion_tokens=8000` or `gemini-3-flash` to confirm it's a token issue, not a content-filter issue. Tracking under ESN-04c.

## What this does **not** test

- Recall on docs where the stored ESN is **wrong** (we have no ground truth here — top-1-match assumes stored is correct, which is true for UUID docs but explicitly false for the 4 manual ecrt redacted ones)
- Cardinality (many-to-many ESN↔doc) — only 1/14 docs (`4b70aab1`) shows a multi-ESN signal here
- Behaviour on the >18K corpus — this is a 14-doc pilot

## Follow-up findings (2026-05-06)

### 1. DS extractor is document-level, not chunk-level

Confirmed via the module docstring at the top of [esn_identifier.py](../DS-ref-code/fsr_pipeline_dbr_final/src/esn_identifier.py):

> "one document-level LLM count call with uniform chunk tags. The document is analyzed once, qualified ESNs are selected using the global count and fraction thresholds, and every chunk in the document receives the same ESN label set."

Architecturally the same as our pipeline (extract once per doc → propagate to all chunks). The chunks are an *input* to `identify_esns()`, not the unit of LLM extraction. The LLM never sees individual chunks. So the comparison vs our pipeline is apples-to-apples on extraction granularity; the differences are *mechanism* and *input*:

| | our pipeline | DS `esn_identifier` |
|---|---|---|
| Extraction unit | document (P1 metadata step) | document (full text → 3-window) |
| LLM calls / doc | 1 (full metadata extraction) | 1 (ESN-only count) |
| Input to LLM | structured JSON from page-1 fields | raw text, start+middle+end windows |
| Decision rule | single LLM string + page-1 regex fallback | count map + (`MIN_ESN_COUNT`, `MIN_ESN_FRACTION`) thresholds |
| Propagation to chunks | P2 chunking copies `esn` into 3 places | `identify_esns()` writes uniform labels onto every chunk |

### 2. DS POC code is the direct ancestor of our metadata extractor

`DS-ref-code/ds-team-docs/FSR Scraping POC/FSR SCraping Code/normalize_json_llm_comb.py` is the original source of our `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py`:

- Same `SYSTEM_PROMPT`
- Same `NORMALIZATION_PROMPT_SUFFIX`
- Same `COLUMN_MAP`

So our metadata path **is** the DS POC scraping code, just productionised. The new piece in `esn_identifier.py` is the **count-then-threshold ESN-only extractor**, not a different prompt for full metadata.

### 3. Only two knobs that change DS behaviour

Of all the constants in `esn_identifier.py`, the two that materially change qualified output on our cohort are:

- `MIN_ESN_COUNT` (default 5)
- `MIN_ESN_FRACTION` (default 0.10)

With DS defaults: only 3/14 docs get a qualified primary because the prepared 3000-char window rarely shows an ESN ≥5 times.

With `MIN_ESN_COUNT=1` (keeping fraction at 0.10) — measured run, see Run B per-doc table above:
- Qualified primary == stored ESN on **8/9** successful UUID docs (one alpha-tiebreak loss on `d3b1da8a`).
- Qualified primary == real ESN on **4/4** redacted manual ecrt docs.
- Qualified *list* becomes noisy — 4-element lists dominated by `SY*` serials and OCR-variant siblings (e.g. `270T434` vs `290T434`). Top-1 is still the right primary, but the list itself isn't a clean multi-ESN signal at this threshold.

The other constants (`DOC_TRUNCATE_WINDOW_CHARS=1000`, `DOC_MAX_LLM_CHARS=3000`, model, retries) don't move outcomes on this cohort.

### 3a. Tiebreaker matters

DS sorts qualified ESNs by `(-count, alpha)`. On `d3b1da8a` the LLM returned `336X233:3` and `335X281:3` co-tied; alpha sort picks `335X281`, missing the stored `336X233`. The right answer is in the qualified list at position 2.

Implications for approach C:
- Pure top-1-by-count is right 8/9 on UUID docs. A single tiebreaker rule could fix the 9th.
- Candidate tiebreakers: (a) prefer ESN that also appears in `current_stored_esn` / `fsr_pdf_ref` if present, (b) prefer ESN whose pattern matches the dominant equipment family in the doc, (c) accept the loss as a known edge.
- Don't over-fit the rule to one cohort doc — revisit after the wider sample run.

### 4. Companion notebook — our regex on the redacted cohort

[nb_our_extractor_redaction_check.ipynb](nb_our_extractor_redaction_check.ipynb) runs **our** `_extract_esn_from_page1_text` regex (from `nb_sdg_fsr_metadata.py`) over the same 14 docs.

- On the 4 manual ecrt docs (stored = `XXXXXX` / `XXXXXXX`), our regex returns the same redacted placeholder it scraped originally — no recovery.
- DS LLM on the same 4 docs returns plausible real ESNs (`298126`, `0298304`, `297897`).

This is the clearest signal that **DS extractor adds value specifically on redacted-page-1 docs**, where our regex/JSON path has nothing real to latch onto but the body text still mentions the real ESN.

## Updated decision direction (ESN-04c)

### Approach: one LLM call, modified prompt — not a fallback, not two calls

Walked through three options:

| Option | LLM calls/doc | Pros | Cons |
|---|---|---|---|
| A. Lift DS as a **fallback** (only when ours returns null/redacted) | 1 or 2 | Lowest blast radius; ours stays primary | Two code paths; doubles call cost on fallback docs; doesn't fix happy-path quality |
| B. **Replace** ours with two LLM calls (ours for non-ESN metadata + DS for ESN) | 2 | Clean separation; easy to A/B the ESN extractor | Doubles LLM calls for the whole corpus; harder runbook |
| C. **One LLM call, modified prompt** — extend our existing metadata prompt to also return `esn_mentions: {esn: count}` from body text | 1 | Single call; same code path; resolver picks top-1 by count with `MIN_ESN_COUNT=1` | Owns one prompt that does two jobs; need to add body-text window to the user message |

**Going with C.** Our existing `nb_sdg_fsr_metadata.py` already extracts all metadata fields in one call from structured page-1 JSON — adding one more output key + a body-text window in the input is the smallest change that captures DS's value (count-then-threshold over body text) without doubling LLM cost or splitting the code path.

### Why not replace fully (option B)

- Our metadata prompt covers **all fields** (install_date, customer, site, unit, work_order, …); DS `esn_identifier` is ESN-only. Replacing means we still need our prompt for everything else.
- Our metadata prompt **is** the DS POC scraping code (same SYSTEM_PROMPT / NORMALIZATION_PROMPT_SUFFIX / COLUMN_MAP). Replacing is misleading framing — we're swapping the *ESN-only path* from "single page-1 string" to "count-then-threshold over body text."
- Cost: ~18K corpus → 18K extra LLM calls if we go two-call.

### Why not fallback (option A)

- Doesn't help happy-path docs where our extractor is also "good enough" but DS surfaces multi-ESN signals (e.g. doc #9: `[298374, 761X004]`).
- Two code paths, two failure modes — harder runbook.
- Fallback only triggers on `null` / `^X{4,}$` — misses cases where our LLM returns a *plausible but wrong* ESN (Pattern A OCR `9→7`, etc.).

### Concrete shape of the prompt change

Today output:
```json
{ "esn": "<page-1 string>", "install_date": "...", ... }
```

Proposed output:
```json
{
  "esn": "<page-1 string as today, kept for backwards compat>",
  "esn_mentions": {"<esn>": <count>, ...},   // NEW — body-text count map
  "install_date": "...",
  ...
}
```

Resolver (~15 lines):
1. If `esn_mentions` non-empty → apply `_qualify_esn_counts(min_count=1, min_fraction=0.10)` → take top-1.
2. Else fall back to `esn` (page-1 string) as today.
3. Strip redacted placeholder `^X{4,}$` at both stages.

Input change: pass page-1 JSON **plus** start+middle+end body window (~3000 chars, same as DS) in the user message.

DS code stays untouched as reference; we lift only the ~15 lines of count-and-threshold logic into our resolver.

## Prod ESN-quality measurement (2026-05-07)

Ran the bucket query from [validation/nb_02_metadata_check.ipynb](../../../fsr-prod-ops/validation/nb_02_metadata_check.ipynb) §5 against prod `vaip.ai_sot_field_service_report.biz_metadata_field_service_report` (18,029 `metadata_status='completed'` docs).

### Bucket counts

| bucket | rule | docs | % |
|---|---|---|---|
| `00_null_or_empty` | `IS NULL OR =''` | 5 | 0.03% |
| `01_redacted_X` | `^X+$` | **0** | 0% |
| `02_alphanum_NNNANNN` | `^[0-9]{3}[A-Z][0-9]{3}$` (e.g. `270T434`) | 2,904 | 16.11% |
| `03_numeric_6_7_digits` | `^[0-9]{6,7}$` (e.g. `297843`) — looks-real format | 12,349 | 68.50% |
| `04_numeric_lt6` | `^[0-9]{1,5}$` — **suspect Pattern C** | **166** | 0.92% |
| `05_numeric_gt7` | `^[0-9]{8,}$` — suspect | 2 | 0.01% |
| `06_other_alphanum` | other 4-12 char `[A-Z0-9]` | 2,334 | 12.95% |
| `07_other` | everything else | 269 | 1.49% |

### Pattern C confirmed in prod

Sampled 50 rows from the `04_numeric_lt6` bucket. The pattern is unambiguous:

- **Sequential clusters** — `10872` (×2), `10873` (×2), `10874` (×2), `26888`, `26891`, `26892` … sequential numbers across distinct docs. These look like work-order or case-ID sequences mis-classified as ESN.
- **Multi-doc duplicates** — same value spans multiple FSRs, e.g. `5928` (2 docs), `9802` (2 docs), `13933` (3 docs), `17872` (3 docs), `19430` (2 docs), `26888`-`26892` (sequential block), `44198` (2 docs), `46452` (2 docs), `53767` (2 docs), `54148` (2 docs). Suggests project / IBAT IDs.
- **Dual-source agreement** — `1083`, `10856`, `43561` are stored under both `llm` AND `fsr_pdf_ref`. Both extraction paths agree on the wrong value, which means the wrong value is literally written on page 1 of the PDF in the ESN field. **This is data-entry / template upstream, not LLM hallucination.**

Approach C body-text mechanism is the right fix: if `1083` is a case ID written once on page 1 but the body mentions a real ESN like `297843` six times, `esn_mentions` ranks the real ESN at top-1.

### Suspect docs with template-style IDs

Three sample rows have `document_id`s like `2_v1.0`, `3_v1.0`, `090dbba1800f08e2` mapped to manual ecrt files `2_V1.0.pdf` / `3_V1.0.pdf`. Likely sample/test PDFs that shouldn't be in prod. Hygiene issue separate from extraction quality — tracked under ESN-04i.

### Implications for approach C

- **Redaction (`XXXXXX`) is dev-only-for-now.** Zero in prod. The redacted-doc story still matters as the dev test bed for the body-text mechanism — but it is **not the rollout-blocking pain in prod**.
- **Pattern C scope in prod is ~166 docs (0.92%)** in the `<6` digit bucket, plus possibly more inside the 12,349 6-7 digit bucket — needs spot-check (ESN-04h).
- **The 84.6% in confident-shape buckets (`02` + `03`) is mostly fine.** `297843` style 6-digit ESNs verified real in our 14-doc cohort. The 6-7 digit bucket has a long tail of suspects, not a corpus-wide failure.
- **Reframing the design draft:** earlier framing was "approach C fixes redacted + Pattern A/B/C across ~12K docs." Prod numbers shrink that to "approach C fixes ~166 confirmed Pattern C cases + unlocks multi-ESN signal for cardinality work." Still worth doing — smaller scope, cleaner success criteria.

## Open items

1. **Spot-check 4 recovered ESNs** (`298126`, `0298304`, `297897`) against the source PDFs to confirm they're real, not hallucinated. **Blocker for committing to approach C.** (ESN-04d)
2. **Reproduce doc #7** (`34bc62b0…`) with `max_completion_tokens=8000` or `gemini-3-flash` to rule out content-filter vs token budget. (ESN-04f)
3. **Draft the prompt change** against [nb_sdg_fsr_metadata.py](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py) — write up in [../design/1-esn-extractor-method.md](../design/1-esn-extractor-method.md).
4. **Validate approach C on the 14-doc dev cohort** before broader rollout — adapt the smoke-test notebook to call our prompt + the proposed `esn_mentions` extension and re-run. (ESN-04e)
5. **Validate approach C on prod Pattern C cohort** — pick 10 docs from the 166 (mix of sequential, multi-doc-duplicate, dual-source-agreement) and run through smoke notebook with `MIN_ESN_COUNT=1`. (ESN-04g)
6. **Spot-check the 6-7 digit bucket** — random 20 docs vs PDFs to confirm 12,349 isn't masking widespread Pattern C in the looks-real range. (ESN-04h)
7. **Investigate template-id manual ecrt rows** (`2_V1.0.pdf`, `3_V1.0.pdf`) — confirm whether these belong in prod. (ESN-04i)

