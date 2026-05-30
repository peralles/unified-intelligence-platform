# Contexto ativo

Última atualização: continual-learning (Hermes SSE + auto-transcrição privada, 66 tools).

## Estado

- MVP: MCP **66 tools** (12 Google + 13 Gmail extra + 1 Calendar + 40 WhatsApp), Fase 2
- CLI WhatsApp: `status` (rápido + `--live`), `configure`, `pair`, `remove`, `disconnect`, `watch`, `watch-service`
- **Admin UI** (`http://127.0.0.1:17320/admin`): instalação, Google OAuth, WhatsApp QR, serviço macOS, Hermes, config runtime, 66 tools, logs — operador pode evitar CLI no dia a dia
- Entrada amigável: `./setup.sh` + `./setup.sh admin` (abre painel)
- Correção MCP: schemas sem `$ref` órfão; log `tool OK` em sucesso (`integrator.tools`)
- Segurança recente: confirm em transcribe+reply, revoke convite, reações; audit nos Google extra; `is_audio` no cache SQLite

## Operacional (este ambiente)

- **Hermes:** SSE → `http://127.0.0.1:17320/sse` (`integrator hermes setup --mode sse`)
- **Integrador:** LaunchAgent `integrator service` (serve-http persistente)
- **WhatsApp:** conectado via serviço SSE; `watch-service` **parado** (conflito de `worker.lock`)
- **Auto-transcrição:** `INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE=true` no `.env`; `TRANSCRIBE_PRIVATE_ONLY=true` (só chats privados)
- **Reload:** `/reload-mcp` após mudanças de código MCP ou YAML Hermes

## Pendências

- Validação manual com Google OAuth real (`credentials.json` + `integrator login`)
- CI GitHub Actions (não existe no repo)

## Próximos passos (planejado)

- Sidecar Unix socket (futuro): stdio Hermes + transcrição 24/7 sem conflito de lock
- Novos providers OAuth no padrão `ToolProvider`

## Bloqueios

- Nenhum bloqueio técnico no código — depende de credenciais Google locais do operador
