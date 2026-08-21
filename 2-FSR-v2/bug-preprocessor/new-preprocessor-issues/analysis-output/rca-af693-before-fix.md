# RCA (Before Fix) — af693a98-1e5c-499d-aa10-cccc54885c64

## Baseline Artifact
- Output JSON: `analysis-output/before-fix/af693a98-1e5c-499d-aa10-cccc54885c64.json`
- Baseline metadata result:
  - `primary_esn = 297652`
  - `primary_equip_type = Gas Turbine`
  - `gt_esn = 297652`
  - `gen_esn = 337X766`
- Region count: `25`

## Observed Bug in Baseline
For the target body occurrence:
- `## 2.6 Generator Mechanical Scope` at char ~`74474`
- `### 2.6.1 Generator Manways` at char ~`74564`
- `## 2.7 Unit Rotor` at char ~`75125`
- `### 2.7.1 Rotor Position Clearances` at char ~`75213`

Current output tags `2.7 Unit Rotor` and `2.7.1 Rotor Position Clearances` as:
- `primary_equip_type = Generator`
- `primary_esn = 337X766`
- `esn_source = parent_inherit`

This violates the locked working rule that context should flip back to parent section (`2 Turbine`) after generator subsection ends.

## Code-Level Root Cause
1. Candidate detection only creates subsection candidates when title contains equipment keyword:
   - `SUBSEC_GEN`: numbered subsection with `Generator`
   - `SUBSEC_GT`: numbered subsection with `Gas Turbine|Turbine`
2. `2.7 Unit Rotor` has no equipment keyword in heading text, so no candidate is created for it.
3. Because no `2.7` candidate exists, prior generator subsection span (`2.6` / `2.6.1`) remains active until a later detected boundary.
4. During ESN/type resolution, following text remains inside generator span by inheritance (`parent_inherit`), causing wrong attribution for `2.7` section content.

## Supporting Trace (Current Run)
Candidates near problematic region:
- start `74474`: SUBSEC, equip `Generator`, level `1`, text `## 2.6 Generator`
- start `74564`: SUBSEC, equip `Generator`, level `2`, text `### 2.6.1 Generator`
- No candidate for `## 2.7 Unit Rotor`

Resulting span:
- `## 2.6 Generator` span: `start=74474`, `end=95837`, resolved to `Generator 337X766`
- This long span encloses `2.7 Unit Rotor`, so `2.7` content inherits generator context.

## Why Prior Parent-Inherit Fix Did Not Resolve This
The earlier parent-inherit correction addressed ancestry/source behavior where candidate spans existed. Here, the failure starts earlier: missing candidate generation for untyped numbered subsection headers (example: `2.7 Unit Rotor`). Without a boundary/span at `2.7`, the model cannot flip context back structurally.

## Fix Direction (For Review)
Add a numbered subsection candidate path for generic headers that do not include equipment keywords, then infer equipment type from nearest valid parent hierarchy (prefer top-level section context like `2 Turbine`) when explicit subsection keyword is absent.

This should enable:
- `2.6*` explicit generator context
- automatic flip-back at `2.7` to parent turbine context
- no dependency on keywords inside `2.7` title/body
