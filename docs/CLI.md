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
| `integrator serve` | Servidor MCP stdio (Hermes inicia o processo) |
| `integrator serve-http` | Servidor HTTP/SSE local (background) |
| `integrator service …` | **macOS:** LaunchAgent (instalar/ativar/desativar) |

Aliases legados: `integrator-auth` → `integrator login`, `integrator-serve` → `integrator serve`.

## Serviço no macOS

O Hermes via **stdio** inicia o MCP sob demanda. Para manter o integrador **sempre rodando** (HTTP/SSE), use LaunchAgent:

```bash
uv run integrator service install    # instala + inicia
uv run integrator service status
uv run integrator service disable    # para (mantém plist)
uv run integrator service start      # reativa
uv run integrator service uninstall  # remove plist e para
```

- Plist: `~/Library/LaunchAgents/com.peralles.langchain-integrator.plist`
- URL SSE: `http://127.0.0.1:17320/sse`
- Logs: `data/logs/service/stdout.log`, `stderr.log`
- Hermes: ver `config/hermes.service.example.yaml`

Porta customizada: `integrator service install --port 18000`

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
