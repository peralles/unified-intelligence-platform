from __future__ import annotations

import shutil
from pathlib import Path

from integrator.config import settings


def session_path() -> Path:
    return settings.whatsapp_session_path.resolve()


def session_db_path() -> Path:
    return session_path() / "neonize.db"


def has_persisted_session() -> bool:
    """True se há artefato de sessão neonize no disco (sem subir o worker)."""
    db = session_db_path()
    return db.is_file() and db.stat().st_size > 0


def local_status_snapshot() -> dict[str, object]:
    """Resumo rápido para CLI/status geral — sem subprocesso neonize."""
    path = session_path()
    db = session_db_path()
    return {
        "enabled": settings.whatsapp_enabled,
        "session_dir": str(path),
        "has_session_db": has_persisted_session(),
        "session_db_bytes": db.stat().st_size if db.is_file() else 0,
        "max_message_chars": settings.whatsapp_max_message_chars,
    }


def remove_session_data(*, keep_directory: bool = True) -> list[str]:
    """
    Apaga credenciais/sessão WhatsApp local (equivalente a logout Google).

    Returns:
        Nomes relativos dos itens removidos (para feedback CLI).
    """
    root = session_path()
    if not root.exists():
        return []

    removed: list[str] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        rel = child.name
        if child.is_file():
            child.unlink(missing_ok=True)
            removed.append(rel)
        elif child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
            removed.append(f"{rel}/")
    if not keep_directory:
        shutil.rmtree(root, ignore_errors=True)
        removed.append("(diretório)")
    elif not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    return removed
