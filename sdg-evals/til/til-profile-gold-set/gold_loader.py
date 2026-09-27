from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def normalize_til_id(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().upper()
    s = re.sub(r"^TIL\s+", "", s)
    return re.sub(r"\s+", "", s)


def _resolve_data_root(gold_root: Path) -> Path:
    if (gold_root / "data").exists():
        return gold_root / "data"
    return gold_root


def load_gold_profiles(gold_root: Path, tils: list[str]) -> dict[str, dict[str, Any]]:
    """Load DS/SME-reviewed gold profiles.

    Expected structure:
    - <gold_root>/data/<til_id>/profile_response.json
    - or <gold_root>/<til_id>/profile_response.json
    """
    out: dict[str, dict[str, Any]] = {}
    wanted = {normalize_til_id(t) for t in tils}

    if not gold_root.exists():
        return out

    data_root = _resolve_data_root(gold_root)

    for til in wanted:
        candidate = data_root / til / "profile_response.json"
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue

        parsed = payload.get("parsed_profile") if isinstance(payload, dict) else None
        if isinstance(parsed, dict):
            out[til] = parsed

    return out
