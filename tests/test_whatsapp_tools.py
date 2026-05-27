from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from integrator.providers.tools import (
    GMAIL_EXTRA_TOOL_COUNT,
    GOOGLE_TOOL_COUNT,
    TOTAL_TOOL_COUNT,
    WHATSAPP_TOOL_COUNT,
    invoke_tool,
    list_all_tool_metadata,
)
from integrator.providers.whatsapp_tools import list_whatsapp_tool_metadata
from integrator.security.policy import (
    ConfirmationRequiredError,
    get_confirm_required_tools,
)


def test_tool_counts():
    meta = list_all_tool_metadata()
    expected = GOOGLE_TOOL_COUNT + GMAIL_EXTRA_TOOL_COUNT + WHATSAPP_TOOL_COUNT
    assert len(meta) == TOTAL_TOOL_COUNT == expected
    names = {m["name"] for m in meta}
    wa = {m["name"] for m in list_whatsapp_tool_metadata()}
    assert wa.issubset(names)
    assert len(wa) == WHATSAPP_TOOL_COUNT


def test_send_whatsapp_requires_confirm():
    with pytest.raises(ConfirmationRequiredError):
        invoke_tool("send_whatsapp_text", {"text": "oi", "number": "5511999999999"})


@patch("integrator.providers.whatsapp_tools.WhatsAppSession.get")
def test_get_whatsapp_connection_status_mock(mock_get: MagicMock) -> None:
    session = MagicMock()
    session.status.return_value = {"state": "connected", "logged_in": True}
    mock_get.return_value = session

    out = invoke_tool("get_whatsapp_connection_status", {})
    data = json.loads(out)
    assert data["state"] == "connected"
    session.status.assert_called_once()


@patch("integrator.providers.whatsapp_tools.WhatsAppSession.get")
def test_find_whatsapp_chats_without_query_lists(mock_get: MagicMock) -> None:
    session = MagicMock()
    session.list_chats.return_value = [
        {
            "chat_id": "5511888888888@s.whatsapp.net",
            "name": "Vazio",
            "unread_count": 0,
            "last_message_preview": "",
            "is_group": False,
        }
    ]
    mock_get.return_value = session

    out = invoke_tool("find_whatsapp_chats", {"limit": 10})
    data = json.loads(out)
    assert data[0]["name"] == "Vazio"
    session.list_chats.assert_called_once_with(limit=10)
    session.find_chats.assert_not_called()


@patch("integrator.providers.whatsapp_tools.WhatsAppSession.get")
def test_list_whatsapp_chats_mock(mock_get: MagicMock) -> None:
    session = MagicMock()
    session.list_chats.return_value = [
        {
            "chat_id": "5511999999999@s.whatsapp.net",
            "name": "Contato",
            "unread_count": 1,
            "last_message_preview": "Olá",
            "is_group": False,
        }
    ]
    mock_get.return_value = session

    out = invoke_tool("list_whatsapp_chats", {"limit": 5})
    data = json.loads(out)
    assert data[0]["name"] == "Contato"


def test_confirm_required_includes_whatsapp_send():
    assert "send_whatsapp_text" in get_confirm_required_tools()
    assert "whatsapp_reply_text" in get_confirm_required_tools()
    assert "delete_whatsapp_messages" in get_confirm_required_tools()
    assert "delete_whatsapp_messages_for_me" in get_confirm_required_tools()


def test_delete_for_me_requires_confirm():
    with pytest.raises(ConfirmationRequiredError):
        invoke_tool(
            "delete_whatsapp_messages_for_me",
            {
                "chat_id": "5511999999999@s.whatsapp.net",
                "message_ids": ["X"],
            },
        )


