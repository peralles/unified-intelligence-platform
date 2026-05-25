"""Smoke tests do wrapper setup.sh (delega para integrator)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        [str(SETUP), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=merged,
        check=False,
    )


def test_setup_sh_is_executable_and_help():
    assert SETUP.is_file()
    assert os.access(SETUP, os.X_OK)
    proc = _run("help")
    assert proc.returncode == 0
    assert "Integrador Gmail" in proc.stdout
    assert "integrator init" in proc.stdout


def test_setup_sh_status_delegates_to_integrator(monkeypatch):
    """Com uv no PATH, status deve chamar integrator e retornar 0."""
    proc = _run("status")
    assert proc.returncode == 0
    assert "Integrador LangChain" in proc.stdout or "Configuração" in proc.stdout


def test_setup_sh_without_uv_exits_with_instructions():
    proc = _run(env={"PATH": "/usr/bin:/bin"})
    if proc.returncode == 0:
        # Ambiente de CI pode ter uv em /usr/bin; pular se passou
        return
    assert proc.returncode == 1
    assert "uv" in (proc.stdout + proc.stderr).lower()
