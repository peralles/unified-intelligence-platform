from __future__ import annotations

from typing import Any

from mcp import types


def metadata_to_mcp_tool(meta: dict[str, Any]) -> types.Tool:
    return types.Tool(
        name=meta["name"],
        description=meta["description"],
        inputSchema=meta["input_schema"],
    )
