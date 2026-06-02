from __future__ import annotations

import copy
import time
from typing import Any, Type

from langchain_core.tools import BaseTool
from langchain_google_community import CalendarToolkit, GmailToolkit
from langchain_google_community.calendar.utils import build_calendar_service
from langchain_google_community.gmail.utils import build_gmail_service

from integrator.accounts.registry import AccountNotFoundError, resolve_account_id
from integrator.auth.google_oauth import GoogleAuthError, load_google_credentials
from integrator.security.policy import (
    ConfirmationRequiredError,
    ToolPolicyError,
    check_confirmation,
    filter_tool_metadata,
    is_tool_allowed,
    strip_control_args,
)
from integrator.security.audit import log_tool_invocation
from integrator.providers.tool_cache import (
    get_cached_live_tools,
    set_cached_live_tools,
)

# Todas as tools (decisão: expor todas)
GMAIL_TOOL_CLASSES: list[Type[BaseTool]] = []
CALENDAR_TOOL_CLASSES: list[Type[BaseTool]] = []

_metadata_cache_key_stored: tuple[Any, ...] | None = None
_metadata_cache_value: list[dict[str, Any]] | None = None


def _compute_metadata_cache_key() -> tuple[Any, ...]:
    from integrator.accounts.registry import list_account_ids
    from integrator.config import settings

    return (
        frozenset(list_account_ids()),
        settings.tool_allowlist,
        settings.tool_denylist,
        settings.confirm_required_tools,
    )


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


def _resolve_json_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Inline $ref apontando para #/$defs/* antes de expor o schema ao MCP/Hermes.

    LangChain/Pydantic costuma emitir $ref em propriedades e $defs no topo;
    remover só $defs quebra validadores (PointerToNowhere).
    """
    defs = schema.get("$defs") or {}

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                key = ref[len("#/$defs/") :]
                if key in defs:
                    target = copy.deepcopy(defs[key])
                    siblings = {k: v for k, v in node.items() if k != "$ref"}
                    if siblings:
                        if isinstance(target, dict):
                            merged = {**target, **siblings}
                        else:
                            merged = siblings
                        return resolve(merged)
                    return resolve(target)
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    resolved = resolve({k: v for k, v in schema.items() if k != "$defs"})
    if isinstance(resolved, dict):
        resolved.pop("$defs", None)
        resolved.pop("title", None)
        if resolved.get("type") == "object" and "properties" not in resolved:
            resolved["properties"] = {}
        return resolved
    return {"type": "object", "properties": {}}


def _schema_contains_ref(node: Any) -> bool:
    if isinstance(node, dict):
        if "$ref" in node:
            return True
        return any(_schema_contains_ref(v) for v in node.values())
    if isinstance(node, list):
        return any(_schema_contains_ref(item) for item in node)
    return False


def prepare_mcp_input_schema(raw_schema: dict[str, Any]) -> dict[str, Any]:
    """Schema JSON pronto para MCP (sem $defs órfãos nem $ref internos)."""
    return _resolve_json_schema_refs(raw_schema)


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
        input_schema = prepare_mcp_input_schema(schema_cls.model_json_schema())
    else:
        input_schema = {"type": "object", "properties": {}}

    return {
        "name": name,
        "description": description or "",
        "input_schema": input_schema,
    }


def invalidate_metadata_cache() -> None:
    global _metadata_cache_key_stored, _metadata_cache_value
    _metadata_cache_key_stored = None
    _metadata_cache_value = None


def list_google_tool_metadata() -> list[dict[str, Any]]:
    global _metadata_cache_key_stored, _metadata_cache_value
    cache_key = _compute_metadata_cache_key()
    if _metadata_cache_value is not None and _metadata_cache_key_stored == cache_key:
        return _metadata_cache_value

    _import_tool_classes()
    raw = [
        *[tool_metadata_from_class(c) for c in GMAIL_TOOL_CLASSES],
        *[tool_metadata_from_class(c) for c in CALENDAR_TOOL_CLASSES],
    ]
    result = filter_tool_metadata(raw)
    _metadata_cache_key_stored = cache_key
    _metadata_cache_value = result
    return result


def build_live_tools(account_id: str) -> dict[str, BaseTool]:
    """Instancia Gmail + Calendar LangChain para a conta Google indicada."""
    cached = get_cached_live_tools(account_id)
    if cached is not None:
        return cached

    credentials = load_google_credentials(account_id=account_id, interactive=False)
    gmail_resource = build_gmail_service(credentials=credentials)
    calendar_resource = build_calendar_service(credentials=credentials)

    gmail_toolkit = GmailToolkit(api_resource=gmail_resource)
    calendar_toolkit = CalendarToolkit(api_resource=calendar_resource)

    tools: dict[str, BaseTool] = {}
    for tool in gmail_toolkit.get_tools() + calendar_toolkit.get_tools():
        tools[tool.name] = tool
    set_cached_live_tools(account_id, tools)
    return tools


def invoke_google_tool(name: str, arguments: dict[str, Any] | None) -> str:
    started = time.perf_counter()
    account_id: str | None = None

    def _finish(*, success: bool, error_kind: str | None = None, blocked: bool = False) -> None:
        log_tool_invocation(
            name,
            success=success,
            duration_ms=(time.perf_counter() - started) * 1000,
            error_kind=error_kind,
            blocked=blocked,
            account_id=account_id,
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
        lc_args, explicit_account = strip_control_args(arguments)
        account_id = resolve_account_id(explicit_account)
    except AccountNotFoundError as exc:
        _finish(success=False, error_kind="account", blocked=True)
        raise ToolPolicyError(str(exc)) from exc

    try:
        registry = build_live_tools(account_id)
    except GoogleAuthError:
        _finish(success=False, error_kind="auth")
        from integrator.providers.tool_cache import invalidate_live_tools
        invalidate_live_tools(account_id)
        raise

    tool = registry.get(name)
    if tool is None:
        _finish(success=False, error_kind="unknown_tool")
        raise KeyError(f"Tool desconhecida: {name}")

    args = lc_args
    try:
        result = tool.invoke(args)
    except Exception:
        _finish(success=False, error_kind="execution")
        from integrator.logging_setup import get_logger

        get_logger("tools").exception(
            "execução falhou | tool=%s | account=%s",
            name,
            account_id,
        )
        raise

    _finish(success=True)
    if isinstance(result, str):
        return result
    import json

    return json.dumps(result, default=str, ensure_ascii=False)


# Aliases usados por testes que exercitam só o provider Google.
list_all_tool_metadata = list_google_tool_metadata
invoke_tool = invoke_google_tool
