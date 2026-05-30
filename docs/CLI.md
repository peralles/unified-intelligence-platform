# CLI — `integrator`

> **Operadores:** use o [console admin](ADMIN.md) em `http://127.0.0.1:17320/admin` (`./setup.sh admin`).  
> A CLI abaixo é **legado / CI** — ative com `INTEGRATOR_CLI_LEGACY=true` se um comando redirecionar ao admin.

CLI única, focada em **bootstrap** (`init`, `serve`, `service`) e suporte a **várias contas Google** (Gmail + Calendar no mesmo login).

## Comandos

| Comando | Descrição |
|---------|-----------|
| `integrator init` | Assistente guiado: deps, Google OAuth, login, Hermes MCP |
| `integrator status` | Contas, tokens, escopos |
| `integrator login <id>` | OAuth no navegador (Gmail + Calendar) |
| `integrator accounts` | Listar contas |
| `integrator use <id>` | Definir conta padrão |
| `integrator logout <id>` | Remover conta e token |
| `integrator whatsapp status` | Situação WhatsApp (rápido; `--live` consulta worker) |
| `integrator whatsapp configure` | Variáveis e caminhos da sessão |
| `integrator whatsapp pair` | Parear ou reconfigurar (QR no terminal) |
| `integrator whatsapp remove` | Apagar sessão local (`-y` sem confirmação) |
| `integrator whatsapp disconnect` | Encerrar worker em memória (sem apagar sessão) |
| `integrator tools` | Listar 21 tools MCP (12 Google + 9 WhatsApp) |
| `integrator hermes doctor` | Pré-requisitos Hermes + integrador |
| `integrator hermes setup` | Gravar `mcp_servers` em `~/.hermes/config.yaml` |
| `integrator serve` | Servidor MCP stdio (Hermes inicia o processo) |
| `integrator serve-http` | Servidor HTTP/SSE local (background) |
| `integrator service …` | **macOS:** LaunchAgent (instalar/ativar/desativar) |
| `integrator logs` | Logs rotativos + diagnóstico de falhas |

## Logs (rotativos)

Arquivos em `data/logs/`:

| Arquivo | Conteúdo |
|---------|----------|
| `integrator.log` | Operação geral (INFO+) |
| `errors.log` | WARNING e erros com stack trace |
| `audit.jsonl` | Invocações de tools (JSON, sem PII) |

Rotação automática (padrão 5 MB, backups numerados `.1`, `.2`, …).

**Performance:** escrita em **fila assíncrona** (não bloqueia tools). Por padrão, **sucesso não grava audit** — só falhas (`INTEGRATOR_AUDIT_LOG_SUCCESS=false`).

```bash
integrator logs                    # lista arquivos + resumo de falhas
integrator logs --failures         # últimas falhas de tools
integrator logs --tail             # final do integrator.log
integrator logs --tail --errors    # final do errors.log
```

Variáveis: `INTEGRATOR_LOG_LEVEL`, `INTEGRATOR_LOG_MAX_BYTES`, `INTEGRATOR_AUDIT_LOG_BACKUP_COUNT` (ver `config/integrator.example.env`).

Aliases legados: `integrator-auth` → `integrator login`, `integrator-serve` → `integrator serve`.

## Configuração guiada (`init`)

Fluxo recomendado para quem não quer editar YAML nem copiar arquivos à mão:

```bash
uv run integrator init
uv run integrator init -y              # sem perguntas
uv run integrator init --account trabalho
uv run integrator init --verbose
```

O assistente abre o navegador no Google Cloud, detecta `credentials.json` (pasta do projeto ou Downloads), executa login OAuth no navegador e grava o MCP no Hermes.

Não automatiza: instalação do binário Hermes (abre o link e espera), chaves de modelo do LLM no Hermes.

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

## Hermes (auto-configuração)

```bash
uv run integrator hermes doctor
uv run integrator hermes setup              # stdio (padrão)
uv run integrator hermes setup --mode sse   # após service install
uv run integrator hermes setup --dry-run
uv run integrator hermes setup --yes        # sobrescrever entrada existente
```

Não automatiza: Google Cloud + `credentials.json`, `integrator login`, instalação do binário Hermes, chaves de modelo. Após `setup`: nova sessão ou `/reload-mcp`.

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
