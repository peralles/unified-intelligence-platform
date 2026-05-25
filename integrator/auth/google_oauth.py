from __future__ import annotations

from pathlib import Path

from langchain_google_community._utils import get_google_credentials

from integrator.accounts.registry import (
    AccountNotFoundError,
    add_account,
    get_account,
    update_account_email,
)
from integrator.config import GOOGLE_SCOPES, settings
from integrator.security.token_permissions import secure_token_file


class GoogleAuthError(Exception):
    """Raised when Google OAuth credentials are missing or invalid."""


def ensure_credentials_file() -> Path:
    path = settings.credentials_path
    if not path.is_file():
        raise GoogleAuthError(
            "Arquivo OAuth não encontrado.\n"
            "Rode: integrator init\n"
            "(O assistente abre o Google Cloud no navegador e configura o arquivo para você.)"
        )
    return path


def _fetch_account_email(creds) -> str | None:
    try:
        from langchain_google_community.gmail.utils import build_gmail_service

        service = build_gmail_service(credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress")
    except Exception:
        return None


def load_google_credentials(*, account_id: str, interactive: bool = False):
    """
    Credenciais Google unificadas (Gmail + Calendar) para uma conta.

    Gmail e Calendar usam o mesmo token/scopes nesta conta.
    """
    settings.ensure_data_dirs()
    creds_path = ensure_credentials_file()
    account = get_account(account_id)
    token_path = account.token_path

    if not interactive and not token_path.is_file():
        raise GoogleAuthError(
            f"Token não encontrado para '{account_id}': {token_path}\n"
            f"Execute: integrator login {account_id}"
        )

    import os

    previous_cwd = os.getcwd()
    try:
        os.chdir(settings.root_dir)
        try:
            creds = get_google_credentials(
                scopes=list(GOOGLE_SCOPES),
                token_file=str(token_path),
                client_secrets_file=str(creds_path),
            )
        except Exception as exc:
            raise GoogleAuthError(
                f"Falha ao carregar/renovar token de '{account_id}' ({token_path}): {exc}\n"
                f"Execute: integrator login {account_id}"
            ) from exc
        secure_token_file(token_path)
        return creds
    finally:
        os.chdir(previous_cwd)


def run_interactive_login(
    account_id: str,
    *,
    label: str | None = None,
) -> Path:
    """OAuth no navegador; persiste token por conta."""
    settings.ensure_data_dirs()
    ensure_credentials_file()
    try:
        get_account(account_id)
    except AccountNotFoundError:
        add_account(account_id, label=label or account_id)

    creds = load_google_credentials(account_id=account_id, interactive=True)
    email = _fetch_account_email(creds)
    if email:
        update_account_email(account_id, email)

    from integrator.providers.tool_cache import invalidate_live_tools

    invalidate_live_tools(account_id)
    return get_account(account_id).token_path
