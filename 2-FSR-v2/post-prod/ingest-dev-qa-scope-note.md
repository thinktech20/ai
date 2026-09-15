# Dev And QA Ingest Scope Note

Updated: 2026-09-15
Date first noted: 2026-09-01

## Summary

The post-prod todo lists `ingest 22K docs in dev and QA` as the first priority.

## Current interpretation

That note aligns with the FSR v2 2016+ ingest scope, but the `22K` figure is outdated.

## Later evidence in repo notes

- `FSR_V2_MIN_DOC_YEAR=2016` is the documented lower bound for the backfill scope.
- Later automation and backfill notes state the eligible corpus is `50,177` docs, not about `22,000`.
- QA tracker snapshots also show a corpus total of `50,177`.

## Why this matters

This changes how the effort should be communicated. The issue is not just an operational push to ingest about 22K docs. It is a 2016+ ingest/backfill scope whose measured corpus size later turned out to be much larger.

## Current status

Open operational dependency. Scope clarified; original count is stale.

## Next checks

1. Communicate this as a 2016+ ingest scope, not a hard 22K target.
2. Use `50,177` as the latest known corpus count unless a newer snapshot supersedes it.
3. Keep dev and QA progress reporting separate from the original estimate.

## Sources

- `post-prod/todo`
- `automation/autonomous.md`
- `backfill/backfill-pulse-log.md`
- `backfill/qa-backfill-tracker.md`
