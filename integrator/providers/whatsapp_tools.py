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
    "delete_whatsapp_messages",
    "delete_whatsapp_messages_for_me",
    "sync_whatsapp_chat_history",
    "whatsapp_reply_text",
    "whatsapp_react_message",
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
            "description": (
                "Busca chats por nome ou trecho do id/número. "
                "Sem query, equivale a list_whatsapp_chats (útil para filtrar chats vazios "
                "pela prévia da última mensagem)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Texto para buscar em nome ou chat_id. "
                            "Opcional: omitir lista os chats recentes."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de resultados (padrão 20).",
                    },
                },
            },
        },
        {
            "name": "get_whatsapp_messages",
            "description": (
                "Mensagens de um chat em cache (texto truncado). "
                "Use sync_whatsapp_chat_history para puxar mensagens mais antigas. "
                "Filtros before_timestamp/after_timestamp (Unix segundos) para limpeza em lote."
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
                    "before_timestamp": {
                        "type": "integer",
                        "description": "Só mensagens anteriores a este Unix timestamp.",
                    },
                    "after_timestamp": {
                        "type": "integer",
                        "description": "Só mensagens posteriores a este Unix timestamp.",
                    },
                    "from_me": {
                        "type": "boolean",
                        "description": "true=só suas; false=só de outros.",
                    },
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "sync_whatsapp_chat_history",
            "description": (
                "Pede ao WhatsApp mensagens mais antigas do chat (preenche cache local). "
                "Requer ao menos uma mensagem já em cache; repita para ir mais atrás no tempo."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do chat."},
                    "count": {
                        "type": "integer",
                        "description": "Quantidade pedida ao servidor (padrão 50).",
                    },
                    "wait_s": {
                        "type": "number",
                        "description": "Segundos aguardando novas mensagens no cache (padrão 25).",
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
            "name": "whatsapp_reply_text",
            "description": (
                "Responde citando uma mensagem (message_id de get_whatsapp_messages). "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do chat."},
                    "reply_to_message_id": {
                        "type": "string",
                        "description": "ID da mensagem a citar.",
                    },
                    "text": {"type": "string", "description": "Texto da resposta."},
                },
                "required": ["chat_id", "reply_to_message_id", "text"],
            },
        },
        {
            "name": "whatsapp_react_message",
            "description": (
                "Reage a uma mensagem com emoji (ex: 👍). "
                "message_id deve estar em cache."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do chat."},
                    "message_id": {"type": "string", "description": "ID da mensagem."},
                    "emoji": {"type": "string", "description": "Emoji da reação."},
                },
                "required": ["chat_id", "message_id", "emoji"],
            },
        },
        {
            "name": "delete_whatsapp_messages_for_me",
            "description": (
                "Apaga mensagens só neste dispositivo (inclui mensagens de outras pessoas). "
                "Use message_ids de get_whatsapp_messages ou filtros before_timestamp para lote. "
                "Não apaga para os outros no WhatsApp deles. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do chat."},
                    "message_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs específicos (opcional se usar filtros de tempo).",
                    },
                    "before_timestamp": {
                        "type": "integer",
                        "description": (
                            "Apaga em cache todas com timestamp < este valor (Unix segundos)."
                        ),
                    },
                    "after_timestamp": {
                        "type": "integer",
                        "description": "Combinar com before_timestamp para faixa de datas.",
                    },
                    "from_me": {
                        "type": "boolean",
                        "description": "Limitar a suas mensagens ou só de terceiros.",
                    },
                    "delete_media": {
                        "type": "boolean",
                        "description": "Também remover mídia local associada.",
                    },
                    "entries": {
                        "type": "array",
                        "description": (
                            "Metadados explícitos se a mensagem não estiver em cache: "
                            "message_id, sender_id, from_me, timestamp."
                        ),
                        "items": {"type": "object"},
                    },
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "delete_whatsapp_messages",
            "description": (
                "Revoga para todos — só mensagens enviadas por você (não use para mensagens de terceiros; "
                "use delete_whatsapp_messages_for_me). Limite de tempo do WhatsApp pode aplicar. "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do chat."},
                    "message_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs das mensagens a apagar (suas).",
                    },
                },
                "required": ["chat_id", "message_ids"],
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
            query = str(
                args.get("query")
                or args.get("q")
                or args.get("search")
                or ""
            ).strip()
            limit = int(args.get("limit", 20))
            if not query:
                result = session.list_chats(limit=limit)
            else:
                result = session.find_chats(query=query, limit=limit)
        elif name == "get_whatsapp_messages":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            before_ts = args.get("before_timestamp")
            after_ts = args.get("after_timestamp")
            from_me_arg = args.get("from_me")
            result = session.get_messages(
                chat_id=chat_id,
                limit=int(args.get("limit", 30)),
                before_timestamp=int(before_ts) if before_ts is not None else None,
                after_timestamp=int(after_ts) if after_ts is not None else None,
                from_me=bool(from_me_arg) if from_me_arg is not None else None,
            )
        elif name == "sync_whatsapp_chat_history":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.request_chat_history(
                chat_id=chat_id,
                count=int(args.get("count", 50)),
                wait_s=float(args.get("wait_s", 25)),
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
        elif name == "whatsapp_reply_text":
            chat_id = str(args.get("chat_id", "")).strip()
            reply_id = str(args.get("reply_to_message_id", "")).strip()
            text = str(args.get("text", "")).strip()
            if not chat_id or not reply_id or not text:
                raise ToolPolicyError(
                    "[integrator] chat_id, reply_to_message_id e text são obrigatórios."
                )
            chat_hint = _hash_chat_id(chat_id)
            result = session.reply_text(
                chat_id=chat_id,
                reply_to_message_id=reply_id,
                text=text,
            )
        elif name == "whatsapp_react_message":
            chat_id = str(args.get("chat_id", "")).strip()
            message_id = str(args.get("message_id", "")).strip()
            emoji = str(args.get("emoji", "")).strip()
            if not chat_id or not message_id or not emoji:
                raise ToolPolicyError(
                    "[integrator] chat_id, message_id e emoji são obrigatórios."
                )
            chat_hint = _hash_chat_id(chat_id)
            result = session.react_message(
                chat_id=chat_id,
                message_id=message_id,
                emoji=emoji,
            )
        elif name == "delete_whatsapp_messages":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            raw_ids = args.get("message_ids")
            if not isinstance(raw_ids, list) or not raw_ids:
                raise ToolPolicyError(
                    "[integrator] Parâmetro 'message_ids' (lista não vazia) é obrigatório."
                )
            message_ids = [str(i).strip() for i in raw_ids if str(i).strip()]
            if not message_ids:
                raise ToolPolicyError(
                    "[integrator] Parâmetro 'message_ids' (lista não vazia) é obrigatório."
                )
            result = session.delete_messages(
                chat_id=chat_id,
                message_ids=message_ids,
            )
        elif name == "delete_whatsapp_messages_for_me":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            raw_ids = args.get("message_ids")
            message_ids = None
            if isinstance(raw_ids, list) and raw_ids:
                message_ids = [str(i).strip() for i in raw_ids if str(i).strip()]
            before_ts = args.get("before_timestamp")
            after_ts = args.get("after_timestamp")
            from_me_arg = args.get("from_me")
            raw_entries = args.get("entries")
            entries = raw_entries if isinstance(raw_entries, list) else None
            if (
                not message_ids
                and before_ts is None
                and after_ts is None
                and not entries
            ):
                raise ToolPolicyError(
                    "[integrator] Informe message_ids, before_timestamp/after_timestamp "
                    "ou entries."
                )
            result = session.delete_messages_for_me(
                chat_id=chat_id,
                message_ids=message_ids,
                before_timestamp=int(before_ts) if before_ts is not None else None,
                after_timestamp=int(after_ts) if after_ts is not None else None,
                from_me=bool(from_me_arg) if from_me_arg is not None else None,
                delete_media=bool(args.get("delete_media", False)),
                entries=entries,
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
