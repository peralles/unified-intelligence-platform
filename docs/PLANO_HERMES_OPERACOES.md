# Plano de implementação — operações Hermes (ordem de velocidade)

**Status:** concluído em `main` (37 tools MCP — lote 2: mute, documento/áudio, forward, anexos Gmail, cache SQLite).

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
