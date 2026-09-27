"""FSR retrieval strategies used by the evaluation harness.

The module deliberately keeps retrieval policy separate from the URA
production service. ``ura_current`` reproduces the current app behavior;
``ura_with_shared_impl`` evaluates the proposed shared-region behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class EligibilityProvider(Protocol):
    def v2_document_ids(self, esn: str, recency_window_months: int) -> list[str]: ...

    def legacy_document_ids(self, esn: str, recency_window_months: int) -> list[str]: ...


class SearchProvider(Protocol):
    def search(
        self,
        *,
        index_name: str,
        query_text: str,
        query_vector: list[float],
        filters: dict[str, Any],
        num_results: int,
        query_type: str,
        columns: list[str],
    ) -> list[dict[str, Any]]: ...


class DatabricksSqlEligibilityProvider:
    """SQL adapter for the v2 gate and legacy document fallback."""

    def __init__(
        self,
        query_client: Any,
        *,
        v2_mapping_table: str,
        v2_metadata_table: str,
        legacy_metadata_table: str,
        legacy_chunks_table: str,
    ) -> None:
        if not hasattr(query_client, "query"):
            raise TypeError("query_client must expose a synchronous query method")
        self._query_client = query_client
        self._v2_mapping_table = v2_mapping_table
        self._v2_metadata_table = v2_metadata_table
        self._legacy_metadata_table = legacy_metadata_table
        self._legacy_chunks_table = legacy_chunks_table

    def v2_document_ids(self, esn: str, recency_window_months: int) -> list[str]:
        rows = self._query_client.query(
            f"""
            SELECT DISTINCT d.document_id
            FROM {self._v2_mapping_table} AS d
            INNER JOIN {self._v2_metadata_table} AS meta
                ON d.document_id = meta.document_id
            WHERE UPPER(d.esn) = UPPER(:esn)
                AND d.is_active = true
                AND meta.chunk_status = 'completed'
                AND meta.outage_start_date >= DATE_FORMAT(
                    ADD_MONTHS(CURRENT_DATE(), -{int(recency_window_months)}),
                    'yyyy-MM-dd'
                )
            """,
            {"esn": esn},
        )
        return _document_ids_from_rows(rows)

    def legacy_document_ids(self, esn: str, recency_window_months: int) -> list[str]:
        rows = self._query_client.query(
            f"""
            SELECT DISTINCT c.document_id
            FROM {self._legacy_metadata_table} AS meta
            INNER JOIN (
                SELECT DISTINCT document_id
                FROM {self._legacy_chunks_table}
                WHERE UPPER(esn) = UPPER(:esn)
            ) AS c ON meta.document_id = c.document_id
            WHERE meta.document_id IS NOT NULL
                AND meta.outage_start_date >= DATE_FORMAT(
                    ADD_MONTHS(CURRENT_DATE(), -{int(recency_window_months)}),
                    'yyyy-MM-dd'
                )
            """,
            {"esn": esn},
        )
        return _document_ids_from_rows(rows)


@dataclass(frozen=True)
class RetrieverConfig:
    v2_index_name: str
    legacy_index_name: str
    top_k: int = 10
    overfetch_k: int | None = None
    recency_window_months: int = 120
    query_type: str = "HYBRID"
    columns: list[str] = field(
        default_factory=lambda: [
            "chunk_id", "document_id", "pdf_name", "page_number", "chunk_text",
            "region_primary_esn", "region_primary_equip_type",
        ]
    )

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be greater than zero")
        if self.overfetch_k is not None and self.overfetch_k < self.top_k:
            raise ValueError("overfetch_k must be greater than or equal to top_k")
        if self.recency_window_months < 0:
            raise ValueError("recency_window_months must not be negative")
        if self.query_type.upper() not in {"HYBRID", "ANN"}:
            raise ValueError("query_type must be HYBRID or ANN")


@dataclass(frozen=True)
class ProbeInput:
    esn: str
    issue_prompt: str


class Retriever(Protocol):
    strategy_name: str

    def retrieve(self, probe: ProbeInput) -> list[dict[str, Any]]: ...


class BaseRetriever:
    strategy_name = "base"

    def __init__(self, config: RetrieverConfig, embedder: Embedder,
                 eligibility: EligibilityProvider, search: SearchProvider) -> None:
        self.config = config
        self._embedder = embedder
        self._eligibility = eligibility
        self._search = search

    def retrieve(self, probe: ProbeInput) -> list[dict[str, Any]]:
        esn = _normalize_esn(probe.esn)
        query_text = probe.issue_prompt.strip()
        if not esn:
            raise ValueError("probe ESN is required")
        if not query_text:
            raise ValueError("probe issue_prompt is required")

        v2_document_ids = _unique(self._eligibility.v2_document_ids(
            esn, self.config.recency_window_months
        ))
        query_vector = self._embedder.embed(query_text)
        if v2_document_ids:
            return self._retrieve_v2(esn, query_text, query_vector, v2_document_ids)

        legacy_document_ids = _unique(self._eligibility.legacy_document_ids(
            esn, self.config.recency_window_months
        ))
        if not legacy_document_ids:
            return []
        return self._retrieve_legacy(esn, query_text, query_vector, legacy_document_ids)

    def _retrieve_v2(self, esn: str, query_text: str, query_vector: list[float],
                     document_ids: list[str]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _retrieve_legacy(self, esn: str, query_text: str, query_vector: list[float],
                         document_ids: list[str]) -> list[dict[str, Any]]:
        rows = self._search.search(
            index_name=self.config.legacy_index_name, query_text=query_text,
            query_vector=query_vector, filters={"esn": esn, "document_id": document_ids},
            num_results=self._request_size(), query_type=self.config.query_type.upper(),
            columns=self.config.columns,
        )
        return self._finalize(rows)

    def _request_size(self) -> int:
        return self.config.overfetch_k or self.config.top_k

    def _finalize(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _dedupe_keep_first(rows)[: self.config.top_k]


class UraCurrentRetriever(BaseRetriever):
    """Reference strategy matching the current URA application behavior."""

    strategy_name = "ura_current"

    def _request_size(self) -> int:
        return self.config.top_k

    def _retrieve_v2(self, esn: str, query_text: str, query_vector: list[float],
                     document_ids: list[str]) -> list[dict[str, Any]]:
        rows = self._search.search(
            index_name=self.config.v2_index_name, query_text=query_text,
            query_vector=query_vector,
            filters={"region_primary_esn": esn, "document_id": document_ids},
            num_results=min(self.config.top_k, 10),
            query_type=self.config.query_type.upper(), columns=self.config.columns,
        )
        return self._finalize(rows)


class UraWithSharedImplRetriever(BaseRetriever):
    """Proposed strategy that adds eligible shared v2 regions."""

    strategy_name = "ura_with_shared_impl"

    def _retrieve_v2(self, esn: str, query_text: str, query_vector: list[float],
                     document_ids: list[str]) -> list[dict[str, Any]]:
        request_size = self._request_size()
        common = {
            "index_name": self.config.v2_index_name, "query_text": query_text,
            "query_vector": query_vector, "num_results": request_size,
            "query_type": self.config.query_type.upper(), "columns": self.config.columns,
        }
        esn_rows = self._search.search(
            **common, filters={"region_primary_esn": esn, "document_id": document_ids}
        )
        shared_rows = self._search.search(
            **common, filters={
                "region_primary_equip_type": "shared", "document_id": document_ids,
            }
        )
        return _dedupe_keep_highest_score([*esn_rows, *shared_rows])[: self.config.top_k]


class DatabricksVectorSearchProvider:
    """Adapter for a Databricks Vector Search direct-access index."""

    def __init__(self, index_client_factory: Any, endpoint_name: str,
                 index_names: dict[str, str]) -> None:
        self._indexes = {
            index_name: index_client_factory.get_index(
                endpoint_name=endpoint_name, index_name=index_name
            )
            for index_name in index_names.values()
        }

    def search(self, *, index_name: str, query_text: str, query_vector: list[float],
               filters: dict[str, Any], num_results: int, query_type: str,
               columns: list[str]) -> list[dict[str, Any]]:
        raw = self._indexes[index_name].similarity_search(
            query_text=query_text, query_vector=query_vector, query_type=query_type,
            columns=columns, num_results=num_results, filters=filters,
        )
        return _parse_results(raw, columns)


def create_retriever(*, strategy: str, config: RetrieverConfig, embedder: Embedder,
                     eligibility: EligibilityProvider, search: SearchProvider) -> Retriever:
    strategies: dict[str, type[BaseRetriever]] = {
        "ura_current": UraCurrentRetriever,
        "ura_with_shared_impl": UraWithSharedImplRetriever,
    }
    try:
        retriever_class = strategies[strategy]
    except KeyError as exc:
        raise ValueError(f"Unknown retriever strategy: {strategy}") from exc
    return retriever_class(config, embedder, eligibility, search)


def _parse_results(raw: dict[str, Any], columns: list[str]) -> list[dict[str, Any]]:
    data = (raw.get("result") or {}).get("data_array") or []
    rows: list[dict[str, Any]] = []
    for raw_row in data:
        row = dict(zip(columns, raw_row[: len(columns)]))
        if len(raw_row) > len(columns):
            row["similarity_score"] = raw_row[-1]
        rows.append(row)
    return rows


def _document_ids_from_rows(rows: Any) -> list[str]:
    document_ids: list[str] = []
    for row in rows or []:
        if isinstance(row, dict):
            value = row.get("document_id")
        else:
            value = getattr(row, "document_id", None)
        if value is not None:
            document_ids.append(str(value))
    return document_ids


def _dedupe_keep_first(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        chunk_id = str(row.get("chunk_id") or "")
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        unique.append(row)
    return unique


def _dedupe_keep_highest_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_chunk: dict[str, dict[str, Any]] = {}
    for row in rows:
        chunk_id = str(row.get("chunk_id") or "")
        if not chunk_id:
            continue
        current = by_chunk.get(chunk_id)
        if current is None or _score(row) > _score(current):
            by_chunk[chunk_id] = row
    return sorted(by_chunk.values(), key=_score, reverse=True)


def _score(row: dict[str, Any]) -> float:
    try:
        return float(row.get("similarity_score", row.get("score", 0.0)) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_esn(value: str) -> str:
    return (value or "").strip().upper()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))
