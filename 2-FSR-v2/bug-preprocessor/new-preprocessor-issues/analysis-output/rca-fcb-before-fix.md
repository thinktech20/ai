# Baseline Check (Before Fix) — fcb1511e-596a-4a56-b151-1e596afa569c

## Baseline Artifact
- Output JSON: `analysis-output/before-fix/fcb1511e-596a-4a56-b151-1e596afa569c.json`
- Metadata summary:
  - `primary_equip_type = Generator`
  - `primary_esn = 337X581`
  - `gt_esn = 298464`
  - `gen_esn = 337X581`
  - `all_esns = 298464, 337X581`
- Region count: `23`

## Quick Findings
1. The section ancestry path frequently retains a `Generator` root while regions are tagged as `Gas Turbine`.
   - Example: `4 Generator > 3 Turbine > ...`
2. Multiple abrupt type flips occur within section 3.x and later sections:
   - Generator -> Gas Turbine -> Generator -> Gas Turbine -> Generator -> Gas Turbine
3. A mid-document generator subsection (`### 3.8.6 Generator`) is followed by turbine subsections, and attribution appears to flip back in some places.
   - This is directionally consistent with flip-back behavior, but the parent path still looks structurally noisy.
4. Later regions also show cross-context paths like:
   - `Generator > 4 Generator > ## 7.1 Combustion`
   which suggests hierarchy/candidate quality issues in addition to ESN assignment behavior.

## Conclusion
- Local standalone preprocessor run was successful, so Databricks is not required for this single-doc baseline check.
- This document likely shares the same underlying hierarchy/candidate-detection weaknesses seen in the af693 issue family.
- Keep this as a before-fix baseline; re-run post-fix for direct comparison.
