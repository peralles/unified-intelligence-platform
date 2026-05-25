# Atividades de implantação — LangChain Hermes Integrator

**Stack escolhida:** Python 3.11+ com **[uv](https://docs.astral.sh/uv/)** (não pip/venv manual; não Node) — `langchain-google-community` só tem toolkits Gmail/Calendar maduros em Python.

**Decisões aplicadas:**

| # | Decisão |
|---|---------|
| 1 | Acesso completo (`mail.google.com` + `calendar`) |
| 2 | Token OAuth **único** em `data/tokens/google.json` |
| 3 | **Todas** as 12 tools expostas via MCP |
| 4 | Hermes na mesma máquina → MCP **stdio** |

---

## Status das atividades

### Fase 0 — Google Cloud (manual)

- [ ] Criar projeto Google Cloud
- [ ] Ativar Gmail API + Google Calendar API
- [ ] Credencial OAuth tipo **Desktop app**
- [ ] Copiar `credentials.json` → `credentials/credentials.json`
- [ ] Adicionar e-mail como usuário de teste (app Testing)

### Fase 1 — Implementação (automática neste repo)

- [x] `pyproject.toml` + pacote `integrator`
- [x] OAuth unificado `integrator/auth/google_oauth.py`
- [x] Providers Gmail + Calendar (12 tools)
- [x] Servidor MCP stdio `integrator/mcp/server.py`
- [x] CLI `python -m integrator.cli.auth_login`
- [x] CLI `python -m integrator.cli.serve`
- [x] Testes unitários (`pytest`)
- [x] Exemplo Hermes `config/hermes.example.yaml`
- [ ] **Você:** rodar `auth_login` com credenciais reais
- [ ] **Você:** validar no Hermes (`hermes tools` + uma chamada)

### Fase 2 — Hardening ✅

- [x] Allowlist/denylist via `INTEGRATOR_TOOL_ALLOWLIST` / `INTEGRATOR_TOOL_DENYLIST`
- [x] Confirmação explícita (`confirm: true`) para `send_gmail_message` e `delete_calendar_event`
- [x] Auditoria JSONL em `data/logs/audit.jsonl` (sem argumentos/PII)
- [x] `chmod 600` automático no token após OAuth/refresh
- [x] Exemplo: `config/integrator.example.env`

### Fase 3 — Extensões (backlog)

- [ ] Template `OAuthProvider` para Slack/Notion
- [ ] Transporte SSE se Hermes remoto
- [ ] Multi-conta (`data/tokens/{account_id}/`)

---

## Comandos de implantação

```bash
cd /caminho/para/unified-intelligence-platform
uv sync --all-extras

# 1) Coloque credentials.json em credentials/
uv run integrator-auth

# 2) Validação técnica (pytest + smoke MCP)
./scripts/validate.sh

# 3) Servidor MCP (Hermes chama este processo)
uv run integrator-serve
```

### Hermes (`~/.hermes/config.yaml`)

Ver `config/hermes.example.yaml` — use `uv run` (recomendado) ou o Python em `.venv/bin/` após `uv sync`.

---

## Tools MCP expostas (12)

**Gmail:** `create_gmail_draft`, `send_gmail_message`, `search_gmail`, `get_gmail_message`, `get_gmail_thread`

**Calendar:** `create_calendar_event`, `search_events`, `update_calendar_event`, `get_calendars_info`, `move_calendar_event`, `delete_calendar_event`, `get_current_datetime`

---

## Validação de aceite

| Critério | Como validar |
|----------|----------------|
| Token persistido | `ls -la data/tokens/google.json` após auth_login |
| MCP lista 12 tools | `pytest tests/test_mcp_list_tools.py` |
| Hermes vê tools | `hermes tools` com MCP configurado |
| Invocação real | Pedir ao Hermes: "liste meus calendários" (`get_calendars_info`) |
| Sem vazamento de secrets | Inspecionar saída das tools |
