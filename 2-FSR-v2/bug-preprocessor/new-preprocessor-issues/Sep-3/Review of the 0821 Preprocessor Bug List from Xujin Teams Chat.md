## Review of the 0821 Preprocessor Bug List from Xujin

cross-checked each item against the actual rule catalog in `preprocessor-rules.md` from Madhurima. Grounded findings below.

### 1. Logic Bugs

**a. 5.1 DC Leakage not assigned to Generator**
This matches a real, identifiable guardrail in the rules: the "Generator keyword subsections" pass (Electrical/Electrification/DC Leakage, confidence 74) **only fires when the root section number was already established as a Generator `SECTION_HDR`**. And the `SECTION_HDR` pass only recognizes the literal labels `Gas Turbine, Generator, Steam Turbine, Exciter, Turbine` — **"Electrical" is not an accepted root label**. So any document where the root heading reads `5 Electrical` (instead of `5 Generator`) never sets the anchor, and every `5.x DC Leakage` subsection under it is silently dropped. "Only 5 will be detected" is consistent with only documents whose root literally says "Generator" surviving. This is a config/keyword-list gap, not a deep logic rewrite — fixable by adding "Electrical"/"Electrification" as alternate root-anchor labels for `SECTION_HDR`, or relaxing the anchor requirement to accept the keyword-subsection pass as its own anchor-setter.

**b. Doesn't flip back to Gas Turbine after Electrical section**
Also traceable to a specific rule: untyped-subsection inference (§2.3) resolves type by finding "the nearest prior span **sharing the same section root**" within the segment bounded by the nearest preceding `HEADER`. It never falls back to the enclosing level‑1 `HEADER`'s own equipment type unless the parent's *root* also matches. So once you're inside a differently-rooted section (e.g., "5 Electrical/Generator"), leaving it doesn't restore Gas Turbine context from the top-level HEADER — matching your observation almost exactly ("level −1 headings are not used for flip back"). Fix would be adding a step to §2.3: if no same-root typed predecessor exists, fall back to the governing HEADER's own type before giving up.

Both (a) and (b) are legitimate, narrow logic bugs — not broad architecture problems.

### 2. Pipeline Bug on Retrieval

**a. Whole documents tagged "shared" excluded from retrieval**
This is a different layer — the retrieval/query-time filter, not the preprocessor's tagging logic. My hypothesis (needs code confirmation, I don't have the retrieval-service source loaded): vector search filters by exact `generator_serial == ESN`; when a document's primary tag is `"shared"` rather than a real ESN, no per-ESN query will ever match it, so it's invisible to all ESN-scoped retrieval. This is likely the cheapest of all these bugs to fix — a retrieval-side patch (e.g., "shared" docs should also match when queried by any ESN in their `all_esns` list), independent of any chunk re-tagging.

### 3. Quick Preprocessor Edits
Straightforward keyword→type additions (Bently Nevada/HMI/couplings/Alignment→Shared; Field/EL CID/LCI→Generator; PIPO/Control System/QCP→Turbine). One caveat: the rule catalog currently has **no dedicated "Shared" typed subsection pass** — only Generator/Gas Turbine/Turbine typed passes exist. Routing keywords to "Shared" may need a small new code path (not just a list edit) since "shared" today only shows up as a *region-emission fallback label*, not a subsection-classification target.

### 4. LLM Experiments & Keith/Jon Requests
These are materially bigger asks, not preprocessor tweaks:
- **Ambiguous tag → URA/separate LLM** and **embedded ToC/final_master_report → LLM**: new classification/routing stage, comparable in size to the existing IBAT resolver step. Needs design, not a quick patch.
- **Bearing T-number → Generator depends on Frame type**: needs a new frame-type-conditional mapping table; not currently modeled at all.
- **Cross-ESN evidence via SBoM** (sister unit installed in this train): a real architectural feature — requires SBoM lookups at ingestion time, well beyond current preprocessor scope.
- **Typos mixing sister-unit ESNs**: source-document data-quality issue. No preprocessor rule can reliably catch this — better handled as a manual override list or targeted post-hoc audit (you already have `check_*` / `audit_*` scripts in this workspace for exactly this kind of spot-check).

---

## Answer to your cost/time question

**Yes — for items 1, 2, 3 this is the right move and will save significant cost/time**, provided the fix stays confined to attribution metadata:

- Embeddings are generated from `chunk_text`, and `chunk_text`/`chunk_id` boundaries come from a separate chunking step, not from ESN/equipment-type tagging. Fixing the tagging rules (1a, 1b, 3) does **not** require re-chunking or re-embedding — those are the expensive steps (LLM + embedding API calls).
- Recommended flow: (1) re-run only the preprocessor's rule-based tagging (no LLM calls) against the existing documents to regenerate corrected regions/metadata, (2) reconcile corrected region attribution to existing `chunk_id`s by page/position overlap, (3) bulk `UPDATE` the `generator_serial`/`metadata` (equipment_type, confidence, source) columns keyed by `chunk_id`. Skip re-chunking and re-embedding entirely.
- Validate on a small known-bad sample first (e.g., the two ESNs you cited: `5a82aa03...` and `0be4a3ad...`) before a full backfill — you already have tooling in this workspace (`accuracy_check.py`, `batch_subcomp_check_v2.py`, etc.) suited to that spot-check.
- **Caveat**: item 2 (retrieval skipping "shared" docs) is a retrieval-service bug, not a chunk-tag problem — fixing it doesn't touch the chunk table at all, so it shouldn't be bundled into the same backfill cost estimate.
- Item 4 items are not "fix and overwrite" candidates yet — they need new logic built and validated first; only after that would a similar cheap tag-overwrite backfill apply.