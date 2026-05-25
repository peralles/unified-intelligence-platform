"""Limites de performance para caminhos críticos (sem rede Google)."""

import time

import pytest

from integrator.accounts.registry import add_account
from integrator.config import settings
from integrator.providers.google_tools import (
    build_live_tools,
    invalidate_metadata_cache,
    list_all_tool_metadata,
)
from integrator.providers.tool_cache import invalidate_live_tools, set_cached_live_tools
@pytest.fixture
def perf_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    invalidate_metadata_cache()
    invalidate_live_tools()
    from integrator.logging_setup import reset_logging, setup_logging

    reset_logging()
    setup_logging(force=True)
    return tmp_path


def test_list_metadata_cached(perf_env):
    add_account("pessoal")
    add_account("profissional")

    start = time.perf_counter()
    first = list_all_tool_metadata()
    first_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    second = list_all_tool_metadata()
    second_ms = (time.perf_counter() - start) * 1000

    assert first is second
    assert len(first) == 12
    assert second_ms < first_ms * 0.5 or second_ms < 5.0


def test_live_tools_cache_hit(perf_env):
    add_account("pessoal")
    set_cached_live_tools("pessoal", {"cached": object()})
    t1 = build_live_tools("pessoal")
    t2 = build_live_tools("pessoal")
    assert t1 is t2


@pytest.mark.asyncio
async def test_mcp_list_tools_under_budget(perf_env):
    from integrator.mcp.server import handle_list_tools

    add_account("pessoal")
    start = time.perf_counter()
    tools = await handle_list_tools()
    elapsed_ms = (time.perf_counter() - start) * 1000
    from integrator.providers.tools import TOTAL_TOOL_COUNT

    assert len(tools) == TOTAL_TOOL_COUNT
    assert elapsed_ms < 500.0, f"list_tools lento: {elapsed_ms:.1f}ms"


def test_policy_block_minimal_overhead(perf_env, monkeypatch):
    """Bloqueio por política: audit async de falha, sem Google API."""
    from integrator.logging_setup import flush_logging
    from integrator.providers.google_tools import invoke_tool
    from integrator.security.policy import ToolPolicyError

    monkeypatch.setattr(settings, "tool_denylist", "search_gmail")
    start = time.perf_counter()
    for _ in range(100):
        try:
            invoke_tool("search_gmail", {})
        except ToolPolicyError:
            pass
    elapsed_ms = (time.perf_counter() - start) * 1000
    flush_logging()
    assert elapsed_ms < 200.0, f"policy block path slow: {elapsed_ms:.1f}ms"
