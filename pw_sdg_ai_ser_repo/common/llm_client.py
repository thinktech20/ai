"""Generic LLM client helpers.

Reusable across pipelines. Specific pipelines should provide their own config
and prompt-building wrappers.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional

import requests

log = logging.getLogger(__name__)

RETRIABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_LAST_LLM_CALL_DIAGNOSTICS: dict[str, Any] = {}


def _set_last_llm_call_diagnostics(**kwargs: Any) -> None:
    global _LAST_LLM_CALL_DIAGNOSTICS
    _LAST_LLM_CALL_DIAGNOSTICS = dict(kwargs)


def get_last_llm_call_diagnostics() -> dict[str, Any]:
    return dict(_LAST_LLM_CALL_DIAGNOSTICS)


def _stringify_response_fragment(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "value", "content", "output_text", "arguments"):
            text = _stringify_response_fragment(value.get(key))
            if text:
                return text
        if value:
            return json.dumps(value)
        return ""
    if isinstance(value, list):
        parts = [_stringify_response_fragment(item) for item in value]
        return "\n".join(part for part in parts if part)
    return str(value)


def _extract_response_text(data: dict[str, Any]) -> Optional[str]:
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message") if isinstance(choice, dict) else {}
        if isinstance(message, dict):
            for key in ("content", "reasoning_content", "refusal"):
                text = _stringify_response_fragment(message.get(key))
                if text:
                    return text
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        continue
                    function_payload = tool_call.get("function")
                    if isinstance(function_payload, dict):
                        text = _stringify_response_fragment(function_payload.get("arguments"))
                        if text:
                            return text
        for key in ("text", "content"):
            text = _stringify_response_fragment(choice.get(key) if isinstance(choice, dict) else None)
            if text:
                return text

    for key in ("output_text", "content", "text"):
        text = _stringify_response_fragment(data.get(key))
        if text:
            return text

    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            text = _stringify_response_fragment(item.get("content"))
            if text:
                return text

    return None


def _resolve_verify_ssl(verify_ssl: bool | str) -> bool | str:
    """Resolve verify setting, honouring corp CA bundle env vars when trust_env is disabled."""
    if verify_ssl is not True:
        return verify_ssl
    ca_bundle = os.getenv("REQUESTS_CA_BUNDLE", "").strip() or os.getenv("SSL_CERT_FILE", "").strip()
    return ca_bundle if ca_bundle else True


def _build_authorization_header(api_key: str) -> str:
    """Build a robust Authorization header value from raw or prefixed API key input."""
    token = (api_key or "").strip()
    # Handle accidental shell-style quoting around the token.
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}:
        token = token[1:-1].strip()

    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


def call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    response_format: dict[str, Any] | None = None,
    timeout: int = 300,
    max_retries: int = 2,
    verify_ssl: bool | str = True,
    user_content: list | None = None,
    length_retry_tokens: int | None = None,
) -> Optional[str]:
    """Call an OpenAI-compatible LLM endpoint and return raw response text.

    Pass ``user_content`` (a list of typed message parts) for multimodal calls
    (e.g. PDF file attachments); ``user_prompt`` is used when it is omitted.
    Pass ``length_retry_tokens`` to retry once with a higher token budget when
    the model truncates the response (finish_reason=="length").
    """
    headers = {
        "Authorization": _build_authorization_header(api_key),
        "Content-Type": "application/json",
    }

    session = requests.Session()
    session.trust_env = False

    user_message_content: list | str = user_content if user_content is not None else user_prompt
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message_content},
        ],
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if response_format is not None:
        payload["response_format"] = response_format

    endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
    content_size = len(json.dumps(user_content)) if user_content is not None else len(user_prompt or "")
    _set_last_llm_call_diagnostics(
        status="started",
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        endpoint=endpoint,
        user_prompt_chars=content_size,
        system_prompt_chars=len(system_prompt or ""),
    )

    effective_verify = _resolve_verify_ssl(verify_ssl)

    for attempt in range(1, max_retries + 1):
        try:
            log.debug("LLM call attempt %s/%s: %s", attempt, max_retries, model)
            response = session.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=timeout,
                verify=effective_verify,
            )

            if response.status_code == 200:
                data = response.json()
                finish_reason = (
                    (data.get("choices") or [{}])[0].get("finish_reason")
                    if isinstance(data.get("choices"), list) and data.get("choices")
                    else None
                )
                text = _extract_response_text(data)

                # One-shot retry with higher token budget if the model was truncated.
                if finish_reason == "length" and length_retry_tokens is not None:
                    retry_payload = {**payload, "max_tokens": length_retry_tokens}
                    retry_resp = session.post(
                        endpoint, json=retry_payload, headers=headers,
                        timeout=timeout, verify=effective_verify,
                    )
                    if retry_resp.status_code == 200:
                        retry_text = _extract_response_text(retry_resp.json())
                        if retry_text:
                            text = retry_text
                            data = retry_resp.json()
                            finish_reason = (
                                (data.get("choices") or [{}])[0].get("finish_reason")
                                if isinstance(data.get("choices"), list) and data.get("choices")
                                else None
                            )

                if text:
                    _set_last_llm_call_diagnostics(
                        status="ok",
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                        endpoint=endpoint,
                        attempt=attempt,
                        status_code=response.status_code,
                        finish_reason=(data.get("choices") or [{}])[0].get("finish_reason") if isinstance(data.get("choices"), list) and data.get("choices") else None,
                        extracted_text_chars=len(text),
                    )
                    return text
                usage = data.get("usage") if isinstance(data, dict) else None
                _set_last_llm_call_diagnostics(
                    status="no_text_response",
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    endpoint=endpoint,
                    attempt=attempt,
                    status_code=response.status_code,
                    finish_reason=(data.get("choices") or [{}])[0].get("finish_reason") if isinstance(data.get("choices"), list) and data.get("choices") else None,
                    completion_tokens=(usage or {}).get("completion_tokens") if isinstance(usage, dict) else None,
                    prompt_tokens=(usage or {}).get("prompt_tokens") if isinstance(usage, dict) else None,
                    response_preview=json.dumps(data)[:1000],
                )
                log.warning(
                    "LLM returned 200 but no text in response. body=%s",
                    json.dumps(data)[:1000],
                )
                return None

            if response.status_code in RETRIABLE_STATUS_CODES and attempt < max_retries:
                log.warning("LLM returned %s, retrying...", response.status_code)
                continue

            _set_last_llm_call_diagnostics(
                status="http_error",
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                endpoint=endpoint,
                attempt=attempt,
                status_code=response.status_code,
                response_preview=response.text[:1000],
            )
            log.error("LLM request failed: %s - %s", response.status_code, response.text[:500])
            return None

        except Exception as exc:
            if attempt < max_retries:
                log.warning("LLM request exception: %s, retrying...", exc)
                time.sleep(1)
                continue
            _set_last_llm_call_diagnostics(
                status="request_exception",
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                endpoint=endpoint,
                attempt=attempt,
                exception_type=type(exc).__name__,
                exception_message=str(exc)[:1000],
            )
            log.error("LLM request failed after %s attempts: %s", max_retries, exc)
            return None

    return None


def parse_llm_response(raw_response: Optional[str]) -> tuple[dict[str, Any] | None, Optional[str]]:
    if not raw_response:
        return None, raw_response
    text = raw_response.strip()

    # Many providers return JSON inside markdown fences.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n?```$", "", text).strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None, raw_response
    except json.JSONDecodeError as exc:
        # Fallback: extract first JSON object region from mixed text responses.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                parsed = json.loads(candidate)
                return parsed if isinstance(parsed, dict) else None, raw_response
            except json.JSONDecodeError:
                pass

        log.error("Failed to parse LLM response as JSON: %s", exc)
        log.debug("Response was: %s", raw_response[:200])
        return None, raw_response
