# Steps To Take Current Notebooks Into The Databricks CI/CD + Airflow Process

**Date:** 2026-04-15
**Inputs reviewed:**
- `internal/notes/source-materials/databricks workspace-arch-naksha-integration-transcript`
- `internal/notes/databricks-architecture-followup`
- `internal/notes/source-materials/_Airflow Pipeline Development - Team Walkthrough.docx`

---

## Goal

Take the current DS experimentation notebooks and notebook-style Python files into the Databricks team process described in the walkthroughs:

- Git-based development in feature / bugfix branches
- PR merge flow through `dev`
- controlled promotion toward `main`
- Airflow-triggered execution through YAML / DAG configuration
- execution in Databricks Dev first, then Prod

---

## What The Databricks Team Process Seems To Be

Based on the transcripts and PDF, the intended process is:

1. Developers work from a shared Git repo using branch naming conventions like `feature_<story>` or `bugfix_<ticket>`.
2. Notebook or DAG changes are committed to the feature branch during development.
3. Related commits are squashed before review.
4. A PR is raised to `dev`.
5. After review and approval, changes are promoted onward toward `main` / release.
6. Airflow reads a YAML-style task definition that points to a Databricks notebook path.
7. Airflow triggers notebook execution in Databricks.
8. The same overall process applies to both notebook changes and Airflow configuration changes.

The deploy PDF also indicates a release discipline where only intended `dev` changes are promoted using a release branch / cherry-pick flow into `main`.

---

## Current Notebook Candidates

These look like the main notebook-style entry points in the current DS repo:

- `ds-experimentation-code/fsr_scraping/run_scraping_pipeline.py`
- `ds-experimentation-code/fsr_pipeline/run_pipeline.py`
- `ds-experimentation-code/fsr_pipeline/run_reenrich.py`
- `ds-experimentation-code/fsr_pipeline/run_evaluation.py`
- `ds-experimentation-code/fsr_pipeline_gt_direct/run_pipeline.py`
- `ds-experimentation-code/fsr_pipeline_gt_direct/run_evaluation.py`

Not all of these should necessarily be productionized.

Most likely production candidates:
- FSR metadata extraction notebook
- FSR chunk ingestion notebook
- maybe a re-enrichment notebook if there is an operational backfill use case

Likely non-production or limited-use notebooks:
- evaluation notebooks
- GT-direct subset notebooks
- one-off experiment notebooks

---

## Recommended Steps

## 1. Decide which notebooks are real deployment units

Before wiring anything into Airflow, split the current notebook set into:

- production ingestion notebooks
- operational support notebooks
- experiment / evaluation notebooks

Suggested first-pass classification:

| Notebook | Recommendation |
|---|---|
| `fsr_scraping/run_scraping_pipeline.py` | production candidate |
| `fsr_pipeline/run_pipeline.py` | production candidate |
| `fsr_pipeline/run_reenrich.py` | optional operational candidate |
| `fsr_pipeline/run_evaluation.py` | keep out of production DAG initially |
| `fsr_pipeline_gt_direct/*` | do not move into production flow initially |

Reason: the Databricks team process looks designed for supported operational jobs, not every experimental notebook in the repo.

## 2. Move from NRC-style experimentation into the target AI workspace structure

The transcripts mention that the POC was happening in the NRC workspace and that new dedicated Dev and Prod AI workspaces now exist.

So the notebooks need to be:

- attached to the correct Databricks Git-backed repo in the Dev workspace
- organized under stable notebook paths
- no longer treated as ad hoc POC-only artifacts

Practical action:

1. Create or confirm the target folder path in the Databricks Dev workspace.
2. Confirm which GitHub repo is the source of truth for notebook deployment.
3. Make sure all developers who need to work on notebooks have Git access and Databricks repo access.

## 3. Normalize notebook structure before onboarding to CI/CD

The current notebook-style `.py` files are workable, but before putting them behind Airflow they should be cleaned up so they are stable execution units.

At minimum:

1. Ensure each notebook has a clear entry point and documented runtime parameters.
2. Separate notebook orchestration from reusable helper logic where possible.
3. Remove hardcoded POC-specific defaults where production values will differ.
4. Standardize notebook names and paths so Airflow YAML can reference them cleanly.
5. Decide which parameters come from widgets, environment, secrets, or tables.

For these notebooks, the immediate parameterization points likely include:

- source volume paths
- output table names
- target Vector Search index / endpoint names
- secret scope names
- force reset / replace behavior
- schedule-specific runtime flags

## 4. Externalize environment-specific configuration

The current DS notebooks contain POC defaults like `main.gp_services_sdg_poc.*` and other environment-specific values.

Before moving into the Databricks CI/CD process, define what is:

- Dev-only
- Prod-only
- shared across environments

At minimum, externalize:

- catalog / schema / table names
- workspace-specific notebook paths if they differ
- secret scope names
- compute target or job cluster choice
- Airflow schedule / trigger settings
- notification targets and failure handling

Without this step, promotion from Dev to Prod will be brittle.

## 5. Map each notebook to an Airflow task contract

The follow-up transcript says the Airflow side is driven by a YAML file containing at least:

- task name
- task key
- notebook path
- airflow tag / DAG identifier

So for each production notebook, define:

1. notebook path in Databricks workspace
2. task name
3. task key
4. schedule or trigger type
5. upstream / downstream dependency
6. parameters passed to the notebook
7. success / failure expectation

Example logical mapping:

