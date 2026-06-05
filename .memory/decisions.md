# Decisões estáveis

Resumo das escolhas já documentadas em `docs/PLANO_LANGCHAIN_HERMES.md` e `README.md`.

## Stack e integração

- **Python** + `langchain-google-community` (Gmail + Calendar) — não Node; toolkits oficiais só em Python
- **MCP** como interface para Hermes; transporte doc padrão **stdio** (`integrator serve`)
- HTTP/SSE (`integrator serve-http`, Docker/Coolify, porta **17320**) para worker WhatsApp persistente quando Hermes usa tools + auto-transcrição
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
- Sessão: `data/whatsapp/` (gitignored); QR no admin (`/admin`)
- Tools destrutivas WhatsApp (`send_*`, `delete_*`) exigem `confirm: true`; delete de terceiros via `delete_whatsapp_messages_for_me` (app state)
- Hermes: **mesmo** `mcp_servers.langchain-integrator` stdio; sem segunda entrada MCP
- **Lockfile**: `data/whatsapp/worker.lock` (fcntl) — uma instância neonize por sessão; stdio `serve` e SSE não podem rodar em paralelo na mesma sessão
- **Transcrição pós-processamento:** `bridges/whatsapp-neonize/transcribe_cleanup.py` remove repetições de cauda do Whisper (ex.: «slang slang…») antes de responder no chat
- **Watch daemon** (`integrator whatsapp watch`): transcrição foreground; conflita com MCP serve/SSE na mesma sessão
- **Hermes + auto-transcrição**: SSE (Docker/`serve-http`) + `INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE=true`; `bridge_client` repassa vars de transcrição do `settings` ao worker (`.env` não chega ao subprocesso via os.environ)
- Confirmação condicional: `transcribe_whatsapp_audio` com `reply=true` e `get_whatsapp_group_invite_link` com `revoke=true` exigem `confirm: true`

## Admin local (operadores)

- Console admin no mesmo processo que `serve-http` / container Docker
- Comandos operacionais (`status`, `login`, `whatsapp`, `hermes`, `logs`, …) **removidos** da CLI — só admin web
- Bootstrap permanece na CLI: `init`, `serve`, `serve-http`, `service`
- Runtime hot-reload: `data/admin/runtime.json` (ex.: ignore list transcrição)
- Doc: `docs/ADMIN.md`

## MCP client setup (Hermes + Claude Desktop)

- Dois adapters de config (**Hermes YAML**, **Claude JSON**) — sem abstração genérica `HostWriter` enquanto só existirem dois hosts
- Orchestrator único: `integrator/clients/mcp_setup.py` (`setup_mcp_clients`, `run_all_client_checks`)
- Terceiro host (Cursor, VS Code, etc.) → reavaliar seam comum; até lá, duplicação load/save/merge é aceitável

## Setup status seam

- Readiness (`is_configured`, `configuration_summary`) em `integrator/setup/status.py` — **não** em `cli/ux`
- Preflight deps (`repo_deps_ok`, `run_uv_sync`) em `integrator/onboarding/preflight.py` — timeout único 90s


- `INTEGRATOR_TOOL_ALLOWLIST` / `INTEGRATOR_TOOL_DENYLIST`
- Confirmação explícita: `send_gmail_message`, `delete_calendar_event` → `confirm: true`
- Auditoria `data/logs/audit.jsonl` — metadados apenas, sem PII de e-mail/evento
- Tokens com `chmod 600` após login/refresh

## Repositório

- Pacote único `integrator` (não monorepo)
- `credentials/` e `data/` no `.gitignore`
- Validação canônica: `./scripts/validate.sh` (ruff, pytest, smokes de 12 tools e performance)
