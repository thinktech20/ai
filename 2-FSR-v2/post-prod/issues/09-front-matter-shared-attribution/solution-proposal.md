# Solution Proposal

Updated: 2026-09-17
Issue: Front-matter shared attribution

## Proposed direction

Classify text before the first reliable unnumbered equipment boundary as `shared` unless the preamble contains explicit, high-confidence equipment evidence.

This should be implemented as an attribution policy, not as a new heading parser. Existing section boundaries, Generator/Turbine logic, and ESN resolution should remain unchanged.

## Proposed behavior

For regions before the first valid equipment boundary:

- preserve the region and its text
- set `primary_equip_type=shared`
- leave `primary_esn` empty by default
- retain section metadata only when it is independently reliable
- do not inherit equipment context backward from the first later equipment header

Known explicit evidence, such as a local equipment header with an ESN, may remain attributed if it is independently recognized. The default should be conservative shared attribution.

## Why this is safer

Assigning preamble text to the first equipment can create false equipment-qualified retrieval results. Shared attribution keeps the content searchable without asserting an equipment relationship that the text does not establish.

## Scope

In scope:

- first-region and preamble attribution policy
- region metadata and confidence/reason codes
- before/after retrieval and chunk metadata validation

Out of scope:

- changing section heading detection
- changing Generator/Turbine span generation
- changing ESN resolution for explicit equipment sections
- dropping preamble content

## Rollout

1. Measure current preamble attribution across a representative sample.
2. Apply the metadata-only change in QA.
3. Compare equipment-filtered retrieval and summary behavior.
4. Reprocess affected documents only after validation.
5. Rechunk and re-embed only when persisted chunk metadata or region boundaries change.

## Acceptance criteria

- preamble text remains present and chunkable
- no equipment attribution is inherited backward without local evidence
- explicit equipment headers remain unchanged
- no unexpected increase in unqualified or missing metadata errors
- retrieval impact is understood before production rollout
