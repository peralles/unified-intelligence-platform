# Decisões estáveis

Resumo das escolhas já documentadas em `docs/PLANO_LANGCHAIN_HERMES.md` e `README.md`.

## Stack e integração

- **Python** + `langchain-google-community` (Gmail + Calendar) — não Node; toolkits oficiais só em Python
- **MCP** como interface para Hermes; transporte principal **stdio** (`integrator serve`)
- HTTP/SSE opcional (`integrator serve-http`, LaunchAgent macOS, porta padrão **17320**)
- Hermes não depende de LangChain diretamente — só do servidor MCP

## Auth e dados

- OAuth Google (InstalledAppFlow) no integrador; refresh fora da sessão do LLM
- `credentials/credentials.json` (OAuth client); tokens em `data/tokens/{account_id}.json`
- Multi-conta: registry `data/accounts.yaml`; argumento MCP `"account"` ou conta padrão (`integrator use`)
- Scopes: Gmail + Calendar completos (`GOOGLE_SCOPES` em `integrator/config.py`)
- Fail closed: sem token válido → erro claro, sem acesso inventado

## Superfície de tools

- **12 tools** Google LangChain + **9 tools** WhatsApp (`whatsapp_*`) via agregador `integrator/providers/tools.py`
- Extensão futura: padrão `ToolProvider` para outros OAuth (Slack, Notion, etc.)

## WhatsApp (neonize)

- Backend: **neonize** (Whatsmeow in-process no worker), não Evolution HTTP no MVP
- `neonize` exige **protobuf ≥7**; `langchain-google-community` fixa **protobuf &lt;7** no mesmo venv — worker isolado em `bridges/whatsapp-neonize/` (subprocesso JSON stdin/stdout)
- Sessão: `data/whatsapp/` (gitignored); QR só em `integrator whatsapp pair`
- Tools destrutivas WhatsApp (`send_*`, `delete_*`) exigem `confirm: true`; delete de terceiros via `delete_whatsapp_messages_for_me` (app state)
- Hermes: **mesmo** `mcp_servers.langchain-integrator` stdio; sem segunda entrada MCP

## Segurança (Fase 2)

- `INTEGRATOR_TOOL_ALLOWLIST` / `INTEGRATOR_TOOL_DENYLIST`
- Confirmação explícita: `send_gmail_message`, `delete_calendar_event` → `confirm: true`
- Auditoria `data/logs/audit.jsonl` — metadados apenas, sem PII de e-mail/evento
- Tokens com `chmod 600` após login/refresh

## Repositório

- Pacote único `integrator` (não monorepo)
- `credentials/` e `data/` no `.gitignore`
- Validação canônica: `./scripts/validate.sh` (ruff, pytest, smokes de 12 tools e performance)
