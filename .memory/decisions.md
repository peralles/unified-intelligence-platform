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

- **12 tools** LangChain expostas via MCP (nomes estáveis; lista em README)
- Extensão futura: padrão `ToolProvider` para outros OAuth (Slack, Notion, etc.)

## Segurança (Fase 2)

- `INTEGRATOR_TOOL_ALLOWLIST` / `INTEGRATOR_TOOL_DENYLIST`
- Confirmação explícita: `send_gmail_message`, `delete_calendar_event` → `confirm: true`
- Auditoria `data/logs/audit.jsonl` — metadados apenas, sem PII de e-mail/evento
- Tokens com `chmod 600` após login/refresh

## Repositório

- Pacote único `integrator` (não monorepo)
- `credentials/` e `data/` no `.gitignore`
- Validação canônica: `./scripts/validate.sh` (ruff, pytest, smokes de 12 tools e performance)
