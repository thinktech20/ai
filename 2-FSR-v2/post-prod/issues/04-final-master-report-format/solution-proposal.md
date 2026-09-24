# Solution Proposal

Updated: 2026-09-22
Issue: Final master report format

## Proposed direction

Treat this format as an explicit preprocessing profile selected from
family-specific evidence. For known in-volume documents, the reliable filename
or document-ID signal can select the profile and parsed structure validates it.
For unknown or future documents, selection should require the structural
signals expected for this family rather than relying on a filename alone.

The filename can be retained as a routing signal for the current document
volume. Names containing `final_master_report` or `Final_Master_Report`, along
with document IDs in the known inventory, are reliable conditions for existing
in-volume documents. Parsed structural signals should still validate the
routing decision and support future documents whose names are inconsistent or
unavailable.

The meeting review also confirms an important family constraint: the observed
final master reports contain at most one turbine and one generator evidence
item. This supports a conservative `shared` fallback for ambiguous content.
It must not be generalized to 36UUID documents, where multiple turbine or
generator evidence items can occur.

## Proposed actions

- Add a behavior-based family detector before profile-specific preprocessing.
- Add a dedicated Components attribution strategy for documents that meet the
	detector's confidence threshold.
- Implement the unlabeled-content page-fallback strategy in the same profile
	implementation, behind an explicit configuration option and separate
	acceptance checks.
- Reuse the existing region, offset, metadata, and full-coverage helpers rather
	than copying the current preprocessor into a second independent pipeline.
- Validate the profile on representative samples from the family and compare
	its output with the current preprocessor output.
- Persist the selected profile, detection method, confidence, and signals for
	operational review.

Each document is processed by exactly one profile. The default/36UUID profile,
the final-master-report profile, and any later legacy/versioned profile each
produce their own heading candidates and attribution spans, then use the same
shared region, offset, metadata, and full-coverage framework. Their outputs are
not merged for an individual document.

## Behavioral family detection

Behavioral detection is a family-specific classification step, not one
universal rule that identifies every document family. The dotted Contents
format (`. . . . . .`) is a strong signal observed in final-master-report
documents. Its presence in 36UUID and versioned/legacy reports has not been
established and should not be assumed without representative parsed samples.
Each family needs its own discriminating signal set and routing rules.

For `final_master_report`, the detector should inspect parsed text, document
identity, and heading candidates using these signals:

1. A fully capitalized numbered heading in the observed form `2. COMPONENTS`
	 or `3. COMPONENTS`: a number, dot, space, then `COMPONENTS`. Do not treat
	 a generic occurrence of the word `COMPONENTS` as equivalent evidence.
2. Fully capitalized category lines inside Components beginning with one of
	 the supported equipment labels: `GAS TURBINE`, `STEAM TURBINE`,
	 `GENERATOR`, or `UNCATEGORIZED`. The same rule applies to all four labels;
	 `GENERATOR` is only an example, not a special case.
3. Number-before-title content headings, such as `2.1 Dallas Shop QC Report`.
4. A plausible boundary from the Components heading to the next top-level
	 section.
5. A filename containing `final_master_report` or `Final_Master_Report`, or a
	 document ID present in the known final-master-report inventory.

Suffixes after these labels are allowed when the label remains the leading
	 fully capitalized phrase, for example `GAS TURBINE - BEARINGS` or
	 `GENERATOR - STATOR`. The `GENERATOR -` form is an additional family
	 signal, but the category-marker rule itself applies equally to Gas Turbine,
	 Steam Turbine, Generator, and Uncategorized. Plain `GENERATOR` can still
	 occur in other formats, so it is not sufficient as a family discriminator
	 by itself.

The exact numbered all-capital `COMPONENTS` heading, supported category markers,
`GENERATOR -` labels, and known final-master-report identity are strong
signals. The dotted Contents format is also a strong signal for the observed
final-master-report format. Number ordering and a valid section boundary
provide supporting evidence.

The dotted signal must be detected in the primary ToC area, not across the
entire document. The initial deterministic boundary is the first 10% of parsed
pages, including at least the first page. This prevents an embedded or
sub-report ToC later in the document from creating a false family signal. A
future parser can replace this heuristic with an explicit primary-ToC boundary
when that boundary is reliably available.

A possible scoring model is:

| Signal | Weight |
| --- | ---: |
| Components heading detected | 2 |
| Supported category marker inside Components | 2 |
| Dotted Contents pattern | 2 |
| `GENERATOR -` discriminator | 2 |
| Number-before-title pattern | 1 |
| Valid next top-level boundary | 1 |
| Known final-master-report filename or document ID | 2 |

The profile should be selected when the routing evidence meets the agreed
threshold. For known in-volume documents, the reliable filename/document-ID
signal may select the profile, with structural validation performed afterward.
For unknown or future documents, require the structural final-master-report
signals instead of relying on the filename alone. Record which signals were
used so filename-routed and behavior-routed decisions are distinguishable.

