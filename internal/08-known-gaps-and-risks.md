# 08 — Known Gaps and Risks

Source: Analysis of DS reference code + data queries + Tao discussion (2026-04-07).

This document captures gaps in the current POC pipeline that need to be addressed before MVP2 production build. Intended for review with Aaron (Databricks architect) and the broader team.

---

## Gap 1 — Document Type Mixing (Most Critical)

**What the problem is:**
The Databricks Volume contains ALL kinds of PDFs — Field Service Reports (FSRs), Technical Instruction Letters (TILs), technical manuals, Engineering Reports, and other documents. They all share the same Volume path and are ingested together. The scraping and chunking pipeline processes every PDF without knowing what type it is — it just opens them one by one.

**What this causes:**
- Non-FSR documents that happen to mention an ESN get tagged to that unit via the LLM ESN identifier and end up in the FSR chunk table
- At query time, the `query_fsr` tool retrieves these non-FSR chunks mixed in with real FSR content
- The LLM reasoning about service history receives a mix of factual FSR findings + general technical guidelines + unrelated procedural documents
- This can mislead the LLM — it may present TIL guidance or manual content as evidence from a service event

**Example observed:**
A TIL document (~19 pages) with an ESN mentioned in it was tagged to that unit and chunked into the FSR table alongside real 800-page FSR documents.

**Why it's hard to fix:**
- PDF filenames in the Volume are bare GUIDs — no metadata in the filename
- There is no document type field in the current ingestion pipeline
- The first-page scraping extracts metadata fields, but does not classify document type (FSR vs TIL vs manual)

**What needs to happen:**
Add document type classification before or during ingestion:
- Option A: Classify from first-page content using LLM (e.g. "is this an FSR, TIL, or technical manual?")
- Option B: Maintain a document type registry linked to the Volume GUIDs upstream
- Option C: Filter by page count / structural signals (real FSRs tend to be long; TILs are ~10-20 pages)
- Regardless: the chunk table should have a `document_type` column and `query_fsr` should filter on it

---

## Gap 2 — LLM-Discovered ESN Links Not Validated

**What the problem is:**
The ESN identifier (`esn_identifier.py`) runs one LLM call per PDF and tags documents to ESNs based on mention counts (≥5 mentions, ≥10% fraction). These links have never been validated against ground truth.

**What this causes:**
- False positives: a document gets tagged to ESN X because it mentions that serial number in passing (e.g. a TIL referencing a known problematic unit)
- For a unit with correct SOT links, the LLM-discovered extras may not all be real FSRs for that unit

**Data observed:**
- 967 PDFs with null ESN in SOT were linked to 611 ESNs by the LLM
- At least some of these are non-FSR documents (Gap 1 above)
- The gap query (SOT vs LLM count per ESN) showed ESNs where LLM finds more — not all extras are genuine

**What needs to happen:**
- Sample validation: pick 20-30 LLM-only links, open the PDFs, verify they are real FSRs for those units
- Add `esn_assignment_scope` metadata column to results (`document` vs `fallback` vs `none`) — already in the code, surface it in the API response so callers can filter

---

## Gap 3 — Production Tables Not Built

**What the problem is:**
The production Unity Catalog tables (`vaid.ai_std_con_field_service_report.*`) do not exist yet. All current work — DS experiments, gap analysis, reference code — runs against the experiment catalog (`main.gp_services_sdg_poc`).

**What this means for MVP2:**
- The ingestion pipeline needs to be run against production catalogs
- Schema decisions (document_type column, ESN validation flags) need to be made before the production table is created
- The Vector Search endpoint (`pw-ser-sdg-vector-search`) needs to be configured against the production table

---

## Gap 4 — SOT Completeness

**What the problem is:**
The `fsr_pdf_ref` SOT table is built by the data team as a transform from FieldVision submissions. It has known gaps:
- 1,812 PDFs in the current corpus have no ESN in the SOT
- Some ESNs have 0 PDFs linked in the SOT even though reports exist (Tao confirmed 2 ESNs in the 30-ESN GT set had 0 SOT links)

**Why it happens:**
- FSRs are created by field engineers and submitted to FieldVision
- The link from PDF → ESN in the SOT requires a manual or automated registration step
- If that step is missed (submission error, system issue), the PDF exists in the Volume but isn't linked

**What needs to happen:**
- Understand the SOT build process with the data team — who triggers the PDF → ESN link?
- Determine whether the 1,812 null-ESN PDFs are recoverable or genuinely unlinked
- The LLM-based recovery (Gap 2) partially addresses this but introduces its own quality issues

---

## Gap 5 — No Document Type Granularity in Retrieval

**What the problem is:**
The Q&A agent needs to retrieve from multiple document types: FSRs (facts from service events), ERs (structured event reports), TILs (technical instructions), technical manuals (procedural guidelines). Currently everything is mixed in one chunk table with no type signal.

**What this causes:**
- The agent cannot distinguish "what happened during a service event" (FSR) from "what procedure should be followed" (TIL/manual)
- Both would be retrieved for the same ESN query, causing confused responses

**What needs to happen:**
Per Tao: each document type should be segmented and labeled. The retrieval agent should be able to target FSR chunks for factual service history and manual/TIL chunks for procedural guidance separately. This likely means either separate VS indexes per document type, or a `document_type` filter on a single index.

---

## Gap 6 — LiteLLM Rate Limiting

**What the problem is:**
LiteLLM (the LLM gateway) enforces rate limits. Both the scraping pipeline (which makes LLM calls for metadata normalization and ESN identification) and the chunking pipeline (which makes LLM calls for chunk processing) are subject to these limits.

**What this causes:**
- Under load, either pipeline can hit rate-limit errors (HTTP 429 or equivalent) and fail mid-run
- No retry/backoff logic exists in the current DS code for this scenario

**What needs to happen (revisit during design):**
- Understand the rate-limit thresholds on the LiteLLM gateway (requests/min, tokens/min)
- Add retry with exponential backoff for rate-limit responses in both pipelines
- Consider batching / throttling LLM calls to stay within limits, especially for large ingestion runs
- Determine whether rate limits differ between dev and prod environments

---

## People to Engage

| Person | Role | What to ask |
|---|---|---|
| **Aaron** | Databricks architect | How is the pipeline hosted? How to build production tables? Who owns the SOT build process? |
| **Shivam** | Databricks team | Hosting mechanism for `query_fsr` service — Model Serving vs Databricks Apps |
| **Data team** | SOT owners | How is `fsr_pdf_ref` built? Can null-ESN PDFs be recovered? Can document type be added upstream? |

---

## Recommended Next Steps

1. **Working notebook** — wire the full `query_fsr` pipeline end-to-end against experiment tables. Demonstrates the current state and the gaps in action.
2. **This document** — post to Confluence for review by Aaron and the broader team before MVP2 planning
3. **Connect with Aaron** via the Databricks/architect channel — bring gaps 1, 3, 5 as discussion items
4. **Connect with Shivam** — resolve hosting mechanism (ADR-001)
5. **Sample validation** — manually inspect 20-30 LLM-only ESN links to quantify Gap 2
