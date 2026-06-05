"""Parsing helpers for model output."""

from __future__ import annotations

import json
import re
from typing import Any, Dict


def parse_json_object(content: str) -> Dict[str, Any]:
    """Parse a JSON object from raw model text.

    The prompt requires JSON, but real models sometimes wrap it in Markdown
    fences. This function accepts that wrapper while still rejecting non-object
    output.
    """

    text = (content or "").strip()
    if not text:
        raise ValueError("empty model output")

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("model output must be a JSON object")
    return data


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def ensure_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()
