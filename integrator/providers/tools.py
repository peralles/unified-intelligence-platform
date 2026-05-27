from __future__ import annotations

from typing import Any

from integrator.auth.google_oauth import GoogleAuthError
from integrator.config import settings
from integrator.providers.google_gmail_extra import (
    GMAIL_EXTRA_TOOL_NAMES,
    invoke_gmail_extra_tool,
    list_gmail_extra_tool_metadata,
)
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
GMAIL_EXTRA_TOOL_COUNT = len(GMAIL_EXTRA_TOOL_NAMES)
WHATSAPP_TOOL_COUNT = len(WHATSAPP_TOOL_NAMES)
TOTAL_TOOL_COUNT = GOOGLE_TOOL_COUNT + GMAIL_EXTRA_TOOL_COUNT + WHATSAPP_TOOL_COUNT


def list_all_tool_metadata() -> list[dict[str, Any]]:
    from integrator.security.policy import filter_tool_metadata

    tools = [
        *list_google_tool_metadata(),
        *filter_tool_metadata(list_gmail_extra_tool_metadata()),
    ]
    if settings.whatsapp_enabled:
        tools = [*tools, *list_whatsapp_tool_metadata()]
    return tools


def is_whatsapp_tool(name: str) -> bool:
    return name in WHATSAPP_TOOL_NAMES


def _invoke_gmail_extra_tool(name: str, arguments: dict[str, Any] | None) -> str:
    import json

    from integrator.accounts.registry import resolve_account_id
    from integrator.providers.google_tools import strip_control_args
    from integrator.security.policy import (
        ToolPolicyError,
        check_confirmation,
        is_tool_allowed,
    )

    if not is_tool_allowed(name):
        raise ToolPolicyError(f"Tool '{name}' não permitida pela política.")
    check_confirmation(name, arguments)
    args, explicit_account = strip_control_args(arguments)
    account_id = resolve_account_id(explicit_account)
    try:
        result = invoke_gmail_extra_tool(name, account_id, args)
    except GoogleAuthError as exc:
        raise ToolPolicyError(f"[integrator] Autenticação necessária: {exc}") from exc
    return json.dumps(result, ensure_ascii=False, default=str)


def invoke_tool(name: str, arguments: dict[str, Any] | None) -> str:
    if is_whatsapp_tool(name):
        return invoke_whatsapp_tool(name, arguments)
    if name in GMAIL_EXTRA_TOOL_NAMES:
        return _invoke_gmail_extra_tool(name, arguments)
    return invoke_google_tool(name, arguments)
