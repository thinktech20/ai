# code/

Step-by-step notebooks for the Phase 1 end-to-end loop. Same medallion split
that prod uses (`pw_sdg_ai_ser_repo`), so concepts map cleanly when explaining
the architecture later.

## Layers

- **bronze/** — raw ingest + first parse. Output: pages of text with page numbers + source metadata. Smallest possible transformations.
- **silver/** — cleaned, chunked, embedded. Output: chunk-level table ready to be indexed (text + metadata + vector).
- **gold/** — query-time: retrieve, (re-rank), generate. Output: an answer with citations.

## Notebooks

- [bronze/nb_01_ingest_parse.py](bronze/nb_01_ingest_parse.py) — ingest one FSR PDF, parse with PyMuPDF baseline.
- _silver/_ — chunk + embed (next).
- _gold/_ — index + retrieve + generate (after that).

## Conventions

- Files are Databricks notebook source (`.py` with `# COMMAND ----------`). Easier to review/diff than `.ipynb`. Databricks renders them as notebooks.
- Numbered `nb_NN_...` so the order is obvious.
- One concept per notebook on the first pass — keep it readable.
