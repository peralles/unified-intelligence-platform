#!/usr/bin/env bash
# Validação técnica, qualidade e performance
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> uv sync"
uv sync --all-extras

echo "==> ruff"
uv run ruff check integrator tests bridges/whatsapp-neonize/worker.py

echo "==> pytest"
uv run pytest -q --tb=short

echo "==> import smoke"
uv run python -c "
from integrator.providers.tools import (
    CALENDAR_EXTRA_TOOL_COUNT,
    GMAIL_EXTRA_TOOL_COUNT,
    GOOGLE_TOOL_COUNT,
    TOTAL_TOOL_COUNT,
    WHATSAPP_TOOL_COUNT,
    list_all_tool_metadata,
)
from integrator.providers.google_tools import list_google_tool_metadata
from integrator.security.policy import get_confirm_required_tools
meta = list_all_tool_metadata()
google = list_google_tool_metadata()
assert len(google) == GOOGLE_TOOL_COUNT == 12, len(google)
expected_total = (
    GOOGLE_TOOL_COUNT
    + GMAIL_EXTRA_TOOL_COUNT
    + CALENDAR_EXTRA_TOOL_COUNT
    + WHATSAPP_TOOL_COUNT
)
assert len(meta) == TOTAL_TOOL_COUNT == expected_total, (len(meta), expected_total)
confirm = get_confirm_required_tools()
for required in (
    'send_gmail_message',
    'reply_gmail_message',
    'modify_gmail_labels',
    'delete_calendar_event',
    'send_whatsapp_text',
    'whatsapp_reply_text',
    'send_whatsapp_image',
    'edit_whatsapp_text',
    'delete_whatsapp_messages',
    'delete_whatsapp_messages_for_me',
    'send_whatsapp_document',
    'send_whatsapp_audio',
    'forward_whatsapp_message',
    'send_whatsapp_video',
    'send_whatsapp_sticker',
    'send_whatsapp_contact',
    'trash_gmail_message',
    'send_whatsapp_poll',
    'send_whatsapp_album',
    'update_whatsapp_blocklist',
    'leave_whatsapp_group',
    'restore_gmail_message',
    'vote_whatsapp_poll',
    'join_whatsapp_group_link',
    'send_gmail_draft',
    'batch_modify_gmail_labels',
    'leave_whatsapp_group_and_purge',
):
    assert required in confirm, required
names = {m['name'] for m in meta}
assert 'transcribe_whatsapp_audio' in names, 'transcribe_whatsapp_audio missing'
assert WHATSAPP_TOOL_COUNT == 40, f'Expected 40 WhatsApp tools, got {WHATSAPP_TOOL_COUNT}'
from integrator.accounts.registry import validate_account_id
assert validate_account_id('Profissional') == 'profissional'
print(
    'OK:', len(meta), 'tools (',
    GOOGLE_TOOL_COUNT, 'Google +', GMAIL_EXTRA_TOOL_COUNT, 'Gmail extra +',
    CALENDAR_EXTRA_TOOL_COUNT, 'Calendar extra +', WHATSAPP_TOOL_COUNT, 'WhatsApp)',
)
"

echo "==> MCP handlers smoke"
uv run python -c "
import asyncio
from integrator.mcp.server import handle_list_tools
from integrator.providers.tools import TOTAL_TOOL_COUNT
tools = asyncio.run(handle_list_tools())
assert len(tools) == TOTAL_TOOL_COUNT
print('OK: MCP list_tools', len(tools))
"

echo "==> whatsapp CLI smoke"
uv run integrator whatsapp configure >/dev/null
uv run integrator whatsapp status >/dev/null
uv run integrator whatsapp watch --help >/dev/null
uv run integrator whatsapp watch-service status >/dev/null 2>&1 || true
echo "OK: whatsapp CLI (configure, status, watch)"

echo "==> performance smoke"
uv run python -c "
import asyncio
import time
from integrator.providers.tools import TOTAL_TOOL_COUNT, list_all_tool_metadata
from integrator.providers.google_tools import invalidate_metadata_cache
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
