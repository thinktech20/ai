# Implementation Plan

Updated: 2026-09-17
Issue: Front-matter shared attribution

## Steps

1. Identify how the first regions are currently attributed in representative UUID, Generator, Turbine, and mixed-equipment documents.
2. Record whether the preamble contains explicit local ESN/equipment evidence.
3. Add focused tests for:
   - cover/TOC text before a Generator header
   - cover/TOC text before a Turbine header
   - explicit equipment header with local ESN in the preamble
   - documents with no equipment header
4. Change only the preamble attribution policy, preserving region boundaries and explicit equipment sections.
5. Run the targeted preprocessor and chunking tests.
6. Run QA validation on a representative sample and compare equipment-qualified retrieval.
7. Reprocess only documents whose persisted metadata changes.

## Components

- `common/fsr_v2/preprocessor_v2.py`: region metadata attribution
- `tests/fsr_v2/test_preprocessor_v2.py`: focused behavior tests
- P1 metadata enrichment: persist changed region metadata
- P2 chunking: re-run only when persisted chunk metadata or boundaries change
- P3 embeddings/index: refresh only changed chunks

## Safety controls

- no backward inheritance from the first later equipment header
- preserve full document coverage
- keep explicit local equipment/ESN evidence authoritative
- compare before/after region metadata before reprocessing
- monitor equipment-filtered retrieval for regressions

## Open decision

Confirm whether report-level summary text should always remain `shared`, or whether specific explicit summary sections may retain equipment context when the enclosing header is unambiguous.
