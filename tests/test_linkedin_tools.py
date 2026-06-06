from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from integrator.providers.linkedin_tools import (
    LINKEDIN_TOOL_NAMES,
    invoke_linkedin_tool,
)
from integrator.providers.tools import LINKEDIN_TOOL_COUNT
from integrator.security.policy import get_confirm_required_tools


def test_linkedin_tool_count() -> None:
    assert LINKEDIN_TOOL_COUNT == 8
    assert len(LINKEDIN_TOOL_NAMES) == 8


def test_linkedin_confirm_required() -> None:
    confirm = get_confirm_required_tools()
    for tool in (
        "share_linkedin_post",
        "share_linkedin_article",
        "delete_linkedin_post",
        "comment_linkedin_post",
        "like_linkedin_post",
        "unlike_linkedin_post",
    ):
        assert tool in confirm, f"{tool} should require confirmation"


def test_linkedin_read_tools_not_confirm_required() -> None:
    confirm = get_confirm_required_tools()
    assert "get_linkedin_profile" not in confirm
    assert "get_linkedin_my_posts" not in confirm


def _mock_token(sub: str = "ABC123") -> dict:
    return {
        "access_token": "test_token",
        "expires_at": time.time() + 3600,
        "sub": sub,
        "name": "Test User",
        "email": "test@example.com",
    }


@patch("integrator.providers.linkedin_tools.load_linkedin_token")
@patch("integrator.providers.linkedin_tools._api_get")
def test_get_linkedin_profile(mock_get: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = _mock_token()
    mock_get.return_value = {
        "sub": "ABC123",
        "name": "Test User",
        "email": "test@example.com",
        "picture": "https://example.com/pic.jpg",
    }
    result = invoke_linkedin_tool("get_linkedin_profile", "default", {})
    assert result["name"] == "Test User"
    assert result["email"] == "test@example.com"
    mock_get.assert_called_once()


@patch("integrator.providers.linkedin_tools.load_linkedin_token")
@patch("integrator.providers.linkedin_tools._api_get")
def test_get_linkedin_my_posts(mock_get: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = _mock_token()
    mock_get.return_value = {
        "elements": [
            {
                "id": "urn:li:ugcPost:123",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": "Hello LinkedIn!"}
                    }
                },
            }
        ]
    }
    result = invoke_linkedin_tool("get_linkedin_my_posts", "default", {"count": 5})
    assert result["count"] == 1
    assert result["posts"][0]["urn"] == "urn:li:ugcPost:123"
    assert result["posts"][0]["text"] == "Hello LinkedIn!"


@patch("integrator.providers.linkedin_tools.load_linkedin_token")
@patch("integrator.providers.linkedin_tools._api_post")
def test_share_linkedin_post(mock_post: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = _mock_token()
    mock_post.return_value = {"id": "urn:li:ugcPost:456"}
    result = invoke_linkedin_tool(
        "share_linkedin_post", "default", {"text": "Test post"}
    )
    assert result["ok"] is True
    assert result["post_urn"] == "urn:li:ugcPost:456"
    call_body = mock_post.call_args[0][2]
    assert call_body["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] == "NONE"
    assert call_body["lifecycleState"] == "PUBLISHED"


@patch("integrator.providers.linkedin_tools.load_linkedin_token")
@patch("integrator.providers.linkedin_tools._api_post")
def test_share_linkedin_article(mock_post: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = _mock_token()
    mock_post.return_value = {"id": "urn:li:ugcPost:789"}
    result = invoke_linkedin_tool(
        "share_linkedin_article",
        "default",
        {
            "text": "Interesting article",
            "url": "https://example.com/article",
            "title": "My Article",
        },
    )
    assert result["ok"] is True
    call_body = mock_post.call_args[0][2]
    content = call_body["specificContent"]["com.linkedin.ugc.ShareContent"]
    assert content["shareMediaCategory"] == "ARTICLE"
    assert content["media"][0]["originalUrl"] == "https://example.com/article"


def test_share_linkedin_post_requires_text() -> None:
    with patch("integrator.providers.linkedin_tools.load_linkedin_token") as m:
        m.return_value = _mock_token()
        with pytest.raises(ValueError, match="text"):
            invoke_linkedin_tool("share_linkedin_post", "default", {})


def test_share_linkedin_post_text_too_long() -> None:
    with patch("integrator.providers.linkedin_tools.load_linkedin_token") as m:
        m.return_value = _mock_token()
        with pytest.raises(ValueError, match="3000"):
            invoke_linkedin_tool(
                "share_linkedin_post", "default", {"text": "x" * 3001}
            )


@patch("integrator.providers.linkedin_tools.load_linkedin_token")
@patch("integrator.providers.linkedin_tools._api_delete")
def test_delete_linkedin_post(mock_delete: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = _mock_token()
    mock_delete.return_value = None
    result = invoke_linkedin_tool(
        "delete_linkedin_post", "default", {"post_urn": "urn:li:ugcPost:999"}
    )
    assert result["ok"] is True
    assert result["deleted_urn"] == "urn:li:ugcPost:999"


@patch("integrator.providers.linkedin_tools.load_linkedin_token")
@patch("integrator.providers.linkedin_tools._api_post")
def test_comment_linkedin_post(mock_post: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = _mock_token()
    mock_post.return_value = {"id": "urn:li:comment:111"}
    result = invoke_linkedin_tool(
        "comment_linkedin_post",
        "default",
        {"post_urn": "urn:li:ugcPost:999", "text": "Great post!"},
    )
    assert result["ok"] is True
    assert result["comment_urn"] == "urn:li:comment:111"


@patch("integrator.providers.linkedin_tools.load_linkedin_token")
@patch("integrator.providers.linkedin_tools._api_post")
def test_like_linkedin_post(mock_post: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = _mock_token()
    mock_post.return_value = {}
    result = invoke_linkedin_tool(
        "like_linkedin_post", "default", {"post_urn": "urn:li:ugcPost:999"}
    )
    assert result["ok"] is True


@patch("integrator.providers.linkedin_tools.load_linkedin_token")
@patch("integrator.providers.linkedin_tools._api_delete")
def test_unlike_linkedin_post(mock_delete: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = _mock_token()
    mock_delete.return_value = None
    result = invoke_linkedin_tool(
        "unlike_linkedin_post", "default", {"post_urn": "urn:li:ugcPost:999"}
    )
    assert result["ok"] is True


def test_unknown_tool_raises() -> None:
    with patch("integrator.providers.linkedin_tools.load_linkedin_token") as m:
        m.return_value = _mock_token()
        with pytest.raises(KeyError):
            invoke_linkedin_tool("nonexistent_tool", "default", {})


def test_linkedin_tool_names_coverage() -> None:
    expected = {
        "get_linkedin_profile",
        "share_linkedin_post",
        "share_linkedin_article",
        "get_linkedin_my_posts",
        "delete_linkedin_post",
        "comment_linkedin_post",
        "like_linkedin_post",
        "unlike_linkedin_post",
    }
    assert LINKEDIN_TOOL_NAMES == expected
