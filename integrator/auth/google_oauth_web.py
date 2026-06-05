"""Browser OAuth redirect flow for admin / Coolify (replaces run_local_server in containers)."""

from __future__ import annotations

import secrets
import threading
import time
from pathlib import Path
from typing import Any

from integrator.accounts.registry import (
    AccountNotFoundError,
    add_account,
    get_account,
    update_account_email,
    validate_account_id,
)
from integrator.auth.google_oauth import (
    GoogleAuthError,
    _fetch_account_email,
    ensure_credentials_file,
)
from integrator.config import GOOGLE_SCOPES, settings
from integrator.security.token_permissions import secure_token_file

_pending_lock = threading.Lock()
_pending: dict[str, dict[str, Any]] = {}
_STATE_TTL_S = 600


def oauth_callback_path() -> str:
    return "/admin/oauth/google/callback"


def build_redirect_uri(public_base: str) -> str:
    return f"{public_base.rstrip('/')}{oauth_callback_path()}"


def resolve_public_base_url(
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


def _purge_expired() -> None:
    now = time.time()
    expired = [
        key
        for key, value in _pending.items()
        if now - float(value.get("created_at", 0)) > _STATE_TTL_S
    ]
    for key in expired:
        _pending.pop(key, None)


def start_oauth_authorization(
    *,
    public_base: str,
    account_id: str,
    label: str | None,
) -> str:
    """Return Google authorization URL; stores OAuth state server-side."""
    aid = validate_account_id(account_id)
    settings.ensure_data_dirs()
    ensure_credentials_file()
    try:
        get_account(aid)
    except AccountNotFoundError:
        add_account(aid, label=label or aid)

    redirect_uri = build_redirect_uri(public_base)
    state = secrets.token_urlsafe(32)
    with _pending_lock:
        _purge_expired()
        _pending[state] = {
            "account_id": aid,
            "redirect_uri": redirect_uri,
            "created_at": time.time(),
        }

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        str(settings.credentials_path),
        scopes=list(GOOGLE_SCOPES),
        redirect_uri=redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",
    )
    return auth_url


def complete_oauth_authorization(*, state: str, code: str) -> Path:
    """Exchange authorization code and persist token for the pending account."""
    with _pending_lock:
        _purge_expired()
        pending = _pending.pop(state, None)
    if not pending:
        raise GoogleAuthError("Sessão OAuth expirada ou inválida. Tente conectar novamente.")

    redirect_uri = str(pending["redirect_uri"])
    account_id = str(pending["account_id"])

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        str(settings.credentials_path),
        scopes=list(GOOGLE_SCOPES),
        redirect_uri=redirect_uri,
        state=state,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_path = get_account(account_id).token_path
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    secure_token_file(token_path)

    email = _fetch_account_email(creds)
    if email:
        update_account_email(account_id, email)

    from integrator.providers.tool_cache import invalidate_live_tools

    invalidate_live_tools(account_id)
    return token_path
