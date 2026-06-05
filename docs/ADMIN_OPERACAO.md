# Guia de operação — console admin

Este integrador roda no servidor (Coolify/Docker). O console web administra **Google**, **WhatsApp** e **política de ferramentas**. Agentes de IA (Hermes, Claude Desktop) configuram-se **no seu computador**, não pelo admin remoto.

## O que fazer aqui (admin)

| Tarefa | Menu |
|--------|------|
| Ver saúde geral | **Painel** |
| OAuth + contas Google | **Google** |
| Parear WhatsApp + transcrição de áudio | **WhatsApp** |
| Allowlist/denylist de tools MCP | **Ferramentas** |
| Logs e nível de log | **Logs** |

### Persistência (volume `/app/data`)

Sem volume persistente, cada redeploy apaga sessão WhatsApp e tokens Google. O **Painel** avisa se `/app/data` não estiver montado.

Backup recomendado:

- `/app/data/whatsapp/` — sessão neonize
- `/app/data/tokens/` — tokens OAuth

### Google

1. No Google Cloud: credencial OAuth **Web** com redirect  
   `https://SEU-DOMINIO/admin/oauth/google/callback`
2. Env no Coolify: `INTEGRATOR_OAUTH_PUBLIC_BASE_URL=https://SEU-DOMINIO`
3. No admin → **Google**: arraste `client_secret.json`, clique para enviar pelo navegador, ou cole o JSON
4. **Conectar nova conta** → autorize no navegador

### WhatsApp

1. **WhatsApp** → **Iniciar pareamento (QR)**
2. No celular: Dispositivos conectados → Adicionar dispositivo
3. Ative **transcrição automática** na mesma tela (modelo `small` ou `large-v3-turbo` em CPU)
4. Números ignorados: um por linha, só dígitos

Reiniciar conexão ≠ apagar sessão. **Apagar sessão local** exige novo QR.

## Agentes no seu PC (VPN / remoto)

O admin **não** configura Hermes nem Claude quando o servidor está atrás de VPN. Use o script na máquina onde rodam os agentes:

```bash
git clone <este-repositorio>
cd unified-intelligence-platform
./scripts/setup-local-agents.sh
```

Informe a URL SSE pública do servidor, por exemplo:

```text
https://USUARIO:SENHA@mcp.seudominio.com/sse
```

(use as mesmas credenciais de `INTEGRATOR_ADMIN_USERNAME` / `INTEGRATOR_ADMIN_PASSWORD`)

Equivalente manual:

```bash
uv sync --all-extras
uv run integrator hermes setup --mode sse --sse-url 'https://...' --yes --force
```

Depois:

- **Hermes:** conversa nova ou `/reload-mcp`
- **Claude Desktop:** sair completamente (⌘Q) e reabrir

## Ferramentas MCP

66 tools (Google + Gmail extra + Calendar + WhatsApp). Em **Ferramentas** você vê a lista e define allowlist/denylist e confirmação para envio/apagar.

## Logs

- `integrator.log` — operação geral
- `errors.log` — falhas
- **Falhas de auditoria** — tools bloqueadas ou com erro

Use **Copiar** para colar no suporte. Eventos estruturados: ver `docs/LOGGING.md`.

## Variáveis úteis (Coolify)

```env
INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE=true
INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL=small
INTEGRATOR_WHATSAPP_TRANSCRIBE_LANGUAGE=pt
INTEGRATOR_ADMIN_USERNAME=...
INTEGRATOR_ADMIN_PASSWORD=...
INTEGRATOR_OAUTH_PUBLIC_BASE_URL=https://mcp.seudominio.com
INTEGRATOR_ALLOWED_HOSTS=mcp.seudominio.com
```

Mais detalhes: `docs/COOLIFY.md`, `docs/DOCKER.md`.
