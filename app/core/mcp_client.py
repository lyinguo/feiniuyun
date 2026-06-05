"""Optional MCP tool loading.

The project does not require MCP to run. When ENABLE_MCP_TOOLS=true and the
langchain MCP adapter is installed, this module can load external tools and
return a short availability report for prompts or diagnostics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.config import settings


async def load_mcp_tool_metadata() -> Dict[str, Any]:
    if not settings.enable_mcp_tools:
        return {"enabled": False, "tools": [], "error": None}

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as exc:  # pragma: no cover - optional dependency
        return {
            "enabled": True,
            "tools": [],
            "error": f"langchain_mcp_adapters is not installed: {exc}",
        }

    if not settings.mcp_config_path:
        return {"enabled": True, "tools": [], "error": "MCP_CONFIG_PATH is not set."}

    # Keep this conservative: external tool execution belongs in a separate
    # extension flow. For this project we only report tool metadata.
    try:
        config_path = Path(settings.mcp_config_path)
        servers = json.loads(config_path.read_text(encoding="utf-8"))
        client = MultiServerMCPClient(servers)  # type: ignore[arg-type]
        tools = await client.get_tools()
        metadata: List[Dict[str, str]] = []
        for tool in tools:
            metadata.append(
                {
                    "name": getattr(tool, "name", "unknown"),
                    "description": getattr(tool, "description", ""),
                }
            )
        return {"enabled": True, "tools": metadata, "error": None}
    except Exception as exc:  # pragma: no cover - optional integration
        return {"enabled": True, "tools": [], "error": str(exc)}
