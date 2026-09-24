## DS Feedback Summary (2026-07-07)

### Overall
- DS confirmed JSON schema/key coverage is aligned between DS and DEV outputs.
- Main concern is extraction quality for part numbers in a few TILs.

### Issue vs Root Cause

<table>
<colgroup>
<col style="width: 4%">
<col style="width: 22%">
<col style="width: 28%">
<col style="width: 46%">
</colgroup>
<thead>
<tr><th>#</th><th>Issue (from DS)</th><th>Root Cause (current assessment)</th><th>Suggested Fix / Improvement</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>Critical part-number mismatches in <code>1937-R2</code> and <code>1945-R2</code> (e.g., <code>145E3626</code> vs expected <code>146E3626</code>)</td><td>Not a normalization issue. Disputed values are already present in <code>raw_profile_json</code> and pass through unchanged into <code>parsed_profile_json</code>. Root-cause zone is upstream extraction (parser output and/or LLM interpretation of table text).</td><td>Run a focused parser-vs-LLM isolation check: (1) capture raw parser table cells for <code>1937-R2</code>/<code>1945-R2</code>, (2) compare with DS foundation raw extraction, (3) if parser text is correct then tighten prompt for table number fidelity, else patch parser/table OCR handling. Add targeted regression assertions for known disputed part numbers.</td></tr>
<tr><td>2</td><td>Range-style values in <code>parts_referenced.part_number</code> for <code>2045-R2</code> (e.g., <code>129T6911P0001 through P048</code>)</td><td>Also not normalization. Range text is emitted in <code>raw_profile_json</code> and retained in <code>parsed_profile_json</code>. Prompt/rules currently allow non-canonical part strings in <code>part_number</code>.</td><td>Add post-LLM normalization rule: keep <code>part_number</code> as canonical identifier only; move range qualifiers to <code>context</code>. Update prompt with explicit examples and add schema-level validator to reject <code>part_number</code> values containing words like <code>through</code>, <code>to</code>, <code>from</code>.</td></tr>
<tr><td>3</td><td><code>til_number</code> format differences (prefix and revision split behavior)</td><td>Pipeline canonicalization step splits hyphen-delimited revision suffixes (for example <code>TIL 1945-R2</code> -> <code>TIL 1945</code> + <code>R2</code>). This is downstream normalization behavior, separate from critical part-number errors.</td><td>Align output contract with DS expectation: preserve <code>til_number</code> as DS-style display value (for example <code>TIL 1945-R2</code>) or add a separate canonical key while keeping display formatting unchanged. Apply one consistent rule across runs.</td></tr>
<tr><td>4</td><td><code>source_location</code> format differences</td><td>Mostly prompt/output-format convention and parser evidence-label style differences (for example labeled table references vs preferred page/location pattern).</td><td>Standardize <code>source_location</code> template (for example <code>Page X, Table Y</code> / <code>Page X, Body text</code>) and add normalization mapping for parser labels to this format. Include 2 to 3 few-shot examples in prompt.</td></tr>
<tr><td>5</td><td><code>sbom_dependency_flag</code> disagreements</td><td>Primarily dependent on extracted MLI/part evidence. DS marked impact lower where downstream SQL logic relies on part-number triggers and values are null/empty.</td><td>Define deterministic override rules: if no MLI and no canonical part number then <code>sbom_dependency_flag=false</code>; if MLI or canonical part number exists then <code>true</code>. Keep LLM rationale in <code>sbom_trigger_reason</code> but enforce deterministic final flag.</td></tr>
<tr><td>6</td><td><code>recurring_indicator_if_found</code> disagreements</td><td>Lower impact in downstream flow because SOT recurring data is used as primary source.</td><td>Prefer SOT value when available; only use LLM-extracted value as fallback. Mark provenance if needed.</td></tr>
<tr><td>7</td><td><code>coarse_outage_type</code> differences</td><td>Lower impact in downstream flow because SOT outage type is used as primary source.</td><td>Prefer SOT outage type as authoritative. Keep LLM outage type as secondary signal for diagnostics only.</td></tr>
<tr><td>8</td><td>Lower average <code>extraction_confidence</code> on DEV output</td><td>Confidence scoring behavior/prompt behavior differs; not a blocker by itself but indicates extraction quality variance to monitor.</td><td>Calibrate confidence computation to evidence quality (table coverage, identity consistency, parse completeness). Add monitoring threshold and trend reporting instead of using raw score as pass/fail.</td></tr>
</tbody>
</table>

