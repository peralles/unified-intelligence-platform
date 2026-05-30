"""Dependency preflight checks shared by admin, init wizard, and Hermes doctor."""

from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser

from integrator.config import settings
from integrator.onboarding.links import UV_INSTALL

REPO_DEPS_TIMEOUT_SEC = 90


def repo_deps_ok(*, timeout: int = REPO_DEPS_TIMEOUT_SEC) -> bool:
    """True when .venv exists or `uv run integrator status` succeeds."""
    if (settings.root_dir / ".venv").is_dir():
        return True
    uv = shutil.which("uv")
    if not uv:
        return False
    try:
        result = subprocess.run(
            [uv, "run", "integrator", "status"],
            cwd=settings.root_dir,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_uv_sync(*, verbose: bool = False) -> int:
    """Install project dependencies via uv sync --all-extras."""
    uv = shutil.which("uv")
    if not uv:
        print("\n  O gerenciador 'uv' não está instalado.")
        print("  Abrindo página de instalação…")
        try:
            webbrowser.open(UV_INSTALL, new=2)
        except Exception:
            print(f"  Instale em: {UV_INSTALL}")
        return 1

    print("\n  Instalando dependências do projeto (pode levar um minuto)…")
    if verbose:
        print(f"  Comando: {uv} sync --all-extras")
    result = subprocess.run(
        [uv, "sync", "--all-extras"],
        cwd=settings.root_dir,
        check=False,
    )
    if result.returncode != 0:
        print("  Falha ao instalar dependências.", file=sys.stderr)
        return result.returncode
    print("  Dependências instaladas.")
    return 0
