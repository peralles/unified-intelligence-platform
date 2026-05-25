from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HermesInstall:
    """Instalação local do Hermes (se detectada)."""

    binary: Path | None
    home: Path
    config_path: Path


def _hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home() / ".hermes"


def _config_path_from_hermes_cli(binary: Path) -> Path | None:
    try:
        result = subprocess.run(
            [str(binary), "config", "path"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    line = (result.stdout or "").strip().splitlines()
    if not line:
        return None
    return Path(line[0]).expanduser().resolve()


def discover_hermes() -> HermesInstall:
    """Localiza binário Hermes e caminho do config.yaml."""
    which = shutil.which("hermes")
    binary = Path(which).resolve() if which else None
    home = _hermes_home()

    config_path: Path | None = None
    if binary is not None:
        config_path = _config_path_from_hermes_cli(binary)

    if config_path is None:
        config_path = home / "config.yaml"

    return HermesInstall(
        binary=binary,
        home=home,
        config_path=config_path,
    )
