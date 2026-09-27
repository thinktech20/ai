"""Compatibility wrapper for older imports.

Use `common.llm_client` for the generic client. This module preserves the
TIL-specific convenience function used by the notebook.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from ..llm_client import call_llm, parse_llm_response, _resolve_verify_ssl  # noqa: F401
from .til_config import (
    TIL_LLM_MAX_RETRIES,
    TIL_LLM_MAX_TOKENS,
    TIL_LLM_MODEL,
    TIL_LLM_TIMEOUT_SECONDS,
    TIL_LLM_TEMPERATURE,
    TIL_LLM_USE_GATEWAY_DEFAULT_MAX_TOKENS,
    get_litellm_config,
)


def extract_til_profile_via_llm(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    verify_ssl: bool | str = True,
) -> tuple[dict[str, Any] | None, str | None, float]:
    """Extract TIL profile via the shared generic LLM client."""
    start_time = time.time()
    litellm_config = get_litellm_config()

    effective_max_tokens = max_tokens
    if effective_max_tokens is None:
        effective_max_tokens = None if TIL_LLM_USE_GATEWAY_DEFAULT_MAX_TOKENS else TIL_LLM_MAX_TOKENS

    raw_response = call_llm(
        system_prompt,
        user_prompt,
        base_url=litellm_config["base_url"],
        api_key=litellm_config["api_key"],
        model=model or litellm_config["model"] or TIL_LLM_MODEL,
        temperature=TIL_LLM_TEMPERATURE if temperature is None else temperature,
        max_tokens=effective_max_tokens,
        timeout=TIL_LLM_TIMEOUT_SECONDS,
        max_retries=TIL_LLM_MAX_RETRIES,
        verify_ssl=verify_ssl,
    )

    parsed_profile, _ = parse_llm_response(raw_response)
    latency = time.time() - start_time
    return parsed_profile, raw_response, latency


def call_llm_for_doc_profile(
    system_prompt: str,
    user_content: list,
    *,
    api_key: str,
    base_url: str,
    model: str,
    max_tokens: int,
    retry_max_tokens: int | None = None,
    verify_ssl: bool | str = True,
    timeout: int = 600,
) -> dict[str, Any]:
    """Call the LiteLLM gateway for document profile extraction (multimodal).

    Consolidates auth, TLS, and length-retry decisions for both PDF-attachment
    and plain-text (docx) profile extraction paths so they share one client.
    ``user_content`` is a typed message list (text + optional file parts).
    """
    raw = call_llm(
        system_prompt,
        "",
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=0.0,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=1,
        verify_ssl=verify_ssl,
        user_content=user_content,
        length_retry_tokens=retry_max_tokens,
    )
    if not raw:
        raise RuntimeError("LLM returned no response for document profile extraction")
    parsed, _ = parse_llm_response(raw)
    if not parsed:
        raise RuntimeError("Could not parse JSON profile from LLM response")
    return parsed
