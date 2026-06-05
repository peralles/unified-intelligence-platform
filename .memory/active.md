# Contexto ativo

Última atualização: CI + OAuth browser + docs Coolify + defaults VPS.

## Estado

- MVP: MCP **66 tools** (12 Google + 13 Gmail extra + 1 Calendar + 40 WhatsApp), Fase 2
- **Produção Coolify:** `https://mcp.peralles.com/admin` — volume `/app/data` obrigatório (Storages UI ou compose), `read_only`
- **Google OAuth produção:** redirect `/admin/oauth/google/callback` (Web client); `INTEGRATOR_OAUTH_PUBLIC_BASE_URL`
- **CI:** `.github/workflows/validate.sh` em push/PR `main`
- **Admin UI:** OAuth mesma aba; hint LaunchAgent quando `INTEGRATOR_SKIP_MACOS_SERVICE=1`
- **Transcrição default Docker:** `small` (VPS CPU)

## Operacional (este ambiente)

- **Hermes:** SSE → `http://127.0.0.1:17320/sse`
- **Mac local:** LaunchAgent só se **não** houver Coolify ativo (evitar lock duplo neonize)
- **Reload:** `/reload-mcp` após mudanças MCP

## Pendências operador

- Coolify: confirmar Storages `/app/data`, env `INTEGRATOR_ALLOWED_HOSTS=mcp.peralles.com`
- Google Cloud: redirect URI Web + JSON em credentials
- Mac prod-only Coolify: `integrator service uninstall`

## Bloqueios

- Nenhum bloqueio técnico no código
