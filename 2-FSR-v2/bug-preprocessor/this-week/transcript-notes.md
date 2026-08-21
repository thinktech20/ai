# Transcript Notes — FSR Pre-processor Edge Cases

Meeting ~32 min. Three recording gaps: 0:47→3:35, 10:59→15:13, 22:08→27:17.

---

## Xujin's edge cases (pre-processor bugs)

She had a categorized list of issues tracked in SharePoint. Main ones walked through:

1. **Multiple same-equipment ESNs in one doc** (~7:00)
   If a report covers two gas turbines (or two generators), the pre-processor tags chunks to the wrong ESN once it hits a new equipment section boundary — everything after gets attributed to the "first active" ESN rather than the correct one.

2. **Generator subsection under a gas turbine section** (~9:12)
   When a generator section is nested under a gas turbine section, chunks should link to the generator ESN on the same train. After the generator subsection ends and the doc returns to gas turbine topics (e.g., inlet bell), the logic incorrectly keeps attributing those chunks to the generator.

3. **"Electrification" section = generator signal** (~15:38)
   A section header called "Electrification" is a reliable indicator of generator content, just like "DC leakage." The pre-processor doesn't currently recognize it.

4. **Generator ESN completely absent from the document** (~16:05)
   Some reports don't have the generator ESN anywhere in the body text — only a gas turbine ESN — but the content clearly discusses generator evidence. Pre-processor has no way to tag those chunks correctly.

5. **Steam turbine doc with embedded generator evidence** (~27:17)
   A steam turbine ESN document that contains generator-related evidence in the body, but the word "generator" doesn't appear in the searchable text. Even an LLM scan wouldn't catch it without using the IBOT train tool to infer the relationship. Acknowledged as potentially unsolvable in the general case; suggestion was to allow SMEs to submit these as special cases.

6. **Same ER case with two different dates** (~30:39)
   Two entries appearing as the same ER case but with dates 2020-03-28 and 2021-04-26. Unclear if duplicates or versioned; Abhinaya flagged to check the vector index.

7. **ER cases not all showing in the app** (~29:38)
   The dev app's data readiness panel showed only one ER case for a unit, but citations in the response referenced others. Abhinaya clarified this was likely a single case — the extra references were internal UUID tokens, not separate ER records.

---

## Epperson's proposal — "intelligent sorter" (~17:40, ~20:25)

A two-stage pre-processing approach to handle edge cases without running everything through an expensive LLM path:

- **Stage 1 (fast sort):** Quickly assess each doc using the table of contents or full text extract and classify it. If it's clearly a pure generator or pure gas turbine doc with no ambiguity, route it straight into the standard metadata + chunking pipeline.
- **Stage 2 (smart LLM path):** If the quick scan flags ambiguity (e.g., generator content but no generator ESN, or "DC leakage" in the ToC without the word "generator"), hand it off to a smarter LLM-based parser to determine the correct ESN attribution.

Goal: avoid taking two weeks to process the full FSR dataset by reserving the heavy LLM path only for genuinely ambiguous docs.

Tao's take: keep the rest of the pipeline unchanged and add targeted fixes to the pre-processor to catch different patterns.
