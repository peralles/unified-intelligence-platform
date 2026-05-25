from __future__ import annotations

import json
import time
from typing import Any

from integrator.config import settings
from integrator.security.audit import log_tool_invocation
from integrator.security.policy import (
    ConfirmationRequiredError,
    ToolPolicyError,
    check_confirmation,
    filter_tool_metadata,
    is_tool_allowed,
    strip_confirm_arg,
)
from integrator.logging_setup import get_logger
from integrator.whatsapp.errors import WhatsAppApiError, WhatsAppNotConnectedError
from integrator.whatsapp.session import WhatsAppSession

_logger = get_logger("tools")

WHATSAPP_TOOL_NAMES = frozenset({
    "get_whatsapp_connection_status",
    "list_whatsapp_chats",
    "find_whatsapp_chats",
    "get_whatsapp_messages",
    "send_whatsapp_text",
    "mark_whatsapp_read",
})

_GOOGLE_TOOL_COUNT = 12


def _base_metadata() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_whatsapp_connection_status",
            "description": (
                "Estado da sessão WhatsApp (conectado, QR, desconectado). "
                "Pareamento inicial só via terminal: integrator whatsapp pair."
            ),
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_whatsapp_chats",
            "description": (
                "Lista chats recentes (id, nome, não lidas, prévia da última mensagem). "
                "Requer sessão pareada via integrator whatsapp pair."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de chats (padrão 30).",
                    },
                },
            },
        },
        {
            "name": "find_whatsapp_chats",
            "description": "Busca chats por nome ou trecho do id/número.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Texto para buscar em nome ou chat_id.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de resultados (padrão 20).",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_whatsapp_messages",
            "description": (
                "Mensagens recentes de um chat (texto truncado). "
                "Histórico depende de sync/eventos após conectar."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "JID do chat (ex: 5511999999999@s.whatsapp.net).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de mensagens (padrão 30).",
                    },
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "send_whatsapp_text",
            "description": (
                "Envia mensagem de texto. Use chat_id ou number (somente dígitos). "
                "Ação irreversível — requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Corpo da mensagem."},
                    "chat_id": {
                        "type": "string",
                        "description": "Destino por JID de chat.",
                    },
                    "number": {
                        "type": "string",
                        "description": "Destino por número (ex: 5511999999999).",
                    },
                },
                "required": ["text"],
            },
        },
        {
            "name": "mark_whatsapp_read",
            "description": "Marca mensagens recentes do chat como lidas.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do chat."},
                    "message_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs opcionais; padrão: últimas recebidas.",
                    },
                },
                "required": ["chat_id"],
            },
        },
    ]


_metadata_cache: list[dict[str, Any]] | None = None


def list_whatsapp_tool_metadata() -> list[dict[str, Any]]:
    global _metadata_cache
    if _metadata_cache is None:
        _metadata_cache = filter_tool_metadata(_base_metadata())
    return _metadata_cache


def _format_result(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _hash_chat_id(chat_id: str) -> str:
    if "@" in chat_id:
        user = chat_id.split("@", 1)[0]
        return f"...{user[-4:]}" if len(user) > 4 else user
    return chat_id[:8] + "..." if len(chat_id) > 8 else chat_id


def invoke_whatsapp_tool(name: str, arguments: dict[str, Any] | None) -> str:
    started = time.perf_counter()
    chat_hint: str | None = None

    def _finish(
        *,
        success: bool,
        error_kind: str | None = None,
        blocked: bool = False,
    ) -> None:
        log_tool_invocation(
            name,
            success=success,
            duration_ms=(time.perf_counter() - started) * 1000,
            error_kind=error_kind,
            blocked=blocked,
            account_id=chat_hint,
        )

    if not settings.whatsapp_enabled:
        _finish(success=False, error_kind="whatsapp_disabled", blocked=True)
        raise ToolPolicyError(
            "[integrator] WhatsApp desabilitado (INTEGRATOR_WHATSAPP_ENABLED=false)."
        )

    if not is_tool_allowed(name):
        _finish(success=False, error_kind="tool_policy", blocked=True)
        raise ToolPolicyError(f"Tool '{name}' não permitida pela política do integrador.")

    try:
        check_confirmation(name, arguments)
    except ConfirmationRequiredError:
        _finish(success=False, error_kind="confirmation_required", blocked=True)
        raise

    args = strip_confirm_arg(arguments)
    session = WhatsAppSession.get()

    try:
        if name == "get_whatsapp_connection_status":
            result = session.status()
        elif name == "list_whatsapp_chats":
            result = session.list_chats(limit=int(args.get("limit", 30)))
        elif name == "find_whatsapp_chats":
            query = str(args.get("query", "")).strip()
            if not query:
                raise ToolPolicyError("[integrator] Parâmetro 'query' é obrigatório.")
            result = session.find_chats(
                query=query,
                limit=int(args.get("limit", 20)),
            )
        elif name == "get_whatsapp_messages":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.get_messages(
                chat_id=chat_id,
                limit=int(args.get("limit", 30)),
            )
        elif name == "send_whatsapp_text":
            text = str(args.get("text", "")).strip()
            if not text:
                raise ToolPolicyError("[integrator] Parâmetro 'text' é obrigatório.")
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para enviar mensagem."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            elif number:
                digits = "".join(c for c in str(number) if c.isdigit())
                chat_hint = f"...{digits[-4:]}" if len(digits) > 4 else digits
            result = session.send_text(
                text=text,
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
            )
        elif name == "mark_whatsapp_read":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            ids = args.get("message_ids")
            message_ids = (
                [str(i) for i in ids]
                if isinstance(ids, list)
                else None
            )
            result = session.mark_read(chat_id=chat_id, message_ids=message_ids)
        else:
            _finish(success=False, error_kind="unknown_tool")
            raise KeyError(f"Tool WhatsApp desconhecida: {name}")
    except WhatsAppNotConnectedError:
        _finish(success=False, error_kind="whatsapp_not_connected")
        raise
    except WhatsAppApiError as exc:
        _finish(success=False, error_kind="whatsapp_api")
        raise ToolPolicyError(str(exc)) from exc
    except ToolPolicyError:
        _finish(success=False, error_kind="tool_policy", blocked=True)
        raise
    except Exception as exc:
        _logger.exception("whatsapp tool FAIL | %s", name)
        _finish(success=False, error_kind="execution")
        raise ToolPolicyError(f"[integrator] Erro ao executar '{name}': {exc}") from exc

    _finish(success=True)
    return _format_result(result)
