# Contexto ativo

Última atualização: integração LinkedIn adicionada (8 tools MCP via OAuth 2.0 oficial).

## Estado

- MCP **79 tools** (12 Google + 13 Gmail extra + 1 Calendar + 5 Contacts + 40 WhatsApp + **8 LinkedIn**), Fase 2
- **Produção Coolify:** `https://mcp.peralles.com/admin` — volume `/app/data` obrigatório, `read_only`
- **Google OAuth produção:** redirect `/admin/oauth/google/callback` (Web client); credenciais em `/app/data/credentials/`
- **Runtime container:** auto via `/.dockerenv` (sem env extra)
- **CLI bootstrap:** `init`, `serve`, `serve-http` — operação diária só admin web
- **Transcrição default Docker:** `small` (VPS CPU)

## Operacional

- **Hermes produção:** SSE → URL pública `/sse` (Coolify)
- **Dev local:** `integrator serve-http` + admin `127.0.0.1:17320`
- **Reload:** `/reload-mcp` após mudanças MCP

## Pendências operador

- Coolify: Storages `/app/data`, env `INTEGRATOR_ALLOWED_HOSTS`, `INTEGRATOR_OAUTH_PUBLIC_BASE_URL`
- Google Cloud: redirect URI Web + JSON via admin upload
- Redeploy após push com `./scripts/build-admin.sh` incluído no pipeline se UI mudou

## LinkedIn

- **OAuth:** Authorization Code flow, escopos `openid profile email w_member_social`
- **Config:** `INTEGRATOR_LINKEDIN_CLIENT_ID` + `INTEGRATOR_LINKEDIN_CLIENT_SECRET`
- **Tokens:** `data/tokens/linkedin_{account_id}.json` (60 dias; refresh 365 dias)
- **Admin:** `/admin` → menu LinkedIn; redirect `/admin/oauth/linkedin/callback`
- **Docs:** `docs/LINKEDIN.md`

## Bloqueios

- Nenhum bloqueio técnico no código
