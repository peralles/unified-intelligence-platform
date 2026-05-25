# Integrador LangChain → Hermes

Servidor **MCP local** (Python) que expõe as **12 ferramentas oficiais** LangChain de **Gmail** e **Google Calendar**, com OAuth Google unificado e **várias contas**, para o agente [Hermes](https://dev.to/emmanuelthecoder/hermes-the-self-improving-agent-you-can-actually-run-yourself-555l).

| Item | Valor |
|------|--------|
| Pacote | `langchain-hermes-integrator` v0.1.0 |
| Python | ≥ 3.11 (recomendado 3.12, ver `.python-version`) |
| Gerenciador | [uv](https://docs.astral.sh/uv/) |
| Transporte MCP | **stdio** (Hermes spawn) ou **HTTP/SSE** (serviço macOS) |
| Porta HTTP padrão | `17320` |

## Por que Python

Os toolkits `GmailToolkit` e `CalendarToolkit` estão em `langchain-google-community`, mantidos em **Python**. A variante JS não cobre o mesmo fluxo OAuth + tools; este repo delega auth e execução ao LangChain e expõe só MCP.

## Estrutura do projeto

```
integrator/           # Pacote principal
  cli/                # CLI integrator
  mcp/                # Servidor MCP (stdio + HTTP/SSE)
  providers/          # Bridge LangChain → MCP (12 tools)
  auth/               # OAuth Google
  accounts/           # Registry multi-conta
  security/           # Allow/deny, confirm, audit
  service/            # LaunchAgent macOS
config/               # Exemplos Hermes + env
credentials/          # OAuth client (gitignored)
data/                 # tokens, accounts.yaml, logs (gitignored)
tests/
scripts/validate.sh   # ruff + pytest + smokes
```

## Requisitos

1. [uv](https://docs.astral.sh/uv/) instalado
2. Projeto Google Cloud com **OAuth client ID (Desktop)** → `credentials/credentials.json`
3. Escopos Gmail + Calendar (configurados no integrador; ver `integrator/config.py`)

## Começar em 1 comando (recomendado)

Depois de clonar o repositório:

```bash
cd unified-intelligence-platform
uv run integrator init
```

O assistente:

1. Instala dependências (`uv sync`) se precisar
2. Abre o **Google Cloud** no navegador (APIs + credencial OAuth) e **espera** o arquivo JSON (também detecta na pasta Downloads)
3. Abre o navegador para você **autorizar** Gmail e Agenda
4. Configura o **Hermes** automaticamente (`~/.hermes/config.yaml`)

No final: abra o Hermes e use `/reload-mcp` ou uma conversa nova. Modelo de IA do Hermes: `hermes model` (se ainda não configurou).

```bash
uv run integrator init --yes      # sem perguntas, só executa o que faltar
uv run integrator init --verbose  # mostra caminhos técnicos
```

## Instalação manual (avançado)

```bash
git clone <repo>
cd unified-intelligence-platform
uv sync --all-extras
```

Comandos disponíveis após o sync:

- `integrator` — CLI principal
- `integrator-auth` — alias de `integrator login`
- `integrator-serve` — alias de `integrator serve`

### Configuração passo a passo

```bash
# credentials.json em credentials/ (ver integrator init para fluxo guiado)
uv run integrator login pessoal
uv run integrator hermes doctor
uv run integrator hermes setup
uv run integrator status
```

Opcional: copie `config/integrator.example.env` para `.env` para política Fase 2 e logging.

---

## CLI — referência completa

A CLI é única (`integrator`). Gmail e Calendar entram no **mesmo** `login` por conta.

```bash
uv run integrator --help
uv run integrator <comando> --help   # quando existir subcomandos
```

### Resumo de comandos

| Comando | Descrição |
|---------|-----------|
| `integrator init` | Assistente guiado (Google + Hermes) |
| `integrator status` | Escopos, contas, tokens, paths de logs |
| `integrator login [id]` | OAuth no navegador (Gmail + Calendar) |
| `integrator accounts` | Listar contas registradas |
| `integrator accounts --default <id>` | Definir conta padrão (alternativa a `use`) |
| `integrator use <id>` | Atalho para definir conta padrão |
| `integrator logout <id>` | Remover conta e apagar token |
| `integrator tools` | Listar as 12 tools expostas ao MCP |
| `integrator hermes doctor` | Verificar pré-requisitos (integrador + Hermes) |
| `integrator hermes setup` | Gravar MCP em `~/.hermes/config.yaml` automaticamente |
| `integrator serve` | Servidor MCP **stdio** (Hermes inicia o processo) |
| `integrator serve-http` | Servidor MCP **HTTP/SSE** em primeiro plano |
| `integrator logs` | Listar arquivos de log + resumo de falhas |
| `integrator service <ação>` | **macOS:** LaunchAgent (install/start/…) |

### `status`

Visão geral: escopos Google, caminho do OAuth client, contas (`*` = padrão), estado do token, e-mail se conhecido, paths de `integrator.log`, `errors.log`, `audit.jsonl`.

```bash
uv run integrator status
```

### `login` — conectar conta Google

Abre o navegador (InstalledAppFlow), grava token em `data/tokens/<id>.json` e atualiza `data/accounts.yaml`.

```bash
uv run integrator login pessoal
uv run integrator login profissional --label "Trabalho"
uv run integrator login profissional -l Trabalho   # alias -l
```

| Situação | Comportamento |
|----------|----------------|
| Sem contas | Usa id `pessoal` automaticamente |
| Uma conta, sem `id` | Reautentica essa conta |
| Várias contas, sem `id` | Erro — informe o `id` |
| `id` informado | Normalizado para minúsculas (`Profissional` → `profissional`) |

**IDs válidos:** `^[a-z][a-z0-9_-]{0,31}$` (ex.: `pessoal`, `profissional`, `trabalho-01`).

### `accounts` e `use`

```bash
uv run integrator accounts
uv run integrator accounts --default profissional
uv run integrator use profissional    # equivalente ao --default
```

### `logout`

Remove a entrada do registry e apaga `data/tokens/<id>.json`.

```bash
uv run integrator logout profissional
```

### `tools`

Lista os nomes MCP das 12 tools LangChain e as contas disponíveis para o parâmetro `account`.

```bash
uv run integrator tools
```

### `serve` — MCP stdio (recomendado com Hermes)

Bloqueia no terminal; o Hermes faz spawn via `command` + `args` no `config.yaml`. Não use em background manual para o fluxo Hermes padrão.

```bash
uv run integrator serve
```

### `serve-http` — MCP HTTP/SSE

Sobe Uvicorn com endpoints SSE/MCP. Útil para testes ou quando o processo roda separado do Hermes.

```bash
uv run integrator serve-http
uv run integrator serve-http --host 127.0.0.1 --port 18000
```

Padrões: host `127.0.0.1`, porta `17320` (`INTEGRATOR_SERVICE_HOST` / `INTEGRATOR_SERVICE_PORT`).

### `logs` — diagnóstico

Arquivos em `data/logs/` (rotação ~5 MB, backups `.1`, `.2`, …):

| Arquivo | Conteúdo |
|---------|----------|
| `integrator.log` | Operação geral (INFO+) |
| `errors.log` | WARNING+ com stack trace |
| `audit.jsonl` | Invocações de tools (JSON, **sem PII**) |

Escrita em fila assíncrona. Por padrão o audit **não** registra sucesso (`INTEGRATOR_AUDIT_LOG_SUCCESS=false`).

```bash
uv run integrator logs                      # lista arquivos + últimas 5 falhas
uv run integrator logs --failures           # falhas no audit.jsonl
uv run integrator logs --failures -n 100  # mais linhas (-n padrão 40)
uv run integrator logs --tail               # final de integrator.log
uv run integrator logs --tail --errors      # final de errors.log
uv run integrator logs --tail -n 80
```

### `service` — macOS LaunchAgent

Mantém o integrador **sempre rodando** em HTTP/SSE (Hermes conecta por URL, não stdio).

```bash
uv run integrator service install              # plist + inicia
uv run integrator service install --no-start   # só grava plist
uv run integrator service install --port 18000
uv run integrator service start                # alias: enable
uv run integrator service stop                 # alias: disable (mantém plist)
uv run integrator service status
uv run integrator service uninstall            # remove plist e para
```

| Detalhe | Valor |
|---------|--------|
| Plist | `~/Library/LaunchAgents/com.peralles.langchain-integrator.plist` |
| SSE | `http://127.0.0.1:17320/sse` |
| Health | `curl http://127.0.0.1:17320/health` |
| Logs do serviço | `data/logs/service/stdout.log`, `stderr.log` |

Fora do macOS o subcomando `service` retorna erro.

### Aliases legados (entry points)

| Alias | Equivalente |
|-------|-------------|
| `integrator-auth` | `integrator login` (+ args) |
| `integrator-serve` | `integrator serve` |

### Exemplos de fluxo (copiar e adaptar)

```bash
# Primeira máquina
uv sync --all-extras
uv run integrator login pessoal
uv run integrator login profissional -l "Trabalho"
uv run integrator use profissional
uv run integrator status
uv run integrator tools

# Hermes stdio (outro terminal só para teste manual)
uv run integrator serve

# macOS: serviço em background
uv run integrator service install
uv run integrator service status

# Depois de erro em tool
uv run integrator logs --failures
uv run integrator logs --tail --errors
```

---

## Integração com Hermes

### Setup automático (recomendado)

Depois de `uv sync`, `credentials/credentials.json` e `integrator login <conta>`:

```bash
uv run integrator hermes doctor          # o que falta (Google, OAuth, uv, Hermes…)
uv run integrator hermes setup           # grava langchain-integrator em ~/.hermes/config.yaml
uv run integrator hermes setup --dry-run # só mostra o YAML
uv run integrator hermes setup --yes     # substituir entrada existente
```

**stdio (padrão):** Hermes faz spawn de `uv run --directory <este-repo> integrator serve`.  
**SSE:** `integrator service install` e depois `integrator hermes setup --mode sse`.

Após o setup: **nova sessão Hermes** ou `/reload-mcp`. Modelo/API do Hermes continua manual (`hermes model`, `~/.hermes/.env`).

Alternativa manual (com UI de tools): `hermes mcp add langchain-integrator --command uv --args …` — fluxo interativo do Hermes.

### Referência YAML (manual)

[`config/hermes.example.yaml`](config/hermes.example.yaml) (stdio) e [`config/hermes.service.example.yaml`](config/hermes.service.example.yaml) (SSE) mostram o mesmo contrato que o `setup` grava.

---

## Múltiplas contas

Cada conta = um login OAuth + um token + Gmail e Calendar juntos.

| Recurso | Caminho |
|---------|---------|
| Tokens | `data/tokens/pessoal.json`, `data/tokens/profissional.json`, … |
| Registry | `data/accounts.yaml` |
| Conta padrão | `integrator use <id>` ou campo no registry |

No Hermes / MCP, em qualquer tool:

```json
{
  "account": "profissional",
  "query": "is:unread"
}
```

Se `account` for omitido, usa a conta padrão do integrador.

---

## Tools MCP (12)

Todas vêm dos toolkits LangChain; nomes estáveis no MCP:

| Tool | Área | Uso típico |
|------|------|------------|
| `create_gmail_draft` | Gmail | Criar rascunho |
| `send_gmail_message` | Gmail | Enviar e-mail (**exige `confirm: true`**) |
| `search_gmail` | Gmail | Buscar mensagens |
| `get_gmail_message` | Gmail | Ler mensagem |
| `get_gmail_thread` | Gmail | Ler thread |
| `create_calendar_event` | Calendar | Criar evento |
| `search_events` | Calendar | Buscar eventos |
| `update_calendar_event` | Calendar | Atualizar evento |
| `get_calendars_info` | Calendar | Listar calendários |
| `move_calendar_event` | Calendar | Mover evento |
| `delete_calendar_event` | Calendar | Apagar evento (**exige `confirm: true`**) |
| `get_current_datetime` | Calendar | Data/hora atual |

Allowlist/denylist pode reduzir a lista exposta ao Hermes (ver Segurança).

---

## Segurança (Fase 2)

| Recurso | Configuração |
|---------|----------------|
| Allowlist | `INTEGRATOR_TOOL_ALLOWLIST` — só essas tools (se definido) |
| Denylist | `INTEGRATOR_TOOL_DENYLIST` — bloqueia tools |
| Confirmação | Padrão: `send_gmail_message`, `delete_calendar_event` precisam de `"confirm": true` nos argumentos |
| Confirmação custom | `INTEGRATOR_CONFIRM_REQUIRED_TOOLS` |
| Auditoria | `data/logs/audit.jsonl` — metadados (tool, conta, duração, erro), **sem** corpo de e-mail/evento |
| Tokens | `chmod 600` em `data/tokens/*.json` após login/refresh |

Exemplo no agente antes de enviar e-mail:

```json
{ "confirm": true, "to": "...", "subject": "...", "body": "..." }
```

`credentials/`, `data/` e `.env` **não** vão para o git. Ver [`config/integrator.example.env`](config/integrator.example.env).

---

## Variáveis de ambiente (`INTEGRATOR_*`)

Prefixo comum: `INTEGRATOR_` (ver `integrator/config.py` e `.env.example`).

| Variável | Efeito |
|----------|--------|
| `INTEGRATOR_CREDENTIALS_FILE` | Caminho do OAuth client JSON |
| `INTEGRATOR_TOKEN_FILE` | Token legado (preferir multi-conta em `data/tokens/`) |
| `INTEGRATOR_TOOL_ALLOWLIST` | Lista CSV de tools permitidas |
| `INTEGRATOR_TOOL_DENYLIST` | Lista CSV de tools bloqueadas |
| `INTEGRATOR_CONFIRM_REQUIRED_TOOLS` | Lista CSV que exige `confirm` |
| `INTEGRATOR_AUDIT_LOG_ENABLED` | Audit JSONL (padrão `true`) |
| `INTEGRATOR_AUDIT_LOG_SUCCESS` | Gravar sucesso no audit (padrão `false`) |
| `INTEGRATOR_AUDIT_LOG_FILE` | Caminho custom do audit |
| `INTEGRATOR_LOG_LEVEL` | Nível do log da app |
| `INTEGRATOR_LOG_MAX_BYTES` | Tamanho antes da rotação |
| `INTEGRATOR_LOG_BACKUP_COUNT` | Backups do integrator.log |
| `INTEGRATOR_AUDIT_LOG_MAX_BYTES` | Rotação do audit |
| `INTEGRATOR_AUDIT_LOG_BACKUP_COUNT` | Backups do audit |
| `INTEGRATOR_LOG_CONSOLE_ENABLED` | Log no stderr |
| `INTEGRATOR_LOG_TOOL_SUCCESS` | Log INFO por tool bem-sucedida |
| `INTEGRATOR_SERVICE_HOST` | Host do `serve-http` / LaunchAgent |
| `INTEGRATOR_SERVICE_PORT` | Porta padrão (17320) |

---

## Desenvolvimento e qualidade

```bash
uv run ruff check integrator tests
uv run pytest -q --tb=short
./scripts/validate.sh    # sync + ruff + pytest + smokes (12 tools, MCP, latência)
```

Relatório detalhado: [`docs/AVALIACAO_QUALIDADE_PERFORMANCE.md`](docs/AVALIACAO_QUALIDADE_PERFORMANCE.md).

Instruções para agentes de código: [`AGENTS.md`](AGENTS.md) (memória persistente em [`.memory/`](.memory/)).

---

## Documentação

| Arquivo | Conteúdo |
|---------|----------|
| [AGENTS.md](AGENTS.md) | Instruções para agentes + `.memory/` |
| [docs/CLI.md](docs/CLI.md) | Referência CLI (espelho resumido) |
| [docs/PLANO_LANGCHAIN_HERMES.md](docs/PLANO_LANGCHAIN_HERMES.md) | Arquitetura e decisões |
| [docs/ATIVIDADES_IMPLANTACAO.md](docs/ATIVIDADES_IMPLANTACAO.md) | Checklist de implantação |
| [docs/FASE2_VALIDACAO.md](docs/FASE2_VALIDACAO.md) | Validação da Fase 2 (segurança) |
| [docs/AVALIACAO_QUALIDADE_PERFORMANCE.md](docs/AVALIACAO_QUALIDADE_PERFORMANCE.md) | Qualidade e performance |
| [config/hermes.example.yaml](config/hermes.example.yaml) | Hermes + MCP stdio |
| [config/hermes.service.example.yaml](config/hermes.service.example.yaml) | Hermes + SSE (serviço) |
| [config/integrator.example.env](config/integrator.example.env) | Variáveis Fase 2 |
