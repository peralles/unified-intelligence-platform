#!/usr/bin/env bash
# Build admin UI (Vite) into integrator/admin/static/dist/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI="${ROOT}/integrator/admin/ui"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm não encontrado — instale Node.js e rode ./scripts/build-admin.sh." >&2
  exit 1
fi

cd "${UI}"
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run build
echo "Admin UI → integrator/admin/static/dist/"
