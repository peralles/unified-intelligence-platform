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
- Superfície MCP: **12** Google (LangChain) + **13** Gmail extra + **1** Calendar extra + **40** WhatsApp; `validate.sh` asserta **66** total
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

- Onboarding para operadores não técnicos: `./setup.sh` (delega ao wizard `integrator init`); operação diária via `./setup.sh admin` após `integrator service install`
- Texto de CLI/docs para o usuário em português; código do pacote `integrator/` em inglês
- Após mudanças no código MCP do integrador: um `/reload-mcp` no Hermes ou conversa nova (não repetir init completo)
- Push para `main` com rebase quando o usuário pedir commit/pull explicitamente
- Comandos operacionais (`status`, `login`, `whatsapp`, `hermes`, `logs`) foram **removidos** da CLI — use o console admin
- Pareamento WhatsApp e Google OAuth no console admin (`/admin`); Hermes não faz QR
- Se `~/.hermes/config.yaml` já aponta para este repo: não refazer `integrator hermes setup` — `uv sync` + `/reload-mcp` basta
- Hermes como agente com WhatsApp (tools + auto-transcrição): serviço SSE persistente (`integrator service` + `hermes setup --mode sse`); parar `watch-service` — evita conflito de lock

## Learned Workspace Facts

- Hermes doc padrão: MCP **stdio**; WhatsApp persistente (tools + auto-transcrição): **`integrator service`** (SSE `127.0.0.1:17320`) + `integrator hermes setup --mode sse` — um worker neonize, Hermes só conecta
- Console admin local **`http://127.0.0.1:17320/admin`** no `serve-http`/LaunchAgent — Google, WhatsApp (QR), Hermes, serviço macOS, config, logs; ver `docs/ADMIN.md`
- CLI bootstrap: `init`, `serve`, `serve-http`, `service` — operação diária só via admin web
- `/reload-mcp` no Hermes pode parecer lento (discovery de plugins, `mcp_reload_confirm`); o integrator sozinho sobe em ~1s
- Schemas MCP: inline de `$ref`/`$defs` antes de expor tools (evita `PointerToNowhere` no Hermes)
- Diagnóstico Hermes+integrador: `~/.hermes/logs/mcp-stderr.log`, `agent.log`; falhas de tools no admin → Logs ou `data/logs/errors.log`
- WhatsApp (MVP): **neonize** em worker isolado `bridges/whatsapp-neonize/` (protobuf 7.x; venv principal fica em protobuf 6 por `langchain-google-community`); sessão `data/whatsapp/`; ver `docs/WHATSAPP.md`
- Hermes: **um** `mcp_servers.langchain-integrator` — **66 tools** (12 Google + 13 Gmail extra + 1 Calendar + 40 WhatsApp); sem segundo MCP nem Evolution HTTP no MVP
- Tools WhatsApp expõem `display_name`/`phone`/`chat_display_name` — agente deve usar esses rótulos, não JIDs `@lid` crus (`chat_id` só para follow-up técnico)
- `find_whatsapp_chats` sem `query` lista chats recentes (fallback para `list_chats`; evita erro quando o modelo omite filtro)
- `watch-service`, `serve` stdio e SSE compartilham `data/whatsapp/worker.lock` — só uma instância neonize por sessão; não reativar watch com serviço SSE ativo
- `INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE=true` transcreve no worker MCP; `serve-http` warm-connecta na subida; hot-reload em `data/admin/runtime.json` (ex.: `transcribe_ignore_numbers`); `TRANSCRIBE_PRIVATE_ONLY=true` ignora `@g.us`; `TRANSCRIBE_ONLY_INCOMING=false` transcreve enviados e recebidos em privado
