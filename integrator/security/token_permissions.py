from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def secure_token_file(path: Path) -> None:
    """Restringe leitura/escrita do token ao usuário local (chmod 600)."""
    if not path.is_file():
        return
    try:
        os.chmod(path, 0o600)
    except OSError:
        logger.warning("Não foi possível aplicar chmod 600 em %s", path)
