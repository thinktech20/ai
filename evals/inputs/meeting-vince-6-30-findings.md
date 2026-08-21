# Vince meeting — 6/30 findings

Source: [meeting-vince-6-30](meeting-vince-6-30) (raw transcript).
Purpose: capture what Vince said, in his own framing. No recommendations here.

## The four things his test harness is meant to do

Vince framed his POC (`sdg-autotest`) as covering four needs:

1. **Prompt tuning + LLM-driven analysis.** Tweak prompts, run N iters per (ESN, issue, component) cell, see verdict drift, narrate why with an LLM analyzer. Avoids the "looks great on 3 ESNs, breaks on the 4th" trap.

2. **SME heatmap self-service.** The unique part of SDG is that SMEs feed a heatmap directly into prompts. Today the loop is manual: SME uploads to Box → team reviews → integrates. He wants a lighter loop where the SME changes the heatmap, runs 5–10 probes, sees if it improved, and deploys.

3. **Golden dataset + periodic auto-test.** SME feedback is now available as ground truth. He wants a small curated set evaluated against periodically — possibly from CI/CD or on every N changes. Called this out as the one most likely to benefit from Databricks speed.

4. **Prototyping unvetted data.** When data hasn't been through the data-science publish process, a lightweight tool to play with chunk size / overlap / embedding model / top-k on a fresh upload. He said this is not yet built.

## How much of those four is implemented today

Based on his `sdg-autotest` repo:

| # | Item | State |
|---|---|---|
| 1 | Prompt tuning + LLM analysis | Built. `Probe Runner`, `Prompt Lab A/B/C`, `analyzer.py`, `probe_analyzer.py`, test report snapshots. |
| 2 | SME heatmap self-service | Partial. SME label ingestion exists (`tools/load_sme_xlsx.py`) and match-rate scoring against `expected_severity` / `correctness`. The self-service edit-run-deploy loop is not built. |
| 3 | Golden dataset + auto-test | Partial. The match-rate metric and SME-labeled cells exist. No scheduler, no CI/CD trigger, no periodic regression sweep. |
| 4 | Prototyping unvetted data | Not built. His own quote: *"I haven't had that yet but I'll add that."* |

## How he reframed those four mid-call

Halfway through he restated the landscape as three buckets:

1. Data not in Databricks yet → prototyping (his #4).
2. Optimization / experiment over the retrieval layer → "this" (our harness).
3. Full prompt evaluation → already implemented in his tool (his #1).

In that framing, his #2 (SME self-service) and #3 (regression auto-test) got folded into bucket 2 — the part he said *"could be lighter and faster, Databricks might help speed this up."*

## His view of how our two tools relate

- Complementary, not overlapping.
- His tool calls the live Risk-Eval API and judges what the LLM does with retrieved chunks.
- Our tool goes straight to the Vector Search index, tunes retrieval knobs, scales across many ESNs.
- His phrasing: *"both are needed… complimentary… we can use it more for the purpose of the different data, more from how we are chunking it and storing the data, data quality perspective, and then we can go one level up, which is LLM as judge."*
- He also flagged that our tool can *"go across a wider sample of data"* — referring to our 45-ESN probe set sampled from the metadata table.

## The specific failure mode he illustrated

He walked through an SME-flagged failing case: one issue where top-k = 10 returned all 10 chunks from a single chatty FSR, even though other relevant FSRs existed for that ESN. He considered bumping top-k globally to 20 but rejected it because it adds latency for every other (ESN, issue) and may not be needed elsewhere. He said our `max_per_doc` knob is closer to the right shape for this.

## His topmost ask (in response to "what's the most urgent thing")

Quote:

> *"It's not exactly that, but kind of like that — when we do make these changes, it would be fantastic if, let's say I went in and I ran the particular issue 16 or 20 times and got the numbers I wanted. Could I then run some sort of a wider test against everything else to see if that change screwed anything up or not? Maybe this tool could help with something like that."*

In plain terms: after tuning a setting for a specific failing case, run a broad sweep across all other ESNs/issues to confirm nothing else regressed.

## Other things he noted in passing

- **Deployment friction.** Even with a Databricks job, every parameter change today requires raising a ticket through the infra/deploy process. Job-based parameter sweeps are not as straightforward as he'd like.
- **MLflow as the SME-facing surface.** He's comfortable with SMEs (and himself) opening MLflow runs to view parameters and compare. Did not push for a custom UI.
- **PRD exists for his harness.** He mentioned having written a PRD with user stories + acceptance criteria for his tool.
- **LiteLLM key gotcha.** His analyzer forces Claude Opus 4.6 through LiteLLM; need to confirm the dev key has access to those models when running his tool locally.
- **Local-deploy tweaks needed.** A few small changes to the SDG app are needed to run his harness against a local copy. He believes Copilot / Claude Code can apply them; they're documented in his README.
- **Repo access.** He confirmed access has been granted (`260010757/sdg-autotest`).

## Open ambiguities to clarify next time

- What defines a "test case type" for his regression sweep — is the grouping by issue name, by ESN bucket, by chronology, or by some SME-curated tag?
- Where do SME-flagged failing cases live today? Is there a list/table we can ingest as a probe set?
- What is the expected cadence for the regression auto-test — per change, daily, weekly?
- Who owns each side of the integration: does our harness write into his Postgres, or does he read our MLflow runs?
