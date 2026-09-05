"""LiteLLM query embeddings for self-managed Databricks Vector Search indexes."""

from __future__ import annotations

import time
from functools import lru_cache

import requests

from config import (
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    VECTOR_SEARCH_EMBEDDING_MODEL,
    VECTOR_SEARCH_EMBEDDING_REQUEST_PATH,
    VECTOR_SEARCH_EMBEDDING_VERIFY_SSL,
)


def _build_request_url(base_url: str, request_path: str) -> str:
    base = base_url.rstrip("/")
    path = request_path if request_path.startswith("/") else f"/{request_path}"
    if base.endswith("/v1") and path.startswith("/v1/"):
        path = path[3:]
    return base + path


def _candidate_request_urls(base_url: str, request_path: str) -> list[str]:
    urls = [_build_request_url(base_url, request_path)]
    for fallback_path in ("/v1/embeddings", "/embeddings"):
        candidate = _build_request_url(base_url, fallback_path)
        if candidate not in urls:
            urls.append(candidate)
    return urls


class _LiteLLMEmbeddingClient:
    def __init__(self) -> None:
        self.api_key = LITELLM_API_KEY.strip()
        self.model = VECTOR_SEARCH_EMBEDDING_MODEL
        self.urls = _candidate_request_urls(
            LITELLM_BASE_URL,
            VECTOR_SEARCH_EMBEDDING_REQUEST_PATH,
        )

        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )
        self.session.verify = VECTOR_SEARCH_EMBEDDING_VERIFY_SSL

    def embed_texts(self, texts: list[str], max_retries: int = 3) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError(
                "Missing LITELLM_API_KEY. Set it before querying the self-managed Vector Search index."
            )

        payload = {"model": self.model, "input": texts}
        failures: list[str] = []

        for url_index, url in enumerate(self.urls):
            for attempt in range(1, max_retries + 1):
                try:
                    response = self.session.post(url, json=payload, timeout=120)
                    if response.status_code == 404 and url_index < len(self.urls) - 1:
                        failures.append(f"{url} -> HTTP 404")
                        break
                    if response.status_code >= 400:
                        raise RuntimeError(
                            f"HTTP {response.status_code}: {response.text[:500]}"
                        )

                    body = response.json()
                    data = body.get("data") or []
                    if len(data) != len(texts):
                        raise RuntimeError(
                            f"Expected {len(texts)} embeddings, received {len(data)}"
                        )

                    ordered = sorted(data, key=lambda item: item.get("index", 0))
                    return [
                        [float(value) for value in item.get("embedding", [])]
                        for item in ordered
                    ]
                except Exception as exc:
                    if attempt >= max_retries:
                        failures.append(f"{url} -> {exc}")
                        continue
                    time.sleep(2 * attempt)

        raise RuntimeError(
            "LiteLLM embedding request failed for all candidate embedding endpoints: "
            + " | ".join(failures)
        )


_CLIENT = _LiteLLMEmbeddingClient()


@lru_cache(maxsize=512)
def _cached_query_vector(text: str) -> tuple[float, ...]:
    query = text.strip()
    if not query:
        raise ValueError("Query text is empty; cannot compute a Vector Search query vector.")
    return tuple(_CLIENT.embed_texts([query])[0])


def get_query_vector(text: str) -> list[float]:
    return list(_cached_query_vector(text))