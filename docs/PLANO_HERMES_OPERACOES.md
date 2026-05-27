# Plano de implementação — operações Hermes (ordem de velocidade)

## Fase 1 — WhatsApp rápido (neonize já expõe API)

| # | Entrega | Tools | Commit |
|---|---------|-------|--------|
| 1 | Reply + reação | `reply_whatsapp_text`, `react_whatsapp_message` | 1 |
| 2 | Organização de chat | `archive_whatsapp_chat`, `pin_whatsapp_chat` | 1 |
| 3 | Mídia saída | `send_whatsapp_image` (+ confirm) | 1 |
| 4 | Busca + grupo | `search_whatsapp_messages`, `get_whatsapp_group_info` | 1 |
| 5 | Editar própria msg | `edit_whatsapp_text` (+ confirm) | 1 |

## Fase 2 — Google custom (API direta, fora do toolkit LC)

| # | Entrega | Tools | Commit |
|---|---------|-------|--------|
| 6 | Labels Gmail | `modify_gmail_labels` (+ confirm se remover INBOX) | 1 |
| 7 | Responder e-mail | `reply_gmail_message` (+ confirm) | 1 |

## Fase 3 — Qualidade

| # | Entrega | Commit |
|---|---------|--------|
| 8 | Docs, validate.sh, testes, varredura bugs | 1+ |

**Total estimado:** 8 commits + 1 commit de correções finais.
