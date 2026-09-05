# FSR Processing Design

This folder contains active design documents for the FSR processing implementation.

## Documents

| File | Purpose |
|---|---|
| [01-data-engineering-ingestion-alignment.md](01-data-engineering-ingestion-alignment.md) | Checks how the DS experimentation code aligns with the reference ingestion design |
| [02-recommended-fsr-architecture.md](02-recommended-fsr-architecture.md) | Recommended target architecture for document registry, chunk store, and query service |
| [03-vince-metadata-materialization-plan.md](03-vince-metadata-materialization-plan.md) | Plan for wiring scraping output into chunk ingestion and materializing selected metadata |
| [pranesh-metadata-design-doc.md](pranesh-metadata-design-doc.md) | Draft end-to-end FSR pipeline design covering scraping and chunking |

## Supporting materials

| File | Purpose |
|---|---|
| [source-materials/SDG_FSR_metadata_schema.pdf](source-materials/SDG_FSR_metadata_schema.pdf) | Source PDF reviewed for the metadata materialization design |

## Rule

Keep FSR-processing-specific design here next to the implementation assets. Keep broader repo-wide decisions and ADRs in [../../../internal/](../../../internal/README.md).