### Config Parity Check (DS vs Pipeline)
- Model family appears aligned (`azure-gpt-5-2`) for compared runs.
- Temperature appears aligned (`0.0`) for profile extraction.
- Main architectural difference remains parser path/method (DS pilot flow vs Databricks AI parser path used in pipeline run).

### Why LLM Is Used for Profile Extraction
- TIL PDFs are unstructured engineering documents. Parser output gives us raw text and loosely structured tables.
- The downstream contract needs a strict JSON profile with typed fields such as `compliance_category_code`, `scope_of_work`, `parts_referenced`, `service_recommendation_line_items`, etc.
- Rule-based extraction can not reliably produce free-form narrative fields like `purpose`, `scope_of_work`, `risk_summary`, `severity_signals`.
- Cross-section reasoning is required for fields such as `sbom_dependency_flag`, `configuration_dependent`, and `service_recommendation_line_items` — meaning the model must combine table content with surrounding paragraphs.
- Table + text fusion is common in TILs — for example part numbers live in tables while their meaning is in surrounding paragraphs.
- The LLM emits a fixed JSON shape, so downstream code does not need a custom parser per TIL format.
- TIL formats and revisions vary widely — deterministic per-format parsers would be brittle and hard to maintain.

What the LLM is not doing:
- It does not resolve PDF discovery or TIL id matching (that is done by regex helpers).
- It does not enforce final schema types (contract normalization does that).
- It should not be authoritative for values that already exist in SOT (like outage type, recurring flag). Those should be treated as SOT-primary and LLM value as secondary.

### DS vs Dev LLM Normalization

Comparison of what each side normalizes after the LLM emits the profile.

