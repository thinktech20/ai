import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from esn_identifier import (
    DOC_TRUNCATE_WINDOW_CHARS,
    identify_esns,
    _prepare_document_text_for_llm,
)
from pdf_processor import process_single_pdf_with_background_doc_analysis


class SectionEsnParallelTests(unittest.TestCase):
    def test_prepare_document_text_for_llm_uses_start_middle_end_windows(self):
        source = "A" * 100000 + "B" * 100000 + "C" * 100000 + "D" * 100000

        prepared = _prepare_document_text_for_llm(source)
        half_window = DOC_TRUNCATE_WINDOW_CHARS // 2

        self.assertTrue(prepared.startswith("A" * DOC_TRUNCATE_WINDOW_CHARS))
        self.assertIn("\n...\n", prepared)
        self.assertIn("B" * half_window + "C" * half_window, prepared)
        self.assertTrue(prepared.endswith("D" * DOC_TRUNCATE_WINDOW_CHARS))

    def test_identify_esns_applies_document_labels_to_all_chunks(self):
        chunks = [
            {
                "text": "section a chunk",
                "metadata": {
                    "document_id": "doc-1",
                    "chunk_index": 0,
                    "section_1": "Inspection Findings",
                    "start_page": 1,
                },
            },
            {
                "text": "section b chunk",
                "metadata": {
                    "document_id": "doc-1",
                    "chunk_index": 1,
                    "section_1": "Recommendations",
                    "start_page": 2,
                },
            },
        ]

        doc_counts = {"297837": 10, "290T658": 4}

        labeled = identify_esns(chunks, doc_counts=doc_counts)

        self.assertEqual(labeled[0]["metadata"]["esn_labels"], ["297837"])
        self.assertEqual(labeled[0]["metadata"]["esn_assignment_scope"], "document")
        self.assertEqual(labeled[1]["metadata"]["esn_labels"], ["297837"])
        self.assertEqual(labeled[1]["metadata"]["esn_assignment_scope"], "document")
        self.assertEqual(labeled[1]["metadata"]["generator_serial"], "297837")

    def test_background_doc_analysis_preloads_text_then_overlaps_chunking(self):
        def fake_text_loader(pdf_path):
            self.assertEqual(pdf_path, "fake.pdf")
            time.sleep(0.15)
            return "preloaded document text"

        def fake_chunk_fn(pdf_path, config):
            time.sleep(0.35)
            return "doc-1", [], {"chunk_count": 0}

        def fake_doc_analysis(document_text):
            self.assertEqual(document_text, "preloaded document text")
            time.sleep(0.35)
            return {"297837": 6}

        started_at = time.perf_counter()
        doc_id, chunks, stats, doc_counts, timings = process_single_pdf_with_background_doc_analysis(
            "fake.pdf",
            config=object(),
            doc_analysis_fn=fake_doc_analysis,
            chunk_fn=fake_chunk_fn,
            text_loader_fn=fake_text_loader,
        )
        elapsed = time.perf_counter() - started_at

        self.assertEqual(doc_id, "doc-1")
        self.assertEqual(chunks, [])
        self.assertEqual(stats["chunk_count"], 0)
        self.assertEqual(doc_counts, {"297837": 6})
        self.assertGreaterEqual(timings["chunk_elapsed"], 0.30)
        self.assertGreaterEqual(timings["esn_elapsed"], 0.50)
        self.assertLess(elapsed, 0.75)

    def test_background_doc_analysis_receives_prepared_snippet(self):
        source = "A" * 100000 + "B" * 100000 + "C" * 100000 + "D" * 100000
        captured = {}

        def fake_text_loader(pdf_path):
            self.assertEqual(pdf_path, "fake.pdf")
            return source

        def fake_chunk_fn(pdf_path, config):
            return "doc-1", [], {"chunk_count": 0}

        def fake_doc_analysis(prepared_text):
            captured["prepared_text"] = prepared_text
            return {"297837": 6}

        process_single_pdf_with_background_doc_analysis(
            "fake.pdf",
            config=object(),
            doc_analysis_fn=fake_doc_analysis,
            chunk_fn=fake_chunk_fn,
            text_loader_fn=fake_text_loader,
        )

        self.assertEqual(captured["prepared_text"], _prepare_document_text_for_llm(source))

    def test_background_doc_analysis_skips_when_text_preload_fails(self):
        def fake_text_loader(pdf_path):
            raise RuntimeError("Cannot open empty file")

        def fake_chunk_fn(pdf_path, config):
            return "doc-1", [{"text": "chunk", "metadata": {}}], {"chunk_count": 1}

        def fake_doc_analysis(document_text):
            raise AssertionError("Doc analysis should not run when preload fails")

        doc_id, chunks, stats, doc_counts, timings = process_single_pdf_with_background_doc_analysis(
            "fake.pdf",
            config=object(),
            doc_analysis_fn=fake_doc_analysis,
            chunk_fn=fake_chunk_fn,
            text_loader_fn=fake_text_loader,
        )

        self.assertEqual(doc_id, "doc-1")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(stats["chunk_count"], 1)
        self.assertEqual(doc_counts, {})
        self.assertGreaterEqual(timings["esn_elapsed"], 0.0)


if __name__ == "__main__":
    unittest.main()