# Monday Talk Track: FSR Metadata Architecture

## Opening

My recommendation is to keep the two-step flow and strengthen the metadata layer.

The current design already has the right overall direction:

1. Process 1 handles scraping and metadata extraction
2. Process 2 handles chunking and embedding

What I think we should align on Monday is that Process 1 should be treated as the canonical document registry, not just an extraction output table.

## Core Position

The metadata architecture should be approved independently of the final chunking algorithm.

That means:

1. Process 1 owns file discovery, metadata extraction, enrichment, classification, precedence, and processing state
2. Process 2 consumes Process 1 output using `volume_path` and status-based pickup
3. chunking stays defined only at workflow level for now

## What We Should Lock Now

We should lock the following now:

1. one canonical metadata row per document
2. stable `document_id`
3. explicit `document_type`
4. explicit ESN precedence and `esn_source`
5. explicit `chunk_status` instead of generic `processed`
6. upsert behavior for re-uploaded files
7. `metadata_version` so metadata can be refreshed later without redesign

## What We Should Not Block On

We should not block the architecture on final chunking logic.

We can say:

1. Process 2 will read pending FSR rows from Process 1
2. it will load the PDF using `volume_path`
3. it will chunk, embed, write chunk rows, and update status
4. the exact chunking algorithm will be improved in a separate design track

## Suggested Meeting Tone

This is not about changing direction. It is about making the current direction more explicit and production-ready.

Suggested phrasing:

- The current split between metadata extraction and chunking is the right foundation.
- The main design question is how strong we want Process 1 to be as a canonical metadata layer.
- If we align on that contract now, we can improve chunking independently without destabilizing the architecture.

## Close

The simplest decision for Monday is:

1. keep the two-process model
2. strengthen Process 1 into the canonical metadata registry
3. define Process 2 as a status-driven consumer of that registry
4. take chunking algorithm design as a separate workstream