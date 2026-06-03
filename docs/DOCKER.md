# Implantação com Docker — VPS / Coolify

Este guia cobre a execução do Integrator em uma VPS (qualquer distribuição Linux) ou em uma instância do **Coolify**, incluindo transcrição de áudio via CPU.

---

## Visão geral da arquitetura Docker

```
┌─────────────────────────────────────────────────────┐
│  Container: integrator                              │
│                                                     │
│  ┌─────────┐   ┌──────────────┐   ┌─────────────┐  │
│  │ MCP SSE │   │ Admin /admin │   │  WhatsApp   │  │
│  │  :17320 │   │   :17320     │   │  (neonize   │  │
│  └────┬────┘   └──────┬───────┘   │  subprocess)│  │
│       │               │           └─────────────┘  │
└───────┼───────────────┼───────────────────────────-─┘
        │               │
   [Hermes/Claude]   [Navegador via Coolify Proxy]
```

- **Porta 17320**: MCP SSE + console admin (protegido por Basic Auth no modo VPS)
- **Volume `/app/data`**: sessão WhatsApp, tokens Google, logs, config em tempo real
- **Volume `/app/credentials`** (read-only): `credentials.json` do Google OAuth

---

## Pré-requisitos

- Docker Engine 24+ e Docker Compose v2
- (Opcional) Conta no Coolify e acesso a uma VPS ARM64 ou x86_64

---

## Início rápido (docker compose local)

```bash
# 1. Clone o repositório
git clone https://github.com/peralles/unified-intelligence-platform.git
cd unified-intelligence-platform

# 2. Crie o .env a partir do template
cp config/integrator.docker.env .env
# Edite .env e defina INTEGRATOR_ADMIN_PASSWORD e INTEGRATOR_ALLOWED_HOSTS

# 3. Coloque o client_secret.json do Google na pasta credentials/
mkdir -p credentials
# cp ~/Downloads/client_secret_*.json credentials/credentials.json

# 4. Suba o serviço
docker compose up -d

# 5. Acesse o console
open http://localhost:17320/admin
```

---

## Implantação no Coolify

### 1. Prepare o repositório

Certifique-se de que o `Dockerfile` está na raiz do repositório (já está).

### 2. Crie o serviço no Coolify

1. No Coolify, acesse **Projects → New Resource → Docker Compose / Dockerfile**
2. Conecte o repositório GitHub
3. Coolify detectará o `Dockerfile` automaticamente
4. Configure as **Environment Variables**:

| Variável | Valor |
|---|---|
| `INTEGRATOR_ADMIN_USERNAME` | `admin` |
| `INTEGRATOR_ADMIN_PASSWORD` | *(senha forte)* |
| `INTEGRATOR_ALLOWED_HOSTS` | `meuapp.coolify.io` |
| `INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE` | `false` *(ative após parear)* |
| `INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL` | `large-v3-turbo` |
| `INTEGRATOR_LOG_LEVEL` | `INFO` |

5. Configure o **Volume persistente**: `/app/data` → volume nomeado
6. Configure a **porta exposta**: `17320`
7. Habilite **HTTPS** via Coolify (Caddy automático)

### 3. Credenciais Google

No Coolify, você pode injetar o `credentials.json` de duas formas:

- **Arquivo via Volume**: monte `/app/credentials` como volume persistente e faça upload via admin UI
- **Admin UI**: após o primeiro deploy, acesse `/admin` → Google → "Salvar JSON colado" e cole o conteúdo do `client_secret.json`

---

## Transcrição de áudio em CPU

A transcrição usa **faster-whisper** com backend CTranslate2, que funciona eficientemente em qualquer CPU x86_64 ou ARM64.

### Escolha do modelo

| Modelo | RAM estimada | Velocidade (CPU) | Qualidade |
|---|---|---|---|
| `tiny` | ~400 MB | Muito rápida | Baixa |
| `base` | ~500 MB | Rápida | Razoável |
| `small` | ~1 GB | Boa | Boa (recomendado para pt-BR) |
| `large-v3-turbo` | ~3 GB | Moderada | Excelente (padrão) |
| `large-v3` | ~6 GB | Lenta em CPU | Máxima |

**Recomendação para VPS com 2–4 vCPUs**: `small` (rápido) ou `large-v3-turbo` (qualidade).

### Configuração

```env
INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE=true
INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL=large-v3-turbo
INTEGRATOR_WHATSAPP_TRANSCRIBE_LANGUAGE=pt
INTEGRATOR_WHATSAPP_TRANSCRIBE_PRIVATE_ONLY=true
INTEGRATOR_WHATSAPP_TRANSCRIBE_ONLY_INCOMING=false
```

> **Nota**: na primeira mensagem de áudio o modelo é baixado do Hugging Face (~1–6 GB). O download é cacheado em `/app/data` dentro do volume persistente.

---

## Segurança

### Basic Auth

Quando `INTEGRATOR_ADMIN_USERNAME` e `INTEGRATOR_ADMIN_PASSWORD` estão definidos, **todas** as rotas exigem autenticação HTTP Basic — incluindo `/admin`, `/sse`, `/mcp` e `/messages/`. A única exceção é `/health`, usada pelo health check do Docker.

