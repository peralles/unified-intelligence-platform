"""LinkedIn OAuth 2.0 Authorization Code flow for admin/Coolify."""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from integrator.config import settings
from integrator.security.token_permissions import secure_token_file

_LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
_LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

_LINKEDIN_SCOPES = "openid profile email w_member_social"

_pending_lock = threading.Lock()
_pending: dict[str, dict[str, Any]] = {}
_STATE_TTL_S = 600


class LinkedInAuthError(Exception):
    """Raised when LinkedIn OAuth credentials are missing or invalid."""


class LinkedInConfigError(Exception):
    """Raised when LinkedIn client_id/client_secret are not configured."""


def _check_configured() -> tuple[str, str]:
    client_id = settings.linkedin_client_id
    client_secret = settings.linkedin_client_secret
    if not client_id or not client_secret:
        raise LinkedInConfigError(
            "LinkedIn não configurado. Defina INTEGRATOR_LINKEDIN_CLIENT_ID e "
            "INTEGRATOR_LINKEDIN_CLIENT_SECRET no ambiente."
        )
    return client_id, client_secret


def linkedin_token_path(account_id: str) -> Path:
    safe_id = account_id.strip().lower()
    return settings.root_dir / "data" / "tokens" / f"linkedin_{safe_id}.json"


def _save_token(account_id: str, data: dict[str, Any]) -> Path:
    path = linkedin_token_path(account_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    secure_token_file(path)
    return path


def _load_raw_token(account_id: str) -> dict[str, Any] | None:
    path = linkedin_token_path(account_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _is_token_valid(token: dict[str, Any]) -> bool:
    expires_at = token.get("expires_at", 0)
    return time.time() < (float(expires_at) - 60)


def _refresh_token(token: dict[str, Any], account_id: str) -> dict[str, Any]:
    client_id, client_secret = _check_configured()
    refresh_tok = token.get("refresh_token")
    if not refresh_tok:
        raise LinkedInAuthError(
            f"Sem refresh_token para '{account_id}'. Reconecte a conta LinkedIn."
        )
    import urllib.request

    params = urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_tok,
        "client_id": client_id,
        "client_secret": client_secret,
    })
    req = urllib.request.Request(
        _LINKEDIN_TOKEN_URL,
        data=params.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        new_tok = json.loads(resp.read())

    now = time.time()
    updated = {
        **token,
        "access_token": new_tok["access_token"],
        "expires_at": now + int(new_tok.get("expires_in", 5184000)),
    }
    if "refresh_token" in new_tok:
        updated["refresh_token"] = new_tok["refresh_token"]
        updated["refresh_token_expires_at"] = now + int(
            new_tok.get("refresh_token_expires_in", 31536000)
        )
    _save_token(account_id, updated)
    return updated


def load_linkedin_token(account_id: str) -> dict[str, Any]:
    """Load and refresh LinkedIn token for account_id."""
    token = _load_raw_token(account_id)
    if not token:
        raise LinkedInAuthError(
            f"Token LinkedIn não encontrado para '{account_id}'. "
            "Conecte a conta no console admin."
        )
    if not _is_token_valid(token):
        token = _refresh_token(token, account_id)
    return token


def get_access_token(account_id: str) -> str:
    return load_linkedin_token(account_id)["access_token"]


def list_linkedin_accounts() -> list[dict[str, Any]]:
    token_dir = settings.root_dir / "data" / "tokens"
    if not token_dir.is_dir():
        return []
    accounts = []
    for path in sorted(token_dir.glob("linkedin_*.json")):
        raw_id = path.stem.removeprefix("linkedin_")
        token = _load_raw_token(raw_id)
        if token is None:
            continue
        now = time.time()
        expires_at = float(token.get("expires_at", 0))
        refresh_expires_at = float(token.get("refresh_token_expires_at", 0))
        accounts.append({
            "id": raw_id,
            "name": token.get("name"),
            "email": token.get("email"),
            "picture": token.get("picture"),
            "sub": token.get("sub"),
            "has_token": True,
            "token_valid": now < expires_at - 60,
            "refresh_valid": now < refresh_expires_at - 60 if refresh_expires_at else None,
            "expires_at": int(expires_at) if expires_at else None,
        })
    return accounts


def remove_linkedin_account(account_id: str) -> bool:
    path = linkedin_token_path(account_id)
    if path.is_file():
        path.unlink()
        return True
    return False


def _purge_expired_states() -> None:
    now = time.time()
    expired = [
        key for key, val in _pending.items()
        if now - float(val.get("created_at", 0)) > _STATE_TTL_S
    ]
    for key in expired:
        _pending.pop(key, None)


def oauth_callback_path() -> str:
    return "/admin/oauth/linkedin/callback"


def _resolve_public_base(
    *,
    forwarded_proto: str | None,
    forwarded_host: str | None,
    host: str | None,
) -> str:
    if settings.oauth_public_base_url:
        return settings.oauth_public_base_url.rstrip("/")
    scheme = (forwarded_proto or "http").split(",")[0].strip()
    hostname = (forwarded_host or host or "127.0.0.1:17320").split(",")[0].strip()
    return f"{scheme}://{hostname}"


def start_linkedin_authorization(
    *,
    public_base: str,
    account_id: str,
) -> str:
    """Return LinkedIn authorization URL; stores OAuth state server-side."""
    _check_configured()
    client_id = settings.linkedin_client_id
    redirect_uri = f"{public_base.rstrip('/')}{oauth_callback_path()}"
    state = secrets.token_urlsafe(32)

    params = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": _LINKEDIN_SCOPES,
        "state": state,
    })
    auth_url = f"{_LINKEDIN_AUTH_URL}?{params}"

    with _pending_lock:
        _purge_expired_states()
        _pending[state] = {
            "account_id": account_id.strip().lower(),
            "redirect_uri": redirect_uri,
            "created_at": time.time(),
        }
    return auth_url


