# FSR v2 Post-Prod Working Area

Updated: 2026-09-15

This folder now has two layers:

- `fix-priorities`: the live tracker and communication summary.
- `issues/` and `ops/`: the working area for ongoing analysis and follow-up.

Standard issue file structure

Each issue folder under `issues/` should use the same four-file layout so the artifacts are easy to share separately:

- `README.md`: issue overview, current status, and links to the shareable documents
- `root-cause-analysis.md`: issue RCA only
- `solution-proposal.md`: proposed solution only
- `implementation-plan.md`: implementation and rollout plan only

How to use this folder

1. Add or update issue status in `fix-priorities`.
2. Do working notes in the matching issue or ops folder.
3. Keep raw source notes at the top level when they are useful as original inputs.

What goes where

- `README.md` in each issue or ops folder: working summary and current state.
- `root-cause-analysis.md`: findings and evidence for the issue.
- `solution-proposal.md`: proposal written for review before implementation.
- `implementation-plan.md`: code, rollout, and validation plan.
- Validation notes: add checks, counts, screenshots, run links, and conclusions either in the issue README or as a separate follow-up note if the issue gets large.

Folders

- `issues/01-section-path-uuid`
- `issues/02-missing-docs-qa`
- `issues/03-mis-qualified-esn`
- `issues/04-final-master-report-format`
- `issues/05-final-master-report-retrieval`
- `issues/06-versioned-legacy-doc-family`
- `issues/07-title-vs-pdf-name-mismatch`
- `issues/08-ambiguous-sections`
- `ops/09-dev-qa-ingest-scope`
- `ops/10-pre-2016-reclaim-job`

Top-level source notes retained for reference

- `section-path-issue-discussion.md`
- `missing_docs_post_2016`
- `mis-qualified-esn/`
- `title-pdf-name-mismatch`
- `final-master-report-retrieval-note.md`
- `ambiguous-sections-note.md`
- `ingest-dev-qa-scope-note.md`
- `pre-2016-reclaim-job-note.md`