from __future__ import annotations

from typing import Any

from integrator.config import settings

# Fase 2: confirmação explícita para ações destrutivas
DEFAULT_CONFIRM_REQUIRED = frozenset({"send_gmail_message", "delete_calendar_event"})


class ToolPolicyError(Exception):
    """Tool bloqueada por política (allowlist/denylist)."""


class ConfirmationRequiredError(Exception):
    """Ação destrutiva sem confirm=true."""


def _parse_tool_list(value: str | None) -> set[str] | None:
    if value is None or not str(value).strip():
        return None
    return {t.strip() for t in str(value).split(",") if t.strip()}


def get_confirm_required_tools() -> frozenset[str]:
    custom = _parse_tool_list(settings.confirm_required_tools)
    if custom is not None:
        return frozenset(custom)
    return DEFAULT_CONFIRM_REQUIRED


def is_tool_allowed(name: str) -> bool:
    allowlist = _parse_tool_list(settings.tool_allowlist)
    denylist = _parse_tool_list(settings.tool_denylist) or set()

    if allowlist is not None:
        return name in allowlist
    return name not in denylist


def filter_tool_metadata(metadata: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_tool_schema(m) for m in metadata if is_tool_allowed(m["name"])]


def enrich_tool_schema(meta: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(meta)
    schema = dict(enriched.get("input_schema") or {"type": "object", "properties": {}})
    properties = dict(schema.get("properties") or {})

    if meta["name"] in get_confirm_required_tools():
        properties["confirm"] = {
            "type": "boolean",
            "description": (
                "Obrigatório: deve ser true para executar esta ação destrutiva/irreversível."
            ),
        }
        schema["properties"] = properties
        enriched["input_schema"] = schema
        enriched["description"] = (
            (enriched.get("description") or "")
            + " [Requer confirm=true para executar.]"
        ).strip()

    return enriched


def check_confirmation(name: str, arguments: dict[str, Any] | None) -> None:
    if name not in get_confirm_required_tools():
        return
    args = arguments or {}
    if args.get("confirm") is True:
        return
    raise ConfirmationRequiredError(
        f"A tool '{name}' exige confirmação explícita. "
        "Inclua \"confirm\": true nos argumentos após validar com o usuário."
    )


def strip_confirm_arg(arguments: dict[str, Any] | None) -> dict[str, Any]:
    if not arguments:
        return {}
    return {k: v for k, v in arguments.items() if k != "confirm"}
