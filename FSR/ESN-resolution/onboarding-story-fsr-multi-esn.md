# FSR Multi-ESN Onboarding Story

## Summary

Bring a newly onboarded engineer to working context on the FSR multi-ESN stream so she can take up follow-on work without a separate discovery cycle.

## Background

The FSR pipeline already runs end to end in production, but multi-ESN understanding is split across two layers:

- the current production FSR ingestion and chunking flow
- the current ad-hoc multi-ESN repair implementation used to correct or extend ESN coverage

Before taking code changes, the engineer needs to understand the current end-to-end flow, the current multi-ESN implementation, and the access/setup needed to work in Git and Databricks.

## User Story

As a newly onboarded engineer on the FSR multi-ESN workstream,
I want a clear understanding of the FSR end-to-end flow, the current multi-ESN implementation, and the required Databricks and Git setup,
so that I can investigate and execute follow-on changes without being blocked by missing context or environment gaps.

## In Scope

- Review the FSR pipeline end to end from metadata discovery through chunking and vector search sync.
- Review the chosen multi-ESN target design versus the current ad-hoc repair implementation.
- Confirm the entrypoints, workflow definitions, notebooks, and config used by the current multi-ESN path.
- Resolve or document Git and Databricks access/setup gaps needed for development and debugging.

## Out of Scope

- Implementing the target multi-ESN design.
- Refactoring the current repair job.
- Running production data changes.
- Closing open design items in the multi-ESN plan.

## Key References

- `FSR/README.md`
- `FSR/KT.md`
- `FSR/fsr-pipeline-design.md`
- `fsr-prod-ops/README.md`
- `FSR/ESN-resolution/plan.md`
- `FSR/ESN-resolution/design/proposed-multi-ESN-design.md`
- `pw_sdg_ai_ser_repo/silver/src/workflows/fsr/pw_sdg_fsr_repair_multi_esn.yml`
- `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_repair_multi_esn.py`

## Expected Deliverables

- A short summary of the current FSR P1 and P2 flow.
- A short comparison of target multi-ESN design versus current ad-hoc implementation.
- A setup checklist covering Git, Databricks workspace access, workflow visibility, and runtime access.
- A blocker list for any missing permissions, secrets, or environment setup.

## Acceptance Criteria

- The engineer can explain the current FSR pipeline at a high level, including discovery, metadata extraction, enrichment, chunking, and vector sync.
- The engineer can identify the current multi-ESN implementation entrypoints in the workflow YAML and repair notebook.
- The engineer can explain the difference between the chosen target design and the currently shipped ad-hoc repair path.
- The engineer can identify the main tables, reference view, and audit artifacts touched by the current repair flow.
- The engineer has working Git and Databricks access needed to inspect the code and workspace assets, or has documented the exact gaps blocking that access.
- The engineer can take up a follow-on task without needing another baseline walkthrough of the FSR multi-ESN area.

## Suggested Subtasks

- Review FSR design and KT documents.
- Trace the current FSR workflow from metadata to chunking.
- Trace the multi-ESN repair workflow and notebook.
- Validate Git and Databricks access.
- Capture findings, open questions, and blockers.

## Notes

- Treat the design docs as the target direction and the repair workflow as the current implementation reality.
- Start review from the workflow YAML and notebook entrypoints, then follow dependent code as needed.
- Access setup is part of the story; it is not a separate prerequisite.