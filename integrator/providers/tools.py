from __future__ import annotations

from typing import Any

from integrator.config import settings
from integrator.providers.google_tools import (
    invoke_google_tool,
    list_google_tool_metadata,
)
from integrator.providers.whatsapp_tools import (
    WHATSAPP_TOOL_NAMES,
    invoke_whatsapp_tool,
    list_whatsapp_tool_metadata,
)

GOOGLE_TOOL_COUNT = 12
WHATSAPP_TOOL_COUNT = len(WHATSAPP_TOOL_NAMES)
TOTAL_TOOL_COUNT = GOOGLE_TOOL_COUNT + WHATSAPP_TOOL_COUNT


def list_all_tool_metadata() -> list[dict[str, Any]]:
    tools = list_google_tool_metadata()
    if settings.whatsapp_enabled:
        tools = [*tools, *list_whatsapp_tool_metadata()]
    return tools


def invoke_tool(name: str, arguments: dict[str, Any] | None) -> str:
    if name in WHATSAPP_TOOL_NAMES or name.startswith("whatsapp_"):
        return invoke_whatsapp_tool(name, arguments)
    return invoke_google_tool(name, arguments)
