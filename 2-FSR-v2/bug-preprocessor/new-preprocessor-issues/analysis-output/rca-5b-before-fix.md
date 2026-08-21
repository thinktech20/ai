# Baseline Check (Before Fix) — 5b688732-39f2-48d2-a887-3239f258d28b

## Input and Output Artifacts
- Source PDF (local): `2-FSR-v2/design/final-dots/single-equip-doc/5b688732-39f2-48d2-a887-3239f258d28b.pdf`
- Before-fix output (pymupdf): `analysis-output/before-fix/5b688732-39f2-48d2-a887-3239f258d28b.pymupdf_v1_0.json`
- Before-fix output (pypdf2): `analysis-output/before-fix/5b688732-39f2-48d2-a887-3239f258d28b.pypdf2_v1_0.json`

## Reproduction Status
Reproduced in both parser paths.

Observed in both outputs:
- A large Generator-attributed region with section path `["Generator"]`.
- The region spans are close to Xujin's report (offsets differ slightly by parser text normalization):
  - pymupdf: `start=94794`, `end=148501`, `primary_esn=316X914`, `primary_equip_type=Generator`, `esn_source=single_type`, `section_path=["Generator"]`
  - pypdf2: `start=94503`, `end=148098`, `primary_esn=316X914`, `primary_equip_type=Generator`, `esn_source=single_type`, `section_path=["Generator"]`

Xujin-reported span:
- `start=96895`, `end=151931`, `primary_esn=316X914`, `primary_equip_type=Generator`, `section_path=["Generator"]`

The behavior matches functionally (same context assignment), with expected parser-dependent offset differences.

## Additional Observations
- Region segmentation count differs by parser:
  - pymupdf: 9 regions
  - pypdf2: 8 regions
- Both show follow-up Gas Turbine subsection entries with unresolved ESN (`None`) under a Generator-root path, indicating hierarchy/source consistency gaps similar to other RCA cases.

## Conclusion
- No Databricks run is required for this baseline reproduction because the PDF is available locally and both parser runs succeeded.
- This case should be included in post-fix regression verification for both parser paths.
