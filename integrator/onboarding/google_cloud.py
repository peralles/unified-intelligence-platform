from __future__ import annotations

import json
import shutil
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


def find_downloads_candidates() -> list[Path]:
    """Procura JSON típico de OAuth client na pasta Downloads."""
    downloads = Path.home() / "Downloads"
    if not downloads.is_dir():
        return []
    patterns = ("client_secret*.json", "credentials*.json", "client*.json")
    found: list[Path] = []
    for pattern in patterns:
        found.extend(downloads.glob(pattern))
    unique = []
    seen: set[str] = set()
    for p in sorted(found, key=lambda x: x.stat().st_mtime, reverse=True):
        key = str(p.resolve())
        if key in seen or not p.is_file():
            continue
        seen.add(key)
        try:
            validate_credentials_file(p)
            unique.append(p)
        except CredentialsValidationError:
            continue
    return unique


def install_credentials_from(source: Path) -> Path:
    """Copia JSON validado para credentials/credentials.json."""
    validate_credentials_file(source)
    dest = settings.credentials_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
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


def try_import_from_downloads(*, auto_yes: bool = False) -> Path | None:
    """Se houver um único candidato válido em Downloads, copia para credentials/."""
    if credentials_ready():
        return settings.credentials_path

    candidates = find_downloads_candidates()
    if not candidates:
        return None

    if len(candidates) == 1:
        src = candidates[0]
        if auto_yes:
            return install_credentials_from(src)
        print(f"\n  Encontramos o arquivo baixado: {src.name}")
        try:
            answer = input("  Usar este arquivo? [S/n] ").strip().lower()
        except KeyboardInterrupt:
            print()
            raise
        if answer in ("", "s", "sim", "y", "yes"):
            return install_credentials_from(src)
        return None

    print("\n  Vários arquivos OAuth encontrados em Downloads:")
    for idx, p in enumerate(candidates[:5], start=1):
        print(f"    {idx}. {p.name}")
    if auto_yes and candidates:
        return install_credentials_from(candidates[0])
    try:
        choice = input("  Número do arquivo a usar (Enter = aguardar cópia manual): ").strip()
    except KeyboardInterrupt:
        print()
        raise
    if not choice:
        return None
    try:
        picked = candidates[int(choice) - 1]
    except (ValueError, IndexError):
        print("  Opção inválida.")
        return None
    return install_credentials_from(picked)


def wait_for_credentials(
    *,
    poll_interval: float = 2.0,
    timeout_seconds: float = 1800.0,
    auto_yes: bool = False,
) -> Path:
    """
    Espera credentials/credentials.json ou importa de Downloads.

    Raises:
        KeyboardInterrupt: usuário cancelou
        TimeoutError: tempo esgotado
    """
    dest = settings.credentials_path
    deadline = time.monotonic() + timeout_seconds
    print("\n  Aguardando o arquivo de credenciais…")
    print("  (Detectamos automaticamente em credentials/ ou na pasta Downloads)")

    while time.monotonic() < deadline:
        imported = try_import_from_downloads(auto_yes=auto_yes)
        if imported is not None:
            print("  Credenciais Google configuradas.")
            return imported

        if dest.is_file():
            try:
                validate_credentials_file(dest)
                print("  Credenciais Google configuradas.")
                return dest
            except CredentialsValidationError as exc:
                print(f"  Arquivo encontrado mas inválido: {exc}")
                print("  Corrija o JSON ou baixe novamente do Google Cloud.")

        time.sleep(poll_interval)

    raise TimeoutError(
        "Tempo esgotado aguardando credentials.json. "
        "Rode integrator init novamente quando tiver o arquivo."
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
            print("  Quando tiver o JSON, coloque em credentials/credentials.json")
            return wait_for_credentials(auto_yes=auto_yes)

    open_google_setup_sequence(interactive=interactive and not auto_yes)

    print("\n  Depois de baixar o JSON:")
    print("  • Renomeie para credentials.json e coloque na pasta credentials/ do projeto, ou")
    print("  • Deixe na pasta Downloads — detectamos automaticamente.")

    return wait_for_credentials(auto_yes=auto_yes)
