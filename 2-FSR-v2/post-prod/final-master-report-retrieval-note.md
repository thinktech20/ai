# Final Master Report Retrieval Note

Updated: 2026-09-15
Date first noted: 2026-09-01

## Summary

This issue tracks retrieval and data-readiness checks for `final_master_report` documents in FSR v2 post-prod follow-up.

## Documents called out

- `d82afaae-8979-436c-bb4e-92aaa8b48f62_605012157-52123-298340-final_master_report`
- `d1348ae1-b54c-418f-9833-b0ce99bcc899_605012157-52122-298339-Final_Master_Report`

## Current concern

The existing note asks to verify whether the URA retriever logic behaves differently for these documents, especially in the data-readiness section and in any path that uses shared chunks.

## Why this matters

The broader post-prod notes already suggest that `final_master_report` is a distinct document family. If retrieval behavior differs here, the issue may not be only preprocessing. It may also involve how shared chunks or family-specific structure are handled downstream.

## Current status

Open. No root-cause note exists yet beyond the original todo entry.

## Next checks

1. Review the current URA retriever logic for these documents.
2. Check whether shared-chunk behavior changes what gets surfaced for the data-readiness section.
3. Confirm whether the fix belongs in preprocessing, retrieval filters, or both.

## Source

Derived from `post-prod/todo` on 2026-09-15.
