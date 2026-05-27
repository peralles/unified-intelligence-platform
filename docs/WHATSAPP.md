# WhatsApp no integrator (Hermes)

Integração **local** com WhatsApp Web (Baileys via [neonize](https://github.com/krypton-byte/neonize)), exposta como **17 tools MCP** no mesmo servidor que Gmail/Calendar.

## Arquitetura

- **Hermes:** um único `mcp_servers.langchain-integrator` com `integrator serve` (stdio). Não é necessário segundo MCP.
- **Diferenciação:** nomes das tools (`whatsapp_*` vs tools Google).
- **Processo neonize:** isolado em `bridges/whatsapp-neonize/` (protobuf 7.x) porque o stack LangChain/Google exige protobuf &lt; 7. O integrator fala com o worker via **JSON-RPC em linha** (subprocesso), sem HTTP nem Docker.

```
Hermes ──stdio──► integrator serve ──► providers/tools.py
                              ├── google_tools (12)
                              └── whatsapp_tools (17) ──► bridge_client ──► worker.py (neonize)
```

## Pré-requisitos (macOS)

```bash
brew install libmagic   # python-magic usado pelo neonize
uv sync --all-extras
cd bridges/whatsapp-neonize && uv sync
```

## Primeiro uso

1. Parear (QR no terminal — **não** pelo Hermes):

   ```bash
   uv run integrator whatsapp pair
   ```

2. Verificar situação (rápido, sem subir o worker):

   ```bash
   uv run integrator whatsapp status
   uv run integrator whatsapp status --live   # estado conectado/logado em tempo real
   ```

3. Configuração e remoção:

   ```bash
   uv run integrator whatsapp configure
   uv run integrator whatsapp remove          # apagar sessão (como logout)
   uv run integrator whatsapp pair            # parear de novo
   uv run integrator whatsapp disconnect      # só encerra worker do MCP serve
   ```

4. Sessão em `data/whatsapp/` (gitignored), como tokens Google em `data/tokens/`.

5. No Hermes: nova conversa ou `/reload-mcp` após atualizar o código.

## Logs

Mesmo padrão do integrator (`data/logs/`):

- `integrator.log` — operações gerais (`whatsapp` logger em DEBUG para bridge)
- `errors.log` — falhas do worker / tools
- `audit.jsonl` — invocações `whatsapp_*` (sem texto de mensagem; `account` = sufixo hash do chat)

Diagnóstico: `integrator logs --failures`

## Tools MCP (33)

| Tool | Confirmação |
|------|-------------|
| `get_whatsapp_connection_status` | não |
| `list_whatsapp_chats` / `find_whatsapp_chats` / `list_whatsapp_groups` | não |
| `get_whatsapp_messages` / `sync_whatsapp_chat_history` / `search_whatsapp_messages` | não |
| `get_whatsapp_group_info` / `get_whatsapp_profile_picture` | não |
| `whatsapp_reply_text` / `send_whatsapp_text` / `send_whatsapp_image` | **`confirm: true`** |
| `send_whatsapp_document` / `send_whatsapp_audio` / `send_whatsapp_video` / `send_whatsapp_sticker` | **`confirm: true`** |
| `send_whatsapp_contact` / `forward_whatsapp_message` | **`confirm: true`** |
| `send_whatsapp_poll` / `send_whatsapp_album` | **`confirm: true`** |
| `update_whatsapp_blocklist` / `leave_whatsapp_group` | **`confirm: true`** |
| `get_whatsapp_blocklist` / `get_whatsapp_group_invite_link` | não |
| `whatsapp_react_message` | não |
| `edit_whatsapp_text` | **`confirm: true`** |
| `delete_whatsapp_messages` / `delete_whatsapp_messages_for_me` | **`confirm: true`** |
| `archive_whatsapp_chat` / `pin_whatsapp_chat` / `mark_whatsapp_read` / `mute_whatsapp_chat` | não |
| `send_whatsapp_typing` | não (usar com moderação) |

Total com Google: **54 tools** (12 LangChain + 9 Gmail extra + 33 WhatsApp).

### Cache persistente

Com `INTEGRATOR_WHATSAPP_PERSIST_CACHE=true` (padrão), o worker grava mensagens em `data/whatsapp/message_cache.db` (SQLite). Reply, reação e encaminhamento de texto dependem do cache — após reiniciar o worker, mensagens antigas continuam disponíveis se já foram ingeridas.

### Encaminhar mensagens

`forward_whatsapp_message` reenvia **texto** do cache (prefixo `↪️` opcional). Mídia pura ainda não é suportada.

### Apagar mensagens

**Mensagens de outras pessoas ou antigas (1–2 anos):** use `delete_whatsapp_messages_for_me` (apaga **só no seu dispositivo** ligado ao integrador).

1. `integrator whatsapp pair` e mantenha o worker conectado.
2. `sync_whatsapp_chat_history` no chat (repita para ir mais atrás).
3. `get_whatsapp_messages` com `before_timestamp` / `limit` para listar IDs.
4. `delete_whatsapp_messages_for_me` com `message_ids` ou `before_timestamp` em lote + `confirm: true`.

**Suas mensagens recentes para todos:** `delete_whatsapp_messages` (`revoke_message`, ~48 h, só `from_me`).

- Cache local até `INTEGRATOR_WHATSAPP_MAX_CACHED_MESSAGES_PER_CHAT` (padrão 5000) por chat.
- Mensagens só existem no MCP se já foram sincronizadas (HistorySync / eventos / `sync_whatsapp_chat_history`).
- Falhas parciais em `failed` na resposta JSON.

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `INTEGRATOR_WHATSAPP_ENABLED` | `true` | `false` expõe só Google no MCP |
| `INTEGRATOR_WHATSAPP_SESSION_DIR` | `data/whatsapp` | Diretório da sessão |
| `INTEGRATOR_WHATSAPP_MAX_MESSAGE_CHARS` | `800` | Truncagem em respostas |
| `INTEGRATOR_WHATSAPP_MAX_CACHED_MESSAGES_PER_CHAT` | `5000` | Mensagens por chat no worker |
| `INTEGRATOR_WHATSAPP_PERSIST_CACHE` | `true` | SQLite `message_cache.db` na sessão |

Ver `config/integrator.example.env`.

## Segurança

- QR e credenciais **nunca** em argumentos de tool.
- Auditoria sem corpo de mensagem (metadados + hash de `chat_id`).
- Tools destrutivas WhatsApp na denylist/allowlist como as tools Google.
- Uso não oficial do WhatsApp Web — risco de banimento; assumido uso pessoal.

## Trilha B (Evolution API) — opcional

Evolution é servidor **Node** (REST :8080) + PostgreSQL + Redis. O pacote `evolutionapi` no pip é só cliente HTTP — **não** embute Baileys no Python.

Use Evolution se precisar de Manager web, webhooks ricos ou vários consumidores REST. Para Hermes + um número, a trilha A (neonize + bridge) é a recomendada.

Não há `docker-compose` Evolution no repositório por padrão; documente localmente se adotar a trilha B.

## Troubleshooting

| Sintoma | Ação |
|---------|------|
| `WhatsApp não conectado` | `integrator whatsapp pair` e escanear QR |
| Erro `libmagic` | `brew install libmagic` |
| Worker não inicia | `cd bridges/whatsapp-neonize && uv sync` |
| Hermes não vê tools novas | `/reload-mcp` ou nova conversa |
| Desligar WhatsApp no MCP | `INTEGRATOR_WHATSAPP_ENABLED=false` |
