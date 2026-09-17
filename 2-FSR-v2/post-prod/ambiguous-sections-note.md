# Ambiguous Sections Note

Updated: 2026-09-15
Date first noted: 2026-09-01

## Summary

Some section types in FSR v2 post-prod follow-up may be too ambiguous to force into the standard section-based retrieval path.

## Ambiguous content called out

- Appendix
- Attachment
- Sub-reports
- Embedded table of contents
- Some `final_master_report` content

## Current concern

The original note suggests either assigning an `Ambiguous` tag or routing these cases through a separate LLM or retrieval path.

## Why this matters

This is a cross-cutting issue because ambiguous content can affect preprocessing, metadata design, retrieval behavior, and response quality.

## Current status

Open exploration item. There is no decision note yet on whether ambiguity should be represented directly in metadata.

## Next checks

1. Decide whether ambiguity should be explicit metadata.
2. Decide whether ambiguous sections should stay in the default retriever path.
3. If needed, define a separate LLM or retrieval workflow for those sections.

## Source

Derived from `post-prod/todo` on 2026-09-15.
