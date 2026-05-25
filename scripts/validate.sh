#!/usr/bin/env bash
# Validação técnica, qualidade e performance
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> uv sync"
uv sync --all-extras

echo "==> ruff"
uv run ruff check integrator tests

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

echo "==> performance smoke"
uv run python -c "
import asyncio
import time
from integrator.providers.google_tools import list_all_tool_metadata, invalidate_metadata_cache
from integrator.mcp.server import handle_list_tools

invalidate_metadata_cache()

t0 = time.perf_counter()
list_all_tool_metadata()
list_all_tool_metadata()
meta_ms = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
asyncio.run(handle_list_tools())
list_ms = (time.perf_counter() - t0) * 1000

print(f'OK: metadata_cache_2x={meta_ms:.1f}ms list_tools={list_ms:.1f}ms')
assert meta_ms < 200, meta_ms
assert list_ms < 500, list_ms
"

echo ""
echo "Validação (qualidade + performance) concluída com sucesso."