| Job | Notebook | Airflow role |
|---|---|---|
| FSR metadata extraction | `run_scraping_pipeline.py` | scheduled ingestion task |
| FSR chunk ingestion | `run_pipeline.py` | scheduled ingestion task, likely after metadata or in parallel depending on design |
| FSR re-enrichment | `run_reenrich.py` | ad hoc or maintenance task |

## 6. Add notebook and DAG config changes through the Git process

Per the transcripts, notebook changes and Airflow YAML changes should both follow the same Git workflow.

Recommended sequence:

1. Create branch: `feature_<ADO_story>` or `bugfix_<ticket>`.
2. Add or update notebook files.
3. Add corresponding Airflow YAML / DAG config.
4. Run notebook tests in Dev workspace.
5. Commit iteratively during development.
6. Squash related commits before final review.
7. Raise PR into `dev`.
8. After review, follow the team’s promotion flow toward `main` / release.

## 7. Validate notebooks in Dev before asking for promotion

The team explicitly asked people to test early so access and setup issues are discovered now.

For each notebook, validate in Dev:

1. Git-backed notebook sync works.
2. Notebook runs with the expected cluster or job compute.
3. Secret access works.
4. Input volume access works.
5. Target table write permissions work.
6. Airflow-triggered execution works from the YAML / DAG configuration.
7. Logs are sufficient to debug failures.

## 8. Define release promotion and production guardrails

The PDF suggests `dev` is not automatically identical to production. Promotion is selective.

So for these notebooks, define:

1. what counts as production-ready
2. who approves notebook promotion
3. whether promotion is PR merge, release branch, or cherry-pick only
4. rollback approach if a notebook deployment fails
5. whether Airflow DAG changes and notebook changes must ship together

## 9. Decide whether notebooks remain notebooks or become packaged jobs later

The Databricks team process clearly supports notebooks today. That is the fastest path.

But for maintainability, a later stage may be:

- keep a thin notebook entry point
- move most logic into Python modules
- have Airflow call the notebook wrapper only

That would make CI/CD cleaner without blocking immediate adoption.

---

## Practical First Cut

If the objective is to get something moving quickly, the minimum viable path is:

1. Pick only two notebooks first:
   - metadata extraction
   - chunk ingestion
2. Put both into the Databricks Dev workspace Git repo.
3. Standardize their notebook names and parameters.
4. Add Airflow YAML entries pointing to those notebook paths.
5. Run them manually in Dev.
6. Run them through Airflow in Dev.
7. Raise PR to `dev`.
8. Confirm the release path to `main` with the Databricks team.

This gives a working template before trying to onboard the rest.

---

## Open Questions For Tomorrow's Meeting

## Repo, Workspace, and Ownership

1. Which GitHub repo is the official source of truth for these Databricks notebooks?
2. Are we expected to migrate the current DS experimentation notebooks into an existing repo, or create a new folder / project inside the current AI Databricks repo?
3. Who owns production support once these notebooks are deployed: Databricks team, app team, or shared ownership?
4. Are Dev and Prod Databricks workspaces already fully ready for this pipeline, or is additional setup still pending?

## Branching and Promotion

5. For notebook deployments, is the exact branch model `feature_* -> dev -> release/main`, or is there any Databricks-specific variation?
6. Is promotion to `main` done by merge, cherry-pick, or both depending on the release?
7. Do notebook changes and Airflow YAML changes need to be in the same PR, or can they be promoted separately?

## Airflow Integration

8. Where does the Airflow YAML live, and who owns edits to it?
9. Can they share a sample YAML template for a Databricks notebook task?
10. Besides task name, task key, notebook path, and airflow tag, what other fields are required?
11. How are notebook parameters passed from Airflow into Databricks notebooks?
12. Does each notebook become a separate DAG task, or should related notebooks be grouped into one DAG?
13. How are retries, alerts, and failure notifications configured?

## Compute and Runtime

14. What compute should these notebooks run on in Dev and Prod: existing job cluster, all-purpose cluster, or serverless?
15. Are there runtime restrictions on external libraries used by the current notebooks, such as `pdfplumber`, `litellm`, `PyMuPDF`, and vector search dependencies?
16. Are secret scopes already provisioned in the AI workspaces for the current notebook requirements?

## Notebook Design and Standards

17. Do they want notebook code to remain notebook-first, or should shared logic be moved into Python modules with thin notebook wrappers?
18. What naming convention should be followed for notebook files, notebook paths, task names, and Airflow tags?
19. Are there mandatory logging, auditing, or metadata standards for production notebooks?
20. Are there code review expectations specific to notebook changes?

## Data and Environment Mapping

21. Should the current POC table names under `main.gp_services_sdg_poc.*` be used in Dev initially, or should we switch immediately to the target AI catalog structure?
22. What is the expected production target for:
   - metadata table
   - chunk table
   - Vector Search index
23. Is there an approved migration path from current POC objects to production objects?

## Scope and Prioritization

24. Which notebooks should be onboarded first?
25. Are evaluation notebooks intentionally excluded from the CI/CD + Airflow path?
26. Is `run_reenrich.py` meant to be a regular scheduled job, or only an ad hoc maintenance notebook?
27. Should the metadata extraction notebook and chunk ingestion notebook be sequenced together in one operational workflow, or treated as separate jobs?

---

## Suggested Meeting Outcome

If the meeting goes well, the best concrete outcome would be agreement on:

1. the target Git repo and workspace path
2. the first two notebooks to onboard
3. the YAML / DAG template to use
4. the branch and promotion flow to follow
5. the target Dev tables / indexes to wire up first
6. who approves and supports production rollout