# Console Admin — operação local

Interface web em **`http://127.0.0.1:17320/admin`** (mesmo host/porta do `serve-http` / LaunchAgent). Substitui a CLI para operadores: Google, WhatsApp, Hermes, serviço macOS, config e logs.

## Pré-requisito

O servidor HTTP precisa estar rodando:

```bash
uv run integrator service install   # macOS — recomendado (persistente)
# ou
uv run integrator serve-http          # terminal aberto
```

Abrir painel:

```bash
./setup.sh admin
```

## Seções do painel

| Seção | Equivalente CLI legado |
|-------|-------------------------|
| **Instalação** | `integrator init`, sync deps, credenciais Google |
| **Google** | `login`, `accounts`, `use`, `logout` |
| **WhatsApp** | `whatsapp pair` (QR no browser), `remove`, `disconnect` |
| **Serviço macOS** | `integrator service …` |
| **Hermes** | `hermes doctor`, `hermes setup` |
| **Config** | `.env` + runtime (ignore transcrição, flags WhatsApp) |
| **Tools** | `integrator tools` (66 tools MCP) |
| **Logs / falhas** | `integrator logs --failures`, tail de logs |

## Runtime (hot reload)

Arquivo: `data/admin/runtime.json` (ou `INTEGRATOR_ADMIN_RUNTIME_FILE`).

Campos usados hoje:

- `whatsapp.transcribe_ignore_numbers` — números ignorados na auto-transcrição (recarrega no worker sem reiniciar).

## Segurança

- Só escuta em **127.0.0.1** por padrão — não expor na rede sem firewall.
- Sem autenticação HTTP: uso **local** na máquina do operador.

## CLI ainda necessária

| Comando | Motivo |
|---------|--------|
| `integrator serve` | Hermes stdio spawn |
| `integrator serve-http` | Sobe admin + MCP SSE |
| `integrator service …` | Instalar LaunchAgent antes do admin |
| `integrator init` | Bootstrap sem serviço (`./setup.sh`) |

Demais comandos operacionais redirecionam para o admin, salvo `INTEGRATOR_CLI_LEGACY=true` (scripts, CI, desenvolvedores).

## Hermes + WhatsApp persistente

1. `integrator service install` — um worker neonize, MCP SSE, admin.
2. Admin → Hermes → **setup modo SSE** (ou `hermes setup --mode sse` com legacy CLI).
3. No Hermes: `/reload-mcp` após mudanças no integrador.
4. **Não** usar `watch-service` junto com o serviço SSE (lock `data/whatsapp/worker.lock`).

Ver também: [WHATSAPP.md](WHATSAPP.md), [CLI.md](CLI.md) (referência legado).
