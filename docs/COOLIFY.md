# Coolify — deploy e persistência

Guia para rodar o integrator em produção no [Coolify](https://coolify.io) com domínio público (ex.: `mcp.peralles.com`).

## Visão geral

| Item | Valor recomendado |
|------|-------------------|
| Build | Dockerfile na raiz do repositório |
| Porta interna | `17320` |
| Admin | `https://SEU-DOMINIO/admin` |
| MCP (Hermes SSE) | `https://SEU-DOMINIO/sse` |
| Dados persistentes | **`/app/data`** (volume obrigatório) |
| OAuth client JSON | **`/app/credentials/credentials.json`** (read-only) |

Sem volume em `/app/data`, cada redeploy apaga sessão WhatsApp, tokens Google e logs.

O admin mostra alerta no **Painel** e em **Serviço** quando `/app/data` não é mount Docker (`INTEGRATOR_SKIP_MACOS_SERVICE=1`). Após configurar o volume, o banner some no próximo refresh.

## Persistência no Coolify

O container usa `read_only: true`; apenas volumes montados permanecem graváveis.

### Opção A — Docker Compose no Coolify

Se o recurso usa o `docker-compose.yml` do repositório, o volume nomeado `integrator_data` já mapeia `/app/data`. Confirme no Coolify que o compose foi importado e que o volume não foi removido entre deploys.

### Opção B — Aplicação Dockerfile (sem compose)

No painel do app → **Storages** (ou **Persistent Storage**):

1. **Type:** `persistent` (volume Docker nomeado)
2. **Mount path:** `/app/data`
3. **Name:** `integrator-data` (Coolify acrescenta UUID do recurso)

Opcional — credencial OAuth (se não embutir no build):

| Mount path | Tipo | Conteúdo |
|------------|------|----------|
| `/app/credentials/credentials.json` | file | JSON OAuth Web do Google Cloud |

### Opção C — Bind mount (servidor único)

Só se você controla o host e faz backup do diretório:

- **Source path (host):** ex. `/var/lib/integrator/data`
- **Destination path:** `/app/data`

Evite bind mount em path que o Coolify recria a cada deploy — use **volume nomeado**.

### Backup

Copie periodicamente o volume (WhatsApp + tokens):

```bash
docker run --rm -v COOLIFY_VOLUME_NAME:/data -v $(pwd):/backup alpine \
  tar czf /backup/integrator-data-$(date +%F).tar.gz -C /data .
```

Restaurar: extrair no volume antes de subir o container.

## Variáveis de ambiente (Coolify UI)

Copie de `config/integrator.docker.env`. Mínimo para produção:

```env
INTEGRATOR_ADMIN_USERNAME=admin
INTEGRATOR_ADMIN_PASSWORD=<senha-forte>

# DNS rebinding / MCP — domínio público SEM https://
INTEGRATOR_ALLOWED_HOSTS=mcp.peralles.com

# OAuth redirect — URL pública COM https://
INTEGRATOR_OAUTH_PUBLIC_BASE_URL=https://mcp.peralles.com

INTEGRATOR_SKIP_MACOS_SERVICE=1

# VPS pequena (CPU): small ~1 GB RAM; large-v3-turbo ~3 GB
INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE=false
INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL=small
```

## Google OAuth (admin no browser)

1. Google Cloud → Credenciais → **OAuth client ID** tipo **Web application**.
2. **Authorized redirect URIs:**  
   `https://SEU-DOMINIO/admin/oauth/google/callback`
3. Envie o JSON via Admin → Google → colar JSON, ou monte em `/app/credentials/credentials.json`.
4. No admin, **Conectar conta** redireciona para Google na mesma aba e volta ao admin com `?oauth=ok`.

Não use fluxo Desktop (`run_local_server`) no container — não há browser local.

## WhatsApp

Pareamento pelo admin (`/admin` → WhatsApp). Sessão fica em `/app/data/whatsapp/`. Sem volume, novo QR a cada deploy.

## LaunchAgent local (Mac)

Se produção é só Coolify, **desinstale** o LaunchAgent no Mac:

```bash
uv run integrator service uninstall
```

Dois processos (Mac + Coolify) disputam `worker.lock` e quebram WhatsApp.

## CI e deploy

- GitHub Actions roda `./scripts/validate.sh` em push/PR para `main`.
- Coolify redeploy após push na branch configurada; não substitui testes locais/CI.

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| MCP/Hermes recusa host | `INTEGRATOR_ALLOWED_HOSTS` vazio ou errado | Definir domínio exato |
| Google OAuth `redirect_uri_mismatch` | URI no Google ≠ URL pública | Conferir `INTEGRATOR_OAUTH_PUBLIC_BASE_URL` |
| WhatsApp despareado após deploy | Sem volume `/app/data` | Adicionar Persistent Storage |
| Admin trava no QR | Worker lock duplo | Parar LaunchAgent local |
| OOM na transcrição | Modelo grande em VPS pequena | `TRANSCRIBE_MODEL=small` ou desligar auto-transcrição |

Ver também [DOCKER.md](./DOCKER.md).
