from __future__ import annotations

from pathlib import Path

from langchain_google_community._utils import get_google_credentials

from integrator.config import GOOGLE_SCOPES, settings


class GoogleAuthError(Exception):
    """Raised when Google OAuth credentials are missing or invalid."""


def ensure_credentials_file() -> Path:
    path = settings.credentials_path
    if not path.is_file():
        raise GoogleAuthError(
            f"Arquivo OAuth não encontrado: {path}\n"
            "Baixe credentials.json (Desktop app) do Google Cloud e coloque em credentials/."
        )
    return path


def load_google_credentials(*, interactive: bool = False):
    """
    Carrega credenciais Google unificadas (Gmail + Calendar) em um único token.

    interactive=False: não abre navegador; falha se token ausente/inválido.
    interactive=True: permite fluxo InstalledAppFlow (auth_login).
    """
    settings.ensure_data_dirs()
    creds_path = ensure_credentials_file()
    token_path = settings.token_path

    if not interactive and not token_path.is_file():
        raise GoogleAuthError(
            f"Token não encontrado: {token_path}\n"
            "Execute: python -m integrator.cli.auth_login"
        )

    # get_google_credentials sempre tenta refresh/local server se inválido.
    # Para modo não interativo sem token, já falhamos acima.
    import os

    previous_cwd = os.getcwd()
    try:
        os.chdir(settings.root_dir)
        return get_google_credentials(
            scopes=list(GOOGLE_SCOPES),
            token_file=str(token_path),
            client_secrets_file=str(creds_path),
        )
    finally:
        os.chdir(previous_cwd)


def run_interactive_login() -> Path:
    """Executa OAuth no navegador e persiste token unificado."""
    settings.ensure_data_dirs()
    ensure_credentials_file()
    load_google_credentials(interactive=True)
    return settings.token_path
