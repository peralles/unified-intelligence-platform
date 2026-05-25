# Integrador LangChain → Hermes

Servidor **MCP local** (Python) que expõe **todas** as ferramentas oficiais LangChain de **Gmail** e **Google Calendar**, com OAuth unificado Google, para o agente [Hermes](https://dev.to/emmanuelthecoder/hermes-the-self-improving-agent-you-can-actually-run-yourself-555l).

## Por que Python (e não Node)?

Os toolkits `GmailToolkit` e `CalendarToolkit` vivem em `langchain-google-community` — mantidos e documentados em **Python**. A variante JS não oferece a mesma cobertura OAuth + tools; para simplicidade e menos código próprio, usamos Python + MCP stdio.

## Início rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Google Cloud: credentials.json em credentials/
python -m integrator.cli.auth_login

pytest -q
python -m integrator.cli.serve   # Hermes conecta via stdio
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

## Segurança

- `credentials/` e `data/tokens/` estão no `.gitignore`
- Acesso completo às APIs Google — use apenas em ambiente confiável
