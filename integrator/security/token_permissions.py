from __future__ import annotations

import os
from pathlib import Path

from integrator.logging_setup import get_logger

logger = get_logger("security")


def secure_token_file(path: Path) -> None:
    """Restringe leitura/escrita do token ao usuário local (chmod 600)."""
    if not path.is_file():
        return
    try:
        os.chmod(path, 0o600)
    except OSError:
        logger.warning("Não foi possível aplicar chmod 600 em %s", path)
