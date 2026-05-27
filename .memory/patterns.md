# Padrões de código

Seguir o que já existe em `integrator/` e `tests/`.

## Python

- `from __future__ import annotations` em módulos do pacote
- Config: `Settings` em `integrator/config.py`, `env_prefix="INTEGRATOR_"`, paths sob `root_dir`
- Account ID: `validate_account_id()` em `integrator/accounts/registry.py` → lowercase

## Tools e segurança

- Metadados Google: `integrator/providers/google_tools.py` (+ cache); WhatsApp: `whatsapp_tools.py`; agregador MCP: `integrator/providers/tools.py`
- Antes de invoke: `check_policy` → `check_confirmation` → `strip_confirm_arg` para LangChain
- Tools destrutivas: schema MCP inclui `confirm`; default em `get_confirm_required_tools()`

## MCP

- Handlers: `integrator/mcp/server.py` (`handle_list_tools`, `handle_call_tool`)
- Erros ao usuário: `_mcp_error(f"[integrator] …")` — auth, policy, confirmação, genérico
- Schema: `integrator/mcp/schema.py`

## CLI e serviço

- Entrada: `integrator/cli/main.py` — subcomandos `status`, `login`, `serve`, `service`, etc.
- macOS LaunchAgent: `integrator/service/macos.py`

## Testes

- `pytest`, `asyncio_mode = auto` (`pyproject.toml`)
- Assert de 21 tools (12 Google + 9 WhatsApp) e tools com confirmação nos smokes de `scripts/validate.sh`
- Performance: budgets em `tests/test_performance.py` e smoke no validate.sh

## Logging

- Fila assíncrona; `data/logs/integrator.log`, `errors.log`, `audit.jsonl`
- Sucesso de tool no audit desligado por padrão (`INTEGRATOR_AUDIT_LOG_SUCCESS=false`)
