# PR #397 Review — Multi-ESN FSR Retrieval

**Repository:** `arc-genai/uai3071390-genai-services-demand-generation-usecase`  
**PR:** [#397 — Multi esn fsr retrieval](https://github.apps.gevernova.net/arc-genai/uai3071390-genai-services-demand-generation-usecase/pull/397)  
**Author:** 560059620  
**Reviewed:** 2026-07-29  
**PR Head Commit:** `678609fb`  
**Verdict:** ❌ **REQUEST CHANGES**

---

## 1. Scope

5 commits, 9 files, +458/−164 lines. This is the **app-side implementation** of the multi-ESN retrieval strategy — the counterpart to PR #156's Databricks-side notebooks.

### Files Changed

| File | Change Summary |
|---|---|
| `retriever_service.py` | Core change — adds multi-ESN index routing for vector search |
| `equipment_service.py` | Adds multi-ESN-aware FSR report listing + data-readiness counts |
| `config.py` | Adds `FV_FSR_METADATA_V2_TABLE` config |
| `prompt_builder.py` | Defensive: gracefully skip missing `fsr_result.json` / `er_result.json` |
| `generate_fsr_similarity_report.py` | New dev/debug script — parses retrieval log → Excel similarity scores |
| `DataReadinessPanel.tsx` | Adds per-source checkboxes (ER/FSR toggling), fixes loading state |
| `RiskConditionRow.tsx` | Breaks long words in evidence text for UI wrapping |
| `Header.tsx` | Adds ServiceNow link button to header |
| `.gitignore` | Adds `fsr_retrieval_log.txt` |

---

## 2. Findings

### Issue 1: XSS Vulnerability — `dangerouslySetInnerHTML` (CRITICAL)

**File:** `frontend/src/components/reliability/RiskConditionRow.tsx`

```tsx
const breakLongWords = (text: string, chunkSize = 100): string => {
  return text.replace(/\S{101,}/g, (word) => {
    return word.match(new RegExp(`.{1,${chunkSize}}`, "g"))!.join("<br>");
  });
};

// Two call sites:
<span dangerouslySetInnerHTML={{ __html: breakLongWords(condition.evidence) }} />
```

`condition.evidence` is raw chunk text sourced from Databricks FSR documents. It is **not sanitized** before being rendered as live HTML. If any FSR chunk contains `<script>`, `<img onerror=...>`, or other HTML payloads, they will execute in the user's browser.

**Fix:** Use CSS `word-break: break-all` or `overflow-wrap: break-word` instead of injecting `<br>` via innerHTML. If HTML injection is truly needed, sanitize with DOMPurify first:

```tsx
import DOMPurify from 'dompurify';
// ...
<span dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(breakLongWords(condition.evidence)) }} />
```

Or preferably, the pure CSS approach (no innerHTML at all):

```tsx
<Typography sx={{ wordBreak: 'break-all', overflowWrap: 'break-word' }}>
  {condition.evidence}
</Typography>
```

---

### Issue 2: `verify=False` on Databricks API Call (HIGH)

**File:** `backend/services/data-service/src/data_service/services/retriever_service.py` (line ~481)

```python
response = requests.post(
    f"{cfg['workspace_url']}/api/2.0/vector-search/indexes/{search_index}/query",
    headers={"Authorization": f"Bearer {cfg['token']}", ...},
    json=query_json,
    timeout=300,
    verify=False,  # ← TLS verification disabled
)
```

TLS certificate verification is disabled for the Databricks vector search API call. This was already flagged in PR #156's Databricks notebooks (`uc2_current.py`, `uc2_future.py`). Now it's in the **production app service** too — a bearer token is sent over a connection that doesn't verify the server's identity. MitM attacks can intercept the token and all query results.

**Fix:** Configure the corporate CA bundle:
```python
import certifi
CA_BUNDLE = os.getenv("REQUESTS_CA_BUNDLE", certifi.where())
# ...
response = requests.post(..., verify=CA_BUNDLE)
```

---

### Issue 3: Inconsistent SQL Parameterization (MEDIUM)

Two different SQL safety patterns are used across the PR:

| File | Pattern | Safety |
|---|---|---|
| `retriever_service.py` | `:sanitized_esn` with `{"sanitized_esn": sanitized_esn}` param dict | ✅ Proper parameterized query |
| `equipment_service.py` | `f"esn = {sql_literal(esn)}"` with `sql_literal` escaping (`'` → `''`) | ⚠️ Weaker — string interpolation with allowlisted-character escaping |

The `sql_literal` approach is pre-existing code (not introduced by this PR) and is minimally safe for alphanumeric ESNs, but the inconsistency is a maintenance risk.

**Recommendation:** Standardize on parameterized queries (`db_client.query_async` with `:param` placeholders) for all new code. Consider a follow-up PR to migrate `equipment_service.py` off `sql_literal`.

---

### Issue 4: Index Routing Doesn't Match 0728 Meeting Decision (DESIGN)

**File:** `retriever_service.py` lines ~374-400

The agreed approach from the 0728 team meeting was: **hardcode ~7-10 specific known-confusion ESNs** to route to the new multi-ESN index in QA, leave everything else on the old index.

The actual implementation does something different — it checks the multi-ESN table first for **every ESN** and falls back to the old index only if no documents are found:

```python
if _FSR_LOOKBACK_SET:
    success, multi_esn_doc_ids = await _retrieve_multi_esn_document(sanitized_esn)
    if success:
        use_multi_esn_index = True  # ← Routes to new index for ANY ESN that has multi-ESN docs
        filtering_json = json.dumps({
            "region_primary_esn": sanitized_esn,
            "document_id": multi_esn_doc_ids,
        })
    else:
        # Fall back to timeboxed primary index
        success, pdf_search_list = await _retrieve_timeboxed_document(sanitized_esn)
```

This is effectively **"new-index-first"** (Madhurima's position from the meeting), not the conservative compromise Epperson agreed to. Worth confirming with the team whether the hardcoded-ESN-list approach was intentionally abandoned.

Also note: `_retrieve_multi_esn_document` filters by `is_active = true` (line ~266), which is subject to the **footer false-positive bug** discussed in the 0728 meeting (blank pages with ESN-listing footers incorrectly marking ESNs as inactive).

---

### Issue 5: Integer Interpolation in SQL Lookback Clause (LOW)

**File:** `retriever_service.py`, `equipment_service.py` (multiple locations)

```python
f"AND m.outage_start_date >= DATE_FORMAT(ADD_MONTHS(CURRENT_DATE(), -{_FSR_LOOKBACK_MONTHS}), 'yyyy-MM-dd')"
```

`_FSR_LOOKBACK_MONTHS` is `int(os.getenv("FSR_LOOKBACK_MONTHS", "120"))` — safely cast at config load time. Direct interpolation is safe as-is. Only a concern if someone later changes the config to accept raw strings without `int()` coercion.

---

### Issue 6: No Step 2b Fallback for Unattributed Chunks (DESIGN)

**File:** `retriever_service.py`

The vector search (Step 2) filters by `region_primary_esn` for the multi-ESN index path. There is **no fallback for unattributed chunks** (`primary_esn == ""`). This is pure **Path A** — strict `primary_esn` filter, no safety net.

The Step 2b fallback that exists in PR #156's Databricks notebooks (`uc2_current.py`) — which searches eligible docs for chunks with `primary_esn == ""` when primary results are insufficient — is **not implemented** on the app side.

**Relevance:** SME feedback from `FSR pattern discussion.txt` (Keith Harris) contradicts the assumptions Path A requires:
- Executive summary details are "sometimes not repeated" in sub-sections → filtering them out loses real content
- Generator evidence appearing under non-Generator headers (e.g., electrical testing sections) "will need to be captured"
- Keith's stated preference: "I would rather start excluding the turbine information **over time**" → prefers inclusion first

This means the app-side retrieval may silently miss Generator evidence that's buried under non-Generator headers or in mixed-content summary sections, with no fallback mechanism to catch it.

---

## 3. Positive Changes

- **Parameterized queries in `retriever_service.py`**: All three SQL statements use `:sanitized_esn` / `:sanitized_query` with param dicts — proper and secure.
- **`prompt_builder.py` defensive guards**: Gracefully returns `[]` when `fsr_result.json` / `er_result.json` are missing, instead of crashing with `FileNotFoundError`. Clean fix.
- **`generate_fsr_similarity_report.py`**: Well-structured dev tooling — parses retrieval summary logs into Excel for offline similarity-score analysis. Handles edge cases (embedded stray timestamps in log lines, unbalanced braces).
- **DataReadinessPanel checkbox UI**: Clean implementation with `aria-label`, event propagation handling (`stopPropagation`), and `isReadinessLoading` local state replacing the global `selectDocumentsLoading` selector (better state scoping, fixes race conditions with per-source detail fetches).
- **Header ServiceNow link**: Uses `rel="noopener noreferrer"` and `target="_blank"` correctly. Proper accessibility with `aria-label` and `title`.

---

## 4. Verdict Summary

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | XSS via `dangerouslySetInnerHTML` on unsanitized evidence text | **Critical** | ❌ Must fix |
| 2 | `verify=False` on Databricks vector search API call | **High** | ❌ Must fix for prod |
| 3 | Inconsistent SQL parameterization (`sql_literal` vs `:param`) | Medium | ⚠️ Pre-existing, recommend follow-up |
| 4 | Index routing is "new-index-first" for all ESNs, not hardcoded subset per 0728 decision | Design | ⚠️ Confirm with team |
| 5 | Integer interpolation in SQL lookback clause | Low | ✅ Acceptable |
| 6 | No Step 2b fallback for unattributed chunks (pure Path A, conflicts with SME feedback) | Design | ⚠️ Confirm with team |

**Overall: REQUEST CHANGES** — Issue #1 (XSS) is a security blocker. Issue #2 (`verify=False`) must not ship to production. Issues #4 and #6 are design-alignment questions requiring team confirmation against the 0728 meeting decisions and SME feedback documented in `FSR pattern discussion.txt`.

---

## 5. Cross-Reference to PR #156

This PR implements the app-side counterpart to PR #156's Databricks-side retrieval notebooks. Shared concerns:
- `verify=False` appears in both PRs (PR #156: `uc2_current.py` line ~56, `uc2_future.py` line ~54; this PR: `retriever_service.py` line ~481)
- The `is_active=true` filter (subject to footer false-positive bug) is used in both PRs
- PR #156's Step 2b fallback logic is present in the notebooks but **not** mirrored here on the app side
- PR #156's SQL injection issues (f-string interpolation of `REQUESTED_ESN`) are **not** present here — `retriever_service.py` correctly uses parameterized queries
