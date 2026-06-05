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

require_npx() {
  command -v npx >/dev/null 2>&1 || die "Claude Desktop precisa de Node/npx (mcp-remote). Instale: https://nodejs.org/"
}

banner() {
  echo ""
  echo "============================================================"
  echo "  Agentes locais → integrador remoto (SSE)"
  echo "============================================================"
  echo ""
  echo "  Configure Hermes e Claude Desktop neste computador."
  echo "  Hermes: SSE direto. Claude: bridge npx mcp-remote (stdio)."
  echo "  O servidor (Coolify/VPN) continua só com o console /admin."
  echo ""
}

run_doctor() {
  uv run python -c "
from integrator.admin.handlers import hermes_doctor

d = hermes_doctor(mode='sse')
for c in d.get('checks') or []:
    print(f\"{c['status']:6} {c['label']}: {c.get('detail') or ''}\")
print(f\"(critical={d.get('critical', 0)})\")
"
}

run_setup() {
  local url="$1"
  uv run python -c "
import sys

from integrator.admin.handlers import hermes_setup

result = hermes_setup(mode='sse', yes=True, force=True, sse_url=sys.argv[1])
for name, info in (result.get('hosts') or {}).items():
    if info.get('ok'):
        print(f\"  {name}: {info.get('message', 'OK')}\")
    else:
        print(f\"  {name}: ERRO — {info.get('error', 'falha')}\", file=sys.stderr)
if not result.get('ok'):
    print(result.get('error', 'falha'), file=sys.stderr)
    sys.exit(1)
" "$url"
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
  require_npx

  SSE_URL="$(read_sse_url)"

  echo "→ Sincronizando dependências…"
  uv sync --all-extras

  echo "→ Diagnóstico (opcional)…"
  run_doctor || true

  echo "→ Gravando MCP em ~/.hermes e Claude Desktop…"
  run_setup "$SSE_URL"

  if command -v hermes >/dev/null 2>&1; then
    echo "→ Testando MCP Hermes…"
    hermes mcp test langchain-integrator || true
  fi

  echo ""
  echo "Pronto."
  echo "  • Hermes: conversa nova ou /reload-mcp"
  echo "  • Claude Desktop: sair completamente (⌘Q) e reabrir"
  echo ""
}

main "$@"
