import json
import os
import stat

import pytest

from integrator.config import settings
from integrator.providers.google_tools import invoke_tool, list_all_tool_metadata
from integrator.security.policy import (
    ConfirmationRequiredError,
    ToolPolicyError,
    check_confirmation,
    enrich_tool_schema,
    is_tool_allowed,
    strip_confirm_arg,
)
from integrator.security.token_permissions import secure_token_file


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    from integrator.logging_setup import reset_logging, setup_logging

    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(settings, "tool_allowlist", None)
    monkeypatch.setattr(settings, "tool_denylist", None)
    monkeypatch.setattr(settings, "confirm_required_tools", None)
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    monkeypatch.setattr(settings, "audit_log_file", tmp_path / "data/logs/audit.jsonl")
    reset_logging()
    setup_logging(force=True)
    return tmp_path


def test_denylist_blocks_tool(isolated_settings, monkeypatch):
    monkeypatch.setattr(settings, "tool_denylist", "send_gmail_message,delete_calendar_event")
    assert is_tool_allowed("search_gmail") is True
    assert is_tool_allowed("send_gmail_message") is False


def test_allowlist_only_permitted(isolated_settings, monkeypatch):
    monkeypatch.setattr(settings, "tool_allowlist", "search_gmail,get_calendars_info")
    assert is_tool_allowed("search_gmail") is True
    assert is_tool_allowed("send_gmail_message") is False


def test_list_tools_respects_denylist(isolated_settings, monkeypatch):
    monkeypatch.setattr(settings, "tool_denylist", "send_gmail_message")
    names = {m["name"] for m in list_all_tool_metadata()}
    assert "send_gmail_message" not in names
    assert len(names) == 11


def test_confirm_schema_added():
    meta = enrich_tool_schema(
        {
            "name": "send_gmail_message",
            "description": "Send",
            "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}},
        }
    )
    assert "confirm" in meta["input_schema"]["properties"]


def test_confirmation_required():
    with pytest.raises(ConfirmationRequiredError):
        check_confirmation("send_gmail_message", {"message": "hi"})
    check_confirmation("send_gmail_message", {"confirm": True})


def test_strip_confirm_arg():
    assert strip_confirm_arg({"confirm": True, "q": "x"}) == {"q": "x"}


def test_invoke_blocked_by_policy(isolated_settings, monkeypatch):
    monkeypatch.setattr(settings, "tool_denylist", "search_gmail")
    with pytest.raises(ToolPolicyError):
        invoke_tool("search_gmail", {"query": "test"})


def test_audit_log_written_on_blocked_invoke(isolated_settings, monkeypatch):
    monkeypatch.setattr(settings, "tool_denylist", "search_gmail")
    log_path = settings.audit_log_path
    with pytest.raises(ToolPolicyError):
        invoke_tool("search_gmail", {})
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["tool"] == "search_gmail"
    assert record["success"] is False
    assert record["blocked"] is True
    assert record["error"] == "tool_policy"
    assert "query" not in record


def test_secure_token_file_chmod(tmp_path):
    token = tmp_path / "google.json"
    token.write_text('{"token": "x"}', encoding="utf-8")
    os.chmod(token, 0o644)
    secure_token_file(token)
    mode = stat.S_IMODE(token.stat().st_mode)
    assert mode == 0o600
