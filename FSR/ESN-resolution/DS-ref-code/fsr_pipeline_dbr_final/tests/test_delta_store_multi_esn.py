import sys
import unittest
from datetime import date, datetime
from pathlib import Path

from langchain_core.documents import Document


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from delta_store import build_delta_rows


class DeltaStoreMultiEsnTests(unittest.TestCase):
    def test_build_delta_rows_duplicates_chunks_for_multi_esn_ref_mapping(self):
        docs = [
            Document(
                page_content="chunk text",
                metadata={
                    "document_id": "e4dbe643-c027-4b47-a27f-a31f8a93cfae",
                    "chunk_index": 7,
                    "start_page": 11,
                },
            )
        ]

        rows = build_delta_rows(
            docs,
            ref_lookup={
                "e4dbe643-c027-4b47-a27f-a31f8a93cfae": {
                    "esns": ["297115", "337X045"],
                    "report_date": date(2023, 12, 30),
                }
            },
            created_at=datetime(2026, 3, 20, 12, 0, 0),
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["generator_serial"] for row in rows},
            {"297115", "337X045"},
        )
        self.assertEqual(
            {row["chunk_id"] for row in rows},
            {
                "e4dbe643-c027-4b47-a27f-a31f8a93cfae_7__297115",
                "e4dbe643-c027-4b47-a27f-a31f8a93cfae_7__337X045",
            },
        )
        self.assertEqual({row["report_date"] for row in rows}, {date(2023, 12, 30)})

    def test_build_delta_rows_unions_ref_esns_with_existing_chunk_labels(self):
        docs = [
            Document(
                page_content="chunk text",
                metadata={
                    "document_id": "doc-1",
                    "chunk_index": 1,
                    "start_page": 3,
                    "esn_labels": ["337X045", "legacy1"],
                },
            )
        ]

        rows = build_delta_rows(
            docs,
            ref_lookup={
                "doc-1": {
                    "esns": ["297115", "337X045"],
                    "report_date": None,
                }
            },
            created_at=datetime(2026, 3, 20, 12, 0, 0),
        )

        self.assertEqual(
            [row["generator_serial"] for row in rows],
            ["297115", "337X045", "LEGACY1"],
        )


if __name__ == "__main__":
    unittest.main()