<table>
<colgroup>
<col style="width: 4%">
<col style="width: 14%">
<col style="width: 22%">
<col style="width: 22%">
<col style="width: 38%">
</colgroup>
<thead>
<tr><th>#</th><th>Concern</th><th>DS (SDG_Scoping_Feedback_Loop)</th><th>Dev (pw_sdg_ai_ser_repo)</th><th>Notes</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>Prompt style</td><td>Loads <code>system</code> + <code>user</code> prompt from <code>SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/prompts/*.txt</code></td><td>Loads system prompt from <code>pw_sdg_ai_ser_repo/silver/src/tils/prompts/til_profile_extraction_v2.txt</code>; user prompt built in <code>pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction_llm.py</code></td><td>Both use file-based prompts.</td></tr>
<tr><td>2</td><td>Model / temperature</td><td><code>azure-gpt-5-2</code>, <code>temperature=0.0</code></td><td><code>azure-gpt-5-2</code>, <code>temperature=0.0</code></td><td>Aligned on parameters that affect determinism.</td></tr>
<tr><td>3</td><td>Response format hint</td><td>Sets <code>response_format={"type": "json_object"}</code> in <code>SDG_Scoping_Feedback_Loop/code_assets/runtime/llm.py</code></td><td>Does not set <code>response_format</code>; relies on prompt to return JSON only</td><td>Minor difference; affects strictness of the JSON envelope.</td></tr>
<tr><td>4</td><td>JSON extraction from response</td><td><code>parse_llm_response</code> in <code>SDG_Scoping_Feedback_Loop/code_assets/runtime/llm.py</code></td><td><code>extract_json_from_llm_response</code> in <code>pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction_llm.py</code></td><td>Both strip code fences and load JSON. Similar behavior.</td></tr>
<tr><td>5</td><td>Schema defaults / list defaults</td><td><code>normalize_profile_schema</code> in <code>SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_til_profile_extraction_pilot.py</code>; sets defaults, leaves values as-is</td><td><code>canonicalize_profile_for_contract</code> in <code>pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_til_metadata.py</code> + <code>normalize_til_profile</code> in <code>pw_sdg_ai_ser_repo/contracts/schemas/tils/til_profile_schema.py</code></td><td>Dev is a bit stricter on shape enforcement.</td></tr>
<tr><td>6</td><td>Identity fields (<code>til_number</code>, <code>revision</code>)</td><td>Left as returned by the LLM</td><td>Splits hyphen-delimited revision suffix (for example <code>TIL 1945-R2</code> -> <code>TIL 1945</code> + <code>R2</code>) in <code>canonicalize_profile_for_contract</code></td><td>Explains the <code>til_number</code> formatting drift.</td></tr>
<tr><td>7</td><td><code>compliance_category_text</code></td><td>Left as returned by the LLM</td><td>Overwritten deterministically from <code>compliance_category_code</code> in <code>canonicalize_profile_for_contract</code></td><td>Current drift point. Priority fix: align to DS and preserve LLM value (remove Dev-side overwrite).</td></tr>
<tr><td>8</td><td>Part numbers</td><td>Not modified after LLM</td><td>Not modified after LLM</td><td>Range values and wrong digits both flow through unchanged.</td></tr>
<tr><td>9</td><td><code>source_location</code></td><td>Not modified after LLM</td><td>Not modified after LLM</td><td>Format differences come from prompt + parser evidence labels.</td></tr>
<tr><td>10</td><td>SOT-primary override for <code>coarse_outage_type</code> / <code>recurring_indicator_if_found</code></td><td>Not applied in pipeline; DS handles these as SOT-primary downstream</td><td>Not applied in pipeline</td><td>Neither side overrides at extraction time. Downstream analysis is where DS prefers SOT.</td></tr>
</tbody>
</table>

### Normalization Comparison — Identifier Helpers (DS vs Dev)

Identifier/normalization helpers used before and after LLM extraction.

