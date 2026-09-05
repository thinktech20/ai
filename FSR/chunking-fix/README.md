# Chunking Fix

Workspace for the FSR chunker upgrade — porting DS `recursive_chunking_v3.py` to add TOC/boilerplate filtering, section hierarchy metadata, and page-range tracking.

| Doc | Purpose |
|---|---|
| [01-chunking-strategy-comparison.md](01-chunking-strategy-comparison.md) | Production vs DS strategy gap analysis (background) |
| [02-plan.md](02-plan.md) | What we're changing, approach, phased rollout, risks |
| [03-tracker.md](03-tracker.md) | Phase / task status, decisions log, open questions |
| [ds-code-n-doc/](ds-code-n-doc) | DS reference code (`recursive_chunking_v3.py` etc.) and PDFs |

**Branch:** `feat/fsr-chunk-metadata-fix` (in `pw_sdg_ai_ser_repo`, off `dev` at 5610314)

**Out of scope:** multi-ESN per PDF (deferred — see `01-chunking-strategy-comparison.md` §6/§7).
