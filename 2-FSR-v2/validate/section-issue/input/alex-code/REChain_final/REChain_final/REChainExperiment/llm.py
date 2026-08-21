"""LLM client: call LiteLLM gateway and parse the risk-rating JSON response."""

from __future__ import annotations

import json
import requests
import urllib3
from typing import Any, Dict, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .config import LITELLM_HOST, LITELLM_TOKEN, LLM_MODEL_NAME, require_setting
from .retry import RETRIABLE_STATUS_CODES, retry_request

# Re-export prompt builder so chain.py import stays unchanged
from .prompting import build_user_prompt  # noqa: F401


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.1,
    verify_ssl: bool | str = False,
) -> Optional[str]:
    """Send system + user prompt to LiteLLM and return raw response text."""
    api_key = require_setting(
        LITELLM_TOKEN,
        name="LiteLLM API key",
        env_names=("LITELLM_API_KEY",),
        file_names=("litellm_token.txt",),
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = retry_request(
            lambda: requests.post(
                LITELLM_HOST + "/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=300,
                verify=verify_ssl,
            ),
            label="LLM",
            retriable_status_codes=RETRIABLE_STATUS_CODES,
        )
    except Exception:
        return None

    if resp.status_code == 200:
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            print(f"[LLM] Unexpected response structure: {str(data)[:500]}")
            return None

    print(f"[LLM] API Error {resp.status_code}: {resp.text[:200]}")
    return None


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Try multiple strategies to extract valid JSON from text."""
    cleaned = text.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: unwrap wrapper object like {"{}": "...actual json..."}
    if cleaned.startswith('{"{}"'):
        try:
            wrapper = json.loads(cleaned)
            if "{}" in wrapper:
                return _extract_json(wrapper["{}"])
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: extract from markdown code fences
    if "```" in cleaned:
        for part in cleaned.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                try:
                    return json.loads(part)
                except (json.JSONDecodeError, ValueError):
                    continue

    # Strategy 4: find first { to last } substring
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def parse_llm_response(raw_response: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from LLM response, handling various malformed formats."""
    if not raw_response:
        return None
    result = _extract_json(raw_response)
    if result is None:
        print(f"[LLM] Could not parse JSON from response")
        print(f"[LLM] Raw response:\n{raw_response[:500]}")
        return None
    if isinstance(result, list):
        result = {"findings": result, "summary": ""}
    return result
