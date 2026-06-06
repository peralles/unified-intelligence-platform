from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from integrator.auth.linkedin_oauth import (
    LinkedInAuthError,
    LinkedInConfigError,
    _is_token_valid,
    _load_raw_token,
    _save_token,
    linkedin_token_path,
    list_linkedin_accounts,
    remove_linkedin_account,
)


@pytest.fixture()
def tmp_token_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(
        "integrator.auth.linkedin_oauth.settings",
        type("S", (), {"root_dir": tmp_path, "linkedin_client_id": "cid", "linkedin_client_secret": "csec", "oauth_public_base_url": None})(),
    )
    (tmp_path / "data" / "tokens").mkdir(parents=True)
    return tmp_path


def _make_token(*, valid: bool = True, sub: str = "ABC") -> dict:
    return {
        "access_token": "tok",
        "expires_at": time.time() + (3600 if valid else -1),
        "refresh_token": "rtok",
        "refresh_token_expires_at": time.time() + 86400,
        "sub": sub,
        "name": "Test User",
        "email": "test@example.com",
    }


def test_token_path_format(tmp_token_dir: Path) -> None:
    path = linkedin_token_path("pessoal")
    assert path.name == "linkedin_pessoal.json"
    assert "tokens" in str(path)


def test_save_and_load_token(tmp_token_dir: Path) -> None:
    tok = _make_token()
    with patch("integrator.auth.linkedin_oauth.settings") as ms:
        ms.root_dir = tmp_token_dir
        _save_token("default", tok)
        loaded = _load_raw_token("default")
    assert loaded is not None
    assert loaded["access_token"] == "tok"


def test_is_token_valid_fresh() -> None:
    tok = _make_token(valid=True)
    assert _is_token_valid(tok) is True


def test_is_token_valid_expired() -> None:
    tok = _make_token(valid=False)
    assert _is_token_valid(tok) is False


def test_list_linkedin_accounts_empty(tmp_token_dir: Path) -> None:
    with patch("integrator.auth.linkedin_oauth.settings") as ms:
        ms.root_dir = tmp_token_dir
        accounts = list_linkedin_accounts()
    assert accounts == []


def test_list_linkedin_accounts_finds_token(tmp_token_dir: Path) -> None:
    tok = _make_token(sub="XYZ")
    with patch("integrator.auth.linkedin_oauth.settings") as ms:
        ms.root_dir = tmp_token_dir
        _save_token("minha", tok)
        accounts = list_linkedin_accounts()
    assert len(accounts) == 1
    assert accounts[0]["id"] == "minha"
    assert accounts[0]["has_token"] is True
    assert accounts[0]["token_valid"] is True


def test_remove_linkedin_account(tmp_token_dir: Path) -> None:
    tok = _make_token()
    with patch("integrator.auth.linkedin_oauth.settings") as ms:
        ms.root_dir = tmp_token_dir
        _save_token("default", tok)
        removed = remove_linkedin_account("default")
        assert removed is True
        accounts = list_linkedin_accounts()
    assert accounts == []


def test_remove_linkedin_account_not_found(tmp_token_dir: Path) -> None:
    with patch("integrator.auth.linkedin_oauth.settings") as ms:
        ms.root_dir = tmp_token_dir
        removed = remove_linkedin_account("nonexistent")
    assert removed is False


def test_check_configured_raises_when_missing() -> None:
    with patch("integrator.auth.linkedin_oauth.settings") as ms:
        ms.linkedin_client_id = None
        ms.linkedin_client_secret = None
        from integrator.auth.linkedin_oauth import _check_configured
        with pytest.raises(LinkedInConfigError):
            _check_configured()


def test_check_configured_ok() -> None:
    with patch("integrator.auth.linkedin_oauth.settings") as ms:
        ms.linkedin_client_id = "cid"
        ms.linkedin_client_secret = "csec"
        from integrator.auth.linkedin_oauth import _check_configured
        cid, csec = _check_configured()
    assert cid == "cid"
    assert csec == "csec"


def test_start_authorization_builds_url() -> None:
    with patch("integrator.auth.linkedin_oauth.settings") as ms:
        ms.linkedin_client_id = "test_client"
        ms.linkedin_client_secret = "test_secret"
        ms.oauth_public_base_url = None
        from integrator.auth.linkedin_oauth import start_linkedin_authorization
        url = start_linkedin_authorization(
            public_base="https://mcp.example.com",
            account_id="pessoal",
        )
    assert "linkedin.com/oauth/v2/authorization" in url
    assert "test_client" in url
    assert "w_member_social" in url
    assert "openid" in url


def test_load_token_missing_raises() -> None:
    with patch("integrator.auth.linkedin_oauth._load_raw_token", return_value=None):
        with pytest.raises(LinkedInAuthError, match="Token LinkedIn não encontrado"):
            from integrator.auth.linkedin_oauth import load_linkedin_token
            load_linkedin_token("nonexistent")
