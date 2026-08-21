"""Shared retry helpers for external HTTP calls."""

from __future__ import annotations

import random
import time
from typing import AbstractSet, Callable, TypeVar

import requests


T = TypeVar("T")

RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def compute_retry_delay(
    attempt: int,
    base_delay: float = 2.0,
    cap_delay: float = 600.0,
    jitter_ratio: float = 0.5,
) -> float:
    """Return capped exponential backoff with +/- jitter_ratio jitter."""
    delay = min(base_delay * (2 ** (attempt - 1)), cap_delay)
    jitter_min = max(0.0, delay * (1.0 - jitter_ratio))
    jitter_max = delay * (1.0 + jitter_ratio)
    return random.uniform(jitter_min, jitter_max)


def max_retry_attempts(
    base_delay: float = 2.0,
    cap_delay: float = 600.0,
    capped_retries: int = 5,
) -> int:
    """Return total attempts: initial try, exponential retries, then capped retries."""
    attempts_before_cap = 0
    delay = base_delay
    while delay < cap_delay:
        attempts_before_cap += 1
        delay *= 2
    return attempts_before_cap + capped_retries + 1


def retry_request(
    request_fn: Callable[[], requests.Response],
    label: str,
    retriable_status_codes: AbstractSet[int] = RETRIABLE_STATUS_CODES,
    base_delay: float = 2.0,
    cap_delay: float = 600.0,
    capped_retries: int = 5,
) -> requests.Response:
    """Execute an HTTP request with capped exponential backoff and jitter."""
    max_attempts = max_retry_attempts(
        base_delay=base_delay,
        cap_delay=cap_delay,
        capped_retries=capped_retries,
    )

    for attempt in range(1, max_attempts + 1):
        try:
            response = request_fn()
        except Exception as exc:
            print(f"[{label}] Connection error (attempt {attempt}/{max_attempts}): {exc}")
            if attempt < max_attempts:
                wait = compute_retry_delay(
                    attempt,
                    base_delay=base_delay,
                    cap_delay=cap_delay,
                )
                print(f"[{label}] Retry in {wait:.1f}s (attempt {attempt + 1}/{max_attempts})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"{label} failed after {max_attempts} attempts: {exc}") from exc

        if response.status_code in retriable_status_codes:
            print(f"[{label}] API Error {response.status_code}: {response.text[:200]}")
            if attempt < max_attempts:
                wait = compute_retry_delay(
                    attempt,
                    base_delay=base_delay,
                    cap_delay=cap_delay,
                )
                print(f"[{label}] Retry in {wait:.1f}s (attempt {attempt + 1}/{max_attempts})")
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"{label} failed after {max_attempts} attempts with HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )

        return response

    raise RuntimeError(f"{label} failed without returning a response")