<table>
<colgroup>
<col style="width: 4%">
<col style="width: 14%">
<col style="width: 22%">
<col style="width: 22%">
<col style="width: 38%">
</colgroup>
<thead>
<tr><th>#</th><th>Concern</th><th>DS (SDG_Scoping_Feedback_Loop)</th><th>Dev (pw_sdg_ai_ser_repo)</th><th>Notes</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>TIL id from filename</td><td><code>_til_number_from_filename</code> in <code>SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/til_pdf_utils.py</code></td><td><code>til_number_from_filename</code> in <code>pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction.py</code></td><td>Same regex <code>TIL\s+([\d\-R]+)</code>. Runs before LLM to discover PDFs. Not related to part-number accuracy.</td></tr>
<tr><td>2</td><td>Canonical TIL key</td><td><code>normalize_til_key</code> in <code>SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_gt_til_scope_eval.py</code> (re-exported in step6 modules)</td><td><code>normalize_til_key</code> in <code>pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction.py</code></td><td>Same rule: uppercase and strip non-alphanumerics. Used for matching, not content extraction.</td></tr>
<tr><td>3</td><td>Base TIL number</td><td><code>extract_base_til_num</code> in <code>SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_gt_til_scope_eval.py</code></td><td><code>extract_base_til_num</code> in <code>pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction.py</code></td><td>Same regex chain: strip leading <code>TIL</code>, trailing <code>R&lt;n&gt;</code>, then extract numeric core. Used for lookup keys.</td></tr>
<tr><td>4</td><td>Revision number</td><td><code>parse_revision_number</code> in <code>SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_gt_til_scope_eval.py</code></td><td><code>parse_revision_number</code> in <code>pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction.py</code></td><td>Same trailing <code>R(\d+)$</code> rule. Not used to modify LLM output.</td></tr>
<tr><td>5</td><td>PDF-to-TIL matching</td><td><code>pick_pdf_row</code> in <code>SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_til_profile_extraction_pilot.py</code></td><td><code>pick_pdf_row</code> / <code>pick_pdf_row_by_name</code> in <code>pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction.py</code></td><td>Same strategy: exact <code>normalized_til_key</code>, else base TIL with highest revision.</td></tr>
<tr><td>6</td><td>Profile schema normalization</td><td><code>normalize_profile_schema</code> in <code>SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_til_profile_extraction_pilot.py</code></td><td><code>canonicalize_profile_for_contract</code> in <code>pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_til_metadata.py</code> + <code>normalize_til_profile</code> in <code>pw_sdg_ai_ser_repo/contracts/schemas/tils/til_profile_schema.py</code></td><td>DS: minimal defaults, does not modify part numbers. Dev: same for parts, but additionally splits hyphen-delimited revision suffixes in <code>til_number</code> (for example <code>TIL 1945-R2</code> -> <code>TIL 1945</code> + <code>R2</code>), which explains the <code>til_number</code> formatting drift. Priority fix: keep strict typing/defaults but stop identity-format rewriting to match DS output shape.</td></tr>
<tr><td>7</td><td><code>compliance_category_text</code> derivation</td><td>Not applied. Uses LLM output as-is.</td><td>Deterministic map from <code>compliance_category_code</code> in <code>canonicalize_profile_for_contract</code>.</td><td>Dev-only enrichment; not related to part-number accuracy.</td></tr>
<tr><td>8</td><td>Part number normalization</td><td>Not applied. LLM output is preserved.</td><td>Not applied. LLM output is preserved.</td><td>Explains why range-style values persist in both raw and parsed on Dev side.</td></tr>
<tr><td>9</td><td><code>source_location</code> normalization</td><td>Not applied. Uses model output directly.</td><td>Not applied. Uses model output directly.</td><td>Style differences flow from prompt instructions and parser evidence labels.</td></tr>
</tbody>
</table>

### Critical Items
- Part number extraction accuracy needs correction for:
	- `1937-R2`
	- `1945-R2`
- DS observed wrong/missing part numbers and reduced counts in these cases.
- Specific example called out by DS:
	- Extracted: `145E3626`
	- Expected: `146E3626`

### High-Priority Adjustments
- Normalize `parts_referenced.part_number` to clean identifier values only.
	- Avoid range-style text in `part_number` (e.g., `... through ...`).
	- Keep any explanatory/range text in context fields, not in `part_number`.
- Align `source_location` format with DS preference (page/location style).

### Priority-First Fixes (Agreed)
1. <b>2nd table, row 7 - <code>compliance_category_text</code> alignment</b>
	- Action: align with DS behavior and stop overriding this field in Dev canonicalization.
	- Implementation note: in <code>canonicalize_profile_for_contract</code>, keep LLM-provided <code>compliance_category_text</code> instead of deterministic remap from code.

2. <b>3rd table, row 6 - profile schema normalization parity</b>
	- Action: keep schema defaults/typing, but remove identity-format transformations that create DS drift (especially <code>til_number</code> revision split).
	- Implementation note: maintain strict typing via <code>normalize_til_profile</code>, but avoid rewriting semantic/display identity values.

3. <b>Part-number cleanup (highest extraction-quality priority)</b>
	- Action: enforce <code>parts_referenced.part_number</code> as identifier-only.
	- Rule: reject or rewrite range-style strings in <code>part_number</code> (for example containing <code>through</code>, <code>to</code>, <code>from</code>, ranges, or long prose).
	- Rule: move qualifiers/range text into context fields, not <code>part_number</code>.

4. <b><code>source_location</code> format alignment</b>
	- Action: standardize to DS page/location style (for example <code>Page X, Table Y</code> / <code>Page X, Body text</code>), with prompt examples and optional post-normalization mapper.

