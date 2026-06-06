from __future__ import annotations

from typing import Any

from integrator.accounts.registry import list_account_ids
from integrator.config import settings

# Fase 2: confirmação explícita para ações destrutivas
DEFAULT_CONFIRM_REQUIRED = frozenset({
    "send_gmail_message",
    "reply_gmail_message",
    "modify_gmail_labels",
    "delete_calendar_event",
    "send_whatsapp_text",
    "delete_whatsapp_messages",
    "delete_whatsapp_messages_for_me",
    "whatsapp_reply_text",
    "send_whatsapp_image",
    "send_whatsapp_document",
    "send_whatsapp_audio",
    "forward_whatsapp_message",
    "send_whatsapp_video",
    "send_whatsapp_sticker",
    "send_whatsapp_contact",
    "trash_gmail_message",
    "send_whatsapp_poll",
    "send_whatsapp_album",
    "update_whatsapp_blocklist",
    "leave_whatsapp_group",
    "restore_gmail_message",
    "vote_whatsapp_poll",
    "join_whatsapp_group_link",
    "send_gmail_draft",
    "batch_modify_gmail_labels",
    "create_google_contact",
    "update_google_contact",
    "delete_google_contact",
    "leave_whatsapp_group_and_purge",
    "edit_whatsapp_text",
    "whatsapp_react_message",
    # LinkedIn — publicações e reações são ações públicas e irreversíveis
    "share_linkedin_post",
    "share_linkedin_article",
    "delete_linkedin_post",
    "comment_linkedin_post",
    "like_linkedin_post",
    "unlike_linkedin_post",
})


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


def _enrich_account_property(properties: dict[str, Any]) -> None:
    account_ids = list_account_ids()
    if not account_ids:
        return
    default_hint = account_ids[0] if len(account_ids) == 1 else "padrão do integrador"
    prop: dict[str, Any] = {
        "type": "string",
        "description": (
            f"Conta Google (Gmail, Calendar, Contacts). IDs: {', '.join(account_ids)}. "
            f"Padrão: {default_hint}."
        ),
    }
    if len(account_ids) > 1:
        prop["enum"] = account_ids
    properties["account"] = prop


def enrich_tool_schema(meta: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(meta)
    schema = dict(enriched.get("input_schema") or {"type": "object", "properties": {}})
    properties = dict(schema.get("properties") or {})

    _enrich_account_property(properties)
    schema["properties"] = properties

    if meta["name"] in get_confirm_required_tools():
        properties["confirm"] = {
            "type": "boolean",
            "description": (
                "Obrigatório: deve ser true para executar esta ação destrutiva/irreversível."
            ),
        }
        schema["properties"] = properties
        enriched["description"] = (
            (enriched.get("description") or "")
            + " [Requer confirm=true para executar.]"
        ).strip()

    enriched["input_schema"] = schema
    return enriched


def _require_confirm(name: str, arguments: dict[str, Any] | None) -> None:
    args = arguments or {}
    if args.get("confirm") is True:
        return
    raise ConfirmationRequiredError(
        f"A tool '{name}' exige confirmação explícita. "
        "Inclua \"confirm\": true nos argumentos após validar com o usuário."
    )


def check_confirmation(name: str, arguments: dict[str, Any] | None) -> None:
    args = arguments or {}
    if name == "transcribe_whatsapp_audio" and args.get("reply") is True:
        _require_confirm(name, arguments)
        return
    if name == "get_whatsapp_group_invite_link" and args.get("revoke") is True:
        _require_confirm(name, arguments)
        return
    if name not in get_confirm_required_tools():
        return
    _require_confirm(name, arguments)


def strip_control_args(arguments: dict[str, Any] | None) -> tuple[dict[str, Any], str | None]:
    """Remove campos de controle MCP; retorna (args_limpos, account_id explícito)."""
    if not arguments:
        return {}, None
    account = arguments.get("account")
    account_str = str(account).strip() if account is not None else None
    cleaned = {k: v for k, v in arguments.items() if k not in ("confirm", "account")}
    return cleaned, account_str or None


def strip_confirm_arg(arguments: dict[str, Any] | None) -> dict[str, Any]:
    args, _ = strip_control_args(arguments)
    return args


def _enrich_linkedin_account_property(properties: dict[str, Any]) -> None:
    """Add LinkedIn-specific account selector (separate from Google accounts)."""
    from integrator.auth.linkedin_oauth import list_linkedin_accounts
    accounts = list_linkedin_accounts()
    ids = [a["id"] for a in accounts]
    if not ids:
        return
    default_hint = ids[0] if len(ids) == 1 else "default"
    prop: dict[str, Any] = {
        "type": "string",
        "description": (
            f"Conta LinkedIn. IDs disponíveis: {', '.join(ids)}. "
            f"Padrão: {default_hint}."
        ),
    }
    if len(ids) > 1:
        prop["enum"] = ids
    properties["account"] = prop


def enrich_linkedin_tool_schema(meta: dict[str, Any]) -> dict[str, Any]:
    """Like enrich_tool_schema but with LinkedIn-specific account field."""
    if not is_tool_allowed(meta["name"]):
        return meta
    enriched = dict(meta)
    schema = dict(enriched.get("input_schema") or {"type": "object", "properties": {}})
    properties = dict(schema.get("properties") or {})

    _enrich_linkedin_account_property(properties)
    schema["properties"] = properties

    if meta["name"] in get_confirm_required_tools():
        properties["confirm"] = {
            "type": "boolean",
            "description": (
                "Obrigatório: deve ser true para executar esta ação destrutiva/irreversível."
            ),
        }
        schema["properties"] = properties
        enriched["description"] = (
            (enriched.get("description") or "")
            + " [Requer confirm=true para executar.]"
        ).strip()

    enriched["input_schema"] = schema
    return enriched
