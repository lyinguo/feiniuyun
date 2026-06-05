"""Local tool registry used by the adaptation service."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from app.tools.base import LocalTool
from app.tools.schema_tool import YamlSchemaTool
from app.tools.text_stats_tool import TextStatsTool


class ToolRegistry:
    def __init__(self, tools: Iterable[LocalTool]):
        self.tools = list(tools)

    def build_context(self, text: str) -> Dict[str, Any]:
        context: Dict[str, Any] = {}
        errors: List[Dict[str, str]] = []

        for tool in self.tools:
            try:
                context[tool.name] = tool.run(text)
            except Exception as exc:
                errors.append({"tool": tool.name, "error": str(exc)})

        if errors:
            context["tool_errors"] = errors
        return context


default_tool_registry = ToolRegistry([YamlSchemaTool(), TextStatsTool()])