### Why Part-Number Behavior Can Differ From DS
- Your hypothesis is likely correct: parser-path differences are the primary suspect.
- DS pilot uses foundation parser flow with pdfplumber fallback; Dev run used Databricks AI parser output.
- For critical mismatches (for example <code>1937-R2</code>, <code>1945-R2</code>), wrong values already appear in <code>raw_profile_json</code>, so downstream schema normalization is not causing those errors.
- Practical interpretation: if parser table text differs, LLM extracts different part numbers; if parser text is identical, then prompt/LLM extraction behavior is the next suspect.
- Recommended isolation check:
  1. Capture raw parser table cells for disputed TILs from both DS and Dev parser paths.
  2. Diff parser outputs before LLM.
  3. Run the same prompt/model on both parser payloads to separate parser vs extraction effects.

### Medium/Low Impact Differences (Not Blocking per DS)
- `coarse_outage_type` differences for a subset of TILs.
	- Not critical because downstream primarily uses SOT outage type.
- `recurring_indicator_if_found` differences.
	- Not critical because downstream primarily uses SOT recurring info.
- `sbom_dependency_flag` disagreements in some TILs.
	- Lower impact where part numbers are null and downstream trigger logic uses part numbers.
- `til_number` formatting drift (e.g., `TIL 1502-2R1` vs `1502-2R1`).
	- Mostly formatting, but should be standardized for downstream consistency.
- DEV-side `extraction_confidence` is lower on average.

### DS Input Provided
- DS shared updated prompt version with edits to address observed disagreements.
- Prompt includes tighter guidance around part extraction, source location formatting, and table handling.

### Recommended Next Steps
1. Re-run extraction after applying part-number fixes (highest priority).
2. Validate specifically on `1937-R2`, `1945-R2`, and `2045-R2`.
3. Standardize `til_number` formatting and `source_location` output style.
4. Re-run 25-TIL comparison and publish delta focused on:
	 - part-number precision/recall
	 - identity-field parity
	 - remaining non-blocking differences.

### References

#### Feedback inputs
- DS feedback comparison: `1-TILs/input/DS-feedback/comparison_DS_vs_DEV_20260707.md`
- DS quick feedback note: `1-TILs/input/DS-feedback/feedback`
- DS updated prompt (shared): `1-TILs/input/DS-feedback/til_profile_extraction_pilot_0707.txt`
- Latest DS extracted profiles: `1-TILs/analysis/ds-team-til-profile-results/til_profile_pilot_20260609_110447`
- Pipeline metadata evidence (raw + parsed profile JSON): `1-TILs/input/til-metadata/til-metadata-08-jul.csv`

#### Dev code paths (our pipeline)
- Identifier helpers (regex, discovery, matching): `pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction.py`
- Extraction notebook (profile canonicalization, Delta merge): `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_til_metadata.py`
- LLM client and default config: `pw_sdg_ai_ser_repo/common/tils/til_llm_client.py`
- Strict schema normalization: `pw_sdg_ai_ser_repo/contracts/schemas/tils/til_profile_schema.py`

#### DS code paths (SDG_Scoping_Feedback_Loop)
- Pilot runner (parser/method/model invocation): `SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_til_profile_extraction_pilot.py`
- Filename discovery + regex helpers: `SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/til_pdf_utils.py`
- Regex/normalization helpers (imported by pilot): `SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_gt_til_scope_eval.py`
- Runtime LLM config: `SDG_Scoping_Feedback_Loop/code_assets/runtime/config.py`
- Runtime LLM client: `SDG_Scoping_Feedback_Loop/code_assets/runtime/llm.py`

### Open Questions for DS
- If we want stronger consistency at pipeline output level, we need a small SOT-override step:
	- lookup TIL row in SOT tables (outage type, recurring flag)
	- if SOT value present, replace LLM value in the profile before Delta merge
	- keep the LLM value in `raw_profile_json` for traceability
