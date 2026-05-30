# Decisões estáveis

Resumo das escolhas já documentadas em `docs/PLANO_LANGCHAIN_HERMES.md` e `README.md`.

## Stack e integração

- **Python** + `langchain-google-community` (Gmail + Calendar) — não Node; toolkits oficiais só em Python
- **MCP** como interface para Hermes; transporte doc padrão **stdio** (`integrator serve`)
- HTTP/SSE (`integrator serve-http`, LaunchAgent `integrator service`, porta **17320**) para worker WhatsApp persistente quando Hermes usa tools + auto-transcrição
- Hermes não depende de LangChain diretamente — só do servidor MCP

## Auth e dados

- OAuth Google (InstalledAppFlow) no integrador; refresh fora da sessão do LLM
- `credentials/credentials.json` (OAuth client); tokens em `data/tokens/{account_id}.json`
- Multi-conta: registry `data/accounts.yaml`; argumento MCP `"account"` ou conta padrão (`integrator use`)
- Scopes: Gmail + Calendar completos (`GOOGLE_SCOPES` em `integrator/config.py`)
- Fail closed: sem token válido → erro claro, sem acesso inventado

## Superfície de tools

- **66 tools** MCP via agregador `integrator/providers/tools.py`: 12 Google LangChain + 13 Gmail extra + 1 Calendar extra + 40 WhatsApp
- WhatsApp: inclui `transcribe_whatsapp_audio` (on-demand via MCP) e auto-transcrição no worker
- Extensão futura: padrão `ToolProvider` para outros OAuth

## WhatsApp (neonize)

- Backend: **neonize** (Whatsmeow in-process no worker), não Evolution HTTP no MVP
- `neonize` exige **protobuf ≥7**; `langchain-google-community` fixa **protobuf &lt;7** no mesmo venv — worker isolado em `bridges/whatsapp-neonize/` (subprocesso JSON stdin/stdout)
- Sessão: `data/whatsapp/` (gitignored); QR no admin (`/admin`) ou CLI legado (`INTEGRATOR_CLI_LEGACY=true`)
- Tools destrutivas WhatsApp (`send_*`, `delete_*`) exigem `confirm: true`; delete de terceiros via `delete_whatsapp_messages_for_me` (app state)
- Hermes: **mesmo** `mcp_servers.langchain-integrator` stdio; sem segunda entrada MCP
- **Lockfile**: `data/whatsapp/worker.lock` (fcntl) — uma instância neonize por sessão; `watch-service`, stdio `serve` e SSE não podem rodar em paralelo
- **Transcrição**: `mlx-whisper` no venv do bridge; modelo padrão `whisper-large-v3-turbo`; `INTEGRATOR_WHATSAPP_TRANSCRIBE_PRIVATE_ONLY=true` (padrão) ignora grupos `@g.us`
- **Watch daemon** (`integrator whatsapp watch` / `watch-service`): transcrição 24/7 sem Hermes; conflita com MCP serve/SSE na mesma sessão
- **Hermes + auto-transcrição**: `integrator service` (SSE) + `INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE=true`; `bridge_client` repassa vars de transcrição do `settings` ao worker (`.env` não chega ao subprocesso via os.environ)
- Confirmação condicional: `transcribe_whatsapp_audio` com `reply=true` e `get_whatsapp_group_invite_link` com `revoke=true` exigem `confirm: true`

## Admin local (operadores)

- Console **`http://127.0.0.1:17320/admin`** no mesmo processo que `serve-http` / LaunchAgent
- Comandos operacionais (`status`, `login`, `whatsapp`, `hermes`, `logs`, …) **redirecionam** ao admin por padrão; `INTEGRATOR_CLI_LEGACY=true` para CI/scripts
- Bootstrap permanece na CLI: `init`, `serve`, `serve-http`, `service`
- Runtime hot-reload: `data/admin/runtime.json` (ex.: ignore list transcrição)
- Doc: `docs/ADMIN.md`

## Segurança (Fase 2)

- `INTEGRATOR_TOOL_ALLOWLIST` / `INTEGRATOR_TOOL_DENYLIST`
- Confirmação explícita: `send_gmail_message`, `delete_calendar_event` → `confirm: true`
- Auditoria `data/logs/audit.jsonl` — metadados apenas, sem PII de e-mail/evento
- Tokens com `chmod 600` após login/refresh

## Repositório

- Pacote único `integrator` (não monorepo)
- `credentials/` e `data/` no `.gitignore`
- Validação canônica: `./scripts/validate.sh` (ruff, pytest, smokes de 12 tools e performance)
