# Validação Fase 2 — Hardening

**Data:** gerado no CI/local via `scripts/validate.sh`  
**Branch:** `cursor/langchain-hermes-integrator-86e5`

## Escopo Fase 2

| Requisito | Implementação | Teste |
|-----------|---------------|-------|
| Allowlist | `INTEGRATOR_TOOL_ALLOWLIST` | `test_allowlist_only_permitted` |
| Denylist | `INTEGRATOR_TOOL_DENYLIST` | `test_denylist_blocks_tool`, `test_list_tools_respects_denylist` |
| Confirmação enviar | `send_gmail_message` + `confirm: true` | `test_confirmation_required`, `test_confirm_schema_added` |
| Confirmação apagar | `delete_calendar_event` + `confirm: true` | `test_mcp_phase2` (MCP isError) |
| Auditoria | `data/logs/audit.jsonl` sem PII | `test_audit_log_written_on_blocked_invoke` |
| Token chmod 600 | `secure_token_file` | `test_secure_token_file_chmod` |
| MCP isError | `CallToolResult.isError=True` em falhas | `test_call_tool_policy_returns_is_error` |

## Comandos

```bash
./scripts/validate.sh
# ou
uv run pytest -q
```

## Critérios de aceite

- [x] Tools denylisted não aparecem em `list_tools`
- [x] Invocação bloqueada gera linha de auditoria com `blocked: true`
- [x] Ações destrutivas sem `confirm` retornam erro MCP (`isError`)
- [x] `confirm` não é repassado à API Google (strip antes do invoke)
- [x] Token com permissão `600` após OAuth

## Configuração recomendada (Hermes)

```env
INTEGRATOR_TOOL_DENYLIST=send_gmail_message,delete_calendar_event
INTEGRATOR_AUDIT_LOG_ENABLED=true
```

Desbloqueie envio/apagar apenas quando o usuário confirmar na conversa; o agente deve passar `"confirm": true`.
