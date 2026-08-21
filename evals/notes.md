Problem
Unit Risk Matrix (URM) risk assessments are non-deterministic — the same generator, same corpus, same prompt produces different answers across runs. Business users can't trust the tool, and we're at risk of getting "put in a corner" (Vince's words) before we even go live.

Underneath that single user-visible symptom, there are at least three independent failure surfaces stacked on top of each other, and right now we have no way to tell which one is firing on any given bad run:

Retrieval layer (FSR vector index).

Top-K=10 homogeneity — all 10 chunks come from one large FSR, so other relevant FSRs for the same unit are silently missed.
Corpus jumped 8K → 50K+ FSRs, which changes neighbor density and amplifies the homogeneity problem.
OCR garbage from tables/images is in the index as "valid" chunks and steals top-K slots.
Generation layer (LLM-as-judge / risk synthesis).

LiteLLM proxy was silently downgrading to a weaker model for some calls (Vince's "40-something problems"). May or may not be fully fixed.
LLM-as-judge ceiling is ~60–70% accuracy even when everything works. We have no calibrated number for our judge.
Data quality of the source itself (FSR + TIL).

Chunk-level: OCR artifacts, table/image regions.
Coverage-level: "is every FSR for this unit actually represented and retrievable?" — the two/three-way check Vince asked for.

The deeper problem is we ship changes blind. There's no regression harness, no golden set, no per-run scorecard. So a fix to chunking, a prompt tweak, or a model swap all look the same from the outside — we just hope the next user report is better.

Questions before I recommend a direction
A few things I want to pin down so the eval work lands in the right place and doesn't get rebuilt in 6 weeks:

Scope for v1 eval — URM end-to-end, or layer-by-layer first? My instinct is layer-by-layer (retrieval evals, generation evals, then end-to-end), because an end-to-end pass/fail won't tell us which layer to fix. Do you want me to propose both and we pick, or go straight to layered?

Golden / labeled set — does one exist? Vince ran 16 iterations Saturday — were those against a fixed set of units with known-correct answers, or just spot-checks? If we have even 20–50 units with SME-validated "this is the right risk assessment, here are the FSRs that should drive it," that's the single highest-leverage asset we can build on. If not, getting Jamal's team to label ~30 units is the first ask.

Who is the judge? Are we OK with LLM-as-judge (with the 60–70% caveat Vince called out) for the bulk of eval, and SME spot-check on a smaller slice? Or does the customer want SME-in-the-loop for every eval run?

TIL — is the schema/extraction frozen enough to start writing evals against, or still moving? If extraction prompts are still churning weekly, eval thresholds will churn too. We can build the harness now and tune gates later.

Where does this run — same workspace/catalog as FSR, or a separate eval schema? I'd lean separate (e.g. vaid.ai_eval_field_service_report.*) so eval tables don't get tangled with prod ingestion tables.

Recommendations
A layered eval program. Three layers, one harness, MLflow as the system of record. I'm not recommending Model Serving yet — see point 4 below.

1. Build the golden set first (non-negotiable, week 1)
Pick 25–40 units that Jamal's team already cares about. For each, SME labels:
The "correct" risk level / key findings.
The 3–10 FSRs (and ideally the TIL applicability calls) that should have driven that answer.
Land it as a Delta table — vaid.ai_eval_field_service_report.urm_golden_set_v1 — versioned, with golden_set_version column. Every eval run pins to a version.
This is the single artifact that makes everything else possible. Without it, every other metric is vibes.
2. Retrieval evals (addresses Vince's top-K homogeneity + "no FSRs missed" ask)
Run as a Databricks workflow (sibling job to pw_sdg_fsr_ingestion), nightly or on-demand. For each golden unit, query the FSR vector index with the same prompts URM uses, then compute:

Recall@K — of the SME-labeled "should-have-retrieved" FSRs, how many showed up in top-K. This directly measures the two/three-way check Vince asked for.
Source diversity / chunks-per-document at K — catches the homogeneity bug (if k=10 returns 10 chunks from 1 FSR, score = bad).
Coverage — for each unit in the corpus, is any chunk retrievable? Run a per-unit probe; flag units with zero retrievable chunks. This is the "no FSRs missed going forward" check, run continuously.
Chunk health — % of top-K chunks that are OCR garbage (cheap heuristic: char-class ratio, table-fragment regex, or a small LLM classifier). Track as a trend, not a gate.
Log everything to MLflow as one experiment per run (fsr_retrieval_eval), with the golden-set version, index name, embedding model, and Top-K as params, and the metrics above as metrics. Tags so we can diff: prompt change, chunk-size change, model swap.

3. Generation / URM end-to-end evals (addresses Vince's "test harness" + LLM-as-judge concern)
Replay URM on each golden unit, capture the answer.
Score with two judges in parallel:
Deterministic checks — does the answer cite at least N distinct FSRs? Does it mention the unit's actual ESN? Cheap, fast, catches the LiteLLM-downgrade class of bugs immediately.
LLM-as-judge — calibrated against the SME labels on the golden set, so we have a real accuracy number for the judge (not the 60–70% folklore number). Use a strong model (GPT-4 class) and a fixed rubric; pin temperature.
Run nightly + on every prompt/model change. MLflow experiment urm_e2e_eval.

4. MLflow now, Model Serving later
MLflow tracking + Evaluate now — gives us experiment history, metric trends, and side-by-side run comparison. This is the leverage piece.
Lakehouse Monitoring on the eval tables — set thresholds (Recall@10 < 0.7 → alert, source-diversity drops > 20% week-over-week → alert).
Model Serving / online eval — defer. URM isn't a served model we own; it's an agent stack. Serving makes sense once we wrap the agent and want online quality signals from real users. For "are business users stuck," batch evals on golden + corpus probes are higher ROI and ship faster.
5. Where it plugs in per pipeline
FSR (already live, can't disrupt ingestion):

New sibling workflow pw_sdg_fsr_eval.yml — reads the existing fsr_chunk_table and fsr_vs_index, writes to a new fsr_eval_results table, logs to MLflow. Zero changes to the ingestion job.
Add a post-P2 step that emits chunk-health metrics (OCR-garbage %, table-fragment %, avg chunk length) to a new fsr_chunk_quality table. Trend, don't gate — gating risks blocking ingestion on noisy signal.
Treat Vince's "two/three-way check" as the corpus coverage probe above — run daily, alert on any unit that goes from "retrievable" to "not retrievable."

TIL (still being built — bake it in now, much cheaper):

Add a P5 til_eval task to pw_sdg_til_metadata.yml alongside the existing validation/evaluation stubs in the design.
Two eval modes from day one:
Per-element extraction eval — for each TIL field, compare against SME-labeled fields on a small TIL golden set. Use MLflow Evaluate.
Pipeline self-consistency — re-run extraction on N% of TILs and measure answer drift run-over-run. This catches the same "non-deterministic" symptom URM is hitting, but at the source. Cheap insurance.
Use the same eval-results schema as FSR (til_eval_results) so dashboards are unified.
6. Ordered plan (rough)
Get SME labels for 25–40 URM units → golden set v1. (gating everything else)
Stand up retrieval eval job against FSR index → baseline numbers for Recall@10, source diversity, coverage. Share with Vince — this is what unblocks his "2000% improvement potential" claim with real data.
Stand up URM end-to-end eval with deterministic + LLM-judge.
Wire MLflow + monitoring alerts.
Bake equivalent eval into TIL P5 before TIL goes live.

If this direction looks right, tell me which question above to answer first (golden set is the critical path) and I'll start scaffolding the eval workflow and table schemas.

====

Got it — read both files. The Tao note is clear in intent (reach out to Vince, don't build in parallel, propose something concrete) and the deep-dive doc already proposes fixes (per-doc cap, MMR, IBAT expansion, quality scoring). What's missing — and what Vince actually asked for — is the harness that tells us if those fixes work.

Here's a tight proposal you can take into the Vince conversation.

The reframe
You're right that this is fundamentally a FSR retrieval problem, not a generation problem. And the deep-dive doc already lists the candidate fixes. So the gap isn't "what to change" — it's:

"If I flip on per-doc-cap, or IBAT expansion, or quality filtering — how do I prove it made things better without waiting weeks for SME labels?"

That's a reference-free retrieval test harness. We can absolutely build it without a golden dataset. The golden set makes it sharper later; it's not a prerequisite.

The proposal — retrieval test harness v1 (no golden set needed)

Core idea
Pick a fixed set of ~50–100 ESNs from the existing biz_metadata_field_service_report table — call it the probe set. The metadata table itself becomes our partial "truth" (it tells us which FSRs exist for each ESN, even if not which are most relevant).

For each ESN in the probe set, run the same query against:

Version A (current retrieval) → record results
Version B (current + per-doc cap, or + IBAT, or + quality filter…) → record results
Score each run on metrics that don't require human labels:

Score each run on metrics that don't require human labels:

Metric	What it measures	Why it works without ground truth
Distinct FSRs in top-K	Direct fix for top-K homogeneity	Higher = better diversity. No label needed.
Coverage vs metadata	# unique FSRs retrieved / # FSRs that exist in metadata for this ESN	Metadata table tells us the ceiling. This is the "no FSRs missed" check Vince asked for.
Zero-result rate	% of probe ESNs returning 0 chunks	Lower is better. Catches the GT/Generator/ST tagging gap.
Chunk-quality score (avg, p10)	Avg quality of returned chunks	Catches OCR garbage in results. Score function already drafted in the deep-dive doc.
ESN grounding %	% of returned chunks whose text actually mentions the queried ESN	Catches false-presence chunks from the multi-ESN duplication issue.
Latency p50/p95	Cost of any over-fetch / reranking changes	Guardrail metric.
How A/B comparison works
Every run logs to MLflow as one experiment per probe — params (retrieval_version, top_k, max_per_doc, ibat_expansion=on/off, etc.) + the metrics above. Then v1 vs v2 is a one-screen comparison. This is exactly the "version 1 result / version 2 result" pattern Tao described.


How A/B comparison works
Every run logs to MLflow as one experiment per probe — params (retrieval_version, top_k, max_per_doc, ibat_expansion=on/off, etc.) + the metrics above. Then v1 vs v2 is a one-screen comparison. This is exactly the "version 1 result / version 2 result" pattern Tao described.

What it looks like operationally
One notebook + one Delta table (fsr_retrieval_eval_runs), no model serving needed. Vector index is already the endpoint we test against.
Probe set is a Delta table (fsr_retrieval_probe_set_v1) — initially seeded from biz_metadata via stratified sample (mix of: ESNs with 1 FSR, ESNs with 10+ FSRs, GT ESNs known to have generator siblings, OCR-heavy ESNs from Vince's testing).
A "configurable retriever" function that takes flags (per_doc_cap, mmr, ibat_expand, quality_filter) — so the same harness compares any combination without code changes.
One job, runnable on demand — every retrieval change gets a run; MLflow shows the delta.
What we get on day 1 (before any fix lands)
A baseline scorecard of current retrieval — "today, for these 100 ESNs, retrieval returns avg 1.4 distinct FSRs out of 6.2 available; 17% return zero results; avg chunk quality 0.62." That alone is gold for the Vince conversation — it puts numbers on what's currently anecdotal.

Where the golden set fits later
When SME labels arrive, we add two more metrics — Recall@K (% of must_cite FSRs in top-K) and MRR — to the same harness. Same plumbing, sharper signal. So no rework.

Why I'd hold the "use Model Serving" instinct
You floated model serving — for this specific problem I'd skip it for now. The thing under test is the vector index, and the index already is an endpoint. Wrapping it in a served model adds infra without changing what we measure. Serving makes sense later when we want to monitor URM in production with live user traffic — different problem.

Suggested next move
Send the note to Vince today.
While waiting, I can scaffold the harness — the probe-set query against biz_metadata, the metric functions, the MLflow logging, and one example A/B (current retrieval vs current + per-doc-cap=3 from the deep-dive doc). That's roughly a day of work and gives us something concrete to show in the next sync.
Want me to go ahead and scaffold it, or wait for Vince's reply first?

