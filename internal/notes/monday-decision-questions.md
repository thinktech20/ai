# Monday Decision Questions

## Metadata Architecture

1. Do we agree that Process 1 should be the canonical document registry, not just an extraction output table?
2. Do we want a stable `document_id` as the primary key of that registry?
3. Do we agree to add `document_type` now so the architecture can support FSR and future document classes cleanly?
4. Do we agree that Process 1 should own final ESN resolution and record `esn_source`?
5. Do we want `metadata_version` in v1 so metadata can be refreshed later without redesign?
6. Do we want lineage fields such as `metadata_resolved_at`, and should `field_source_map` be v1 or later-phase?

## Process Handoff

1. Do we want to replace `processed` with a clearer `chunk_status` model: `pending`, `processing`, `completed`, `failed`?
2. On failure, what is the minimum set of operational fields we want on the metadata row: error code, error reason, retry count, last attempted timestamp?
3. Should Process 2 mark rows as `processing` at start, or only set final status after completion?

## Re-uploads and Incremental Logic

1. For a re-uploaded PDF with the same filename or path, do we agree on upsert rather than append?
2. Is `volume_path` the right operational uniqueness key, or do we need a different document identity rule?
3. When a file is updated, should the system always reset chunk status and re-run Process 2 automatically?

## Chunking and Embedding Workflow

1. Do we agree that Process 2 should only work from Process 1 output and should not rescan volumes directly?
2. Which metadata fields must be top-level columns on the chunk table in v1?
3. Which fields can remain only in `chunk_metadata` for now?
4. Do we want one chunk row per ESN for multi-ESN documents, and if yes, should Process 1 stay one row per document while Process 2 handles fan-out?
5. Are embeddings stored directly on the chunk table, or do we rely on managed vectorization depending on the platform setup?

## Environment and Deployment

1. Can we confirm the correct source and target catalogs for DEV, UAT, and PROD?
2. Can we confirm what the application and retrieval layer will read from in each environment?
3. Do we want one chunk/index structure per document type, or is that decision intentionally deferred?

## Scope Boundaries

1. Do we agree not to finalize the chunking algorithm in this architecture discussion?
2. Are we aligned that chunking quality improvements should be tracked as a separate design workstream?
3. Is there any chunking-related requirement that must be fixed now because it changes the metadata contract?