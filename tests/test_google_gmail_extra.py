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
from integrator.security.policy import ConfirmationRequiredError, get_confirm_required_tools


def test_total_tool_count():
    assert TOTAL_TOOL_COUNT == GOOGLE_TOOL_COUNT + GMAIL_EXTRA_TOOL_COUNT + WHATSAPP_TOOL_COUNT
    assert len(list_all_tool_metadata()) == TOTAL_TOOL_COUNT


def test_gmail_extra_confirm_required():
    assert "modify_gmail_labels" in get_confirm_required_tools()
    assert "reply_gmail_message" in get_confirm_required_tools()


@patch("integrator.providers.tools.invoke_gmail_extra_tool")
@patch("integrator.accounts.registry.resolve_account_id", return_value="pessoal")
def test_modify_gmail_labels_routes_to_extra(
    _mock_account: MagicMock,
    mock_invoke: MagicMock,
) -> None:
    mock_invoke.return_value = {"message_id": "m1", "label_ids": ["INBOX"]}
    out = invoke_tool(
        "modify_gmail_labels",
        {
            "confirm": True,
            "message_id": "m1",
            "remove_labels": ["INBOX"],
        },
    )
    data = json.loads(out)
    assert data["message_id"] == "m1"


def test_reply_gmail_requires_confirm():
    with pytest.raises(ConfirmationRequiredError):
        invoke_tool("reply_gmail_message", {"message_id": "x", "body": "hi"})


@patch("integrator.providers.google_gmail_extra._gmail_service")
@patch("integrator.accounts.registry.resolve_account_id", return_value="pessoal")
def test_list_gmail_attachments(
    _mock_account: MagicMock,
    mock_service_fn: MagicMock,
) -> None:
    service = MagicMock()
    mock_service_fn.return_value = service
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "payload": {
            "parts": [
                {
                    "filename": "doc.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att-1", "size": 1024},
                }
            ]
        }
    }
    from integrator.providers.google_gmail_extra import invoke_gmail_extra_tool

    result = invoke_gmail_extra_tool(
        "list_gmail_attachments",
        "pessoal",
        {"message_id": "msg1"},
    )
    assert result["count"] == 1
    assert result["attachments"][0]["attachment_id"] == "att-1"


@patch("integrator.providers.google_gmail_extra._gmail_service")
@patch("integrator.accounts.registry.resolve_account_id", return_value="pessoal")
def test_get_gmail_attachment_writes_file(
    _mock_account: MagicMock,
    mock_service_fn: MagicMock,
    tmp_path,
) -> None:
    service = MagicMock()
    mock_service_fn.return_value = service
    import base64

    payload = base64.urlsafe_b64encode(b"hello").decode("ascii")
    service.users.return_value.messages.return_value.attachments.return_value.get.return_value.execute.return_value = {
        "data": payload
    }
    dest = tmp_path / "out.bin"
    from integrator.providers.google_gmail_extra import invoke_gmail_extra_tool

    result = invoke_gmail_extra_tool(
        "get_gmail_attachment",
        "pessoal",
        {
            "message_id": "msg1",
            "attachment_id": "att-1",
            "output_path": str(dest),
        },
    )
    assert dest.read_bytes() == b"hello"
    assert result["size"] == 5


def test_send_gmail_draft_requires_confirm():
    with pytest.raises(ConfirmationRequiredError):
        invoke_tool("send_gmail_draft", {"draft_id": "d1"})


@patch("integrator.providers.google_gmail_extra._gmail_service")
def test_list_gmail_labels(mock_service_fn: MagicMock) -> None:
    service = MagicMock()
    mock_service_fn.return_value = service
    service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": [{"id": "INBOX", "name": "INBOX", "type": "system"}]
    }
    from integrator.providers.google_gmail_extra import invoke_gmail_extra_tool

    result = invoke_gmail_extra_tool("list_gmail_labels", "pessoal", {})
    assert result["count"] == 1


def test_restore_gmail_requires_confirm():
    with pytest.raises(ConfirmationRequiredError):
        invoke_tool("restore_gmail_message", {"message_id": "m1"})


@patch("integrator.providers.google_gmail_extra._gmail_service")
def test_mark_gmail_read(mock_service_fn: MagicMock) -> None:
    service = MagicMock()
    mock_service_fn.return_value = service
    service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {
        "labelIds": ["INBOX"]
    }
    from integrator.providers.google_gmail_extra import invoke_gmail_extra_tool

    result = invoke_gmail_extra_tool(
        "mark_gmail_read", "pessoal", {"message_id": "m1"}
    )
    assert result["read"] is True


def test_trash_gmail_requires_confirm():
    with pytest.raises(ConfirmationRequiredError):
        invoke_tool("trash_gmail_message", {"message_id": "m1"})


@patch("integrator.providers.google_gmail_extra._gmail_service")
def test_star_gmail_message(mock_service_fn: MagicMock) -> None:
    service = MagicMock()
    mock_service_fn.return_value = service
    service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {
        "labelIds": ["STARRED", "INBOX"]
    }
    from integrator.providers.google_gmail_extra import invoke_gmail_extra_tool

    result = invoke_gmail_extra_tool(
        "star_gmail_message",
        "pessoal",
        {"message_id": "m1", "starred": True},
    )
    assert result["starred"] is True
