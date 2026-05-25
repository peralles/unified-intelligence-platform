#!/usr/bin/env bash
# Validação técnica e de qualidade — Fase 2+
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> uv sync"
uv sync --all-extras

echo "==> pytest"
uv run pytest -q --tb=short

echo "==> import smoke"
uv run python -c "
from integrator.providers.google_tools import list_all_tool_metadata
from integrator.security.policy import get_confirm_required_tools
meta = list_all_tool_metadata()
assert len(meta) == 12, len(meta)
assert get_confirm_required_tools() == frozenset({'send_gmail_message', 'delete_calendar_event'})
from integrator.accounts.registry import validate_account_id
assert validate_account_id('Profissional') == 'profissional'
print('OK:', len(meta), 'tools, confirm tools:', get_confirm_required_tools())
"

echo "==> MCP handlers smoke"
uv run python -c "
import asyncio
from integrator.mcp.server import handle_list_tools
tools = asyncio.run(handle_list_tools())
assert len(tools) == 12
print('OK: MCP list_tools', len(tools))
"

echo ""
echo "Validação concluída com sucesso."
