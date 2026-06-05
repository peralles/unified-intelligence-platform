# Instruções para agentes

## Package Manager

- Use **uv**: `uv sync --all-extras`, `uv run integrator …`
- Python 3.11+ (pin 3.12 em `.python-version`)

## Comandos por arquivo

| Tarefa | Comando |
|--------|---------|
| Setup usuário | `./setup.sh` ou `uv run integrator init` |
| Lint (arquivo) | `uv run ruff check integrator/caminho/arquivo.py` |
| Lint (pacote) | `uv run ruff check integrator tests` |
| Teste (arquivo) | `uv run pytest tests/test_arquivo.py -q --tb=short` |
| Validação completa | `./scripts/validate.sh` |

## Atribuição de commit

Commits de IA devem incluir:

```
Co-Authored-By: <nome do modelo> <noreply@anthropic.com>
```

## Checklist obrigatório (cada implementação)

Antes de dar por concluído, verificar e alinhar:

1. **Logs** — `get_logger` / `integrator.audit` / `tools`: fila assíncrona, sem PII no audit; falhas em `errors.log`; domínio WhatsApp usa `get_logger("whatsapp")` e `log_tool_invocation` como Google.
2. **Performance** — hot path MCP sem I/O desnecessário; worker neonize reutilizado via `WhatsAppSession` (um subprocesso por `serve`); CLI `whatsapp status` rápido sem `--live`; truncagem de mensagens via settings.
3. **CLI** — comandos espelhando Google (`status`, `configure`, `pair`/reconfigurar, `remove`, `disconnect`); `integrator status` resume WhatsApp; mensagens em PT-BR.
4. **Scripts shell** — `./setup.sh` / `./scripts/validate.sh` coerentes (smoke de imports, contagem de tools, subcomandos CLI se aplicável).
5. **Docs e memória** — `docs/CLI.md`, `docs/WHATSAPP.md`, `config/integrator.example.env`, `.memory/active.md` / `decisions.md` quando a decisão for estável.

## Convenções-chave

- Settings: prefixo env `INTEGRATOR_*` — ver `integrator/config.py`, `config/integrator.example.env`
- Account IDs: `^[a-z][a-z0-9_-]{0,31}$`; entrada normalizada com `.strip().lower()`
- Superfície MCP: **12** Google (LangChain) + **13** Gmail extra + **1** Calendar extra + **5** Contacts extra + **40** WhatsApp; `validate.sh` asserta **71** total
- Confirmação: envio/edição/apagar (Gmail e WhatsApp) — ver `get_confirm_required_tools()` em `integrator/security/policy.py`
- Erros MCP: prefixo `[integrator]` em `integrator/mcp/server.py`
- Nunca commitar `credentials/`, `data/`, `.env`; tokens fora do contexto do LLM
- Código em inglês; docs/CLI em português — seguir estilo existente no módulo tocado
- `from __future__ import annotations` nos módulos `integrator/`

## Arquivos críticos

| Área | Caminho |
|------|---------|
| MCP | `integrator/mcp/server.py` |
| Tools | `integrator/providers/tools.py`, `google_tools.py`, `whatsapp_tools.py` |
| WhatsApp | `integrator/whatsapp/`, `bridges/whatsapp-neonize/`, `docs/WHATSAPP.md` |
| Segurança | `integrator/security/policy.py` |
| Contas | `integrator/accounts/registry.py` |
| Config | `integrator/config.py` |

## Memória do projeto

- Ler `.memory/active.md` no início de tarefas amplas
- Decisões estáveis: `.memory/decisions.md`; padrões: `.memory/patterns.md`
- Ao concluir trabalho relevante: atualizar `active.md`; promover decisões estáveis para `decisions.md`
- Manutenção: `.memory/README.md`

## Cursor (IDE)

- Regras versionadas: `.cursor/rules/` (`project.mdc`, `python-integrator.mdc`)
- Não versionar: `.cursor/hooks/state/`

## Referências

- Onboarding: `./setup.sh` ou `integrator init` (preferir sobre fluxo manual)
- Hermes: `integrator hermes doctor` → `integrator hermes setup`
- Arquitetura: `docs/PLANO_LANGCHAIN_HERMES.md`
- CLI: `docs/CLI.md`
- Hermes YAML ref: `config/hermes.example.yaml`
- Implantação: `docs/ATIVIDADES_IMPLANTACAO.md`

## Learned User Preferences

