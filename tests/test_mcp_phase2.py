import pytest
import mcp.types as types

from integrator.config import settings
from integrator.mcp.server import handle_call_tool, handle_list_tools


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(settings, "tool_allowlist", None)
    monkeypatch.setattr(settings, "tool_denylist", "send_gmail_message,delete_calendar_event")
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    monkeypatch.setattr(settings, "audit_log_file", tmp_path / "data/logs/audit.jsonl")
    return tmp_path


@pytest.mark.asyncio
async def test_list_tools_excludes_denylisted(isolated_settings):
    tools = await handle_list_tools()
    names = {t.name for t in tools}
    assert "send_gmail_message" not in names
    assert "delete_calendar_event" not in names
    assert "search_gmail" in names


@pytest.mark.asyncio
async def test_call_tool_policy_returns_is_error(isolated_settings):
    result = await handle_call_tool("send_gmail_message", {"confirm": True})
    assert isinstance(result, types.CallToolResult)
    assert result.isError is True
    assert "Política" in result.content[0].text


@pytest.mark.asyncio
async def test_call_tool_confirmation_returns_is_error(isolated_settings, monkeypatch):
    monkeypatch.setattr(settings, "tool_denylist", None)
    result = await handle_call_tool(
        "delete_calendar_event",
        {"event_id": "abc"},
    )
    assert result.isError is True
    assert "Confirmação" in result.content[0].text


@pytest.mark.asyncio
async def test_destructive_tools_schema_has_confirm():
    tools = await handle_list_tools()
    by_name = {t.name: t for t in tools}
    for name in ("send_gmail_message", "delete_calendar_event"):
        schema = by_name[name].inputSchema
        assert "confirm" in schema.get("properties", {})