@patch("integrator.providers.whatsapp_tools.WhatsAppSession.get")
def test_delete_whatsapp_messages_for_me_mock(mock_get: MagicMock) -> None:
    session = MagicMock()
    session.delete_messages_for_me.return_value = {
        "mode": "for_me",
        "deleted": ["X"],
        "failed": [],
        "deleted_count": 1,
    }
    mock_get.return_value = session

    out = invoke_tool(
        "delete_whatsapp_messages_for_me",
        {
            "confirm": True,
            "chat_id": "5511999999999@s.whatsapp.net",
            "before_timestamp": 1700000000,
        },
    )
    data = json.loads(out)
    assert data["deleted_count"] == 1
    session.delete_messages_for_me.assert_called_once()
    call_kw = session.delete_messages_for_me.call_args.kwargs
    assert call_kw["before_timestamp"] == 1700000000


@patch("integrator.providers.whatsapp_tools.WhatsAppSession.get")
def test_reply_whatsapp_mock(mock_get: MagicMock) -> None:
    session = MagicMock()
    session.reply_text.return_value = {"message_id": "R1", "chat_id": "c@s.whatsapp.net"}
    mock_get.return_value = session

    out = invoke_tool(
        "whatsapp_reply_text",
        {
            "confirm": True,
            "chat_id": "c@s.whatsapp.net",
            "reply_to_message_id": "M1",
            "text": "ok",
        },
    )
    assert json.loads(out)["message_id"] == "R1"


@patch("integrator.providers.whatsapp_tools.WhatsAppSession.get")
def test_react_whatsapp_mock(mock_get: MagicMock) -> None:
    session = MagicMock()
    session.react_message.return_value = {"emoji": "👍"}
    mock_get.return_value = session

    out = invoke_tool(
        "whatsapp_react_message",
        {"chat_id": "c@s.whatsapp.net", "message_id": "M1", "emoji": "👍"},
    )
    assert json.loads(out)["emoji"] == "👍"


@patch("integrator.providers.whatsapp_tools.WhatsAppSession.get")
def test_sync_whatsapp_chat_history_mock(mock_get: MagicMock) -> None:
    session = MagicMock()
    session.request_chat_history.return_value = {
        "requested": True,
        "added": 12,
        "cache_after": 40,
    }
    mock_get.return_value = session

    out = invoke_tool(
        "sync_whatsapp_chat_history",
        {"chat_id": "5511999999999@s.whatsapp.net", "count": 100},
    )
    data = json.loads(out)
    assert data["added"] == 12


def test_delete_whatsapp_requires_confirm():
    with pytest.raises(ConfirmationRequiredError):
        invoke_tool(
            "delete_whatsapp_messages",
            {
                "chat_id": "5511999999999@s.whatsapp.net",
                "message_ids": ["ABC123"],
            },
        )


@patch("integrator.providers.whatsapp_tools.WhatsAppSession.get")
def test_delete_whatsapp_messages_mock(mock_get: MagicMock) -> None:
    session = MagicMock()
    session.delete_messages.return_value = {
        "chat_id": "5511999999999@s.whatsapp.net",
        "deleted": ["ABC123"],
        "failed": [],
        "deleted_count": 1,
    }
    mock_get.return_value = session

    out = invoke_tool(
        "delete_whatsapp_messages",
        {
            "confirm": True,
            "chat_id": "5511999999999@s.whatsapp.net",
            "message_ids": ["ABC123"],
        },
    )
    data = json.loads(out)
    assert data["deleted_count"] == 1
    session.delete_messages.assert_called_once_with(
        chat_id="5511999999999@s.whatsapp.net",
        message_ids=["ABC123"],
    )


@patch("integrator.whatsapp.bridge_client.subprocess.Popen")
def test_bridge_client_rpc(mock_popen: MagicMock) -> None:
    from pathlib import Path

    from integrator.whatsapp.bridge_client import WhatsAppBridgeClient

    proc = MagicMock()
    proc.poll.return_value = None
    proc.stdin = MagicMock()
    proc.stdout.readline.return_value = json.dumps(
        {"id": "1", "ok": True, "result": {"pong": True}}
    ) + "\n"
    mock_popen.return_value = proc

    client = WhatsAppBridgeClient(Path("/tmp/wa-test"))
    result = client.call("ping")
    assert result == {"pong": True}
    client.close()
