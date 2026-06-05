from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from integrator.auth import google_oauth_web as oauth_web
from integrator.auth.google_oauth_web import (
    build_redirect_uri,
    complete_oauth_authorization,
    resolve_public_base_url,
    start_oauth_authorization,
)


def test_build_redirect_uri() -> None:
    assert (
        build_redirect_uri("https://mcp.example.com")
        == "https://mcp.example.com/admin/oauth/google/callback"
    )


def test_resolve_public_base_url_prefers_settings() -> None:
    with patch.object(oauth_web.settings, "oauth_public_base_url", "https://fixed.example.com"):
        assert (
            resolve_public_base_url(
                forwarded_proto="http",
                forwarded_host="wrong.example.com",
                host="localhost",
            )
            == "https://fixed.example.com"
        )


def test_resolve_public_base_url_from_forwarded_headers() -> None:
    with patch.object(oauth_web.settings, "oauth_public_base_url", None):
        assert (
            resolve_public_base_url(
                forwarded_proto="https",
                forwarded_host="mcp.example.com",
                host="127.0.0.1:17320",
            )
            == "https://mcp.example.com"
        )


def test_start_oauth_authorization_returns_auth_url() -> None:
    flow = MagicMock()
    flow.code_verifier = "pkce-verifier"
    flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?x=1", None)

    with (
        patch("integrator.auth.google_oauth_web.settings") as mock_settings,
        patch("integrator.auth.google_oauth_web.ensure_credentials_file"),
        patch("integrator.auth.google_oauth_web.get_account"),
        patch("google_auth_oauthlib.flow.Flow.from_client_secrets_file", return_value=flow),
    ):
        mock_settings.credentials_path = "/tmp/credentials.json"
        mock_settings.ensure_data_dirs = MagicMock()
        url = start_oauth_authorization(
            public_base="https://mcp.example.com",
            account_id="pessoal",
            label=None,
        )

    assert url.startswith("https://accounts.google.com/")
    kwargs = flow.authorization_url.call_args.kwargs
    assert kwargs["access_type"] == "offline"
    assert kwargs["prompt"] == "consent"
    assert kwargs["state"]
    assert oauth_web._pending[kwargs["state"]]["code_verifier"] == "pkce-verifier"


def test_complete_oauth_authorization_persists_token(tmp_path) -> None:
    token_path = tmp_path / "pessoal.json"
    creds = MagicMock()
    creds.to_json.return_value = '{"token": "x"}'
    start_flow = MagicMock()
    start_flow.code_verifier = "pkce-verifier"
    start_flow.authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/auth",
        None,
    )
    complete_flow = MagicMock()
    complete_flow.credentials = creds

    account = MagicMock()
    account.token_path = token_path

    with (
        patch("integrator.auth.google_oauth_web.settings") as mock_settings,
        patch("integrator.auth.google_oauth_web.ensure_credentials_file"),
        patch("integrator.auth.google_oauth_web.get_account", return_value=account),
        patch("integrator.auth.google_oauth_web._fetch_account_email", return_value="a@b.com"),
        patch("integrator.auth.google_oauth_web.update_account_email") as mock_update_email,
        patch("integrator.auth.google_oauth_web.secure_token_file") as mock_secure,
        patch("integrator.providers.tool_cache.invalidate_live_tools"),
        patch(
            "google_auth_oauthlib.flow.Flow.from_client_secrets_file",
            side_effect=[start_flow, complete_flow],
        ) as mock_from_secrets,
    ):
        mock_settings.credentials_path = "/tmp/credentials.json"
        mock_settings.ensure_data_dirs = MagicMock()
        start_oauth_authorization(
            public_base="https://mcp.example.com",
            account_id="pessoal",
            label=None,
        )
        state = start_flow.authorization_url.call_args.kwargs["state"]
        out = complete_oauth_authorization(state=state, code="auth-code")

    assert token_path.is_file()
    mock_secure.assert_called_once_with(token_path)
    mock_update_email.assert_called_once_with("pessoal", "a@b.com")
    assert out == token_path
    complete_flow.fetch_token.assert_called_once_with(code="auth-code")
    complete_kwargs = mock_from_secrets.call_args_list[1].kwargs
    assert complete_kwargs["code_verifier"] == "pkce-verifier"
    assert complete_kwargs["autogenerate_code_verifier"] is False


def test_complete_oauth_invalid_state_raises() -> None:
    from integrator.auth.google_oauth import GoogleAuthError

    with pytest.raises(GoogleAuthError, match="expirada|inválida"):
        complete_oauth_authorization(state="missing", code="code")
