"""Stage 5 embedding client helpers."""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("fsr.v2.chunking")


def embed_batch(
    texts: list[str],
    base_url: str,
    api_key: str,
    model: str,
    verify_ssl: Any,
    max_retries: int = 3,
) -> list[list[float]]:
    """Embed one batch against LiteLLM endpoint with retries."""
    import requests  # noqa: PLC0415

    base = base_url.rstrip("/")
    urls = [f"{base}/v1/embeddings", f"{base}/embeddings"]
    payload = {"model": model, "input": texts}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(1, max_retries + 1):
        for url in urls:
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=120, verify=verify_ssl)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = sorted(resp.json().get("data", []), key=lambda x: x.get("index", 0))
                if len(data) != len(texts):
                    raise RuntimeError(f"Expected {len(texts)} embeddings, got {len(data)}")
                return [item["embedding"] for item in data]
            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    wait = 5 * (2 ** (attempt - 1))
                    log.warning(f"Embed attempt {attempt} failed ({e}); retrying in {wait}s")
                    time.sleep(wait)
    raise RuntimeError(f"Embedding failed after {max_retries} retries: {last_err}")


def safe_embed_batch(
    batch_idx: int,
    texts: list[str],
    refs: list,
    base_url: str,
    api_key: str,
    model: str,
    verify_ssl: Any,
    max_retries: int,
) -> list[tuple]:
    """Embed a batch; bisect to per-chunk on failure to isolate poison inputs."""
    try:
        vecs = embed_batch(texts, base_url, api_key, model, verify_ssl, max_retries)
        return [(ref, vec) for ref, vec in zip(refs, vecs)]
    except Exception as batch_exc:
        log.error(f"Batch {batch_idx} failed ({batch_exc}); bisecting {len(texts)} chunks")
        results = []
        for ref, text in zip(refs, texts):
            try:
                vec = embed_batch([text], base_url, api_key, model, verify_ssl, max_retries)[0]
                results.append((ref, vec))
            except Exception as e:
                log.warning(f"  Bisect: chunk {ref} failed: {str(e)[:120]}")
                results.append((ref, None))
        return results
