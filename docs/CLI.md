# CLI — `integrator`

CLI única, focada em **poucos comandos** e suporte a **várias contas Google** (Gmail + Calendar no mesmo login).

## Comandos

| Comando | Descrição |
|---------|-----------|
| `integrator status` | Contas, tokens, escopos |
| `integrator login <id>` | OAuth no navegador (Gmail + Calendar) |
| `integrator accounts` | Listar contas |
| `integrator use <id>` | Definir conta padrão |
| `integrator logout <id>` | Remover conta e token |
| `integrator tools` | Listar 12 tools MCP |
| `integrator serve` | Servidor MCP (Hermes) |

Aliases legados: `integrator-auth` → `integrator login`, `integrator-serve` → `integrator serve`.

## Múltiplas contas (pessoal + profissional)

```bash
uv run integrator login pessoal
uv run integrator login profissional --label "Trabalho"
uv run integrator use profissional    # padrão quando o agente omitir "account"
uv run integrator status
```

Tokens: `data/tokens/pessoal.json`, `data/tokens/profissional.json`  
Registro: `data/accounts.yaml`

No Hermes / MCP, passe em qualquer tool:

```json
{ "account": "profissional", "query": "is:unread" }
```

## Google Calendar

Sim — cada conta autenticada expõe **Gmail e Calendar** (mesmos 12 tools LangChain):

- Calendar: `create_calendar_event`, `search_events`, `get_calendars_info`, etc.
- Gmail: `search_gmail`, `send_gmail_message`, etc.

## IDs de conta válidos

Letras minúsculas, números, `_`, `-` (ex: `pessoal`, `profissional`, `trabalho-01`).
