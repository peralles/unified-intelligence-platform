#!/usr/bin/env bash
# Configura Hermes + Claude Desktop no computador local apontando para integrador remoto (SSE).
# Uso: ./scripts/setup-local-agents.sh
#      INTEGRATOR_SSE_URL='https://user:pass@host/sse' ./scripts/setup-local-agents.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

die() {
  echo "✗ $*" >&2
  exit 1
}

require_uv() {
  command -v uv >/dev/null 2>&1 || die "Instale uv: https://docs.astral.sh/uv/"
}

banner() {
  echo ""
  echo "============================================================"
  echo "  Agentes locais → integrador remoto (SSE)"
  echo "============================================================"
  echo ""
  echo "  Configure Hermes e Claude Desktop neste computador."
  echo "  O servidor (Coolify/VPN) continua só com o console /admin."
  echo ""
}

read_sse_url() {
  local url="${INTEGRATOR_SSE_URL:-}"
  if [[ -n "$url" ]]; then
    echo "$url"
    return 0
  fi
  echo "URL SSE do servidor (com auth Basic na URL se houver):" >&2
  echo "  ex.: https://usuario:senha@mcp.seudominio.com/sse" >&2
  read -r url
  [[ -n "$url" ]] || die "URL SSE obrigatória."
  echo "$url"
}

main() {
  banner
  require_uv

  SSE_URL="$(read_sse_url)"

  echo "→ Sincronizando dependências…"
  uv sync --all-extras

  echo "→ Diagnóstico (opcional)…"
  uv run integrator hermes doctor --mode sse || true

  echo "→ Gravando MCP em ~/.hermes e Claude Desktop…"
  uv run integrator hermes setup --mode sse --sse-url "$SSE_URL" --yes --force --skip-test

  echo ""
  echo "Pronto."
  echo "  • Hermes: conversa nova ou /reload-mcp"
  echo "  • Claude Desktop: sair completamente (⌘Q) e reabrir"
  echo ""
}

main "$@"
