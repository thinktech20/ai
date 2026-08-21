# 8-19 with Electrical / Electrification top-level rule

Snapshot of the two working files before revert.

Change: added `N Electrical System / N Electrical / N Electrification` as a Generator top-level section (SECTION_HDR) so free-form subsections under it (e.g. `5.2 Sniff check`, `5.3 Shaft Seal Housing`, `5.4 Hydrogen Coolers`) get emitted as Generator regions instead of being dropped by the SUBSEC_GENERIC Generator-context filter.

Files:
- `preprocessor_v2.py` — new `SECTION_HDR_GEN_KEYWORD` regex + top-level loop, `_toc_equipment_anchors` extended, SUBSEC_GENERIC guardrail relaxed for explicit Generator roots.
- `test_preprocessor_v2.py` — `test_electrical_system_root_types_generator_and_promotes_subsections`.

Status: not committed in `fsr_v2` branch. Kept here for reference; can be re-applied via `cp` back into the repo when ready.
