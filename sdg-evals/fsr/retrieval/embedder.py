"""Embed query text via the LiteLLM gateway used by the FSR pipeline.

Why a separate module
---------------------
The FSR vector index is a **direct-access** index — it stores pre-computed
embeddings but has no model attached. So consumers must embed the query
themselves, using the *same model* the ingestion pipeline used, or the query
vector lives in the wrong space and recall collapses.

This module is intentionally tiny: one POST call with a small retry on
transient failures. Different from production embedding code at
`gold/src/etl/nb_sdg_fsr_chunks.py::embed_batch`, which handles batch
fan-out, 429 backoff, poison-chunk isolation, etc.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout


@dataclass
class EmbedderConfig:
    base_url: str
    api_key: str
    model: str = "azure-text-embedding-3-large-1"
    verify_ssl: bool | str = False
    timeout_s: int = 120       # pipeline uses 120; gateway can be slow (was 30 → 60 → 120)
    max_retries: int = 3       # backoff 1s, 2s, 4s on transient failures


class LiteLLMEmbedder:
    """One-shot text → vector via the LiteLLM gateway."""

    def __init__(self, cfg: EmbedderConfig) -> None:
        self.cfg = cfg
        self._urls = [
            f"{cfg.base_url.rstrip('/')}/v1/embeddings",
            f"{cfg.base_url.rstrip('/')}/embeddings",
        ]
        self._headers = {
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        }
        self._working_url: str | None = None

    def embed(self, text: str) -> list[float]:
        payload: dict[str, Any] = {"model": self.cfg.model, "input": [text]}
        urls = [self._working_url] if self._working_url else self._urls
        last_err: Exception | None = None
        for attempt in range(1, self.cfg.max_retries + 1):
            for url in urls:
                try:
                    r = requests.post(
                        url,
                        headers=self._headers,
                        json=payload,
                        timeout=self.cfg.timeout_s,
                        verify=self.cfg.verify_ssl,
                    )
                    if r.status_code == 404:
                        continue  # try the other URL variant
                    r.raise_for_status()
                    data = r.json().get("data", [])
                    if not data:
                        raise RuntimeError(f"Empty embedding response from {url}")
                    self._working_url = url
                    return data[0]["embedding"]
                except (ReadTimeout, RequestsConnectionError) as e:
                    last_err = e  # transient; will retry the outer loop
                except Exception as e:
                    last_err = e  # try the next URL variant
            if attempt < self.cfg.max_retries:
                time.sleep(2 ** (attempt - 1))  # 1s, 2s, 4s
        raise RuntimeError(f"Embedding call failed after {self.cfg.max_retries} attempt(s): {last_err}")


def embedder_from_env(model: str | None = None) -> LiteLLMEmbedder:
    """Build an embedder from job widgets / env vars — matches fsr_config pattern."""
    base = os.getenv("LITELLM_BASE_URL", "")
    key = os.getenv("LITELLM_API_KEY", "")
    if not base or not key:
        raise RuntimeError(
            "LITELLM_BASE_URL / LITELLM_API_KEY not set. "
            "Set widgets or env vars before constructing the embedder."
        )
    return LiteLLMEmbedder(EmbedderConfig(
        base_url=base,
        api_key=key,
        model=model or "azure-text-embedding-3-large-1",
    ))
