# Preprocessor Fix Review

## 1. `5.1 DC Leakage` not assigned to Generator

**Document:** `5a82aa03-e7dd-45c4-b226-460c508a4889`

**Issue:** The `5.1 DC Leakage` subsection was not classified as Generator. Only a root-level `5 DC Leakage` pattern was being detected in some cases.

**Current fix:** The preprocessor now recognizes electrical Generator roots such as `5 Electrical`, `5 Electrical System`, and `5 Electrification`. It then recognizes Generator subsections such as `5.1 DC Leakage` under that root.

**Status:** Fix is present and confirmed locally with PyMuPDF. `5.1 DC Leakage Test` is emitted as a Generator region. No Generator ESN is available in this document's inventory, so the section's ESN remains empty.

## 2. No flip-back to Gas Turbine after Electrical section

**Document:** `0be4a3ad-7395-41ea-8ec2-e7669c9c15aa`

**Issue:** After a Generator/Electrical subsection, later content continued to inherit Generator context instead of returning to the Gas Turbine context.

**Current fix:** The preprocessor now creates candidates for supported untyped dotted subsections and resolves their equipment type from the same-root context or the governing equipment header. This allows Generator subsection context to end and Gas Turbine context to resume at the next applicable boundary.

**Status:** Fix is present for supported subsection heading forms. A focused local PyMuPDF run confirmed that `6 Sub Reports` now creates a Gas Turbine boundary after the Electrical/Generator span.

## 3. Quick keyword edits

The following keyword mappings are now implemented for numbered Generator subsections:

- `Field`, `EL CID`, `LCI` -> `Generator`

This includes headings such as `5.1 Field Winding`, `5.1 Field Inspection`, `5.1 EL CID Test`, and `5.1 LCI`. The matcher intentionally supports only the narrow `EL CID` spelling; `EL-CID` and `ELCID` are not included.

The following mappings are now implemented as generic Turbine subsection triggers:

- `PIPO`, `Control System`, `QCP` -> `Turbine`

These mappings are supported at root and subsection levels using exact heading names. The existing context resolution selects Gas Turbine or Steam Turbine. Suffix variants such as `PIPO Check`, `Control System Inspection`, and `Quality Checkpoint` are intentionally excluded. Focused validation passed for both contexts.

The following mapping remains deferred:

- `Bently Nevada`, `HMI`, `couplings`, `Alignment` -> `Shared`

They were not included in the current logic-fix change because they require explicit span-scoped classification rules and validation of where each classification starts and ends.

The `Shared` mapping needs additional design work because `shared` currently exists as a fallback label for unclassified/gap regions, not as a normal subsection equipment type.

## Validation needed

Run the standalone preprocessor on both documents and verify:

- `5.1 DC Leakage` is tagged `Generator`.
- Content after the Electrical section is tagged `Gas Turbine` where the governing header is Gas Turbine.
- The emitted `section_path`, `primary_equip_type`, and `primary_esn` are correct around both boundaries.