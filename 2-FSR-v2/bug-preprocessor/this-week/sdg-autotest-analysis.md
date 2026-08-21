# sdg-autotest — Analysis & FSR Usage Notes

## What it does

`sdg-autotest` is a UI-driven, DB-backed testing harness for the **SDG Risk Evaluation Assistant**. It drives the existing `risk-eval` service over HTTP rather than reimplementing any pipeline logic.

Six features:

| Feature | What it does |
|---|---|
| **Probe Runner** | Runs N iterations of `/run-single` against risk-eval; live SSE stream + per-iter persistence. Good for checking determinism / variance. |
| **Prompt Lab (A/B/C)** | Primes FSR/ER chunks once, then replays with up to 3 swapped prompts. Chunks are frozen across variants — only the prompt changes. Supports per-variant temperature, reasoning effort, top-K FSR/ER slicing. |
| **Ground Truth** | SME labels loaded from `SME-feedback-analysis.csv`; scores run results against expected severity. |
| **Retrieval Inspector** | Per-iter FSR/ER chunk view + Jaccard heatmap across iters. Shows how stable retrieval is across runs. |
| **Test Reports** | Write-once frozen snapshots of a lab run (all prompts, all iters, scoring vs SME label). Downloadable as a single JSON. |
| **LLM Prompt Analyzer** | Passes the frozen report to a LiteLLM model and gets structured suggestions for improving the system/user prompt. |

Stack: FastAPI + Postgres 16 + pgvector. SPA frontend (vanilla JS, no build step). No ORM — raw SQL only.

---

## How to run it

### Prerequisites

1. **Main SDG stack must be running** — `docker compose up -d` in the SDG repo. This brings up `risk-eval:8082`, the LiteLLM proxy, and the `sdg_default` Docker network.
2. **`run-single` endpoint must exist** in `risk-evaluation-assistant` — it's a custom endpoint added in the local fork (see `risk_assessment_creation_api.py`). Without it, nothing except Ground Truth works.

### Steps

```bash
# 1. Copy and fill env
cp .env.example .env
# Fill in: LITELLM_BASE_URL, LITELLM_API_KEY, HTTP_PROXY/HTTPS_PROXY as needed
# RISK_EVAL_BASE_URL defaults to http://risk-eval:8082 (correct when joined to sdg_default network)

# 2. Start the harness
make up
# → API at http://localhost:8001/
# → Docs at http://localhost:8001/docs

# 3. (Once) Load SME ground truth labels
make load-sme
# Reads docs/SME-feedback-analysis.csv (or use load_sme_xlsx.py for xlsx)

# 4. Open the UI
open http://localhost:8001/
```

### Network note

`docker-compose.yml` joins the external `sdg_default` network so `http://risk-eval:8082` resolves. If the SDG stack uses a different project name, check `docker network ls` and update `networks.sdg.name` in `docker-compose.yml`.

### Useful Makefile targets

| Command | Purpose |
|---|---|
| `make up` | Start api + postgres |
| `make down` | Stop |
| `make clean` | Stop + drop postgres volume (fresh DB) |
| `make logs-api` | Tail API logs |
| `make shell-db` | psql into the DB (for manual schema tweaks) |
| `make load-sme` | Load SME CSV into `sme_labels` |

---

## Using it for FSR testing

The **Prompt Lab** is the primary tool for FSR-related testing.

### Typical workflow

1. **Pick an ESN + issue + component** — the lab calls `/run-single`, which filters the heatmap to that single cell and fetches FSR/ER chunks from Databricks.
2. **Prime retrieval** — the first call fetches and freezes FSR/ER chunks. All subsequent variant replays use the same chunks, so retrieval variance is eliminated.
3. **Define prompt variants A/B/C** — swap system prompt and/or user prompt template. Variants can also differ in model, temperature, reasoning effort, and top-K chunk count.
4. **Run the lab** — each variant runs N iters of LLM calls with the frozen chunks inline in the prompt override.
5. **Inspect results** — severity distribution per variant, parse-ok rate, token counts, per-iter raw responses.
6. **Score vs ground truth** — if a matching SME label exists, match rate against expected severity is computed per variant.
7. **Freeze a test report** — `POST /api/reports/from-lab/{run_id}` creates a write-once snapshot with everything: prompts, iters, chunks, scoring. Downloadable as JSON for offline analysis or sharing.
8. **Run the analyzer** — sends the frozen report to the LLM and gets structured suggestions for improving the system/user prompt.

### What it's useful for in FSR-v2

- **Prompt iteration**: test prompt changes against a fixed evidence set without re-running retrieval.
- **Regression checks**: freeze a report against known SME labels; re-run after a prompt change and compare match rates.
- **Retrieval stability**: Retrieval Inspector + Jaccard heatmap shows how consistently the same FSR chunks come back across iterations.
- **Top-K sensitivity**: vary `top_k_fsr` / `top_k_er` per variant to see if chunk count affects severity outputs.
- **Model comparison**: A vs B can differ only in model (e.g. GPT-5 vs o3) with identical prompts and chunks.

### Key constraint

The `user_prompt_override` inlines the frozen chunks directly, so the template needs a `{fsr_chunks}` / `{er_chunks}` placeholder (or `verbatim` mode for a fully static prompt). The system prompt is shared across all issues in a lab run.

---


