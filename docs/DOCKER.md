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

Quando `INTEGRATOR_ADMIN_USERNAME` e `INTEGRATOR_ADMIN_PASSWORD` estão definidos, todas as rotas `/admin/*` exigem autenticação HTTP Basic.

As rotas MCP (`/sse`, `/mcp`, `/messages/`) e `/health` são **isentas** de Basic Auth — elas são usadas por agentes de IA (Hermes/Claude) que se conectam pela rede interna.

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

## Variáveis de ambiente completas

Veja `config/integrator.docker.env` para o template completo com todos os valores padrão e comentários.