- Onboarding: `./setup.sh` → `integrator init`; operação diária via admin (`./setup.sh admin` após `serve-http` local ou URL Coolify)
- Texto de CLI/docs para o usuário em português; código do pacote `integrator/` em inglês
- Após mudanças no código MCP do integrador: um `/reload-mcp` no Hermes ou conversa nova (não repetir init completo)
- Integração na `main`: push direto em `main` quando o trabalho estiver validado (sem PR, salvo pedido explícito); rebase ao atualizar `main` quando pedir commit/pull
- Após correções integrador/WhatsApp: `./scripts/validate.sh`, atualizar docs/README se contagens ou comportamento mudaram, push `main`, redeploy Coolify se ativo, apagar branches feature já mergeadas
- Produção: Coolify (`https://mcp.peralles.com/admin`); um processo SSE por sessão WhatsApp (lock `worker.lock`)
- Comandos operacionais (`status`, `login`, `whatsapp`, `hermes`, `logs`) foram **removidos** da CLI — use o console admin
- Pareamento WhatsApp e Google OAuth no console admin (`/admin`); credencial OAuth Google via upload de `client_secret.json` no navegador (sem import `~/Downloads` em Docker/Coolify); Hermes não faz QR
- Deploy remoto (Coolify): admin web para Google/WhatsApp/Ferramentas/Logs; agentes Hermes/Claude Desktop no Mac via `./scripts/setup-local-agents.sh`, não pelo admin remoto
- Se `~/.hermes/config.yaml` já aponta para MCP remoto/local: não refazer setup — `uv sync` + `/reload-mcp` basta
- Hermes + Claude no Mac (SSE remoto Coolify): `./scripts/setup-local-agents.sh` com `INTEGRATOR_SSE_URL` (senha URL-encoded); não usar subcomando CLI `integrator hermes` (removido)

## Learned Workspace Facts

- Hermes doc padrão: MCP **stdio**; WhatsApp persistente: **HTTP/SSE** (`serve-http` / Docker) — um worker neonize; agentes locais via `./scripts/setup-local-agents.sh` (`hermes_setup`/`hermes_doctor` Python, não CLI `integrator hermes`)
- Console admin **`http://127.0.0.1:17320/admin`** (local) ou **`https://mcp.peralles.com/admin`** (Coolify); menu **Painel · Google · WhatsApp · Ferramentas · Logs · Guia** (Guia = `docs/ADMIN_OPERACAO.md`); deploy/persistência **`docs/COOLIFY.md`**
- CLI bootstrap: `init`, `serve`, `serve-http`, `service` — operação diária só via admin web; mudanças na UI admin → `./scripts/build-admin.sh` (ou `./scripts/validate.sh`)
- Deploy produção **Coolify** (`https://mcp.peralles.com`): env `INTEGRATOR_ADMIN_PASSWORD`, `INTEGRATOR_ALLOWED_HOSTS`, `INTEGRATOR_OAUTH_PUBLIC_BASE_URL`, `INTEGRATOR_SERVICE_HOST=0.0.0.0`; volume `/app/data`; Basic Auth em `/admin`, `/sse`, `/mcp`; health `GET /health` sem auth
- Schemas MCP: inline de `$ref`/`$defs` antes de expor tools (evita `PointerToNowhere` no Hermes)
- Diagnóstico Hermes+integrador: `~/.hermes/logs/mcp-stderr.log`, `agent.log`; `/reload-mcp` pode parecer lento; falhas no admin → Logs ou `data/logs/errors.log`
- WhatsApp (MVP): **neonize** em worker isolado `bridges/whatsapp-neonize/` (protobuf 7.x; venv principal em protobuf 6); sessão `data/whatsapp/`; em Docker `read_only` lançar com `bridges/whatsapp-neonize/.venv/bin/python worker.py` (não `uv run` em runtime); ver `docs/WHATSAPP.md`
- Hermes: **um** `mcp_servers.langchain-integrator` — **71 tools** (12 Google + 13 Gmail extra + 1 Calendar + 5 Contacts + 40 WhatsApp); sem segundo MCP nem Evolution HTTP no MVP; Contacts exige **People API** ativa no GCP + reconectar OAuth (scope `contacts`)
- Tools WhatsApp: usar `display_name`/`phone`/`chat_display_name` (não JIDs `@lid` crus; `chat_id` só follow-up); `find_whatsapp_chats` sem `query` lista recentes; com telefone/nome usa `bridges/whatsapp-neonize/chat_search.py` (dígitos normalizados, cache `@lid`, reidratação pós-restart do cache SQLite); query ≥10 dígitos sem match local retorna candidato sintético `{digits}@s.whatsapp.net`
- `serve` stdio e SSE compartilham `data/whatsapp/worker.lock` — só uma instância neonize por sessão
- `INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE=true` transcreve no worker MCP; `serve-http` warm-connecta na subida; hot-reload em `data/admin/runtime.json` (ex.: `transcribe_ignore_numbers`); `TRANSCRIBE_PRIVATE_ONLY=true` ignora `@g.us`; `TRANSCRIBE_ONLY_INCOMING=false` transcreve enviados e recebidos em privado
- **Configurar MCP** no Mac: admin web (serviço local) ou `./scripts/setup-local-agents.sh` (SSE remoto Coolify) — grava `~/.hermes/config.yaml` e Claude Desktop (`claude_desktop_config.json`); após setup Claude, reiniciar o app (⌘Q); Google OAuth web redirect `/admin/oauth/google/callback` (PKCE `code_verifier` persistido entre start/callback)
