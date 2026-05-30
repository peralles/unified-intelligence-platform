#!/usr/bin/env bash
# Ponto de entrada amigável — delega toda a lógica para a CLI (integrator).
# Uso: ./setup.sh          → assistente de configuração
#      ./setup.sh status   → ver se já está pronto
#      ./setup.sh help     → ajuda rápida
set -euo pipefail

UV_INSTALL_URL="https://docs.astral.sh/uv/getting-started/installation/"

banner() {
  echo ""
  echo "============================================================"
  echo "  Integrador Gmail + Agenda para o Hermes"
  echo "============================================================"
  echo ""
}

die() {
  echo ""
  echo "  ✗ $*" >&2
  echo "" >&2
  exit 1
}

repo_root() {
  local dir
  dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ ! -f "${dir}/pyproject.toml" ]]; then
    die "Execute este script na pasta do projeto (onde está o pyproject.toml)."
  fi
  echo "${dir}"
}

require_uv() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  banner
  echo "  Falta instalar o gerenciador Python \"uv\" (só uma vez no computador)."
  echo ""
  echo "  1. Abra no navegador:"
  echo "     ${UV_INSTALL_URL}"
  echo "  2. Siga o passo \"Installation\" para macOS/Linux/Windows"
  echo "  3. Feche e abra o terminal, volte aqui e rode de novo:"
  echo ""
  echo "     ./setup.sh"
  echo ""
  exit 1
}

run_integrator() {
  cd "$(repo_root)"
  uv run integrator "$@"
}

usage() {
  banner
  cat <<'EOF'
  Comandos:

    ./setup.sh              Configurar (CLI init ou Admin após serviço)
    ./setup.sh status       Ver se Gmail, Agenda e Hermes já estão prontos
    ./setup.sh admin        Abrir console web (requer serve-http ativo)
    ./setup.sh help         Esta ajuda

  Console web (após serviço rodando):

    http://127.0.0.1:17320/admin

  Opções repassadas ao assistente (exemplos):

    ./setup.sh --yes        Configura sem perguntas, só o que faltar
    ./setup.sh --verbose    Mostra caminhos de arquivos no disco

  Quem já usa a linha de comando também pode:

    uv run integrator init
    uv run integrator status

EOF
}

run_setup() {
  require_uv
  banner
  echo "  Vamos configurar Gmail, Agenda e Hermes passo a passo."
  echo "  (O navegador pode abrir algumas vezes — é normal.)"
  echo ""
  run_integrator init "$@"
}

run_status() {
  require_uv
  banner
  echo "  Verificando configuração…"
  echo ""
  INTEGRATOR_CLI_LEGACY=true run_integrator status "$@"
}

if [[ $# -eq 0 ]]; then
  run_setup
  exit $?
fi

case "$1" in
  -h|--help|help)
    usage
    ;;
  status|check|verificar)
    shift
    run_status "$@"
    ;;
  admin|ui|painel)
    PORT="${INTEGRATOR_SERVICE_PORT:-17320}"
    URL="http://127.0.0.1:${PORT}/admin"
    echo ""
    echo "  Admin: ${URL}"
    echo "  (Serviço deve estar ativo: integrator service install ou serve-http)"
    echo ""
    if command -v open >/dev/null 2>&1; then
      open "${URL}" || true
    fi
    ;;
  setup|init|configurar)
    shift
    run_setup "$@"
    ;;
  *)
    run_setup "$@"
    ;;
esac
