from __future__ import annotations

import unittest

from fsr.retrieval.retriever import (
    ProbeInput,
    RetrieverConfig,
    UraCurrentRetriever,
    UraWithSharedImplRetriever,
    create_retriever,
)


class FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        return [float(len(text))]


class FakeEligibility:
    def __init__(self, v2: list[str], legacy: list[str] | None = None) -> None:
        self.v2 = v2
        self.legacy = legacy or []
        self.calls: list[tuple[str, str, int]] = []

    def v2_document_ids(self, esn: str, recency_window_months: int) -> list[str]:
        self.calls.append(("v2", esn, recency_window_months))
        return self.v2

    def legacy_document_ids(self, esn: str, recency_window_months: int) -> list[str]:
        self.calls.append(("legacy", esn, recency_window_months))
        return self.legacy


class FakeSearch:
    def __init__(self, rows_by_filter: dict[str, list[dict]]) -> None:
        self.rows_by_filter = rows_by_filter
        self.calls: list[dict] = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if "region_primary_equip_type" in kwargs["filters"]:
            return self.rows_by_filter.get("shared", [])
        if "region_primary_esn" in kwargs["filters"]:
            return self.rows_by_filter.get("esn", [])
        return self.rows_by_filter.get("legacy", [])


def row(chunk_id: str, score: float, **extra) -> dict:
    return {"chunk_id": chunk_id, "similarity_score": score, **extra}


class RetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = RetrieverConfig("v2", "legacy", top_k=2, overfetch_k=4)
        self.probe = ProbeInput(" esn-1 ", "find vibration")

    def test_current_uses_esn_filter_and_keeps_first_duplicate(self) -> None:
        eligibility = FakeEligibility(["doc-1"])
        search = FakeSearch({"esn": [row("a", 0.4), row("a", 0.9), row("b", 0.8)]})
        retriever = UraCurrentRetriever(self.config, FakeEmbedder(), eligibility, search)

        results = retriever.retrieve(self.probe)

        self.assertEqual([r["chunk_id"] for r in results], ["a", "b"])
        self.assertEqual(search.calls[0]["filters"], {
            "region_primary_esn": "ESN-1", "document_id": ["doc-1"]
        })
        self.assertEqual(search.calls[0]["num_results"], 2)

    def test_current_caps_v2_request_at_ten(self) -> None:
        eligibility = FakeEligibility(["doc-1"])
        search = FakeSearch({"esn": [row(str(i), 1.0) for i in range(20)]})
        config = RetrieverConfig("v2", "legacy", top_k=20, overfetch_k=20)
        retriever = UraCurrentRetriever(config, FakeEmbedder(), eligibility, search)

        retriever.retrieve(self.probe)

        self.assertEqual(search.calls[0]["num_results"], 10)

    def test_shared_merges_shared_rows_and_keeps_highest_duplicate_score(self) -> None:
        eligibility = FakeEligibility(["doc-1"])
        search = FakeSearch({
            "esn": [row("duplicate", 0.4), row("esn-only", 0.7)],
            "shared": [row("duplicate", 0.9), row("shared-only", 0.8)],
        })
        retriever = UraWithSharedImplRetriever(self.config, FakeEmbedder(), eligibility, search)

        results = retriever.retrieve(self.probe)

        self.assertEqual([r["chunk_id"] for r in results], ["duplicate", "shared-only"])
        self.assertEqual(results[0]["similarity_score"], 0.9)
        self.assertEqual(search.calls[1]["filters"], {
            "region_primary_equip_type": "shared", "document_id": ["doc-1"]
        })

    def test_no_v2_documents_uses_legacy_fallback(self) -> None:
        eligibility = FakeEligibility([], ["legacy-doc"])
        search = FakeSearch({"legacy": [row("legacy-chunk", 0.5)]})
        retriever = UraCurrentRetriever(self.config, FakeEmbedder(), eligibility, search)

        results = retriever.retrieve(self.probe)

        self.assertEqual([r["chunk_id"] for r in results], ["legacy-chunk"])
        self.assertEqual(search.calls[0]["index_name"], "legacy")
        self.assertEqual(search.calls[0]["filters"]["esn"], "ESN-1")

    def test_factory_selects_named_strategies(self) -> None:
        eligibility = FakeEligibility([])
        search = FakeSearch({})
        current = create_retriever(
            strategy="ura_current", config=self.config, embedder=FakeEmbedder(),
            eligibility=eligibility, search=search,
        )
        shared = create_retriever(
            strategy="ura_with_shared_impl", config=self.config, embedder=FakeEmbedder(),
            eligibility=eligibility, search=search,
        )

        self.assertEqual(current.strategy_name, "ura_current")
        self.assertEqual(shared.strategy_name, "ura_with_shared_impl")


if __name__ == "__main__":
    unittest.main()
