"""Unit tests for FSR v2 redesign preprocessor and region-first chunking."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from common.fsr_v2 import preprocessor as legacy_preprocessor
from common.fsr_v2 import preprocessor_v2
from common.fsr_v2.preprocessor_v2 import EsnConfidence, EsnSource, HeadingType, SectionSpan
from gold.src.etl.fsr_v2.chunk_splitter import chunk_region_metadata, split_region_first_with_offsets
from silver.src.etl.fsr_v2 import metadata_processor_v2
from silver.src.etl.fsr_v2.parsing import ParsedDocument, load_parsed_document, save_parsed_document


def _build_ctx(full_text: str, pages: list[str] | None = None, raw_pages: list[str] | None = None):
    page_list = pages if pages is not None else [full_text]
    raw_page_list = raw_pages if raw_pages is not None else page_list
    return SimpleNamespace(
        pages=page_list,
        raw_pages=raw_page_list,
        page_offsets=[{"start": 0, "end": len(full_text)}],
        full_text=full_text,
        fields=[
            {"name": "primary_esn"},
            {"name": "primary_equip_type"},
            {"name": "primary_technology_code"},
            {"name": "inactive_esns"},
            {"name": "gt_esn"},
            {"name": "gen_esn"},
            {"name": "st_esn"},
            {"name": "all_esns"},
            {"name": "outage_start_date"},
            {"name": "outage_end_date"},
            {"name": "report_issued_date"},
            {"name": "document_name"},
        ],
        filename="test.pdf",
    )


class TestPreprocessorV2(unittest.TestCase):
    def test_regex_parity_with_legacy_preprocessor(self):
        self.assertEqual(preprocessor_v2.HEADER, legacy_preprocessor.HEADER)
        self.assertEqual(preprocessor_v2.GT_LABELS, legacy_preprocessor.GT_LABELS)
        self.assertEqual(preprocessor_v2.GEN_LABELS, legacy_preprocessor.GEN_LABELS)
        self.assertEqual(preprocessor_v2.ST_LABELS, legacy_preprocessor.ST_LABELS)
        self.assertEqual(preprocessor_v2.GENERIC_LABELS, legacy_preprocessor.GENERIC_LABELS)


    def test_unnumbered_equipment_heading_detection_bug3(self):
        full_text = "\n".join([
            "This paragraph mentions GAS TURBINE in prose and should not match.",
            "GAS TURBINE",
            "Some text",
            "GENERATOR",
        ])
        proc = preprocessor_v2.FSRV2Preprocessor()
        candidates, _ = proc._collect_heading_candidates(full_text, raw_pages=[])

        unnumbered = [
            c for c in candidates
            if c.heading_type == HeadingType.UNNUMBERED and c.equipment_type in {"Gas Turbine", "Generator"}
        ]

        self.assertGreaterEqual(len(unnumbered), 2)
        self.assertTrue(all(c.level == -1 for c in unnumbered))


    def test_hierarchy_end_offsets_and_flip_back_behavior(self):
        full_text = "\n".join([
            "GAS TURBINE (297191 | SY0000001)",
            "1 GAS TURBINE",
            "1.1 Generator Stator Test",
            "Generator details",
            "1.2 Turbine Compressor Check",
            "Turbine details",
        ])

        proc = preprocessor_v2.FSRV2Preprocessor()
        esn_ctx = proc._discover_esn_context([full_text], full_text)
        candidates, _ = proc._collect_heading_candidates(full_text, raw_pages=[])
        spans = proc._build_hierarchical_spans(candidates, len(full_text))
        proc._resolve_span_esn_local_first(spans, esn_ctx, ibat_resolver=None)

        gen_span = next(s for s in spans if "1.1 Generator" in s.heading_text)
        gt_span = next(s for s in spans if "1.2 Turbine" in s.heading_text)

        self.assertLessEqual(gen_span.end, gt_span.start)
        self.assertEqual(gt_span.resolved_esn, "297191")
        self.assertIn(gt_span.esn_source, {EsnSource.PARENT_INHERIT, EsnSource.SINGLE_TYPE})

    def test_bare_turbine_section_hdr_typed_from_doc_inventory_when_no_header(self):
        # Regression: fcb1511e — doc has no `GAS TURBINE (ESN | SY...)` HEADER line,
        # so the backward-scan in the SECTION_HDR loop can't resolve bare `N Turbine`.
        # Doc-level equipment inventory (from title-page GT_LABELS) must type it as
        # Gas Turbine, otherwise SUBSEC_GENERIC will not promote downstream siblings
        # like `3.8.7 Rotor` and they'll be dropped or mis-typed to Generator.
        full_text = "\n".join([
            "Field Service Report",
            "Gas Turbine ESN: 298464",
            "Generator ESN: 337X581",
            "",
            "3 Turbine",
            "Some turbine content",
            "### 3.8.6 Generator",
            "Generator inspection content",
            "### 3.8.7 Rotor",
            "Rotor inspection content",
        ])
        ctx = _build_ctx(full_text)
        result = preprocessor_v2.preprocess(ctx)

        regions_by_last_section = {
            r["metadata"].get("section_path", [])[-1]: r
            for r in result["regions"]
            if r["metadata"].get("section_path")
        }

        turbine_region = regions_by_last_section.get("3 Turbine")
        self.assertIsNotNone(turbine_region, "bare `3 Turbine` SECTION_HDR must be emitted as a region")
        self.assertEqual(turbine_region["metadata"].get("primary_equip_type"), "Gas Turbine")

        rotor_region = regions_by_last_section.get("### 3.8.7 Rotor")
        self.assertIsNotNone(rotor_region, "`3.8.7 Rotor` must be promoted via SUBSEC_GENERIC and emitted as a region")
        self.assertEqual(
            rotor_region["metadata"].get("primary_equip_type"),
            "Gas Turbine",
            "Rotor must inherit Gas Turbine context from typed `3 Turbine` parent (not flip to Generator)",
        )

        generator_region = regions_by_last_section.get("### 3.8.6 Generator")
        self.assertIsNotNone(generator_region)
        self.assertEqual(generator_region["metadata"].get("primary_equip_type"), "Generator")


    def test_section_hdr_early_body_survives_via_toc_crosscheck(self):
        # Regression: 4597a853 — bare `3 Generator` at page 11 in a long doc lands
        # inside the old `toc_cutoff = len // 20` (5%) window and was being dropped.
        # TOC cross-check keeps it because TOC contains `3 Generator`, restoring
        # doc-level primary_equip_type / primary_esn resolution.
        toc_page = "\n".join([
            "Table of Contents",
            "1 Executive Summary ....... 3",
            "2 Overview .............. 5",
            "3 Generator ............. 11",
            "3.1 Field Winding Test .. 15",
            "3.2 Rotor Inspection .... 20",
            "3.3 Stator Test ......... 25",
            "4 Support .............. 100",
            "5 Attachments .......... 200",
        ])
        title_page = "\n".join([
            "Field Service Report",
            "Generator ESN: 338X447",
            "Gas Turbine ESN: 298250",
            "Job Start Date: 12 Dec",
        ])
        body = "\n".join([
            "3 Generator",
            "This section covers Generator inspection.",
        ])
        padding = "\n".join(["irrelevant filler content"] * 3000)
        full_text = "\n".join([title_page, toc_page, body, padding])

        # Sanity: `3 Generator` body offset must be inside the old 5% cutoff window.
        toc_cutoff_old = len(full_text) // 20
        toc_marker = full_text.find("Table of Contents")
        gen_offset = full_text.find("3 Generator", toc_marker + 20)
        self.assertLessEqual(gen_offset, toc_cutoff_old, "test fixture must exercise the pre-cutoff window")

        ctx = _build_ctx(full_text)
        result = preprocessor_v2.preprocess(ctx)

        self.assertEqual(result["metadata"].get("primary_equip_type"), "Generator")
        self.assertEqual(result["metadata"].get("primary_esn"), "338X447")

        # `3 Generator` must be emitted as its own SECTION_HDR-anchored region.
        gen_paths = [
            r for r in result["regions"]
            if r["metadata"].get("section_path") and r["metadata"]["section_path"][-1] == "3 Generator"
        ]
        self.assertTrue(gen_paths, "`3 Generator` SECTION_HDR must survive TOC cross-check")
        self.assertEqual(gen_paths[0]["metadata"].get("primary_equip_type"), "Generator")


    def test_subsec_generic_ocr_artifact_filtered_when_toc_available(self):
        # b775cf29-style artifact: `3.8\nPosition` OCR heading that has no matching TOC entry.
        # Expected: SUBSEC_GENERIC drops it because `3.8` in TOC maps to a different title
        # ("3.8 Turbine Section") whose tokens do not overlap with `Position`.
        toc_page = "\n".join([
            "Table of Contents",
            "1 Executive Summary ....... 3",
            "2 Overview .............. 5",
            "3 Turbine ............... 11",
            "3.1 Compressor .......... 15",
            "3.8 Turbine Section ..... 20",
            "4 Generator ............ 100",
            "5 Attachments .......... 200",
        ])
        header_line = "GAS TURBINE (298250 | SY0000001)"
        body = "\n".join([
            "3 Turbine",
            "Turbine content",
            "### 3.1 Compressor",
            "Compressor content",
            "3.8",
            "Position",
            "Table label OCR artifact content",
        ])
        full_text = "\n".join([toc_page, header_line, body])
        ctx = _build_ctx(full_text)
        result = preprocessor_v2.preprocess(ctx)

        # No region should end in a `Position`-only section path element.
        for r in result["regions"]:
            sp = r["metadata"].get("section_path", [])
            for elem in sp:
                self.assertNotIn(
                    "position", elem.lower(),
                    f"OCR artifact `3.8\\nPosition` must be filtered by TOC cross-check; found in section_path: {sp}",
                )


    def test_subsec_generic_drops_multiline_ocr_artifact_even_without_toc(self):
        # Regression: b775cf29 real-doc behavior — TOC extractor returned very few
        # entries so the TOC cross-check safety fallback bypassed filtering. The
        # multi-line drop is a doc-independent guard that must fire regardless of
        # TOC availability. A real heading never spans lines.
        full_text = "\n".join([
            "GAS TURBINE (297651 | SY0000001)",
            "3 Turbine",
            "Turbine intro content",
            "3.8",
            "Position",
            "This is a table label artifact, not a real section.",
        ])
        ctx = _build_ctx(full_text)
        result = preprocessor_v2.preprocess(ctx)

        for r in result["regions"]:
            sp = r["metadata"].get("section_path", [])
            for elem in sp:
                self.assertNotIn(
                    "position", elem.lower(),
                    f"Multi-line OCR artifact `3.8\\nPosition` must be dropped even with weak TOC; section_path: {sp}",
                )


    def test_section_hdr_toc_cutoff_still_filters_true_front_matter(self):
        # Regression: 4597a853 real-doc behavior — a `3 Generator` line inside the
        # front-matter zone (TOC index area) was being pulled as a body header
        # because the TOC cross-check safety fallback (weak TOC parse) bypassed
        # filtering. The small `toc_cutoff` base guard must still drop it.
        title_page = "\n".join([
            "Field Service Report",
            "Generator ESN: 338X447",
        ])
        toc_page = "\n".join([
            "Table of Contents",
            "1 Executive Summary ..... 3",
            "2 Overview ............ 5",
            "3 Generator ........... 11",
            "3.1 Field Winding ..... 15",
            "3.2 Rotor Test ........ 20",
            "3.3 Stator Test ....... 25",
            "4 Support ............ 100",
            "5 Attachments ........ 200",
        ])
        # Padding must not look like TOC entries (avoid `<text> <number>` pattern).
        padding = "This is body prose without trailing page numbers so the TOC extractor ignores it. " * 400
        body_section = "\n".join(["3 Generator", "Body content for the Generator section."])
        full_text = "\n".join([title_page, toc_page, padding, body_section])

        expected_cutoff = min(len(full_text) // 50, 5000)
        proc = preprocessor_v2.FSRV2Preprocessor()
        candidates, _ = proc._collect_heading_candidates(
            full_text, raw_pages=[full_text], pages=[full_text], page_offsets=[0],
        )

        section_hdrs = [c for c in candidates if c.heading_type == HeadingType.SECTION_HDR]
        self.assertTrue(section_hdrs, "at least one SECTION_HDR must be emitted for body `3 Generator`")
        # No SECTION_HDR candidate may land inside the front-matter guard.
        for c in section_hdrs:
            self.assertGreater(
                c.start_char, expected_cutoff,
                f"SECTION_HDR candidate at char {c.start_char} landed inside the front-matter guard (cutoff={expected_cutoff}); heading={c.heading_text!r}",
            )
        # `3 Generator` SECTION_HDR must survive (typed Generator).
        gen_hdrs = [c for c in section_hdrs if c.equipment_type == "Generator"]
        self.assertTrue(gen_hdrs, "body `3 Generator` SECTION_HDR must survive TOC cross-check")


    def test_electrical_system_root_types_generator_and_promotes_subsections(self):
        # Reviewer-reported scenario: `5 Electrical System` is a top-level Generator
        # section in some FSR docs. Its numbered subsections cover a mix of Generator
        # component work (`5.1 Generator`, `5.5 Generator Synthetic Pressure Test`)
        # and free-form Generator titles (`5.2 Sniff check`, `5.3 Shaft Seal Housing`,
        # `5.4 Hydrogen Coolers`). All must be emitted as Generator regions when a
        # Generator equipment header supplies the ESN.
        full_text = "\n".join([
            "Field Service Report",
            "Generator ESN: 337X581",
            "",
            "GENERATOR (337X581 | SY0000002)",
            "Body content upstream",
            "",
            "5 Electrical System",
            "Intro paragraph",
            "5.1 Generator",
            "Content of 5.1",
            "5.2 Sniff check external leak before H2 degas",
            "Content of 5.2",
            "5.3 Shaft Seal Housing",
            "Content of 5.3",
            "5.4 Hydrogen Coolers",
            "Content of 5.4",
            "5.5 Generator Synthetic Pressure Test",
            "Content of 5.5",
            "5.6 Rotor Axial Position",
            "Content of 5.6",
            "5.7 Bearing Assembly",
            "Content of 5.7",
        ])
        ctx = _build_ctx(full_text)
        result = preprocessor_v2.preprocess(ctx)

        self.assertEqual(result["metadata"].get("primary_equip_type"), "Generator")
        self.assertEqual(result["metadata"].get("primary_esn"), "337X581")

        regions_by_leaf = {}
        for r in result["regions"]:
            sp = r["metadata"].get("section_path", [])
            if sp:
                regions_by_leaf[sp[-1]] = r

        expected_leaves = [
            "5 Electrical System",
            "5.1 Generator",
            "5.2 Sniff check external leak before H2 degas",
            "5.3 Shaft Seal Housing",
            "5.4 Hydrogen Coolers",
            "5.5 Generator",
            "5.6 Rotor Axial Position",
            "5.7 Bearing Assembly",
        ]
        for leaf in expected_leaves:
            region = regions_by_leaf.get(leaf)
            self.assertIsNotNone(region, f"expected region for leaf {leaf!r} in output")
            self.assertEqual(
                region["metadata"].get("primary_equip_type"), "Generator",
                f"subsection {leaf!r} must be typed Generator under `5 Electrical System`",
            )
            self.assertEqual(
                region["metadata"].get("primary_esn"), "337X581",
                f"subsection {leaf!r} must inherit ESN 337X581 from the Generator header",
            )


    def test_esn_resolution_precedence_local_parent_single_type_ibat(self):
        proc = preprocessor_v2.FSRV2Preprocessor()
        spans = [
            SectionSpan(
                start=0,
                end=10,
                level=-1,
                heading_text="GAS TURBINE (297191 | SY0000001)",
                heading_type=HeadingType.HEADER,
                equipment_type="Gas Turbine",
                local_esn="297191",
                parent_idx=None,
            ),
            SectionSpan(
                start=10,
                end=20,
                level=0,
                heading_text="1 GAS TURBINE",
                heading_type=HeadingType.SECTION_HDR,
                equipment_type="Gas Turbine",
                parent_idx=0,
            ),
            SectionSpan(
                start=20,
                end=30,
                level=0,
                heading_text="1 GENERATOR",
                heading_type=HeadingType.SECTION_HDR,
                equipment_type="Generator",
                parent_idx=None,
            ),
            SectionSpan(
                start=30,
                end=40,
                level=0,
                heading_text="2 GENERATOR",
                heading_type=HeadingType.SECTION_HDR,
                equipment_type="Generator",
                parent_idx=None,
            ),
        ]

        esn_ctx = {
            "active": {"297191", "338X827", "337X766"},
            "active_by_type": {
                "Gas Turbine": ["297191"],
                "Generator": ["338X827", "337X766"],
                "Steam Turbine": [],
            },
        }

        def ibat_resolver(equip_type, _context):
            if equip_type == "Generator":
                return ["338X827"]
            return []

        proc._resolve_span_esn_local_first(spans, esn_ctx, ibat_resolver=ibat_resolver)

        self.assertEqual(spans[0].resolved_esn, "297191")
        self.assertEqual(spans[0].esn_source, EsnSource.LOCAL_HEADER)
        self.assertEqual(spans[1].resolved_esn, "297191")
        self.assertEqual(spans[1].esn_source, EsnSource.PARENT_INHERIT)
        self.assertEqual(spans[2].resolved_esn, "338X827")
        self.assertEqual(spans[2].esn_source, EsnSource.IBAT_TRAIN)
        self.assertEqual(spans[2].esn_confidence, EsnConfidence.LOW)

        def ibat_ambiguous(_equip_type, _context):
            return ["338X827", "337X766"]

        spans[3].resolved_esn = None
        spans[3].esn_source = EsnSource.NONE
        spans[3].esn_confidence = EsnConfidence.NONE
        proc._resolve_span_esn_local_first([spans[3]], esn_ctx, ibat_resolver=ibat_ambiguous)
        self.assertIsNone(spans[3].resolved_esn)
        self.assertEqual(spans[3].esn_confidence, EsnConfidence.NONE)


    def test_boundary_path_eligibility_multi_esn_same_type_bug41(self):
        full_text = "\n".join([
            "GENERATOR (337X766 | SY0072576)",
            "1 GENERATOR",
            "Generator work block A",
            "GENERATOR (338X827 | SY0072577)",
            "1 GENERATOR",
            "Generator work block B",
        ])

        ctx = _build_ctx(full_text)
        result = preprocessor_v2.preprocess(ctx)
        region_esns = [r.get("metadata", {}).get("primary_esn") for r in result["regions"]]

        self.assertIn("337X766", region_esns)
        self.assertIn("338X827", region_esns)

    def test_all_esns_is_structured_set_not_broad_scan(self):
        full_text = "\n".join([
            "GAS TURBINE (297191 | SY0000001)",
            "Repeated token 338X827 appears in body.",
            "338X827",
            "338X827",
        ])
        ctx = _build_ctx(full_text)
        result = preprocessor_v2.preprocess(ctx)

        all_esns = set(x.strip() for x in result["metadata"].get("all_esns", "").split(",") if x.strip())
        self.assertIn("297191", all_esns)
        self.assertNotIn("338X827", all_esns)

    def test_level_conflict_is_flagged_when_numbering_disagrees_with_local_hierarchy(self):
        proc = preprocessor_v2.FSRV2Preprocessor()
        candidates = [
            preprocessor_v2.HeadingCandidate(
                start_char=0,
                heading_text="1 GAS TURBINE",
                heading_type=HeadingType.SECTION_HDR,
                equipment_type="Gas Turbine",
                level=0,
                confidence_rank=80,
            ),
            preprocessor_v2.HeadingCandidate(
                start_char=20,
                heading_text="2 GENERATOR",
                heading_type=HeadingType.SECTION_HDR,
                equipment_type="Generator",
                level=0,
                confidence_rank=80,
            ),
            preprocessor_v2.HeadingCandidate(
                start_char=40,
                heading_text="1.1 Generator Test",
                heading_type=HeadingType.SUBSEC,
                equipment_type="Generator",
                level=1,
                confidence_rank=75,
            ),
            preprocessor_v2.HeadingCandidate(
                start_char=60,
                heading_text="3 GAS TURBINE",
                heading_type=HeadingType.SECTION_HDR,
                equipment_type="Gas Turbine",
                level=0,
                confidence_rank=80,
            ),
        ]

        spans = proc._build_hierarchical_spans(candidates, full_len=100)
        self.assertTrue(any(span.level_conflict for span in spans))

    def test_gap_guardrail_large_gap_avoids_neighbor_esn_inheritance(self):
        proc = preprocessor_v2.FSRV2Preprocessor()
        left = preprocessor_v2.Region(
            start=0,
            end=10,
            metadata=preprocessor_v2.RegionMetadata(
                primary_esn="297191",
                primary_equip_type="Gas Turbine",
            ),
        )
        meta = proc._gap_region_meta(left, None, gt_tech=None, gen_tech=None, gap_len=2501)
        self.assertIsNone(meta.primary_esn)
        self.assertEqual(meta.primary_equip_type, "shared")
        self.assertEqual(meta.esn_confidence, EsnConfidence.NONE)


    def test_full_document_region_coverage_front_gap_trailing(self):
        proc = preprocessor_v2.FSRV2Preprocessor()
        spans = [
            SectionSpan(
                start=10,
                end=20,
                level=0,
                heading_text="1 GAS TURBINE",
                heading_type=HeadingType.SECTION_HDR,
                equipment_type="Gas Turbine",
                resolved_esn="297191",
                esn_source=EsnSource.LOCAL_HEADER,
                esn_confidence=EsnConfidence.HIGH,
            )
        ]

        regions = proc._emit_regions_full_coverage(spans, full_len=30, gt_tech=None, gen_tech=None)
        self.assertEqual(regions[0].start, 0)
        self.assertEqual(regions[-1].end, 30)

        cursor = 0
        for reg in regions:
            self.assertEqual(reg.start, cursor)
            self.assertGreaterEqual(reg.end, reg.start)
            cursor = reg.end
        self.assertEqual(cursor, 30)
        self.assertEqual(regions[1].metadata.section_path, ["1 GAS TURBINE"])

    def test_nested_generator_subsection_produces_distinct_atomic_regions(self):
        full_text = "\n".join([
            "GAS TURBINE (297191 | SY0000001)",
            "1 GAS TURBINE",
            "GT parent text",
            "1.1 Generator Stator Test",
            "Generator child text",
            "1.2 Turbine Compressor Check",
            "GT resumes here",
        ])
        ctx = _build_ctx(full_text)
        result = preprocessor_v2.preprocess(ctx)
        regions = [
            region for region in result["regions"]
            if region.get("metadata", {}).get("primary_equip_type") in {"Gas Turbine", "Generator"}
        ]
        equip_sequence = [region["metadata"].get("primary_equip_type") for region in regions]
        self.assertIn("Gas Turbine", equip_sequence)
        self.assertIn("Generator", equip_sequence)
        self.assertGreaterEqual(len(regions), 3)
        generator_idx = equip_sequence.index("Generator")
        self.assertGreater(generator_idx, 0)
        self.assertLess(generator_idx, len(equip_sequence) - 1)
        self.assertEqual(equip_sequence[generator_idx - 1], "Gas Turbine")
        self.assertEqual(equip_sequence[generator_idx + 1], "Gas Turbine")


    def test_summary_from_toc_seeded_spans(self):
        raw_pages = [
            "Table of Contents\nExecutive Summary .... 2\nTechnical Section .... 3",
            "Executive Summary\nThis is summary text for validation.",
            "Technical Section\nDetails...",
        ]
        full_text = "\n\n".join(raw_pages)
        ctx = _build_ctx(full_text, pages=raw_pages, raw_pages=raw_pages)
        result = preprocessor_v2.preprocess(ctx)

        summary = result["metadata"].get("document_summary")
        self.assertTrue(summary)
        self.assertIn("summary", summary.lower())


    def test_region_first_chunking_inherits_region_metadata(self):
        text = "Front\nGenerator section text with details.\nTail"
        regions = [
            {
                "start": 0,
                "end": len(text),
                "metadata": {
                    "primary_esn": "338X827",
                    "primary_equip_type": "Generator",
                    "section_path": ["GENERATOR", "1 GENERATOR"],
                },
            }
        ]
        chunks = split_region_first_with_offsets(
            text,
            regions,
            chunk_size=20,
            chunk_overlap=0,
            min_chunk_size=1,
        )
        self.assertTrue(chunks)
        self.assertTrue(all(ch["region_metadata"].get("primary_esn") == "338X827" for ch in chunks))
        self.assertTrue(all(ch["section_metadata"].get("section_1") == "GENERATOR" for ch in chunks))

    def test_region_first_chunking_fills_uncovered_text_as_shared(self):
        text = "GENERATOR\n" + ("Generator detail. " * 80)
        regions = [{
            "start": 10,
            "end": len(text) - 10,
            "metadata": {"primary_esn": "338X827", "primary_equip_type": "Generator"},
        }]

        chunks = split_region_first_with_offsets(
            text, regions, chunk_size=380, chunk_overlap=0, min_chunk_size=1,
        )

        self.assertTrue(chunks)
        self.assertTrue(any(not chunk["region_metadata"].get("primary_esn") for chunk in chunks))
        self.assertTrue(any(chunk["region_metadata"].get("primary_esn") == "338X827" for chunk in chunks))

    def test_chunk_metadata_preserves_p1_region_provenance(self):
        chunk = {
            "region_primary_esn": "338X827",
            "region_primary_equip_type": "Generator",
            "region_metadata": {
                "primary_esn": "338X827",
                "primary_equip_type": "Generator",
                "esn_confidence": "high",
                "esn_source": "parent_inherit",
                "equip_type_source": "heading",
                "region_source": "section_span",
                "section_path": ["GENERATOR", "3 Generator"],
                "fallback_chain": ["local", "parent", "none"],
            },
        }

        persisted = chunk_region_metadata(chunk)

        self.assertEqual(persisted["esn_confidence"], "high")
        self.assertEqual(persisted["region_source"], "section_span")
        self.assertEqual(persisted["section_path"], ["GENERATOR", "3 Generator"])
        self.assertEqual(persisted["fallback_chain"], ["local", "parent", "none"])

    def test_parsed_document_save_and_load_roundtrip(self):
        parsed_doc = ParsedDocument(
            document_id="doc-1",
            filename="demo.pdf",
            volume_path="/tmp/demo.pdf",
            full_text="clean-page",
            parser_version="pymupdf_v1.0",
            pages=["clean-page"],
            raw_pages=["raw-page"],
            page_offsets=[{"start": 0, "end": 10}],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            saved = save_parsed_document(parsed_doc, tmpdir, "pymupdf_v1.0")
            self.assertTrue(Path(saved.parsed_volume_path).exists())
            loaded = load_parsed_document(saved.parsed_volume_path)
            self.assertEqual(loaded.document_id, "doc-1")
            self.assertEqual(loaded.pages, ["clean-page"])
            self.assertEqual(loaded.raw_pages, ["raw-page"])
            self.assertEqual(loaded.parser_version, "pymupdf_v1.0")

    def test_metadata_processor_v2_as_thin_adapter(self):
        captured = {}

        def fake_preprocess(ctx):
            captured["raw_pages"] = ctx.raw_pages
            captured["pages"] = ctx.pages
            captured["filename"] = ctx.filename
            return {"metadata": {"ok": True}, "hints": "x", "regions": []}

        with patch.object(metadata_processor_v2._preprocessor, "preprocess", side_effect=fake_preprocess):
            parsed_doc = ParsedDocument(
                document_id="doc-1",
                filename="demo.pdf",
                volume_path="/tmp/demo.pdf",
                full_text="hello",
                pages=["clean-page"],
                raw_pages=["raw-page"],
                page_offsets=[{"start": 0, "end": 5}],
            )

            out = metadata_processor_v2.run(parsed_doc)
            self.assertTrue(out["metadata"]["ok"])
            self.assertEqual(captured["raw_pages"], ["raw-page"])
            self.assertEqual(captured["pages"], ["clean-page"])
            self.assertEqual(captured["filename"], "demo.pdf")


if __name__ == "__main__":
    unittest.main()
