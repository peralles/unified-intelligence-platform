# Plano de implementação — operações Hermes (ordem de velocidade)

**Status:** 66 tools na `main` (incl. busca WhatsApp por telefone).

## Fase 4 — Lote 3 (mídia e Gmail)

| # | Tools | Status |
|---|-------|--------|
| 8 | `send_whatsapp_video`, `send_whatsapp_sticker`, `send_whatsapp_contact` | ✅ |
| 9 | `list_whatsapp_groups`, `get_whatsapp_profile_picture`, `send_whatsapp_typing` | ✅ |
| 10 | `trash_gmail_message`, `star_gmail_message` | ✅ |

## Fase 5 — Lote 4 (enquete, álbum, bloqueio, grupo)

| # | Tools | Status |
|---|-------|--------|
| 11 | `send_whatsapp_poll`, `send_whatsapp_album` | ✅ |
| 12 | `get_whatsapp_blocklist`, `update_whatsapp_blocklist` | ✅ |
| 13 | `get_whatsapp_group_invite_link`, `leave_whatsapp_group` | ✅ |
| 14 | `mark_gmail_read`, `mark_gmail_unread`, `restore_gmail_message` | ✅ |

## Fase 6 — Lote 5 (voto enquete, entrar grupo, user info, drafts Gmail)

| # | Tools | Status |
|---|-------|--------|
| 15 | `vote_whatsapp_poll`, `join_whatsapp_group_link`, `get_whatsapp_user_info` | ✅ |
| 16 | `list_gmail_labels`, `create_gmail_draft_api`, `send_gmail_draft` | ✅ |

## Fase 7 — Lote 6 (preview grupo, purge, batch Gmail, Calendar range)

| # | Tools | Status |
|---|-------|--------|
| 17 | `preview_whatsapp_group_link`, `clear_whatsapp_chat_cache`, `leave_whatsapp_group_and_purge` | ✅ |
| 18 | `batch_modify_gmail_labels`, `list_calendar_events_range` | ✅ |

## Fase 1 — WhatsApp

| # | Tools | Status |
|---|-------|--------|
| 1 | `whatsapp_reply_text`, `whatsapp_react_message` | ✅ |
| 2 | `archive_whatsapp_chat`, `pin_whatsapp_chat` | ✅ |
| 3 | `send_whatsapp_image` | ✅ |
| 4 | `search_whatsapp_messages`, `get_whatsapp_group_info` | ✅ |
| 5 | `edit_whatsapp_text` | ✅ |

## Fase 2 — Gmail extra

| # | Tools | Status |
|---|-------|--------|
| 6 | `modify_gmail_labels` | ✅ |
| 7 | `reply_gmail_message` | ✅ |

## Fase 3 — Qualidade

Docs, `validate.sh`, testes (`test_google_gmail_extra.py`), roteamento `is_whatsapp_tool` / `GMAIL_EXTRA_TOOL_NAMES`.