If the evidence is insufficient, the document should remain on the existing
default preprocessing profile.

## Components labeling rule (from the 2026-09-22 review)

- Detect the `COMPONENTS` section by title, allowing `2. COMPONENTS` and `3. COMPONENTS`; do not hard-code the section number.
- Default: all content outside both Components and Appendix is labeled
	`shared`.
- PDF reference entries, such as `4.1 VIBRATION REPORT.PDF`, are expected to
	 occur only within Components or Appendix. This supports keeping all content
	 outside those two sections as `shared`.
- Inside Components, explicitly labeled content follows the equipment-leading
	marker. If Components has no usable category label, send the complete
	Components section to page fallback.
- Walk content in order and flip the active label only when a category line begins with `GAS TURBINE`, `STEAM TURBINE`, `GENERATOR`, or `UNCATEGORIZED`.
- Everything after a detected label is tagged to that label until the next detection (no lookback, no parent/section-number-driven overrides).
- `UNCATEGORIZED` maps to `shared`; the other three leading phrases map to Gas Turbine, Steam Turbine, or Generator. For example, `GAS TURBINE - BEARINGS` maps to `Gas Turbine`.
- Send Appendix content to page fallback.
- If Components is absent, still apply page fallback to Appendix when present;
	otherwise use the document-level fallback rule below.
- Heading-order assumption for this family: the section number precedes the title (e.g. `2.1 Dallas Shop QC Report`).

Category matching should be anchored to a heading/category line, not to any
incidental mention in body text. For example, `Generator flange above` should
not start a Generator region. Labels with additional text are allowed when
the supported equipment phrase is the leading phrase, while unrelated nested
labels such as `JOURNAL BEARING` do not change the active equipment label.

## Page fallback assessment

Page fallback is implemented in the same profile but remains a separate
decision within that profile. It applies only to an entirely unlabeled
Components section and to Appendix content, especially scanned or embedded
sub-reports where a category marker is missing. It must not override an
explicit Components label.

The supplied reference implementation shows that page-level classification is
feasible with the existing parsed-page offsets. It uses ESN presence,
equipment-specific forms, and keyword signatures, then merges adjacent pages
with the same metadata. It is not directly reusable for this requirement:

- it assigns pages to Generator or Gas Turbine when one signal wins;
- mixed Generator/Gas Turbine signals fall back to the document's primary type;
- it does not implement the proposed safety behavior of assigning ambiguous
	unlabeled content to `shared` when Generator evidence is high.
- its page-assignment branch is used only when fewer than two distinct
	equipment types were already found in structured boundaries, so it would not
	automatically solve unlabeled appendix pages in every mixed document.

The fallback checks for Generator evidence within its eligible span: one
Generator occurrence in the ToC or repeated, anchored Generator evidence in
body text. If the calibrated evidence threshold is met, assign the fallback
span to `shared`. When that occurs, use the resolved Gas/Steam Turbine ESN as
the train anchor for an IBAT Generator lookup. If IBAT returns one active
Generator ESN, persist it as document-level `gen_esn` while keeping the fallback
span `shared`. Otherwise, record the resolution as unresolved or ambiguous and
do not guess a Generator ESN. If Generator evidence does not qualify, assign
the fallback span to the document's single identified turbine type, Gas Turbine
or Steam Turbine. If turbine type cannot be resolved confidently, assign
`shared` rather than guessing.

Use `>7` qualifying Generator evidence items as the initial experiment
threshold, configured rather than hard-coded. This is a starting point for
validation, not a permanent production value. Raw substring counts remain
unsafe because ordinary prose can repeat `generator`; the implementation must
count anchored keyword groups within page/span boundaries and record the
evidence that triggered the fallback. Recalibrate the threshold against
scanned and text sub-reports before broad rollout.

This fallback is feasible in the same implementation because the reference
code already has page offsets and signature-count patterns. It should be
implemented as a new shared-fallback decision, not copied wholesale from the
older preprocessor. The Components label rule and page fallback should still
have separate feature settings, tests, metrics, and acceptance criteria so
either behavior can be compared or rolled back independently.

## Shared implementation boundary

The profile should use the existing preprocessor output contract:

```text
metadata, hints, regions
```

Shared code should continue to own parsed-page offsets, region construction,
full character coverage, shared gap handling, metadata serialization, and
downstream compatibility. The profile-specific code should own only family
detection and Components label transitions. Generic parent equipment
inheritance should not override the explicit Components label state.

This keeps the default and final-master-report behavior in one maintained
preprocessing framework. Fixes to offsets, region coverage, or metadata shape
are made once and remain compatible with existing chunking and enrichment.

## Fallback behavior

- Unknown or low-confidence family: use the existing default profile.
- Known in-volume final-master-report filename or document ID: allow the
	final-master-report profile, then validate its Components/Contents structure.
- Outside Components and Appendix: assign `shared`.
- Explicitly labeled Components content: follow the recognized category label.
- Entirely unlabeled Components content and Appendix: apply page fallback.
- Generator evidence found once in ToC or repeatedly in the eligible body span:
  assign `shared`.
