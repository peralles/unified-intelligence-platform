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
    "archive_whatsapp_chat",
    "pin_whatsapp_chat",
    "send_whatsapp_image",
    "search_whatsapp_messages",
    "get_whatsapp_group_info",
    "edit_whatsapp_text",
    "mark_whatsapp_read",
    "mute_whatsapp_chat",
    "send_whatsapp_document",
    "send_whatsapp_audio",
    "forward_whatsapp_message",
    "send_whatsapp_video",
    "send_whatsapp_sticker",
    "send_whatsapp_contact",
    "list_whatsapp_groups",
    "get_whatsapp_profile_picture",
    "send_whatsapp_typing",
    "send_whatsapp_poll",
    "send_whatsapp_album",
    "get_whatsapp_blocklist",
    "update_whatsapp_blocklist",
    "get_whatsapp_group_invite_link",
    "leave_whatsapp_group",
    "vote_whatsapp_poll",
    "join_whatsapp_group_link",
    "get_whatsapp_user_info",
    "preview_whatsapp_group_link",
    "clear_whatsapp_chat_cache",
    "leave_whatsapp_group_and_purge",
    "transcribe_whatsapp_audio",
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
                "Lista chats recentes. Ao responder ao usuário, use sempre display_name "
                "(nome + telefone quando existir). O campo chat_id é só para outras tools — "
                "nunca mostre JIDs @lid ou números internos crus. "
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
                "Busca chats por nome, telefone (com ou sem formatação) ou trecho do id. "
                "Chats privados @lid incluem phone quando disponível. "
                "Use display_name ao falar com o usuário; chat_id só para follow-up técnico. "
                "Sem query, equivale a list_whatsapp_chats."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Nome, número (ex. 5519992034333) ou chat_id. "
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
                "Cada item inclui chat_display_name — use esse rótulo, não chat_id, ao resumir para o usuário. "
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
                "message_id deve estar em cache. Requer confirm=true."
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
            "name": "send_whatsapp_image",
            "description": (
                "Envia imagem por caminho local absoluto no disco. "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Caminho absoluto do arquivo de imagem.",
                    },
                    "chat_id": {"type": "string"},
                    "number": {"type": "string"},
                    "caption": {"type": "string"},
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "search_whatsapp_messages",
            "description": (
                "Busca texto nas mensagens em cache (opcionalmente por chat_id). "
                "Use chat_display_name nos resultados ao responder ao usuário."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto a buscar."},
                    "chat_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_whatsapp_group_info",
            "description": "Metadados de grupo WhatsApp (nome, participantes).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "JID do grupo (@g.us).",
                    },
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "edit_whatsapp_text",
            "description": (
                "Edita mensagem de texto enviada por você. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "message_id": {"type": "string"},
                    "text": {"type": "string", "description": "Novo texto."},
                },
                "required": ["chat_id", "message_id", "text"],
            },
        },
        {
            "name": "archive_whatsapp_chat",
            "description": "Arquiva ou desarquiva um chat no WhatsApp.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do chat."},
                    "archived": {
                        "type": "boolean",
                        "description": "true=arquivar, false=desarquivar (padrão true).",
                    },
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "pin_whatsapp_chat",
            "description": "Fixa ou desfixa um chat no topo.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do chat."},
                    "pinned": {
                        "type": "boolean",
                        "description": "true=fixar, false=desfixar (padrão true).",
                    },
                },
                "required": ["chat_id"],
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
            "name": "mute_whatsapp_chat",
            "description": (
                "Silencia notificações do chat (padrão 8h) ou reativa com unmute=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do chat."},
                    "mute_hours": {
                        "type": "integer",
                        "description": "Horas de silêncio (mín. 1; padrão 8).",
                    },
                    "unmute": {
                        "type": "boolean",
                        "description": "true=reativar notificações.",
                    },
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "send_whatsapp_document",
            "description": (
                "Envia documento/arquivo por caminho local absoluto. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Caminho absoluto do arquivo.",
                    },
                    "chat_id": {"type": "string"},
                    "number": {"type": "string"},
                    "caption": {"type": "string"},
                    "filename": {
                        "type": "string",
                        "description": "Nome exibido no WhatsApp (padrão: nome do arquivo).",
                    },
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "send_whatsapp_audio",
            "description": (
                "Envia áudio por caminho local. voice_note=true envia como mensagem de voz. "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "chat_id": {"type": "string"},
                    "number": {"type": "string"},
                    "voice_note": {
                        "type": "boolean",
                        "description": "true = PTT (bolinha de voz).",
                    },
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "forward_whatsapp_message",
            "description": (
                "Reenvia texto de mensagem em cache para outro chat (prefixo ↪️ opcional). "
                "Mídia pura ainda não suportada. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "source_chat_id": {"type": "string"},
                    "message_id": {"type": "string"},
                    "target_chat_id": {"type": "string"},
                    "target_number": {"type": "string"},
                    "include_prefix": {
                        "type": "boolean",
                        "description": "Adiciona ↪️ antes do texto (padrão true).",
                    },
                },
                "required": ["source_chat_id", "message_id"],
            },
        },
        {
            "name": "send_whatsapp_video",
            "description": (
                "Envia vídeo por caminho local. view_once e gif_playback opcionais. "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "chat_id": {"type": "string"},
                    "number": {"type": "string"},
                    "caption": {"type": "string"},
                    "view_once": {"type": "boolean"},
                    "gif_playback": {
                        "type": "boolean",
                        "description": "Reproduzir como GIF no chat.",
                    },
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "send_whatsapp_sticker",
            "description": (
                "Envia figurinha (WebP) por caminho local. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "chat_id": {"type": "string"},
                    "number": {"type": "string"},
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "send_whatsapp_contact",
            "description": (
                "Compartilha cartão de contato (nome + número). Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"},
                    "contact_number": {
                        "type": "string",
                        "description": "Número com DDI (só dígitos).",
                    },
                    "chat_id": {"type": "string"},
                    "number": {"type": "string", "description": "Destino se não usar chat_id."},
                },
                "required": ["contact_name", "contact_number"],
            },
        },
        {
            "name": "list_whatsapp_groups",
            "description": "Lista grupos dos quais você participa (id, nome, participantes).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Máximo (padrão 50)."},
                },
            },
        },
        {
            "name": "get_whatsapp_profile_picture",
            "description": (
                "URL e metadados da foto de perfil de um chat/contato (não baixa o arquivo)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID do contato ou grupo."},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "send_whatsapp_typing",
            "description": (
                "Indica digitando ou pausa (composing true/false). "
                "Use com moderação — não spammar presença."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "composing": {
                        "type": "boolean",
                        "description": "true=digitando, false=pausado (padrão true).",
                    },
                    "media": {
                        "type": "string",
                        "description": "text ou audio (padrão text).",
                    },
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "send_whatsapp_poll",
            "description": (
                "Cria enquete no chat (question + options, mín. 2). "
                "allow_multiple para voto múltiplo. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "chat_id": {"type": "string"},
                    "number": {"type": "string"},
                    "allow_multiple": {"type": "boolean"},
                },
                "required": ["question", "options"],
            },
        },
        {
            "name": "send_whatsapp_album",
            "description": (
                "Envia álbum de imagens/vídeos (lista de caminhos locais). "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Caminhos absolutos (2+ arquivos).",
                    },
                    "chat_id": {"type": "string"},
                    "number": {"type": "string"},
                    "caption": {"type": "string"},
                },
                "required": ["file_paths"],
            },
        },
        {
            "name": "get_whatsapp_blocklist",
            "description": "Lista JIDs/contatos bloqueados.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "update_whatsapp_blocklist",
            "description": (
                "Bloqueia ou desbloqueia contato (block true/false). Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "number": {"type": "string"},
                    "block": {
                        "type": "boolean",
                        "description": "true=bloquear, false=desbloquear (padrão true).",
                    },
                },
            },
        },
        {
            "name": "get_whatsapp_group_invite_link",
            "description": (
                "Obtém link de convite do grupo. revoke=true invalida link anterior "
                "e exige confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID @g.us"},
                    "revoke": {"type": "boolean"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "leave_whatsapp_group",
            "description": "Sai do grupo WhatsApp. Requer confirm=true.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID @g.us"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "vote_whatsapp_poll",
            "description": (
                "Vota em enquete existente (poll_message_id em cache + selected_options). "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "poll_message_id": {"type": "string"},
                    "selected_options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Texto exato da(s) opção(ões) escolhida(s).",
                    },
                },
                "required": ["chat_id", "poll_message_id", "selected_options"],
            },
        },
        {
            "name": "join_whatsapp_group_link",
            "description": (
                "Entra em grupo via link chat.whatsapp.com/... ou código. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "invite_link": {
                        "type": "string",
                        "description": "URL completa ou código do convite.",
                    },
                },
                "required": ["invite_link"],
            },
        },
        {
            "name": "get_whatsapp_user_info",
            "description": (
                "Status/nome verificado de um ou mais contatos (chat_id ou chat_ids). "
                "Útil para enriquecer chats @lid antes de responder ao usuário."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "chat_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        {
            "name": "preview_whatsapp_group_link",
            "description": (
                "Pré-visualiza grupo pelo link de convite (sem entrar)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "invite_link": {"type": "string"},
                },
                "required": ["invite_link"],
            },
        },
        {
            "name": "clear_whatsapp_chat_cache",
            "description": (
                "Remove mensagens do cache local (memória + SQLite) deste chat. "
                "Não apaga no WhatsApp dos outros."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "leave_whatsapp_group_and_purge",
            "description": (
                "Sai do grupo, apaga em cache no dispositivo (delete for me) e limpa cache local. "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "JID @g.us"},
                    "delete_media": {"type": "boolean"},
                },
                "required": ["chat_id"],
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
        {
            "name": "transcribe_whatsapp_audio",
            "description": (
                "Transcreve localmente um áudio (nota de voz) do WhatsApp usando mlx-whisper "
                "(Apple Silicon). Baixa o áudio do CDN do WhatsApp e retorna o texto. "
                "Requer que a mensagem esteja em cache (use get_whatsapp_messages para obter "
                "o message_id). Por padrão, grupos (@g.us) são rejeitados "
                "(INTEGRATOR_WHATSAPP_TRANSCRIBE_PRIVATE_ONLY). "
                "Auto-transcrição (SSE + AUTO_TRANSCRIBE=true): só chats privados; "
                "áudios enviados e recebidos (ONLY_INCOMING=false, padrão). "
                "reply=true envia o texto no chat e exige confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "JID do chat (ex: 5511999999999@s.whatsapp.net).",
                    },
                    "message_id": {
                        "type": "string",
                        "description": "ID da mensagem de áudio a transcrever.",
                    },
                    "reply": {
                        "type": "boolean",
                        "description": (
                            "Se true, envia o texto transcrito como resposta no mesmo chat "
                            "(padrão false)."
                        ),
                    },
                },
                "required": ["chat_id", "message_id"],
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
        elif name == "send_whatsapp_image":
            file_path = str(args.get("file_path", "")).strip()
            if not file_path:
                raise ToolPolicyError("[integrator] Parâmetro 'file_path' é obrigatório.")
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para enviar imagem."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.send_image(
                file_path=file_path,
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
                caption=str(args["caption"]) if args.get("caption") else None,
            )
        elif name == "search_whatsapp_messages":
            query = str(args.get("query", "")).strip()
            if not query:
                raise ToolPolicyError("[integrator] Parâmetro 'query' é obrigatório.")
            chat_id = args.get("chat_id")
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.search_messages(
                query=query,
                chat_id=str(chat_id) if chat_id else None,
                limit=int(args.get("limit", 30)),
            )
        elif name == "get_whatsapp_group_info":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.get_group_info(chat_id=chat_id)
        elif name == "edit_whatsapp_text":
            chat_id = str(args.get("chat_id", "")).strip()
            message_id = str(args.get("message_id", "")).strip()
            text = str(args.get("text", "")).strip()
            if not chat_id or not message_id or not text:
                raise ToolPolicyError(
                    "[integrator] chat_id, message_id e text são obrigatórios."
                )
            chat_hint = _hash_chat_id(chat_id)
            result = session.edit_text(
                chat_id=chat_id, message_id=message_id, text=text
            )
        elif name == "archive_whatsapp_chat":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.set_chat_archived(
                chat_id=chat_id,
                archived=bool(args.get("archived", True)),
            )
        elif name == "pin_whatsapp_chat":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.set_chat_pinned(
                chat_id=chat_id,
                pinned=bool(args.get("pinned", True)),
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
        elif name == "mute_whatsapp_chat":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            mute_hours = args.get("mute_hours")
            result = session.set_chat_muted(
                chat_id=chat_id,
                mute_hours=int(mute_hours) if mute_hours is not None else None,
                unmute=bool(args.get("unmute", False)),
            )
        elif name == "send_whatsapp_document":
            file_path = str(args.get("file_path", "")).strip()
            if not file_path:
                raise ToolPolicyError("[integrator] Parâmetro 'file_path' é obrigatório.")
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para enviar documento."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.send_document(
                file_path=file_path,
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
                caption=str(args["caption"]) if args.get("caption") else None,
                filename=str(args["filename"]) if args.get("filename") else None,
            )
        elif name == "send_whatsapp_audio":
            file_path = str(args.get("file_path", "")).strip()
            if not file_path:
                raise ToolPolicyError("[integrator] Parâmetro 'file_path' é obrigatório.")
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para enviar áudio."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.send_audio(
                file_path=file_path,
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
                voice_note=bool(args.get("voice_note", False)),
            )
        elif name == "forward_whatsapp_message":
            source_chat_id = str(args.get("source_chat_id", "")).strip()
            message_id = str(args.get("message_id", "")).strip()
            if not source_chat_id or not message_id:
                raise ToolPolicyError(
                    "[integrator] source_chat_id e message_id são obrigatórios."
                )
            target_chat_id = args.get("target_chat_id")
            target_number = args.get("target_number")
            if not target_chat_id and not target_number:
                raise ToolPolicyError(
                    "[integrator] Informe target_chat_id ou target_number."
                )
            chat_hint = _hash_chat_id(source_chat_id)
            result = session.forward_message(
                source_chat_id=source_chat_id,
                message_id=message_id,
                target_chat_id=str(target_chat_id) if target_chat_id else None,
                target_number=str(target_number) if target_number else None,
                include_prefix=bool(args.get("include_prefix", True)),
            )
        elif name == "send_whatsapp_video":
            file_path = str(args.get("file_path", "")).strip()
            if not file_path:
                raise ToolPolicyError("[integrator] Parâmetro 'file_path' é obrigatório.")
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para enviar vídeo."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.send_video(
                file_path=file_path,
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
                caption=str(args["caption"]) if args.get("caption") else None,
                view_once=bool(args.get("view_once", False)),
                gif_playback=bool(args.get("gif_playback", False)),
            )
        elif name == "send_whatsapp_sticker":
            file_path = str(args.get("file_path", "")).strip()
            if not file_path:
                raise ToolPolicyError("[integrator] Parâmetro 'file_path' é obrigatório.")
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para enviar figurinha."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.send_sticker(
                file_path=file_path,
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
            )
        elif name == "send_whatsapp_contact":
            contact_name = str(args.get("contact_name", "")).strip()
            contact_number = str(args.get("contact_number", "")).strip()
            if not contact_name or not contact_number:
                raise ToolPolicyError(
                    "[integrator] contact_name e contact_number são obrigatórios."
                )
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para enviar contato."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.send_contact(
                contact_name=contact_name,
                contact_number=contact_number,
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
            )
        elif name == "list_whatsapp_groups":
            result = session.list_joined_groups(limit=int(args.get("limit", 50)))
        elif name == "get_whatsapp_profile_picture":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.get_profile_picture(chat_id=chat_id)
        elif name == "send_whatsapp_typing":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.send_chat_presence(
                chat_id=chat_id,
                composing=bool(args.get("composing", True)),
                media=str(args.get("media", "text")),
            )
        elif name == "send_whatsapp_poll":
            question = str(args.get("question", "")).strip()
            raw_opts = args.get("options")
            if not question:
                raise ToolPolicyError("[integrator] Parâmetro 'question' é obrigatório.")
            if not isinstance(raw_opts, list) or len(raw_opts) < 2:
                raise ToolPolicyError(
                    "[integrator] options deve ser lista com pelo menos 2 itens."
                )
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para enviar enquete."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.send_poll(
                question=question,
                options=[str(o) for o in raw_opts],
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
                allow_multiple=bool(args.get("allow_multiple", False)),
            )
        elif name == "send_whatsapp_album":
            raw_paths = args.get("file_paths")
            if not isinstance(raw_paths, list) or len(raw_paths) < 2:
                raise ToolPolicyError(
                    "[integrator] file_paths deve ter pelo menos 2 arquivos."
                )
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para enviar álbum."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.send_album(
                file_paths=[str(p) for p in raw_paths],
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
                caption=str(args["caption"]) if args.get("caption") else None,
            )
        elif name == "get_whatsapp_blocklist":
            result = session.get_blocklist()
        elif name == "update_whatsapp_blocklist":
            chat_id = args.get("chat_id")
            number = args.get("number")
            if not chat_id and not number:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou number para bloquear/desbloquear."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.update_blocklist(
                chat_id=str(chat_id) if chat_id else None,
                number=str(number) if number else None,
                block=bool(args.get("block", True)),
            )
        elif name == "get_whatsapp_group_invite_link":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.get_group_invite_link(
                chat_id=chat_id,
                revoke=bool(args.get("revoke", False)),
            )
        elif name == "leave_whatsapp_group":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.leave_group(chat_id=chat_id)
        elif name == "vote_whatsapp_poll":
            chat_id = str(args.get("chat_id", "")).strip()
            poll_id = str(args.get("poll_message_id", "")).strip()
            raw_opts = args.get("selected_options")
            if not chat_id or not poll_id:
                raise ToolPolicyError(
                    "[integrator] chat_id e poll_message_id são obrigatórios."
                )
            if not isinstance(raw_opts, list) or not raw_opts:
                raise ToolPolicyError(
                    "[integrator] selected_options deve ser lista não vazia."
                )
            chat_hint = _hash_chat_id(chat_id)
            result = session.vote_poll(
                chat_id=chat_id,
                poll_message_id=poll_id,
                selected_options=[str(o) for o in raw_opts],
            )
        elif name == "join_whatsapp_group_link":
            invite_link = str(args.get("invite_link", "")).strip()
            if not invite_link:
                raise ToolPolicyError("[integrator] invite_link é obrigatório.")
            result = session.join_group_link(invite_link=invite_link)
        elif name == "get_whatsapp_user_info":
            chat_id = args.get("chat_id")
            raw_ids = args.get("chat_ids")
            chat_ids = (
                [str(i).strip() for i in raw_ids if str(i).strip()]
                if isinstance(raw_ids, list)
                else None
            )
            if not chat_id and not chat_ids:
                raise ToolPolicyError(
                    "[integrator] Informe chat_id ou chat_ids."
                )
            if chat_id:
                chat_hint = _hash_chat_id(str(chat_id))
            result = session.get_user_info(
                chat_ids=chat_ids,
                chat_id=str(chat_id).strip() if chat_id else None,
            )
        elif name == "preview_whatsapp_group_link":
            invite_link = str(args.get("invite_link", "")).strip()
            if not invite_link:
                raise ToolPolicyError("[integrator] invite_link é obrigatório.")
            result = session.preview_group_from_link(invite_link=invite_link)
        elif name == "clear_whatsapp_chat_cache":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.clear_chat_local_cache(chat_id=chat_id)
        elif name == "leave_whatsapp_group_and_purge":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                raise ToolPolicyError("[integrator] Parâmetro 'chat_id' é obrigatório.")
            chat_hint = _hash_chat_id(chat_id)
            result = session.leave_group_and_purge(
                chat_id=chat_id,
                delete_media=bool(args.get("delete_media", False)),
            )
        elif name == "transcribe_whatsapp_audio":
            chat_id = str(args.get("chat_id", "")).strip()
            message_id = str(args.get("message_id", "")).strip()
            if not chat_id or not message_id:
                raise ToolPolicyError(
                    "[integrator] 'chat_id' e 'message_id' são obrigatórios."
                )
            chat_hint = _hash_chat_id(chat_id)
            text = session.transcribe_audio(chat_id=chat_id, message_id=message_id)
            result = {"message_id": message_id, "chat_id": chat_id, "text": text}
            if args.get("reply") is True and text:
                session.send_text(text=f"🎙️ {text}", chat_id=chat_id)
                result["replied"] = True
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
