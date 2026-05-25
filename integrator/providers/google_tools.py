from __future__ import annotations

import time
from typing import Any, Type

from langchain_core.tools import BaseTool
from langchain_google_community import CalendarToolkit, GmailToolkit
from langchain_google_community.calendar.utils import build_calendar_service
from langchain_google_community.gmail.utils import build_gmail_service

from integrator.auth.google_oauth import GoogleAuthError, load_google_credentials
from integrator.security.policy import (
    ConfirmationRequiredError,
    ToolPolicyError,
    check_confirmation,
    filter_tool_metadata,
    is_tool_allowed,
    strip_confirm_arg,
)
from integrator.security.audit import log_tool_invocation

# Todas as tools (decisão: expor todas)
GMAIL_TOOL_CLASSES: list[Type[BaseTool]] = []
CALENDAR_TOOL_CLASSES: list[Type[BaseTool]] = []


def _import_tool_classes() -> None:
    global GMAIL_TOOL_CLASSES, CALENDAR_TOOL_CLASSES
    if GMAIL_TOOL_CLASSES:
        return

    from langchain_google_community.calendar.create_event import CalendarCreateEvent
    from langchain_google_community.calendar.current_datetime import GetCurrentDatetime
    from langchain_google_community.calendar.delete_event import CalendarDeleteEvent
    from langchain_google_community.calendar.get_calendars_info import GetCalendarsInfo
    from langchain_google_community.calendar.move_event import CalendarMoveEvent
    from langchain_google_community.calendar.search_events import CalendarSearchEvents
    from langchain_google_community.calendar.update_event import CalendarUpdateEvent
    from langchain_google_community.gmail.create_draft import GmailCreateDraft
    from langchain_google_community.gmail.get_message import GmailGetMessage
    from langchain_google_community.gmail.get_thread import GmailGetThread
    from langchain_google_community.gmail.search import GmailSearch
    from langchain_google_community.gmail.send_message import GmailSendMessage

    GMAIL_TOOL_CLASSES = [
        GmailCreateDraft,
        GmailSendMessage,
        GmailSearch,
        GmailGetMessage,
        GmailGetThread,
    ]
    CALENDAR_TOOL_CLASSES = [
        CalendarCreateEvent,
        CalendarSearchEvents,
        CalendarUpdateEvent,
        GetCalendarsInfo,
        CalendarMoveEvent,
        CalendarDeleteEvent,
        GetCurrentDatetime,
    ]


def tool_metadata_from_class(tool_cls: Type[BaseTool]) -> dict[str, Any]:
    """Metadados MCP sem instanciar api_resource Google."""
    _import_tool_classes()
    name_field = tool_cls.model_fields.get("name")
    desc_field = tool_cls.model_fields.get("description")
    args_field = tool_cls.model_fields.get("args_schema")

    name = name_field.default if name_field else tool_cls.__name__
    description = desc_field.default if desc_field else ""
    schema_cls = args_field.default if args_field else None

    if schema_cls is not None:
        input_schema = schema_cls.model_json_schema()
        if input_schema.get("type") == "object" and "properties" not in input_schema:
            input_schema["properties"] = {}
    else:
        input_schema = {"type": "object", "properties": {}}

    for key in ("title", "$defs"):
        input_schema.pop(key, None)

    return {
        "name": name,
        "description": description or "",
        "input_schema": input_schema,
    }


def list_all_tool_metadata() -> list[dict[str, Any]]:
    _import_tool_classes()
    raw = [
        *[tool_metadata_from_class(c) for c in GMAIL_TOOL_CLASSES],
        *[tool_metadata_from_class(c) for c in CALENDAR_TOOL_CLASSES],
    ]
    return filter_tool_metadata(raw)


def build_live_tools() -> dict[str, BaseTool]:
    """Instancia todas as tools LangChain com credenciais válidas."""
    credentials = load_google_credentials(interactive=False)
    gmail_resource = build_gmail_service(credentials=credentials)
    calendar_resource = build_calendar_service(credentials=credentials)

    gmail_toolkit = GmailToolkit(api_resource=gmail_resource)
    calendar_toolkit = CalendarToolkit(api_resource=calendar_resource)

    tools: dict[str, BaseTool] = {}
    for tool in gmail_toolkit.get_tools() + calendar_toolkit.get_tools():
        tools[tool.name] = tool
    return tools


def invoke_tool(name: str, arguments: dict[str, Any] | None) -> str:
    started = time.perf_counter()

    def _finish(*, success: bool, error_kind: str | None = None, blocked: bool = False) -> None:
        log_tool_invocation(
            name,
            success=success,
            duration_ms=(time.perf_counter() - started) * 1000,
            error_kind=error_kind,
            blocked=blocked,
        )

    if not is_tool_allowed(name):
        _finish(success=False, error_kind="tool_policy", blocked=True)
        raise ToolPolicyError(
            f"Tool '{name}' não permitida pela política do integrador. "
            "Ajuste INTEGRATOR_TOOL_ALLOWLIST ou INTEGRATOR_TOOL_DENYLIST."
        )

    try:
        check_confirmation(name, arguments)
    except ConfirmationRequiredError:
        _finish(success=False, error_kind="confirmation_required", blocked=True)
        raise

    try:
        registry = build_live_tools()
    except GoogleAuthError:
        _finish(success=False, error_kind="auth")
        raise

    tool = registry.get(name)
    if tool is None:
        _finish(success=False, error_kind="unknown_tool")
        raise KeyError(f"Tool desconhecida: {name}")

    args = strip_confirm_arg(arguments)
    try:
        result = tool.invoke(args)
    except Exception:
        _finish(success=False, error_kind="execution")
        raise

    _finish(success=True)
    if isinstance(result, str):
        return result
    import json

    return json.dumps(result, default=str, ensure_ascii=False)
