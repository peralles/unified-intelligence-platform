# Logging operacional

Estratégia para diagnosticar integrador, WhatsApp e admin sem PII nos logs.

## Onde ficam os logs

| Arquivo | Conteúdo |
|---------|----------|
| `data/logs/integrator.log` | App (MCP, HTTP, admin, bridge parent) |
| `data/logs/errors.log` | WARNING+ do app (sem audit) |
| `data/logs/audit.jsonl` | Falhas de tools MCP (JSON, uma linha por evento) |
| stderr do worker neonize | WhatsApp + transcrição (mesmo formato `event=`) |

Docker/Coolify: monte volume em `/app/data` para persistir tudo.

## Formato

**App (integrator):**

```
2026-06-05 13:43:59Z | INFO    | integrator.whatsapp | event=whatsapp.transcribe.ok | chars=64 | chat=***9061@lid
```

**Worker (stderr):**

```
2026-06-05 13:43:59,046 [whatsapp INFO] - event=whatsapp.transcribe.ok | chars=64 | chat=***9061@lid
```

Regra: toda linha operacional importante usa prefixo `event=<domínio>.<ação>` e campos `chave=valor` separados por ` | `.

## Módulos

| Código | Uso |
|--------|-----|
| `integrator/logging_setup.py` | Fila async, rotação, audit JSON |
| `integrator/ops_log.py` | `log_event()`, `redact_jid()` no pacote principal |
| `bridges/whatsapp-neonize/ops_log.py` | Mesma API no worker isolado |
| `integrator/security/audit.py` | Tools MCP (`tool FAIL` + audit.jsonl) |

## Eventos WhatsApp (grep)

```bash
grep 'event=whatsapp' data/logs/integrator.log
grep 'event=whatsapp.transcribe' data/logs/integrator.log   # ou stderr Coolify
```

| Evento | Significado |
|--------|-------------|
| `whatsapp.bridge.start` | Worker neonize subiu |
| `whatsapp.bridge.start_failed` | Falha ao spawn subprocess |
| `whatsapp.bridge.rpc_failed` | RPC JSON-line falhou |
| `whatsapp.transcribe.model_loaded` | faster-whisper pronto |
| `whatsapp.transcribe.ok` | Áudio transcrito e resposta enviada |
| `whatsapp.transcribe.download_failed` | Download do áudio falhou |
| `whatsapp.transcribe.transcription_failed` | Whisper/IO falhou |
| `whatsapp.transcribe.send_failed` | Transcrição ok, envio falhou |

## Eventos admin

| Evento | Significado |
|--------|-------------|
| `admin.config.saved` | runtime.json atualizado |
| `admin.oauth.start_failed` | OAuth Google falhou no início |
| `admin.oauth.callback_failed` | Callback OAuth falhou |

## Privacidade

- Nunca logar tokens, QR payload completo, corpo de mensagem, e-mail ou telefone inteiro.
- JIDs: usar `redact_jid()` → `***9061@lid`.
- Erros: truncar em ~240 caracteres (`ops_log.truncate`).

## Audit vs ops

- **audit.jsonl** — só invocações de tools MCP (métricas, falhas para Hermes/admin).
- **integrator.log** — ciclo de vida do serviço, bridge, transcrição, config.
- Sucesso de tool no audit desligado por padrão: `INTEGRATOR_AUDIT_LOG_SUCCESS=false`.

## Diagnóstico rápido

1. Admin → Logs ou `tail -f data/logs/integrator.log`
2. Falhas MCP → `data/logs/errors.log` ou admin audit failures
3. WhatsApp/transcrição → grep `event=whatsapp` no integrator.log **e** logs do container (worker stderr)
4. Hermes MCP → `~/.hermes/logs/mcp-stderr.log`

## Variáveis úteis

| Env | Efeito |
|-----|--------|
| `INTEGRATOR_LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING` |
| `INTEGRATOR_LOG_CONSOLE_ENABLED` | stderr no processo principal |
| `INTEGRATOR_AUDIT_LOG_SUCCESS` | gravar sucesso de tools no audit |