- No qualifying Generator evidence: assign the resolved Gas Turbine or Steam
  Turbine; unresolved turbine type remains `shared`.

## Retrieval attribution implications

The expected retrieval behavior has three cases:

1. **Explicit Generator label:** A `GENERATOR - ...` span receives Generator
	attribution. Other labels and content outside Components/Appendix remain
	`shared`. Shared chunks can be retrieved through both the Generator and Gas
	Turbine ESNs when both ESNs are present in the chunk's active-ESN metadata.
2. **Unlabeled fallback with Generator evidence:** The fallback span remains
	`shared`, and the resolved Gas/Steam Turbine ESN is used for a train-scoped
	IBAT Generator lookup. If IBAT returns one active Generator ESN, persist it
	as document-level `gen_esn`. This allows the whole document to be retrieved
	through both Generator and turbine ESNs without pretending the content can be
	separated reliably. If IBAT returns zero or multiple candidates, retain the
	shared span and record the Generator resolution as unresolved rather than
	guessing.
3. **No label and no Generator fallback:** Keep the content `shared` and do
	not add a Generator ESN. Generator-ESN retrieval should not return the
	document, while Gas Turbine retrieval may still return it through the
	document's Gas Turbine ESN.

The chunking layer builds active-ESN metadata from document-level ESNs and
region-level ESNs. Therefore, the fallback's `primary_equip_type="shared"`
alone does not make a chunk retrievable through both equipment ESNs; both ESNs
must be present in the persisted metadata.

The selected profile should record detection metadata similar to:

```json
{
	"preprocessor_profile": "final_master_report",
	"preprocessor_profile_version": "v2",
	"profile_detection": {
		"method": "behavioral",
		"confidence": 0.92,
		"signals": [
			"components_heading",
			"equipment_category_marker",
			"number_before_title",
			"valid_top_level_boundary"
		]
	}
}
```

The exact confidence representation can follow the existing metadata schema;
the important requirement is that the routing decision is explainable.

Persist the actual profile and strategy used for every document, not only the
expected profile for the run. Store profile, profile version, strategy name,
routing signals, score, and fallback reason in the existing
`preprocessor_regions` JSON immediately. Add document-level metadata columns for
`preprocessor_profile`, `preprocessor_profile_version`,
`preprocessor_strategy`, and `preprocessor_profile_detection` when operational
reporting requires simple SQL aggregation by profile. Region diagnostics should
include the fallback mode and reason so individual attribution decisions can be
reviewed.

For example, one run may contain documents recorded as:

```json
{
	"preprocessor_profile": "final_master_report_v2",
	"preprocessor_strategy": "components_labels",
	"preprocessor_profile_version": "v2.1",
	"profile_detection": {
		"method": "known_document_inventory",
		"signals": ["final_master_report_filename", "dotted_contents", "components_heading"],
		"score": 6
	}
}
```

Another document in the same `run_id` can record
`preprocessor_profile="uuid_section_path_v1"` and
`preprocessor_strategy="numbered_toc_sections"`. The run ID groups the
operation; the per-document profile fields show which strategy actually ran.

## Validation and acceptance

Validate at least the following cases:

- Components numbered as section 2.
- Components numbered as section 3.
- Gas Turbine labels with suffixes, such as `GAS TURBINE - BEARINGS`.
- Steam Turbine, Generator, and `UNCATEGORIZED` transitions.
- Explicitly labeled Components content remaining unchanged.
- Entirely unlabeled Components and Appendix content.
- Generator once in ToC, repeated Generator body evidence, and no qualifying
	Generator evidence.
- Gas Turbine, Steam Turbine, and unresolved-turbine page-fallback outcomes.
- Short reports without Components.
- Reports whose filenames do not clearly identify the family.
- Non-final-master-report documents containing incidental equipment words.
- Dotted Contents in the primary first-10%-of-pages window.
- Dotted Contents appearing only in a later embedded or sub-report ToC.

Acceptance requires that:

- the behavioral detector selects the profile only for structurally matching
	documents;
- all content outside Components and Appendix is `shared`;
- only unlabeled Components and Appendix enter page fallback;
- page fallback maps qualifying Generator-evidence spans to `shared` and
  otherwise uses the resolved turbine type or `shared` when unresolved;
- `UNCATEGORIZED` produces `shared`;
- equipment-leading labels map to the expected equipment;
- nested or incidental body-text mentions do not cause label flips;
- region offsets remain contiguous and non-overlapping; and
- existing default-profile regression tests remain unchanged.

Page-fallback acceptance is separate from the core profile acceptance. Compare
the same unlabeled Components and Appendix cases with fallback disabled and
enabled, and verify that explicit Components labels and all non-fallback regions
are unchanged.

## Expected outcome

Behavior-based routing and the same-profile page-fallback implementation should
improve section attribution and downstream chunk quality for this format
without changing the default profile or destabilizing other document families.