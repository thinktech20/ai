# FSR v2 Preprocessor Validation

Use `run-preprocessor-standalone.ipynb` for document-level validation with the same PyMuPDF parser and preprocessor path used by P1.

## Required regression checks

For each cited document, capture:

- candidate heading count and heading text
- section-path leaves and parent paths
- `primary_equip_type`, `primary_esn`, `esn_source`, and confidence
- region coverage and overlap
- chunk ownership after region-first splitting
- OCR/page-join artifact count

The current follow-up regression set should include:

- a `Quality Checkpoint (QCP)` root heading
- a Generator `-1` document with generic numbered subsections, especially `c9ed4e93-8408-4371-9f90-4e8641dd1ee6`
- a sub-report or attachment document where local numbering reuses a main-report number
- a long-label example, `27fa1fe0-369e-456f-b795-d9a9fc9cd52d`
- the uploaded 575-page document used for the multi-page TOC and OCR-artifact regressions

## Pass criteria

- `Quality Checkpoint (QCP)` is detected without broadening unrelated root headings.
- Generic Generator subsections are retained only when structural signals support them.
- Sub-report content remains chunkable and is scoped under an attachment/appendix/sub-report context when detected.
- Incomplete TOC coverage does not discard valid body content.
- Multiline/table/page-join artifacts do not become section headings.
- Long-label changes are retained only if the broader regression set remains stable.

The standalone notebook may run a single case or a custom batch. Save `_batch_summary.json` and per-document JSON outputs under the configured output directory for comparison and review.
