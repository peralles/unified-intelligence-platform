from __future__ import annotations

import json
import time
import webbrowser
from pathlib import Path

from integrator.config import settings
from integrator.onboarding.links import GOOGLE_SETUP_STEPS


class CredentialsValidationError(Exception):
    """JSON OAuth inválido para o integrador."""


def validate_credentials_file(path: Path) -> None:
    """Garante que o arquivo é um OAuth client Desktop/Web válido."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CredentialsValidationError(
            "O arquivo baixado não é um JSON válido."
        ) from exc

    if not isinstance(data, dict):
        raise CredentialsValidationError("Formato do JSON não reconhecido.")

    block = data.get("installed") or data.get("web")
    if not isinstance(block, dict):
        raise CredentialsValidationError(
            "Esperado um OAuth client do Google (chave 'installed' ou 'web')."
        )
    if not block.get("client_id") or not block.get("client_secret"):
        raise CredentialsValidationError(
            "O JSON não contém client_id e client_secret."
        )


def credentials_ready() -> bool:
    path = settings.credentials_path
    if not path.is_file():
        return False
    try:
        validate_credentials_file(path)
        return True
    except CredentialsValidationError:
        return False


def install_credentials_from(source: Path) -> Path:
    """Copia JSON validado para data/credentials/credentials.json."""
    validate_credentials_file(source)
    dest = settings.credentials_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def open_url(url: str) -> None:
    try:
        webbrowser.open(url, new=2)
    except Exception:
        print(f"  Abra no navegador: {url}")


def open_google_setup_sequence(*, interactive: bool = True) -> None:
    """Abre passos do Google Cloud no navegador."""
    total = len(GOOGLE_SETUP_STEPS)
    for i, step in enumerate(GOOGLE_SETUP_STEPS, start=1):
        print(f"\n  ({i}/{total}) {step.title}")
        print(f"      {step.instruction}")
        open_url(step.url)
        if interactive and i < total:
            try:
                input("  Pressione Enter para o próximo passo (ou Ctrl+C para cancelar)… ")
            except KeyboardInterrupt:
                print()
                raise


def wait_for_credentials(
    *,
    poll_interval: float = 2.0,
    timeout_seconds: float = 1800.0,
    auto_yes: bool = False,
) -> Path:
    """
    Espera data/credentials/credentials.json (ou upload via admin).

    Raises:
        KeyboardInterrupt: usuário cancelou
        TimeoutError: tempo esgotado
    """
    _ = auto_yes
    dest = settings.credentials_path
    deadline = time.monotonic() + timeout_seconds
    print("\n  Aguardando o arquivo de credenciais…")
    print(f"  Caminho: {dest}")
    print("  Envie client_secret.json no admin (/admin → Google) ou copie manualmente.")

    while time.monotonic() < deadline:
        if dest.is_file():
            try:
                validate_credentials_file(dest)
                print("  Credenciais Google configuradas.")
                return dest
            except CredentialsValidationError as exc:
                print(f"  Arquivo encontrado mas inválido: {exc}")
                print("  Corrija o JSON ou envie novamente pelo admin.")

        time.sleep(poll_interval)

    raise TimeoutError(
        "Tempo esgotado aguardando credentials.json. "
        "Envie o JSON no admin ou rode integrator init novamente."
    )


def run_google_credentials_wizard(*, interactive: bool, auto_yes: bool) -> Path:
    """Fluxo completo: abrir Console, esperar JSON, validar."""
    if credentials_ready():
        return settings.credentials_path

    print("\nVamos criar um acesso seguro ao seu Gmail e calendário.")
    print("O Google pede uma configuração única no navegador (cerca de 5 minutos).")

    if interactive and not auto_yes:
        try:
            answer = input("\n  Abrir o assistente do Google no navegador? [S/n] ").strip().lower()
        except KeyboardInterrupt:
            print()
            raise
        if answer not in ("", "s", "sim", "y", "yes"):
            print(f"  Quando tiver o JSON, envie no admin ou coloque em {settings.credentials_path}")
            return wait_for_credentials(auto_yes=auto_yes)

    open_google_setup_sequence(interactive=interactive and not auto_yes)

    print("\n  Depois de baixar o JSON:")
    print("  • Envie no console admin (/admin → Google), ou")
    print(f"  • Copie para {settings.credentials_path}")

    return wait_for_credentials(auto_yes=auto_yes)
