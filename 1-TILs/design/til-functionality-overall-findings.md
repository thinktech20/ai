# TIL Step-6 Functionality Summary (DS Docs + Code Review)

## Scope Reviewed

This summary is based on:
- DS team docs under `TILs/analysis/docs-from-ds-team` (E6.2 to E6.6)
- Referenced implementation under `SDG_Scoping_Feedback_Loop/code_assets/experiments/step6`
- Runtime helper modules under `SDG_Scoping_Feedback_Loop/code_assets/runtime`

Main orchestration entrypoint reviewed:
- `code_assets/experiments/step6/run_gt_til_applicability_eval.py`

---

## What TIL Step-6 Does Overall

Step 6 is a multi-stage, evidence-aware TIL disposition workflow. It does not rely on a single final LLM call. It builds structured context across several lanes, applies deterministic short-circuit gates where possible, then runs a final applicability evaluation.

Core goal:
- Decide whether a candidate TIL should be treated as applicable, not applicable, conditionally applicable, or insufficient information for an outage case.

Current behavior in practice:
- Uses profile extraction + optional document context
- Uses template coverage and information-only routing before expensive downstream checks
- Uses prior service-history evidence (FSR and ER retrieval paths) plus completion review
- Uses SBOM as supporting configuration evidence (not as a hard exclusion gate)
- Writes rich run artifacts for audit and SME review

---

## End-to-End Functional Flow

1. Load candidate rows and enrich event/unit context.
2. Resolve TIL profile context (from extraction artifacts) and optional document text/tables.
3. Run information-only check.
4. Run template coverage for non-information-only rows.
5. Short-circuit rows as:
   - `information_only_skip`, or
   - `template_covered_skip`
6. For remaining rows, run service-history evidence retrieval and completion review.
7. Build SBOM context from strict part/MLI keys and matched ESN.
8. Assemble final case payload.
9. Run final applicability LLM for non-short-circuited rows.
10. Write summary + line-item + prompt/evidence artifacts.

---

## Functional Lanes and Their Role

### E6.2 TIL Profile Extraction

Primary script:
- `run_til_profile_extraction_pilot.py`

What it does:
- Finds TIL PDFs from Databricks volume, workspace sample PDFs, and SQL fallback payloads.
- Extracts document content (`foundation`, `pdfplumber`, or `auto`).
- Calls LLM to produce structured profile JSON.
- Normalizes profile schema and writes per-TIL artifacts.

Why it matters:
- Supplies profile context consumed later by Step-6 applicability runner.

### E6.3 SBOM Logic

Primary module:
- `sbom_lookup.py`

What it does:
- Extracts strict part and MLI keys from profile context.
- Queries SBOM SOT tables first.
- Falls back to local workbook parsing if SOT misses.
- Performs deterministic matching and returns structured evidence/status.

How it is used:
- As supporting configuration evidence only.
- No SBOM match does not auto-mean not-applicable.

### E6.4 Evidence Cross-Check (Implementation Status)

Primary modules:
- `runtime/service_history_completion.py`
- `runtime/fsr_completion.py`

What it does:
- Retrieves prior service evidence from vector paths (FSR/ER).
- Falls back to SQL FSR retrieval if FSR evidence is missing from vector retrieval.
- Applies retrieval policy based on disposition + recurring signals.
- Runs completion-review LLM over summarized evidence.

Key policy shape in code:
- `complete + recurring` -> latest-report policy
- `incomplete` -> backsearch until completion
- `complete + non-recurring` -> backsearch until completion
- otherwise -> bounded full-history default

### E6.5 Standard Template Coverage + Information-Only

Primary module:
- `runtime/template_coverage.py`

What it does:
- Deterministically flags information-only cases.
- Loads template context (historical template mapping + Primavera activity context).
- Runs template coverage classification and partitions line items into covered/gap/unclear.

How it is used:
- Pre-applicability dedup stage.
- Enables short-circuit skips before deeper evidence/final LLM stages.

### E6.6 End-to-End Disposition Evaluation

Primary script:
- `run_gt_til_applicability_eval.py`

What it does:
- Orchestrates all lanes above.
- Applies skip routing and/or full final LLM decision path.
- Produces operational and review artifacts.

---

## Inputs and Source Systems (Current)

Major data inputs include:
- Candidate CSV/workbook outputs from Step-6 candidate generation
- Event/equipment/unit context tables (EV, IBAT)
- TIL PDFs from Databricks volume + workspace sample + SQL fallback
- FSR and ER retrieval backends
- Primavera project/WBS/activity context
- SBOM SOT tables + local sample fallback workbooks

---

## Outputs and Artifacts (Current)

Current run outputs include:
- Summary CSV/workbook views
- `records.jsonl`
- Prompt payload and prompt artifacts
- Template coverage records
- Completion/evidence line-item exports
- Markdown companions for run summary/context

From a functional perspective, outputs are designed for:
- auditability
- SME walkthroughs
- post-run QA and calibration

---

## Decisioning Characteristics

The current Step-6 design is evidence-weighted and conservative:
- Uses deterministic gates first (information-only, template coverage skip).
- Uses retrieval and synthesized completion review for prior implementation signals.
- Keeps SBOM as supporting evidence, not as a single hard gate.
- Encourages `conditionally_applicable` or `insufficient_information` when evidence is incomplete/ambiguous.

This reduces overconfident false negatives/positives from single-signal logic.

---

## What Is Implemented vs What Still Needs Hardening

Implemented now:
- Multi-lane orchestration in active runner
- Routing skips
- Service-history retrieval + completion review path
- SBOM deterministic matching with source fallback
- Artifact-rich output contracts

Hardening still needed for production readiness:
- Environment/source preflight health checks
- Clear run-level quality KPIs and acceptance thresholds
- Stronger schema validation and error taxonomy
- Better source coverage reconciliation and drift monitoring
- Calibration loops for cross-lane interactions (template vs completion vs final verdict)

---

## Bottom Line

Current TIL Step-6 functionality is already a staged decision pipeline, not just prompt engineering. It combines deterministic routing, structured evidence assembly, and LLM reasoning in a traceable flow. The core functional shape is strong for design handoff; most remaining work is runtime hardening, governance metrics, and calibration at scale.
