"""Unit tests for FSR v2 redesign preprocessor and region-first chunking."""

import concurrent.futures
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from common.fsr_v2 import preprocessor_v2
from common.fsr_v2 import final_master_report_profile
from common.fsr_v2.preprocessor_v2 import EsnConfidence, EsnSource, HeadingType, SectionSpan
from gold.src.etl.fsr_v2.chunk_splitter import (
    chunk_region_metadata,
    split_region_first_with_offsets,
    split_with_offsets,
)
from silver.src.etl.fsr_v2 import metadata_processor
from silver.src.etl.fsr_v2.parsing import (
    ParsedDocument,
    build_parsed_volume_path,
    determine_doc_date,
    extract_doc_year_from_page1,
    load_parsed_document,
    save_parsed_document,
)


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
    def test_final_master_report_profile_routes_by_filename_and_records_strategy(self):
        ctx = _build_ctx(
            "Contents . . . . . .\n"
            "2. COMPONENTS\n"
            "GAS TURBINE - BEARINGS\n"
            "Bearing details\n"
            "3. APPENDIX\n"
            "Appendix details",
        )
        ctx.filename = "report_Final_Master_Report.pdf"

        self.assertTrue(final_master_report_profile.is_final_master_report(ctx))
        result = metadata_processor.run(
            ParsedDocument(
                document_id="doc-1",
                filename=ctx.filename,
                pages=ctx.pages,
                raw_pages=ctx.raw_pages,
                page_offsets=ctx.page_offsets,
                full_text=ctx.full_text,
                volume_path="/vol/report.pdf",
                parsed_volume_path=None,
                parser_version="test",
            )
        )

        self.assertEqual(result["metadata"]["preprocessor_profile"], "final_master_report")
        self.assertIn("preprocessor_strategy=components_labels_and_appendix_fallback", result["hints"])
        self.assertTrue(any(
            region["metadata"].get("primary_equip_type") == "Gas Turbine"
            for region in result["regions"]
        ))

    def test_final_master_report_unlabeled_fallback_is_configurable(self):
        full_text = (
            "2. COMPONENTS\n"
            "Unlabeled sub-report\n"
            + "Generator winding inspection\n" * 8
            + "3. APPENDIX\n"
            + "Scanned appendix\n"
        )
        result = final_master_report_profile.preprocess(
            _build_ctx(full_text),
            page_fallback_enabled=True,
            generator_threshold=7,
        )

        fallback = [
            region for region in result["regions"]
            if region["metadata"].get("fallback_reason") == "generator_evidence_threshold"
        ]
        self.assertTrue(fallback)
        self.assertTrue(all(region["metadata"]["primary_equip_type"] == "shared" for region in fallback))

    def test_final_master_report_fallback_respects_page_boundaries(self):
        pages = [
            "2. COMPONENTS\nUnlabeled generator winding inspection\n" * 4,
            "Generator winding inspection\n" * 4,
        ]
        full_text = "".join(pages)
        page_offsets = []
        cursor = 0
        for page in pages:
            page_offsets.append({"start": cursor, "end": cursor + len(page)})
            cursor += len(page)
        ctx = _build_ctx(full_text, pages=pages)
        ctx.page_offsets = page_offsets

        result = final_master_report_profile.preprocess(ctx, generator_threshold=7)

        fallback = [
            region for region in result["regions"]
            if region["metadata"].get("region_source") == "page_fallback"
        ]
        self.assertEqual(len(fallback), 2)
        self.assertEqual([(region["start"], region["end"]) for region in fallback], [
            (page_offsets[0]["start"], page_offsets[0]["end"]),
            (page_offsets[1]["start"], page_offsets[1]["end"]),
        ])

    def test_default_preprocessor_does_not_route_by_final_master_rules(self):
        full_text = "2. COMPONENTS\nGAS TURBINE - BEARINGS\nDetails\n"
        result = preprocessor_v2.preprocess(_build_ctx(full_text))

        self.assertNotEqual(result["metadata"].get("preprocessor_profile"), "final_master_report")

    def test_late_dotted_contents_does_not_trigger_profile_detection(self):
        pages = [
            "2. COMPONENTS\nUnlabeled content\n",
            "Body content\n",
            "Embedded sub-report Contents . . . . . .\n",
        ]
        ctx = _build_ctx("".join(pages), pages=pages)

        self.assertFalse(final_master_report_profile.is_final_master_report(ctx))

    def test_final_master_profile_requires_number_dot_space_components(self):
        exact = _build_ctx("2. COMPONENTS\nGAS TURBINE - BEARINGS\nDetails\n")
        generic = _build_ctx("COMPONENTS\nGAS TURBINE - BEARINGS\nDetails\n")
        lowercase = _build_ctx("2. components\nGAS TURBINE - BEARINGS\nDetails\n")

        self.assertTrue(final_master_report_profile.is_final_master_report(exact))
        self.assertFalse(final_master_report_profile.is_final_master_report(generic))
        self.assertFalse(final_master_report_profile.is_final_master_report(lowercase))

    def test_plain_generator_does_not_identify_final_master_profile(self):
        ctx = _build_ctx("1. SUMMARY\nGENERATOR\nGenerator details\n")

        self.assertFalse(final_master_report_profile.is_final_master_report(ctx))

    def test_final_master_profile_preserves_default_metadata(self):
        ctx = _build_ctx("2. COMPONENTS\nGAS TURBINE - BEARINGS\nDetails\n")
        result = final_master_report_profile.preprocess(ctx)

        self.assertIn("document_name", result["metadata"])
        self.assertIn("preprocessor_profile", result["metadata"])

    def test_final_master_profile_preserves_shared_section_paths(self):
        full_text = "\n".join([
            "GAS TURBINE (297652 | SY1234567)",
            "2. COMPONENTS",
            "GAS TURBINE - BEARINGS",
            "2 Turbine",
            "2.1 Auxiliaries",
            "Inspection findings",
        ])

        ctx = _build_ctx(full_text)
        shared_result = preprocessor_v2.preprocess(ctx)
        self.assertTrue(any(
            "2.1 Auxiliaries" in region["metadata"].get("section_path", [])
            for region in shared_result["regions"]
        ))

        result = final_master_report_profile.preprocess(ctx)
        auxiliary_regions = [
            region for region in result["regions"]
            if "2.1 Auxiliaries" in region["metadata"].get("section_path", [])
        ]

        self.assertTrue(auxiliary_regions)
        self.assertTrue(all(
            region["metadata"].get("primary_equip_type") == "Gas Turbine"
            for region in auxiliary_regions
        ))
        self.assertEqual(result["regions"][0]["start"], 0)
        self.assertEqual(result["regions"][-1]["end"], len(full_text))
        self.assertTrue(all(
            left["end"] == right["start"]
            for left, right in zip(result["regions"], result["regions"][1:])
        ))

    def test_page_fallback_uses_document_turbine_type(self):
        full_text = "STEAM TURBINE report\n2. COMPONENTS\nUnlabeled appendix text\n"
        result = final_master_report_profile.preprocess(_build_ctx(full_text))

        fallback = [
            region for region in result["regions"]
            if region["metadata"].get("fallback_reason") == "turbine_fallback"
        ]
        self.assertTrue(fallback)
        self.assertTrue(all(
            region["metadata"]["primary_equip_type"] == "Steam Turbine"
            for region in fallback
        ))

    def test_final_master_profile_ignores_toc_component_markers_for_attribution(self):
        pages = [
            "CONTENTS . . . . . .\n2. COMPONENTS\nSTEAM TURBINE - BEARINGS\n",
            "2. COMPONENTS\nSTEAM TURBINE - CLEARANCES\nBody inspection findings\n",
        ]
        full_text = "".join(pages)
        ctx = _build_ctx(full_text, pages=pages)
        cursor = 0
        ctx.page_offsets = []
        for page in pages:
            ctx.page_offsets.append({"start": cursor, "end": cursor + len(page)})
            cursor += len(page)

        result = final_master_report_profile.preprocess(ctx)
        toc_marker = full_text.index("STEAM TURBINE - BEARINGS")
        body_marker = full_text.index("STEAM TURBINE - CLEARANCES")
        toc_region = next(
            region for region in result["regions"]
            if region["start"] <= toc_marker < region["end"]
        )
        body_region = next(
            region for region in result["regions"]
            if region["start"] <= body_marker < region["end"]
        )

        self.assertEqual(toc_region["metadata"]["primary_equip_type"], "shared")
        self.assertEqual(body_region["metadata"]["primary_equip_type"], "Steam Turbine")

    def test_final_master_profile_selects_body_components_within_first_ten_percent(self):
        pages = ["CONTENTS . . . . . .\n2. COMPONENTS\nSTEAM TURBINE - TOC\n"]
        pages.extend(f"Page {page_number} filler\n" for page_number in range(2, 8))
        pages.append("2. COMPONENTS\nSTEAM TURBINE - BODY\nBody findings\n")
        pages.extend(f"Page {page_number} filler\n" for page_number in range(9, 101))
        full_text = "".join(pages)
        ctx = _build_ctx(full_text, pages=pages)
        cursor = 0
        ctx.page_offsets = []
        for page in pages:
            ctx.page_offsets.append({"start": cursor, "end": cursor + len(page)})
            cursor += len(page)

        result = final_master_report_profile.preprocess(ctx)
        toc_marker = full_text.index("STEAM TURBINE - TOC")
        body_marker = full_text.index("STEAM TURBINE - BODY")
        toc_region = next(
            region for region in result["regions"]
            if region["start"] <= toc_marker < region["end"]
        )
        body_region = next(
            region for region in result["regions"]
            if region["start"] <= body_marker < region["end"]
        )

        self.assertEqual(toc_region["metadata"]["primary_equip_type"], "shared")
        self.assertEqual(body_region["metadata"]["primary_equip_type"], "Steam Turbine")

    def test_final_master_profile_skips_repeated_toc_components_entries(self):
        pages = [
            "CONTENTS . . . . . .\n2. COMPONENTS\nSTEAM TURBINE - TOC\n",
            "CONTENTS (continued)\n2. COMPONENTS\nGENERATOR - TOC\n",
            "2. COMPONENTS\nSTEAM TURBINE - BODY\nBody findings\n",
        ]
        full_text = "".join(pages)
        ctx = _build_ctx(full_text, pages=pages)
        cursor = 0
        ctx.page_offsets = []
        for page in pages:
            ctx.page_offsets.append({"start": cursor, "end": cursor + len(page)})
            cursor += len(page)

        match = final_master_report_profile._body_section_match(
            final_master_report_profile._COMPONENTS_RE,
            ctx,
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.start(), full_text.index("2. COMPONENTS", len(pages[0]) + len(pages[1])))

    def test_final_master_profile_keeps_first_components_without_primary_toc(self):
        full_text = (
            "2. COMPONENTS\nGAS TURBINE - BODY\nBody findings\n"
            "2. COMPONENTS\nSTEAM TURBINE - EMBEDDED REPORT\nEmbedded findings\n"
        )

        match = final_master_report_profile._body_section_match(
            final_master_report_profile._COMPONENTS_RE,
            _build_ctx(full_text),
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.start(), 0)

    def test_generator_fallback_resolves_train_scoped_esn_without_retyping_region(self):
        full_text = (
            "Gas Turbine ESN: 297422\n"
            "2. COMPONENTS\n"
            + "Generator winding inspection\n" * 8
        )
        resolver_calls = []

        def resolver(equip_type, context):
            resolver_calls.append((equip_type, context))
            return ["337X766"]

        result = final_master_report_profile.preprocess(
            _build_ctx(full_text),
            ibat_resolver=resolver,
            generator_threshold=7,
        )

        self.assertEqual(result["metadata"]["gen_esn"], "337X766")
        self.assertEqual(result["metadata"]["generator_esn_resolution"], "ibat_train")
        self.assertEqual(resolver_calls, [("Generator", {"current_turbine_esn": "297422"})])
        fallback = [
            region for region in result["regions"]
            if region["metadata"].get("fallback_reason") == "generator_evidence_threshold"
        ]
        self.assertTrue(fallback)
        self.assertTrue(all(
            region["metadata"]["primary_equip_type"] == "shared"
            for region in fallback
        ))

    def test_generator_fallback_does_not_guess_ambiguous_ibat_esn(self):
        full_text = (
            "Gas Turbine ESN: 297422\n"
            "2. COMPONENTS\n"
            + "Generator winding inspection\n" * 8
        )
        result = final_master_report_profile.preprocess(
            _build_ctx(full_text),
            ibat_resolver=lambda _equip_type, _context: ["337X766", "337X767"],
            generator_threshold=7,
        )

        self.assertNotIn("gen_esn", result["metadata"])
        self.assertEqual(result["metadata"]["generator_esn_resolution"], "ibat_ambiguous")

    def test_explicit_generator_label_resolves_one_non_sy_train_esn(self):
        full_text = (
            "Gas Turbine ESN: 297422\n"
            "2. COMPONENTS\n"
            "GENERATOR - INSPECTION\n"
            "Inspection findings\n"
        )

        result = final_master_report_profile.preprocess(
            _build_ctx(full_text),
            ibat_resolver=lambda _equip_type, _context: ["SY0093781", "337X766"],
        )

        self.assertEqual(result["metadata"]["gen_esn"], "337X766")
        self.assertEqual(result["metadata"]["generator_esn_resolution"], "ibat_train")
        generator_regions = [
            region for region in result["regions"]
            if region["metadata"].get("primary_equip_type") == "Generator"
        ]
        self.assertTrue(generator_regions)
        self.assertTrue(all(
            region["metadata"].get("primary_esn") == "337X766"
            for region in generator_regions
        ))

    def test_existing_sy_generator_metadata_is_replaced_by_non_sy_train_esn(self):
        generator_esn, resolution = final_master_report_profile._resolve_fallback_generator_esn(
            {"gen_esn": "SY0093781", "gt_esn": "297422"},
            lambda _equip_type, _context: ["337X766"],
        )

        self.assertEqual(generator_esn, "337X766")
        self.assertEqual(resolution, "ibat_train")

    def test_final_master_profile_recognizes_approved_generator_labels(self):
        labels = (
            "GENERATOR ASSEMBLED",
            "GENERATOR EXCITATION",
            "GENERATOR ALIGNMENT",
            "GENERATOR COOLERS",
            "GENERATOR VISUAL",
        )

        for label in labels:
            with self.subTest(label=label):
                result = final_master_report_profile.preprocess(
                    _build_ctx(f"2. COMPONENTS\n{label}\nInspection findings\n")
                )
                self.assertTrue(any(
                    region["metadata"].get("primary_equip_type") == "Generator"
                    for region in result["regions"]
                ))

        arbitrary = final_master_report_profile.preprocess(
            _build_ctx("2. COMPONENTS\nGENERATOR PERFORMANCE NOTES\nDetails\n")
        )
        self.assertFalse(any(
            region["metadata"].get("primary_equip_type") == "Generator"
            for region in arbitrary["regions"]
        ))

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

    def test_repeated_unnumbered_equipment_noise_is_suppressed_with_pages(self):
        page_text = "\n".join([
            "GENERATOR (337X164 | SY0072347)",
            "GENERATOR",
            "Measurement table",
            "GENERATOR",
            "More measurement rows",
        ])
        candidates, _ = preprocessor_v2.FSRV2Preprocessor()._collect_heading_candidates(
            page_text,
            raw_pages=[page_text],
            pages=[page_text],
            page_offsets=[{"start": 0, "end": len(page_text)}],
        )

        standalone = [
            candidate for candidate in candidates
            if candidate.heading_type == HeadingType.UNNUMBERED
            and candidate.heading_text == "GENERATOR"
        ]

        self.assertLessEqual(len(standalone), 1)


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

    def test_dc_leakage_under_sub_reports_is_generator(self):
        full_text = "\n".join([
            "GAS TURBINE (298340 | SY0048193)",
            "5 Sub Reports",
            "## 5.1 DC Leakage Test",
            "Generator electrical test content",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        leakage_regions = [
            region for region in result["regions"]
            if any("5.1 DC Leakage" in heading for heading in region["metadata"].get("section_path", []))
        ]

        self.assertTrue(leakage_regions)
        self.assertTrue(all(
            region["metadata"].get("primary_equip_type") == "Generator"
            for region in leakage_regions
        ))

    def test_full_generator_subsection_label_preserved(self):
        full_text = "\n".join([
            "GAS TURBINE (297652 | SY1234567)",
            "1 Turbine",
            "3.2.1 Generator Bearing Metal 2",
            "Bearing metal inspection details.",
            "3.2.2 Generator Rotor",
            "Rotor details.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        matching_regions = [
            region for region in result["regions"]
            if any("Generator Bearing Metal 2" in heading for heading in region["metadata"].get("section_path", []))
        ]

        self.assertTrue(matching_regions)
        self.assertIn(
            "3.2.1 Generator Bearing Metal 2",
            matching_regions[0]["metadata"]["section_path"],
        )

    def test_full_gas_turbine_subsection_label_creates_own_region(self):
        full_text = "\n".join([
            "GAS TURBINE (298339 | SY0048192)",
            "1 Turbine",
            "## 1.1 Timers and Counters",
            "Timer details.",
            "## 1.2 Gas Turbine Executive Summary",
            "Executive summary details.",
            "## 1.3 Work Scope",
            "Work scope details.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        leaves = [
            region["metadata"]["section_path"][-1]
            for region in result["regions"]
            if region["metadata"].get("section_path")
        ]

        self.assertIn("1.2 Gas Turbine Executive Summary", leaves)

    def test_generic_report_root_headings_are_detected(self):
        full_text = "\n".join([
            "GAS TURBINE (298340 | SY0048193)",
            "OUTAGE DETAILS",
            "Outage details.",
            "1 Summary",
            "Summary details.",
            "2 Technical",
            "Technical details.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        leaves = [
            region["metadata"]["section_path"][-1]
            for region in result["regions"]
            if region["metadata"].get("section_path")
        ]

        self.assertIn("OUTAGE DETAILS", leaves)
        self.assertIn("1 Summary", leaves)
        self.assertIn("2 Technical", leaves)

    def test_quality_checkpoint_root_heading_is_detected(self):
        full_text = "\n".join([
            "GAS TURBINE (298340 | SY0048193)",
            "6 Quality Checkpoint (QCP)",
            "Quality checkpoint details.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        leaves = [
            region["metadata"]["section_path"][-1]
            for region in result["regions"]
            if region["metadata"].get("section_path")
        ]

        self.assertIn("6 Quality Checkpoint (QCP)", leaves)

    def test_generator_generic_subsections_use_structural_support(self):
        full_text = "\n".join([
            "GENERATOR (337X164 | SY0072347)",
            "1.1 Stator Inspection",
            "Stator details.",
            "1.2 Rotor Inspection",
            "Rotor details.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        leaves = [
            region["metadata"]["section_path"][-1]
            for region in result["regions"]
            if region["metadata"].get("section_path")
        ]

        self.assertIn("1.1 Stator Inspection", leaves)
        self.assertIn("1.2 Rotor Inspection", leaves)
        for region in result["regions"]:
            if region["metadata"].get("section_path", [])[-1:] in [
                ["1.1 Stator Inspection"],
                ["1.2 Rotor Inspection"],
            ]:
                self.assertEqual(region["metadata"].get("primary_equip_type"), "Generator")

    def test_subreport_numbering_stays_under_attachment_context(self):
        full_text = "\n".join([
            "GAS TURBINE (298340 | SY0048193)",
            "5 PIPO",
            "PIPO details.",
            "6 Attachments",
            "5.0 Safety Performance",
            "Safety details.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        matching = [
            region for region in result["regions"]
            if region["metadata"].get("section_path", [])[-1:] == ["5.0 Safety Performance"]
        ]

        self.assertTrue(matching)
        self.assertEqual(
            matching[0]["metadata"]["section_path"][-2:],
            ["6 Attachments", "5.0 Safety Performance"],
        )

    def test_attachment_heading_survives_when_primary_toc_omits_local_number(self):
        full_text = "\n".join([
            "GENERATOR (337X164 | SY0072347)",
            "3 Generator",
            "3.1 Attachments",
            "Attachment details.",
            "8.1Attachments",
            "More attachment details.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        leaves = [
            region["metadata"]["section_path"][-1]
            for region in result["regions"]
            if region["metadata"].get("section_path")
        ]

        self.assertIn("3.1 Attachments", leaves)
        self.assertIn("8.1Attachments", leaves)

    def test_numeric_measurement_rows_are_not_subsections(self):
        full_text = "\n".join([
            "STEAM TURBINE (170X537 | SY0023187)",
            "3 Turbine",
            "3.9.3 Bearing Inspection",
            "33.3 rps).",
            "14.00 Mils",
            "10.83 Mils",
            "3.9.4 Rotor Inspection",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        leaves = [
            region["metadata"]["section_path"][-1]
            for region in result["regions"]
            if region["metadata"].get("section_path")
        ]

        self.assertIn("3.9.3 Bearing Inspection", leaves)
        self.assertIn("3.9.4 Rotor Inspection", leaves)
        self.assertNotIn("33.3 rps).", leaves)
        self.assertNotIn("14.00 Mils", leaves)
        self.assertNotIn("10.83 Mils", leaves)

    def test_multipage_toc_continuation_does_not_emit_section_candidates(self):
        toc_page_1 = "\n".join([
            "Table Of Contents",
            "1 Summary",
            "__________ 1",
            "3.1 Auxiliaries",
            "__________ 15",
        ])
        toc_page_2 = "\n".join([
            "3.8 Generator",
            "__________ 183",
            "3.8.1 Generator Executive Summary",
            "__________ 183",
            "7.1 Combustion",
            "__________ 358",
        ])
        body_page = "\n".join([
            "GAS TURBINE (298340 | SY0048193)",
            "3 Turbine",
            "3.1 Auxiliaries",
            "Body details.",
            "7 PIPO",
            "7.1 Combustion",
            "Combustion details.",
        ])
        pages = [toc_page_1, toc_page_2, body_page]
        full_text = "\n".join(pages)
        offsets = []
        cursor = 0
        for page in pages:
            offsets.append({"start": cursor, "end": cursor + len(page)})
            cursor += len(page) + 1

        candidates, _ = preprocessor_v2.FSRV2Preprocessor()._collect_heading_candidates(
            full_text,
            raw_pages=pages,
            pages=pages,
            page_offsets=offsets,
            active_by_type={"Gas Turbine": ["298340"], "Steam Turbine": []},
        )
        aux_candidates = [candidate for candidate in candidates if candidate.heading_text == "3.1 Auxiliaries"]
        combustion_candidates = [candidate for candidate in candidates if candidate.heading_text == "7.1 Combustion"]

        self.assertEqual(len(aux_candidates), 1)
        self.assertGreaterEqual(aux_candidates[0].start_char, offsets[2]["start"])
        self.assertEqual(len(combustion_candidates), 1)
        self.assertGreaterEqual(combustion_candidates[0].start_char, offsets[2]["start"])

    def test_toc_parser_supports_same_line_and_wrapped_entries(self):
        pages = ["\n".join([
            "Table of Contents",
            "1 Summary 1",
            "3.1 Auxiliaries 15",
            "3.8.14 Resistance Test and Megger",
            "Test on RTDs",
            "__________ 229",
        ])]

        entries, _ = preprocessor_v2._extract_toc_entries_from_pages(pages)

        self.assertIn(("1 Summary", 1), entries)
        self.assertIn(("3.1 Auxiliaries", 15), entries)
        self.assertIn(("3.8.14 Resistance Test and Megger Test on RTDs", 229), entries)

    def test_region_metadata_records_heading_diagnostics(self):
        full_text = "\n".join([
            "GAS TURBINE (297652 | SY1234567)",
            "1 Turbine",
            "1.1 Compressor Inspection",
            "Inspection details.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        subsection_regions = [
            region for region in result["regions"]
            if region["metadata"].get("section_path", [])[-1:] == ["1.1 Compressor Inspection"]
        ]

        self.assertTrue(subsection_regions)
        metadata = subsection_regions[0]["metadata"]
        self.assertEqual(metadata["heading_confidence"], "high")
        self.assertIn("numbered_subsection", metadata["heading_reason_codes"])

    def test_turbine_keyword_subsections_use_gas_turbine_context(self):
        full_text = "\n".join([
            "GAS TURBINE (297652 | SY1234567)",
            "1 Turbine",
            "1.1 PIPO",
            "1.2 Control System",
            "1.3 QCP",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        keyword_regions = [
            region for region in result["regions"]
            if any(
                keyword in heading
                for heading in region["metadata"].get("section_path", [])
                for keyword in ("1.1 PIPO", "1.2 Control System", "1.3 QCP")
            )
        ]

        self.assertEqual(len(keyword_regions), 3)
        self.assertTrue(all(
            region["metadata"].get("primary_equip_type") == "Gas Turbine"
            for region in keyword_regions
        ))

    def test_turbine_keyword_subsection_uses_steam_turbine_context(self):
        full_text = "\n".join([
            "STEAM TURBINE (123456 | SY7654321)",
            "2 Turbine",
            "2.1 QCP",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        qcp_regions = [
            region for region in result["regions"]
            if any("2.1 QCP" in heading for heading in region["metadata"].get("section_path", []))
        ]

        self.assertEqual(len(qcp_regions), 1)
        self.assertEqual(qcp_regions[0]["metadata"].get("primary_equip_type"), "Steam Turbine")

    def test_turbine_keywords_match_exact_root_and_subsection_headings(self):
        full_text = "\n".join([
            "GAS TURBINE (297652 | SY1234567)",
            "1 PIPO",
            "1.1 Control System",
            "1.2 QCP",
            "1.3 PIPO Check",
            "1.4 Quality Checkpoint",
        ])

        candidates, _ = preprocessor_v2.FSRV2Preprocessor()._collect_heading_candidates(
            full_text,
            raw_pages=[full_text],
            pages=[full_text],
            page_offsets=[{"start": 0, "end": len(full_text)}],
            active_by_type={"Gas Turbine": ["297652"], "Steam Turbine": []},
        )
        keyword_texts = [
            candidate.heading_text
            for candidate in candidates
            if any(keyword in candidate.heading_text for keyword in ("PIPO", "Control System", "QCP"))
        ]

        self.assertEqual(keyword_texts, ["1 PIPO", "1.1 Control System", "1.2 QCP"])

    def test_turbine_keyword_root_uses_steam_turbine_context(self):
        full_text = "\n".join([
            "STEAM TURBINE (123456 | SY7654321)",
            "2 QCP",
            "Steam turbine QCP content",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        qcp_regions = [
            region for region in result["regions"]
            if any("2 QCP" in heading for heading in region["metadata"].get("section_path", []))
        ]

        self.assertEqual(len(qcp_regions), 1)
        self.assertEqual(qcp_regions[0]["metadata"].get("primary_equip_type"), "Steam Turbine")

    def test_page_number_before_final_subsection_does_not_hide_heading(self):
        full_text = "\n".join([
            "GAS TURBINE (297652 | SY1234567)",
            "4 Turbine",
            "Inspection content",
            "658",
            "4.14 Final Inspection",
            "Final inspection details",
        ])

        candidates, _ = preprocessor_v2.FSRV2Preprocessor()._collect_heading_candidates(
            full_text,
            raw_pages=[full_text],
            pages=[full_text],
            page_offsets=[{"start": 0, "end": len(full_text)}],
            active_by_type={"Gas Turbine": ["297652"], "Steam Turbine": []},
        )

        self.assertTrue(any(
            candidate.heading_text == "4.14 Final Inspection"
            for candidate in candidates
        ))

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

        rotor_region = regions_by_last_section.get("3.8.7 Rotor")
        self.assertIsNotNone(rotor_region, "`3.8.7 Rotor` must be promoted via SUBSEC_GENERIC and emitted as a region")
        self.assertEqual(
            rotor_region["metadata"].get("primary_equip_type"),
            "Gas Turbine",
            "Rotor must inherit Gas Turbine context from typed `3 Turbine` parent (not flip to Generator)",
        )

        generator_region = regions_by_last_section.get("3.8.6 Generator")
        self.assertIsNotNone(generator_region)
        self.assertEqual(generator_region["metadata"].get("primary_equip_type"), "Generator")

    def test_numbered_turbine_root_does_not_inherit_generator_header(self):
        processor = preprocessor_v2.FSRV2Preprocessor()
        candidates = [
            preprocessor_v2.HeadingCandidate(
                start_char=0,
                heading_text="Generator",
                heading_type=HeadingType.UNNUMBERED,
                equipment_type="Generator",
                level=-1,
                confidence_rank=60,
            ),
            preprocessor_v2.HeadingCandidate(
                start_char=10,
                heading_text="2 Turbine",
                heading_type=HeadingType.SECTION_HDR,
                equipment_type="Gas Turbine",
                level=0,
                confidence_rank=80,
            ),
            preprocessor_v2.HeadingCandidate(
                start_char=20,
                heading_text="2.1 Auxiliaries",
                heading_type=HeadingType.SUBSEC,
                equipment_type="Gas Turbine",
                level=1,
                confidence_rank=70,
            ),
        ]

        spans = processor._build_hierarchical_spans(candidates, full_len=40)

        self.assertIsNone(spans[1].parent_idx)
        self.assertEqual(processor._section_path_for_span(spans, spans[1]), ["2 Turbine"])
        self.assertEqual(
            processor._section_path_for_span(spans, spans[2]),
            ["2 Turbine", "2.1 Auxiliaries"],
        )


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

    def test_subsec_generic_survives_when_toc_misses_body_number(self):
        toc_page = "\n".join([
            "Table of Contents",
            "1 Executive Summary ....... 3",
            "2 Overview .............. 5",
            "3 Turbine ............... 11",
            "3.8 Turbine Section ..... 20",
            "4 Generator ............ 100",
            "5 Attachments .......... 200",
        ])
        full_text = "\n".join([
            toc_page,
            "GAS TURBINE (298250 | SY0000001)",
            "3 Turbine",
            "3.8.14 Existing Section",
            "Existing content",
            "3.9.1 Missing From Toc",
            "Body content for a valid section absent from the incomplete TOC.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        section_paths = [
            region["metadata"].get("section_path", [])
            for region in result["regions"]
        ]

        self.assertTrue(any(path and path[-1] == "3.9.1 Missing From Toc" for path in section_paths))

    def test_duplicate_numbered_heading_does_not_hide_later_body_content(self):
        full_text = "\n".join([
            "GAS TURBINE (298250 | SY0000001)",
            "7 Turbine",
            "7.1 Compressor Inspection",
            "First 7.1 content.",
            "7.1 Combustion Inspection",
            "Second 7.1 content.",
        ])

        result = preprocessor_v2.preprocess(_build_ctx(full_text))
        leaves = [
            region["metadata"]["section_path"][-1]
            for region in result["regions"]
            if region["metadata"].get("section_path")
        ]

        self.assertIn("7.1 Compressor Inspection", leaves)
        self.assertIn("7.1 Combustion Inspection", leaves)


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

    def test_specialized_subsections_drop_multiline_table_and_toc_artifacts(self):
        full_text = "\n".join([
            "GAS TURBINE (297651 | SY0000001)",
            "3 Turbine",
            "3.1 Compressor",
            "3.1.1 Valid Heading",
            "25.0",
            "Generator flange above (mils)",
            "7.1 Combustion",
            "__________ 358",
        ])

        candidates, _ = preprocessor_v2.FSRV2Preprocessor()._collect_heading_candidates(
            full_text,
            raw_pages=[full_text],
            pages=[full_text],
            page_offsets=[0],
        )

        headings = [candidate.heading_text for candidate in candidates]
        self.assertIn("3.1.1 Valid Heading", headings)
        self.assertFalse(any("Generator flange" in heading for heading in headings))
        self.assertFalse(any("Combustion\n" in heading for heading in headings))


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
            "5.5 Generator Synthetic Pressure Test",
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

    def test_ibat_pool_fallback_tries_all_esns_after_ambiguous_broad_pool(self):
        proc = preprocessor_v2.FSRV2Preprocessor()

        resolved = proc._resolve_span_esn_with_ibat_train(
            "Generator",
            {"Generator": ["337X581", "337X582"]},
            lambda _equip_type, _context: ["337X581", "337X582"],
            {
                "broad_esns": ["337X581", "337X582"],
                "all_esns": ["337X581"],
            },
        )

        self.assertEqual(resolved, "337X581")


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

    def test_region_first_chunking_retains_a_short_standalone_region(self):
        short_text = "1.3 Work Scope\nBrief but valid section."
        long_text = "Detailed findings. " * 40
        text = short_text + "\n" + long_text
        regions = [
            {
                "start": 0,
                "end": len(short_text),
                "metadata": {"section_path": ["1.3 Work Scope"]},
            },
            {
                "start": len(short_text) + 1,
                "end": len(text),
                "metadata": {"section_path": ["1.4 Findings"]},
            },
        ]

        chunks = split_region_first_with_offsets(
            text,
            regions,
            chunk_size=3800,
            chunk_overlap=150,
            min_chunk_size=450,
        )

        work_scope_chunks = [
            chunk for chunk in chunks
            if chunk["section_metadata"].get("section_1") == "1.3 Work Scope"
        ]
        self.assertEqual(len(work_scope_chunks), 1)
        self.assertIn("Brief but valid section.", work_scope_chunks[0]["chunk_text"])

    def test_chunk_filter_merges_short_tail_without_losing_source_coverage(self):
        text = "A" * 4000

        chunks, _ = split_with_offsets(
            text,
            chunk_size=3800,
            chunk_overlap=150,
            min_chunk_size=450,
            strategy="recursive",
        )

        self.assertTrue(chunks)
        self.assertEqual(chunks[0][1], 0)
        self.assertEqual(chunks[-1][2], len(text))
        self.assertEqual(chunks[-1][0], text[chunks[-1][1]:chunks[-1][2]])

    def test_chunk_filter_still_rejects_a_tiny_nonsemantic_input(self):
        chunks, _ = split_with_offsets(
            "x",
            chunk_size=3800,
            chunk_overlap=150,
            min_chunk_size=450,
            strategy="recursive",
        )

        self.assertEqual(chunks, [])

    def test_region_first_chunking_removes_exact_vertical_next_heading(self):
        first_region = "Inspection details.\n2\n.\n1\nA\nU\nX\nI\nL\nI\nA\nR\nI\nE\nS\n"
        second_region = "2.1 AUXILIARIES\nFollowing section details."
        text = first_region + second_region
        regions = [
            {
                "start": 0,
                "end": len(first_region),
                "metadata": {"section_path": ["2 Turbine"]},
            },
            {
                "start": len(first_region),
                "end": len(text),
                "metadata": {"section_path": ["2 Turbine", "2.1 AUXILIARIES"]},
            },
        ]

        chunks = split_region_first_with_offsets(
            text,
            regions,
            chunk_size=3800,
            chunk_overlap=0,
            min_chunk_size=1,
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["chunk_text"], "Inspection details.")
        self.assertEqual(chunks[0]["end_char"], len("Inspection details."))
        self.assertTrue(chunks[1]["chunk_text"].startswith("2.1 AUXILIARIES"))

    def test_region_first_chunking_keeps_nonmatching_vertical_text(self):
        first_region = "Inspection details.\nF\nR\nO\nM\n"
        second_region = "2.1 AUXILIARIES\nFollowing section details."
        text = first_region + second_region
        regions = [
            {
                "start": 0,
                "end": len(first_region),
                "metadata": {"section_path": ["2 Turbine"]},
            },
            {
                "start": len(first_region),
                "end": len(text),
                "metadata": {"section_path": ["2 Turbine", "2.1 AUXILIARIES"]},
            },
        ]

        chunks = split_region_first_with_offsets(
            text,
            regions,
            chunk_size=3800,
            chunk_overlap=0,
            min_chunk_size=1,
        )

        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0]["chunk_text"].endswith("F\nR\nO\nM"))

    def test_region_first_chunking_keeps_repeated_text_within_same_section(self):
        first_region = "Inspection details.\nRepeated line\n"
        second_region = "Repeated line\nFollowing details."
        text = first_region + second_region
        regions = [
            {
                "start": 0,
                "end": len(first_region),
                "metadata": {
                    "section_path": ["2 Turbine"],
                    "fallback_reason": "first",
                },
            },
            {
                "start": len(first_region),
                "end": len(text),
                "metadata": {
                    "section_path": ["2 Turbine"],
                    "fallback_reason": "second",
                },
            },
        ]

        chunks = split_region_first_with_offsets(
            text,
            regions,
            chunk_size=3800,
            chunk_overlap=0,
            min_chunk_size=1,
        )

        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0]["chunk_text"].endswith("Repeated line"))

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

        def fake_preprocess(ctx, ibat_resolver=None):
            captured["raw_pages"] = ctx.raw_pages
            captured["pages"] = ctx.pages
            captured["filename"] = ctx.filename
            return {"metadata": {"ok": True}, "hints": "x", "regions": []}

        with patch.object(metadata_processor._preprocessor, "preprocess", side_effect=fake_preprocess):
            parsed_doc = ParsedDocument(
                document_id="doc-1",
                filename="demo.pdf",
                volume_path="/tmp/demo.pdf",
                full_text="hello",
                pages=["clean-page"],
                raw_pages=["raw-page"],
                page_offsets=[{"start": 0, "end": 5}],
            )

            out = metadata_processor.run(parsed_doc)
            self.assertTrue(out["metadata"]["ok"])
            self.assertEqual(captured["raw_pages"], ["raw-page"])
            self.assertEqual(captured["pages"], ["clean-page"])
            self.assertEqual(captured["filename"], "demo.pdf")


    def test_ibat_resolver_issues_train_scoped_sql_with_turbine_esn(self):
        # When context supplies current_turbine_esn, the resolver must issue a
        # train-scoped SQL that joins on train_sys_id_fk against the anchor
        # turbine. Fixes cross-run non-determinism where the type-only query
        # returned every Generator ESN and depended on doc-text broad_esns.
        from unittest.mock import MagicMock

        spark = MagicMock()
        spark.sql.return_value.collect.return_value = [MagicMock(candidate_esn="337X765")]

        resolver = metadata_processor._make_ibat_resolver(spark, "cat.sch.ibat")
        result = resolver("Generator", {"current_turbine_esn": "297651"})

        self.assertEqual(result, ["337X765"])
        issued_sql = spark.sql.call_args[0][0]
        self.assertIn("train_sys_id_fk IN (", issued_sql)
        self.assertIn("'297651'", issued_sql)
        self.assertIn("UPPER(TRIM('Generator'))", issued_sql)
        self.assertIn("'InService'", issued_sql)
        self.assertIn("'Active'", issued_sql)


    def test_ibat_resolver_falls_back_when_turbine_esn_missing(self):
        # No anchor turbine — resolver must run the wider type-only query
        # rather than emitting a broken subquery. Keeps behaviour graceful for
        # docs without a discoverable turbine ESN.
        from unittest.mock import MagicMock

        spark = MagicMock()
        spark.sql.return_value.collect.return_value = []

        resolver = metadata_processor._make_ibat_resolver(spark, "cat.sch.ibat")
        resolver("Generator", {})

        issued_sql = spark.sql.call_args[0][0]
        self.assertNotIn("train_sys_id_fk IN", issued_sql)
        self.assertIn("UPPER(TRIM('Generator'))", issued_sql)
        self.assertIn("'InService'", issued_sql)


    def test_ibat_resolver_guards_against_malformed_turbine_esn(self):
        # Defense in depth: an ESN with anything outside [A-Z0-9]{4,10} must
        # not be interpolated into SQL. Resolver should fall back to the wider
        # query instead of issuing a train-scoped join with unsafe input.
        from unittest.mock import MagicMock

        spark = MagicMock()
        spark.sql.return_value.collect.return_value = []

        resolver = metadata_processor._make_ibat_resolver(spark, "cat.sch.ibat")
        resolver("Generator", {"current_turbine_esn": "297651'); DROP TABLE users; --"})

        issued_sql = spark.sql.call_args[0][0]
        self.assertNotIn("DROP TABLE", issued_sql.upper())
        self.assertNotIn("train_sys_id_fk IN", issued_sql)


def _make_parsed_doc(doc_id: str = "test-doc", volume_path: str = "/vol/test.pdf") -> ParsedDocument:
    return ParsedDocument(
        document_id=doc_id,
        filename="test.pdf",
        volume_path=volume_path,
        full_text="Outage Start Date: 2019-03-01\nGAS TURBINE (298250)",
        pages=["Outage Start Date: 2019-03-01\nGAS TURBINE (298250)"],
        raw_pages=["Outage Start Date: 2019-03-01\nGAS TURBINE (298250)"],
        page_offsets=[{"start": 0, "end": 50}],
    )


class TestParsedDocumentVolume(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        doc = _make_parsed_doc()
        with tempfile.TemporaryDirectory() as tmp:
            saved = save_parsed_document(doc, tmp, "pymupdf_v1.0")
            self.assertTrue(Path(saved.parsed_volume_path).exists())
            loaded = load_parsed_document(saved.parsed_volume_path)
            self.assertEqual(loaded.document_id, doc.document_id)
            self.assertEqual(loaded.pages, doc.pages)

    def test_load_raises_on_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            corrupt = Path(tmp) / "bad-doc.json"
            corrupt.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                load_parsed_document(str(corrupt))
            self.assertIn("Corrupt", str(ctx.exception))


class TestEnrichmentLLMFailurePropagates(unittest.TestCase):
    def test_llm_exception_propagates(self):
        from silver.src.etl.fsr_v2 import enrichment
        doc = _make_parsed_doc()
        with patch("silver.src.etl.fsr_v2.enrichment.extract_llm_metadata",
                   side_effect=RuntimeError("LLM timeout")):
            with self.assertRaises(RuntimeError, msg="LLM failure must not be swallowed"):
                enrichment.run(
                    spark=MagicMock(),
                    parsed_doc=doc,
                    processor_output={"metadata": {}, "hints": "", "regions": []},
                    metadata_table="cat.sch.tbl",
                    llm_base_url="http://localhost",
                    llm_api_key="key",
                    llm_model="gpt-4",
                )

    def test_pre_2016_document_is_persisted(self):
        from silver.src.etl.fsr_v2 import enrichment
        doc = _make_parsed_doc()
        with patch("silver.src.etl.fsr_v2.enrichment.extract_llm_metadata",
                   return_value={"outage_start_date": "2013-06-15"}), \
             patch("silver.src.etl.fsr_v2.enrichment.write_enriched_metadata",
                   return_value={"document_id": doc.document_id}) as write_metadata:
            result = enrichment.run(
                spark=MagicMock(),
                parsed_doc=doc,
                processor_output={"metadata": {}, "hints": "", "regions": []},
                metadata_table="cat.sch.tbl",
                llm_base_url="http://localhost",
                llm_api_key="key",
                llm_model="gpt-4",
            )

        self.assertEqual(result, {"document_id": doc.document_id})
        self.assertEqual(write_metadata.call_args.kwargs["doc_year"], 2013)

    def test_unparseable_document_date_is_persisted_without_year(self):
        from silver.src.etl.fsr_v2 import enrichment
        doc = _make_parsed_doc()
        with patch("silver.src.etl.fsr_v2.enrichment.write_enriched_metadata",
                   return_value={"document_id": doc.document_id}) as write_metadata:
            result = enrichment.run(
                spark=MagicMock(),
                parsed_doc=doc,
                processor_output={"metadata": {}, "hints": "", "regions": []},
                metadata_table="cat.sch.tbl",
                llm_base_url="http://localhost",
                llm_api_key="key",
                llm_model="gpt-4",
                llm_meta={"outage_start_date": "Unknown"},
            )

        self.assertEqual(result, {"document_id": doc.document_id})
        self.assertIsNone(write_metadata.call_args.kwargs["doc_year"])

class TestPageOneDateExtraction(unittest.TestCase):
    """Tests for the reusable page-1 date extraction helper."""

    def test_extracts_year_from_outage_label(self):
        self.assertEqual(extract_doc_year_from_page1("Outage Start Date: 2013-06-15"), 2013)

    def test_extracts_year_from_job_start_label(self):
        self.assertEqual(extract_doc_year_from_page1("Job Start Date: September 15, 2016"), 2016)

    def test_extracts_year_from_report_issued_label(self):
        self.assertEqual(extract_doc_year_from_page1("Report Issued: 15 May 2023"), 2023)

    def test_extracts_year_from_approved_date_label(self):
        self.assertEqual(extract_doc_year_from_page1("Approved Date: 05/05/2020"), 2020)

    def test_extracts_year_case_insensitive(self):
        self.assertEqual(extract_doc_year_from_page1("APPROVED DATE 2021-01-01"), 2021)

    def test_returns_none_when_no_date(self):
        self.assertIsNone(extract_doc_year_from_page1("No date info here"))

    def test_returns_none_for_empty_text(self):
        self.assertIsNone(extract_doc_year_from_page1(""))

    def test_backward_compat_alias(self):
        from silver.src.etl.fsr_v2.parsing import extract_outage_year_from_page1
        self.assertEqual(extract_outage_year_from_page1("Job Start Date: 2019-01-01"), 2019)


class TestDetermineDocDate(unittest.TestCase):
    def test_prefers_outage_start_date(self):
        date, src = determine_doc_date("2019-03-01", "2018-01-01", "2017-05-01")
        self.assertEqual(date, "2019-03-01")
        self.assertEqual(src, "outage_start_date")

    def test_falls_back_to_job_start_date(self):
        date, src = determine_doc_date(None, "2016-09-15", "2020-05-05")
        self.assertEqual(date, "2016-09-15")
        self.assertEqual(src, "job_start_date")

    def test_falls_back_to_approved_date(self):
        date, src = determine_doc_date("", "", "2020-05-05")
        self.assertEqual(date, "2020-05-05")
        self.assertEqual(src, "approved_date")

    def test_falls_back_to_report_issued_date(self):
        date, src = determine_doc_date(None, None, None, "2022-11-01")
        self.assertEqual(date, "2022-11-01")
        self.assertEqual(src, "report_issued_date")

    def test_returns_none_when_all_empty(self):
        date, src = determine_doc_date(None, None, None)
        self.assertIsNone(date)
        self.assertEqual(src, "missing")


class TestRequestedEsnValidation(unittest.TestCase):
    def test_valid_esn_passes(self):
        for esn in ("298250", "338X447", "1234ABCD"):
            self.assertIsNotNone(re.fullmatch(r"[A-Z0-9]{4,12}", esn.upper()))

    def test_sql_injection_rejected(self):
        self.assertIsNone(re.fullmatch(r"[A-Z0-9]{4,12}", "' OR 1=1 --"))

    def test_too_short_rejected(self):
        self.assertIsNone(re.fullmatch(r"[A-Z0-9]{4,12}", "AB"))


if __name__ == "__main__":
    unittest.main()
