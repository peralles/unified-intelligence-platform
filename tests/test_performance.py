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


def test_live_tools_cache_hit(perf_env, monkeypatch):
    add_account("pessoal")
    calls = {"n": 0}

    def fake_build(account_id: str):
        calls["n"] += 1
        return {"search_gmail": object()}

    monkeypatch.setattr(
        "integrator.providers.google_tools.load_google_credentials",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "integrator.providers.google_tools.build_gmail_service",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "integrator.providers.google_tools.build_calendar_service",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "integrator.providers.google_tools.GmailToolkit",
        lambda **_: type("T", (), {"get_tools": lambda self: []})(),
    )
    monkeypatch.setattr(
        "integrator.providers.google_tools.CalendarToolkit",
        lambda **_: type("T", (), {"get_tools": lambda self: []})(),
    )

    set_cached_live_tools("pessoal", {"cached": object()})
    t1 = build_live_tools("pessoal")
    t2 = build_live_tools("pessoal")
    assert t1 is t2
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_mcp_list_tools_under_budget(perf_env):
    from integrator.mcp.server import handle_list_tools

    add_account("pessoal")
    start = time.perf_counter()
    tools = await handle_list_tools()
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert len(tools) == 12
    assert elapsed_ms < 500.0, f"list_tools lento: {elapsed_ms:.1f}ms"