def complete_linkedin_authorization(*, state: str, code: str) -> dict[str, Any]:
    """Exchange authorization code and persist token."""
    with _pending_lock:
        _purge_expired_states()
        pending = _pending.pop(state, None)
    if not pending:
        raise LinkedInAuthError("Sessão OAuth expirada ou inválida. Tente conectar novamente.")

    account_id = str(pending["account_id"])
    redirect_uri = str(pending["redirect_uri"])
    client_id, client_secret = _check_configured()

    import urllib.request

    params = urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    })
    req = urllib.request.Request(
        _LINKEDIN_TOKEN_URL,
        data=params.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        tok_data = json.loads(resp.read())

    if "access_token" not in tok_data:
        raise LinkedInAuthError(
            f"LinkedIn recusou o token: {tok_data.get('error_description', tok_data)}"
        )

    now = time.time()
    token: dict[str, Any] = {
        "access_token": tok_data["access_token"],
        "expires_at": now + int(tok_data.get("expires_in", 5184000)),
        "scope": tok_data.get("scope", _LINKEDIN_SCOPES),
    }
    if "refresh_token" in tok_data:
        token["refresh_token"] = tok_data["refresh_token"]
        token["refresh_token_expires_at"] = now + int(
            tok_data.get("refresh_token_expires_in", 31536000)
        )

    # Fetch user profile
    profile_req = urllib.request.Request(
        _LINKEDIN_USERINFO_URL,
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    try:
        with urllib.request.urlopen(profile_req, timeout=10) as resp:
            profile = json.loads(resp.read())
        token["sub"] = profile.get("sub")
        token["name"] = profile.get("name")
        token["email"] = profile.get("email")
        token["picture"] = profile.get("picture")
        token["given_name"] = profile.get("given_name")
        token["family_name"] = profile.get("family_name")
    except Exception:
        pass

    settings.ensure_data_dirs()
    _save_token(account_id, token)
    return {
        "account_id": account_id,
        "name": token.get("name"),
        "email": token.get("email"),
    }
