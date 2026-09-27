from __future__ import annotations

import unittest

from fsr.retrieval_eval.metrics import exact_chunk_metrics, page_level_metrics
from fsr.retrieval_eval.validation import validate_probe_labels


class ValidationAndMetricsTests(unittest.TestCase):
    def test_probe_requires_chunk_table_version_for_chunk_labels(self) -> None:
        with self.assertRaisesRegex(ValueError, "chunk_table_version"):
            validate_probe_labels(
                esn="ESN-1",
                expected_document_ids=["doc-1"],
                expected_cited_doc_pages=[("doc-1", 10)],
                expected_chunk_ids=["chunk-1"],
                chunk_table_version=None,
            )

    def test_page_metrics_use_unique_document_page_pairs(self) -> None:
        results = [
            {"document_id": "doc-1", "page_number": 10, "chunk_id": "a"},
            {"document_id": "doc-1", "page_number": 10, "chunk_id": "b"},
            {"document_id": "doc-1", "page_number": 11, "chunk_id": "c"},
        ]

        metrics = page_level_metrics(results, [("doc-1", 10), ("doc-1", 12)])

        self.assertEqual(metrics["matched_page_pair_count"], 1)
        self.assertEqual(metrics["recall_at_k"], 0.5)
        self.assertEqual(metrics["precision_at_k"], 2 / 3)

    def test_exact_chunk_metrics_match_chunk_ids(self) -> None:
        metrics = exact_chunk_metrics(
            [{"chunk_id": "chunk-1"}, {"chunk_id": "chunk-extra"}],
            {"chunk-1", "chunk-2"},
        )

        self.assertEqual(metrics["chunk_recall_at_k"], 0.5)
        self.assertEqual(metrics["chunk_precision_at_k"], 0.5)
        self.assertEqual(metrics["missing_chunk_ids"], ["chunk-2"])


if __name__ == "__main__":
    unittest.main()
