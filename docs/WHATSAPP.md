# WhatsApp no integrator (Hermes)

Integração **local** com WhatsApp Web (Baileys via [neonize](https://github.com/krypton-byte/neonize)), exposta como **7 tools MCP** no mesmo servidor que Gmail/Calendar.

## Arquitetura

- **Hermes:** um único `mcp_servers.langchain-integrator` com `integrator serve` (stdio). Não é necessário segundo MCP.
- **Diferenciação:** nomes das tools (`whatsapp_*` vs tools Google).
- **Processo neonize:** isolado em `bridges/whatsapp-neonize/` (protobuf 7.x) porque o stack LangChain/Google exige protobuf &lt; 7. O integrator fala com o worker via **JSON-RPC em linha** (subprocesso), sem HTTP nem Docker.

```
Hermes ──stdio──► integrator serve ──► providers/tools.py
                              ├── google_tools (12)
                              └── whatsapp_tools (7) ──► bridge_client ──► worker.py (neonize)
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

## Tools MCP (7)

| Tool | Confirmação |
|------|-------------|
| `get_whatsapp_connection_status` | não |
| `list_whatsapp_chats` | não |
| `find_whatsapp_chats` | não |
| `get_whatsapp_messages` | não |
| `send_whatsapp_text` | **`confirm: true`** |
| `delete_whatsapp_messages` | **`confirm: true`** |
| `mark_whatsapp_read` | não |

Total com Google: **19 tools** (12 + 7).

### Apagar mensagens

- `delete_whatsapp_messages` usa `revoke_message` do neonize (**apagar para todos**).
- Só funciona para **mensagens enviadas por você** (`from_me`); IDs vêm de `get_whatsapp_messages`.
- WhatsApp impõe janela de tempo (~48 h) e outras regras; falhas parciais aparecem em `failed` na resposta JSON.
- Não suporta “apagar só para mim” mensagens de terceiros (fluxo `send_app_state` do WhatsApp).

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `INTEGRATOR_WHATSAPP_ENABLED` | `true` | `false` expõe só Google no MCP |
| `INTEGRATOR_WHATSAPP_SESSION_DIR` | `data/whatsapp` | Diretório da sessão |
| `INTEGRATOR_WHATSAPP_MAX_MESSAGE_CHARS` | `800` | Truncagem em respostas |

Ver `config/integrator.example.env`.

## Segurança

- QR e credenciais **nunca** em argumentos de tool.
- Auditoria sem corpo de mensagem (metadados + hash de `chat_id`).
- `send_whatsapp_text` e `delete_whatsapp_messages` na denylist/allowlist como as tools Google.
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
