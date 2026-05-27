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