Os agentes de IA (Hermes/Claude) se conectam via SSE com as credenciais embutidas na URL (`http://user:pass@host:port/sse`). O comando `integrator hermes setup --mode sse` configura isso automaticamente.

**Recomendação**: exponha apenas a porta 17320 via proxy reverso com TLS (Coolify faz isso automaticamente). Nunca deixe a porta exposta diretamente sem TLS.

### Hosts permitidos (DNS rebinding protection)

O MCP protocol tem proteção contra DNS rebinding. Configure os domínios permitidos:

```env
INTEGRATOR_ALLOWED_HOSTS=meuapp.coolify.io,meuapp.exemplo.com
```

---

## Arquivos persistentes (Volume `/app/data`)

| Caminho | Conteúdo | Crítico? |
|---|---|---|
| `/app/data/whatsapp/` | Sessão neonize + cache de mensagens | **Sim** (perder = reparear) |
| `/app/data/tokens/` | Tokens OAuth do Google | **Sim** (perder = refazer login) |
| `/app/data/admin/runtime.json` | Config em tempo real | Não (recriado) |
| `/app/data/logs/` | Logs de auditoria e erros | Não (informativo) |

> **Backup**: faça backup periódico de `/app/data/whatsapp/` e `/app/data/tokens/`.

---

## Comandos úteis

```bash
# Ver logs em tempo real
docker compose logs -f integrator

# Reiniciar sem recriar o container
docker compose restart integrator

# Atualizar para nova versão (rebuild)
docker compose pull && docker compose up -d --build

# Entrar no container para diagnóstico
docker compose exec integrator bash

# Verificar saúde
curl http://localhost:17320/health
```

---

## Migrando autenticação Google existente (instalação local → Docker)

Se você já tem uma instalação local funcionando com Gmail e Google Calendar configurados (tokens OAuth presentes), pode reutilizar esses arquivos sem refazer a autenticação.

### Estrutura dos arquivos a migrar

```
data/
├── tokens/
│   ├── pessoal.json          # token OAuth por conta
│   ├── profissional.json
│   └── default.json          # conta migrada do formato legado (google.json)
└── accounts.yaml             # registry das contas
credentials/
└── credentials.json          # OAuth client secret (não é token — é o app)
```

### Passo 1 — Credenciais OAuth (client secret)

Copie o `credentials.json` da instalação local para a pasta `credentials/` do repositório (ela é montada como bind-mount read-only no container):

```bash
cp /caminho/antigo/credentials/credentials.json ./credentials/credentials.json
```

No Coolify, você também pode colar o conteúdo diretamente pelo console admin (`/admin → Google → Salvar JSON colado`) após o primeiro deploy.

### Passo 2 — Copie os tokens para o volume Docker

Use um container auxiliar Alpine para copiar e já corrigir as permissões de uma vez:

```bash
# Substitua ./data pelo caminho real da instalação anterior se diferente
docker run --rm \
  -v integrator_data:/app/data \
  -v "$(pwd)/data":/host-data \
  alpine sh -c "
    mkdir -p /app/data/tokens &&
    cp -r /host-data/tokens/. /app/data/tokens/ &&
    [ -f /host-data/accounts.yaml ] && cp /host-data/accounts.yaml /app/data/accounts.yaml || true &&
    chown -R 1000:1000 /app/data/tokens /app/data/accounts.yaml 2>/dev/null || true
  "
```

> **Nota**: execute antes de `docker compose up` ou com o serviço parado (`docker compose stop`). O volume `integrator_data` é criado automaticamente pelo Docker quando necessário.

### Passo 3 — Suba o serviço e verifique

```bash
docker compose up -d

# Aguarde o health check ficar healthy
docker compose ps

# Verifique as contas reconhecidas
docker exec integrator integrator status
```

A saída deve listar suas contas com tokens válidos. Se aparecer "token expirado", o integrador renova automaticamente na próxima chamada de tool.

### Token legado (`google.json`)

Se a instalação anterior usava o formato de conta única (`data/tokens/google.json`), o integrador migra automaticamente para `data/tokens/default.json` na primeira inicialização. Basta incluí-lo na cópia:

```bash
docker run --rm \
  -v integrator_data:/app/data \
  -v "$(pwd)/data/tokens":/host-tokens \
  alpine sh -c "
    mkdir -p /app/data/tokens &&
    cp /host-tokens/google.json /app/data/tokens/google.json &&
    chown 1000:1000 /app/data/tokens/google.json
  "
docker compose up -d
```

### No Coolify (acesso via SSH)

No Coolify o container tem um nome gerado automaticamente. Localize-o e use `docker cp` normalmente:

```bash
# SSH na VPS, depois:
docker ps --filter "name=integrator" --format "{{.Names}}"
# Ex.: coolify-integrator-abc123

# Substitua <container> pelo nome encontrado
docker cp ./data/tokens/. <container>:/app/data/tokens/
docker cp ./data/accounts.yaml <container>:/app/data/accounts.yaml
docker exec -u root <container> chown -R 1000:1000 /app/data/tokens /app/data/accounts.yaml
docker restart <container>
```

---

## Variáveis de ambiente completas

Veja `config/integrator.docker.env` para o template completo com todos os valores padrão e comentários.
