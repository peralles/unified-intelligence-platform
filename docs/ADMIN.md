# Console Admin — operação

Interface web no mesmo processo que `serve-http` (local ou Docker/Coolify).

| Ambiente | URL |
|----------|-----|
| Dev local | `http://127.0.0.1:17320/admin` |
| Coolify | `https://SEU-DOMINIO/admin` |

Substitui comandos operacionais da CLI: Google, WhatsApp, Hermes, config e logs.

## Pré-requisito

Servidor HTTP ativo:

```bash
uv run integrator serve-http          # dev local (terminal aberto)
# ou deploy Coolify / docker compose up
```

Abrir painel local:

```bash
./setup.sh admin
```

## UI (Vite)

Código fonte: `integrator/admin/ui/`. Build obrigatório antes de validar/deploy:

```bash
./scripts/build-admin.sh
```

Saída: `integrator/admin/static/dist/` (servida em `/admin`).

Dev com proxy para API:

```bash
cd integrator/admin/ui && npm run dev
```

## Seções do painel

| Seção | Função |
|-------|--------|
| **Instalação** | sync deps, credenciais Google (upload JSON) |
| **Google** | login OAuth web, contas, logout |
| **WhatsApp** | pareamento QR, remove, disconnect |
| **Hermes** | doctor, setup MCP (stdio ou SSE) |
| **Claude Desktop** | Configurar MCP (SSE) |
| **Config** | `.env` / runtime (ignore transcrição, flags WhatsApp) |
| **Tools** | lista 71 tools MCP |
| **Logs / falhas** | tail e falhas de audit |

## Runtime (hot reload)

Arquivo: `data/admin/runtime.json` (ou `INTEGRATOR_ADMIN_RUNTIME_FILE`).

Campos usados hoje:

- `whatsapp.transcribe_ignore_numbers` — números ignorados na auto-transcrição (recarrega no worker sem reiniciar).

## Segurança

- **Local:** escuta `127.0.0.1` por padrão — sem auth HTTP.
- **Produção:** defina `INTEGRATOR_ADMIN_USERNAME` + `INTEGRATOR_ADMIN_PASSWORD` e `INTEGRATOR_ALLOWED_HOSTS`.

## CLI ainda necessária

| Comando | Motivo |
|---------|--------|
| `integrator serve` | Hermes stdio spawn |
| `integrator serve-http` | Sobe admin + MCP SSE (dev) |
| `integrator init` | Bootstrap (`./setup.sh`) |

Demais operações estão **somente** no admin web.

## Hermes + WhatsApp persistente

1. Deploy SSE (Coolify) ou `integrator serve-http` local — um worker neonize, MCP SSE, admin.
2. Admin → Hermes → **setup modo SSE** (URL pública ou `127.0.0.1:17320`).
3. No Hermes: `/reload-mcp` após mudanças no integrador.
4. **Não** rodar dois processos com a mesma sessão WhatsApp (lock `data/whatsapp/worker.lock`).

## Google OAuth (Coolify)

1. Credencial **Web application** no Google Cloud.
2. Redirect URI: `https://SEU-DOMINIO/admin/oauth/google/callback`
3. Admin → Google → upload JSON (grava em `/app/data/credentials/` no volume).

Ver também: [WHATSAPP.md](WHATSAPP.md), [CLI.md](CLI.md), [COOLIFY.md](COOLIFY.md).
