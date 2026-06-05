"""YAML serialization helpers."""

from __future__ import annotations

from typing import Any


def to_yaml(data: Any) -> str:
    """Serialize data to YAML.

    PyYAML is preferred. A compact fallback is kept so tests for non-LLM pieces
    can still run in minimal environments.
    """

    try:
        import yaml

        return yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
    except ImportError:
        return _fallback_yaml(data)


def _fallback_yaml(value: Any, depth: int = 0) -> str:
    indent = "  " * depth
    if isinstance(value, dict):
        if not value:
            return f"{indent}{{}}"
        lines = []
        for key, item in value.items():
            if _is_scalar(item):
                lines.append(f"{indent}{key}: {_format_scalar(item)}")
            else:
                lines.append(f"{indent}{key}:")
                lines.append(_fallback_yaml(item, depth + 1))
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{indent}[]"
        lines = []
        for item in value:
            if _is_scalar(item):
                lines.append(f"{indent}- {_format_scalar(item)}")
            else:
                lines.append(f"{indent}-")
                lines.append(_fallback_yaml(item, depth + 1))
        return "\n".join(lines)
    return f"{indent}{_format_scalar(value)}"


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{text}"'
