from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from integrator.config import settings

_CONFIGURED = False
AUDIT_LOGGER_NAME = "integrator.audit"


def log_dir() -> Path:
    if settings.log_dir:
        return settings.log_dir
    return settings.root_dir / "data" / "logs"


def app_log_path() -> Path:
    return log_dir() / "integrator.log"


def error_log_path() -> Path:
    return log_dir() / "errors.log"


class _ReadableFormatter(logging.Formatter):
    """Linha única legível para grep e tail."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        level = record.levelname
        name = record.name
        msg = record.getMessage()
        base = f"{ts}Z | {level:7} | {name} | {msg}"
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            base = f"{base}\n{record.exc_text}"
        return base


def reset_logging() -> None:
    """Reinicia configuração (útil em testes)."""
    global _CONFIGURED
    _CONFIGURED = False
    for name in ("integrator", AUDIT_LOGGER_NAME):
        logging.getLogger(name).handlers.clear()


def setup_logging(*, force: bool = False) -> None:
    """Configura logging rotativo (idempotente)."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return
    if force:
        reset_logging()

    log_dir().mkdir(parents=True, exist_ok=True)
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = _ReadableFormatter()

    app_handler = RotatingFileHandler(
        app_log_path(),
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(level)

    err_handler = RotatingFileHandler(
        error_log_path(),
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    err_handler.setFormatter(formatter)
    err_handler.setLevel(logging.WARNING)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.setLevel(level)

    root = logging.getLogger("integrator")
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(app_handler)
    root.addHandler(err_handler)
    root.addHandler(console)
    root.propagate = False

    audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)
    audit_logger.handlers.clear()
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False

    audit_handler = RotatingFileHandler(
        settings.audit_log_path,
        maxBytes=settings.audit_log_max_bytes,
        backupCount=settings.audit_log_backup_count,
        encoding="utf-8",
    )
    audit_handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(audit_handler)

    _CONFIGURED = True
    root.info(
        "Logging iniciado | app=%s | errors=%s | audit=%s",
        app_log_path(),
        error_log_path(),
        settings.audit_log_path,
    )


def get_logger(name: str) -> logging.Logger:
    if not _CONFIGURED:
        setup_logging()
    if name.startswith("integrator."):
        return logging.getLogger(name)
    return logging.getLogger(f"integrator.{name}")


def write_audit_record(record: dict[str, Any]) -> None:
    if not settings.audit_log_enabled:
        return
    settings.ensure_data_dirs()
    if not _CONFIGURED:
        setup_logging()
    logging.getLogger(AUDIT_LOGGER_NAME).info(json.dumps(record, ensure_ascii=False))


def list_log_files() -> list[Path]:
    """Arquivos de log do integrador (inclui backups rotativos)."""
    base = log_dir()
    patterns = [
        "integrator.log*",
        "errors.log*",
        "audit.jsonl*",
        "service/*.log*",
    ]
    found: list[Path] = []
    for pattern in patterns:
        found.extend(base.glob(pattern))
    return sorted({p.resolve() for p in found if p.is_file()})


def tail_file(path: Path, *, lines: int = 40) -> list[str]:
    if not path.is_file():
        return []
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return content[-lines:]


def read_audit_failures(*, limit: int = 30) -> list[dict[str, Any]]:
    """Últimas falhas de tools (success=false) em todos os audit*.jsonl."""
    failures: list[dict[str, Any]] = []
    audit_dir = settings.audit_log_path.parent
    files = sorted(audit_dir.glob("audit.jsonl*"), reverse=True)
    for path in files:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("success") is False:
                failures.append(row)
        if len(failures) >= limit:
            break
    failures.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return failures[:limit]
