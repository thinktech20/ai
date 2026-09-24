# 04. Final Master Report Format

Updated: 2026-09-22

## Brief

Priority bucket: `2`

Current summary:

- `final_master_report` is a distinct document family.
- Current inventory notes suggest about `4,923` docs in this family.
- The working direction is a dedicated preprocessing profile rather than treating it like the UUID family.
- The latest review (`review-9-21`) scopes the rule to the `COMPONENTS` section, which may be `2. COMPONENTS` or `3. COMPONENTS`; all other sections, unlabeled Components content, and reports without Components default to `shared`.
- Inside Components, labels with an equipment leading phrase map to that equipment (`GAS TURBINE - BEARINGS` -> `Gas Turbine`); the initial vocabulary is Gas Turbine, Steam Turbine, Generator, and Uncategorized (`shared`).
- Strong structural indicators include the fully capitalized numbered forms
	`2. COMPONENTS` or `3. COMPONENTS`, the primary-ToC dotted format, and
	`GENERATOR -` labels. Plain `GENERATOR` is not sufficient by itself because
	it can occur in other document formats.
- Also noted: in `final_master_report` parsed text, the content/section number precedes the content title (e.g. `2.1 Dallas Shop QC Report`), which should hold as a heading-order assumption for this family's detection regex.

Primary source:

- `../../section-path-issue-discussion.md`
- `root-cause-analysis.md`
- `solution-proposal.md`
- `implementation-plan.md`
- `review-9-21` (latest Teams input, with screenshot reference)

## Root cause analysis

- `root-cause-analysis.md`

## Implementation

- `solution-proposal.md`
- `implementation-plan.md`

## Validation

Initial dev acceptance candidates are listed in `implementation-plan.md`. The
validation should confirm that content outside Components is `shared`, that
Components may be section 2 or 3, that unlabeled Components content is
`shared`, and that labels switch only on the agreed equipment-leading markers.

An `ambiguous` label and page fallback remain deferred until more sub-report
examples are reviewed.