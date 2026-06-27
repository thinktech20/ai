# rag-skeleton

Reusable skeleton for medallion-style document/RAG pipelines.

This is a **scaffold only** — interfaces, contracts, and job entry-point stubs.
It carries no concrete parser, chunker, embedder, or vector-store implementation.
The intent is that any new pipeline (TIL, FSR-style, future doc types) can drop
in adapters behind these interfaces without rewriting the pipeline shell.

## What's here

```
src/rag_skeleton/
  types.py            # Document, ExtractedMetadata, Chunk, ChunkWithEmbedding,
                      # RetrievedChunk, GenerationResult
  status.py           # StageStatus enum + claim/release contracts
  config.py           # Pipeline / Parser / Chunker / Embedder config dataclasses
  interfaces/         # Protocols (one file per contract)
    # batch indexing:
    parser.py         # DocumentParser
    chunker.py        # Chunker
    embedder.py       # Embedder
    vector_store.py   # VectorStoreSink
    validator.py      # Validator
    evaluator.py      # Evaluator
    # serving / RAG:
    retriever.py      # Retriever
    generator.py      # Generator (LLM call)
    guardrail.py      # InputGuardrail, OutputGuardrail
  runtime/
    claim.py          # status-driven row-claim contract (FSR-style queue)
    tracking.py       # MLflow run wrapper for jobs
    audit.py          # pipeline_run_audit write contract (first iteration)
  jobs/               # one skeleton per job in the design
    bronze_ingestion.py
    silver_metadata.py
    gold_chunk_embed.py
    validation.py
    vector_sync.py    # Job F: triggers Vector Search Delta Sync (table-wide)
    evaluation.py
  serving/            # serving-side composition
    guarded_generator.py  # Generator decorator that runs input/output guardrails
  adapters/           # concrete implementations live here (empty in skeleton)
    parsers/
    chunkers/
    embedders/
    vector_stores/    # used by VectorStoreSink and Retriever adapters
```

## Design alignment

Maps 1:1 to the high-level design in `dbx/TILs/design/til-pipeline-design`:

- Contract-first modules — every replaceable component is a Protocol in `interfaces/`.
- **Two surfaces**:
  - *Batch indexing* (parse / chunk / embed / validate / publish) — the pipeline jobs.
  - *Serving / RAG* (retrieve / guardrail / generate) — protocols + a `GuardedGenerator`
    composition stub in v1; consumed by a future PyFunc + Model Serving endpoint
    when the deferred section is activated.
- Status-driven queuing — `runtime/claim.py` defines the claim/release contract;
  jobs only see "give me a batch in status X".
- MLflow tracking — `runtime/tracking.py` wraps each job execution as an MLflow run.
- Job-per-stage — `jobs/` mirrors Jobs B/C/D/E/F + evaluation from the design.
- Vector index sync is a Delta Sync index (self-managed embeddings) triggered
  explicitly by `jobs/vector_sync.py` at the end of the pipeline, plus a daily
  safety-net cron. Mirrors the FSR `pw_sdg_fsr_vs_sync` pattern: POST /sync,
  no per-row vector status column, validation enforced at write time. The
  `VectorStoreSink` interface and `adapters/vector_stores/` package remain in
  the skeleton for ops paths (manual delete by chunk_id) and as the natural
  home for `Retriever` adapters at serving time.
- Pipeline state lives in Delta — this skeleton does not embed Spark/Delta calls;
  the Delta-side concerns are isolated to adapters and runtime helpers, so this
  scaffold can be unit-tested without a Databricks runtime.
- `pipeline_run_audit` is a first-iteration construct; once MLflow run coverage
  is validated, it can be dropped or replaced with a Delta view over MLflow runs.

## How to reuse for a new pipeline

1. Copy `rag-skeleton/` into the target repo (or import as a package).
2. Implement adapters under `adapters/` for the parser/chunker/embedder/vector-store
   you need.
3. Wire concrete adapters in `config.py` (or via your config loader).
4. Run jobs from `jobs/` as Databricks job entry points.

## Status

Skeleton only. Stubs raise `NotImplementedError`. No I/O, no Spark, no MLflow
calls — only the shape.
