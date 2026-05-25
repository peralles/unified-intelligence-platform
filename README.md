# Integrador LangChain → Hermes

Servidor **MCP local** (Python) que expõe **todas** as ferramentas oficiais LangChain de **Gmail** e **Google Calendar**, com OAuth unificado Google, para o agente [Hermes](https://dev.to/emmanuelthecoder/hermes-the-self-improving-agent-you-can-actually-run-yourself-555l).

## Por que Python (e não Node)?

Os toolkits `GmailToolkit` e `CalendarToolkit` vivem em `langchain-google-community` — mantidos e documentados em **Python**. A variante JS não oferece a mesma cobertura OAuth + tools; para simplicidade e menos código próprio, usamos Python + MCP stdio.

## Início rápido

Requer [uv](https://docs.astral.sh/uv/):

```bash
uv sync --all-extras

# Google Cloud: credentials/credentials.json (OAuth Desktop)
uv run integrator login pessoal
uv run integrator login profissional --label "Trabalho"

uv run integrator status    # contas + tokens
uv run integrator use profissional   # conta padrão
uv run integrator serve     # MCP para o Hermes
```

**Gmail + Google Calendar** usam o mesmo login por conta (`pessoal`, `profissional`, etc.). No Hermes, passe `"account": "profissional"` nas tools (ou use a conta padrão).

```bash
uv run integrator --help
uv run pytest
```

### Hermes

Copie e adapte [`config/hermes.example.yaml`](config/hermes.example.yaml) para `~/.hermes/config.yaml`.

## Documentação

| Arquivo | Conteúdo |
|---------|----------|
| [docs/PLANO_LANGCHAIN_HERMES.md](docs/PLANO_LANGCHAIN_HERMES.md) | Arquitetura e decisões |
| [docs/ATIVIDADES_IMPLANTACAO.md](docs/ATIVIDADES_IMPLANTACAO.md) | Checklist de implantação |

## Tools (12)

Gmail: `create_gmail_draft`, `send_gmail_message`, `search_gmail`, `get_gmail_message`, `get_gmail_thread`

Calendar: `create_calendar_event`, `search_events`, `update_calendar_event`, `get_calendars_info`, `move_calendar_event`, `delete_calendar_event`, `get_current_datetime`

## Segurança (Fase 2)

- **Denylist/allowlist:** `INTEGRATOR_TOOL_DENYLIST` / `INTEGRATOR_TOOL_ALLOWLIST` (ver `config/integrator.example.env`)
- **Confirmação:** `send_gmail_message` e `delete_calendar_event` exigem `"confirm": true` nos argumentos
- **Auditoria:** `data/logs/audit.jsonl` — só metadados (tool, sucesso, duração), sem conteúdo de e-mails/eventos
- **Token:** `chmod 600` em `data/tokens/google.json` após login/refresh
- `credentials/` e `data/` não vão para o git
