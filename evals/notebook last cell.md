notebook last cell
   └── run_eval(...)                                      (harness.py)
          └── for each of 45 probes:
                 └── ThinRetriever.query(query, esn)      (retriever.py)
                        ├── embedder.embed(query)         → LiteLLM gateway (1 call)
                        └── index.similarity_search(...)  → Databricks VS (1 call)

                        "Your harness measures what the LLM does with the chunks it gets. Mine measures what the chunks look like before the LLM sees them. If your verdicts drift and my retrieval is stable, the cause is the LLM. If my retrieval drifts, your verdicts will never be stable no matter what prompt you write. We need both."



What he has that we don't
Live-service integration — he calls the real risk-eval service, so his chunks are exactly what production sees.
Iter-level persistence — every chunk, every probe, every iter, in Postgres. We dump to MLflow artifacts; he has a queryable DB.
LLM-as-judge — Claude reads chunks + verdicts and writes diagnoses.
A UI — FastAPI + static frontend.


What we have that he doesn't
Tunable retrieval knobs — top_k, max_per_doc, (quality_threshold); his are fixed by the service.
Direct VS access — no service dependency, faster, cheaper.
A coverage-vs-known metric — we can score retrieval quality without SME labels.
MLflow — comparison view that scales to dozens of configs without writing a UI.

That's why our two pieces dovetail well — if he wants to ask "would a different retrieval config change my verdicts?", he can't answer it today. We can.