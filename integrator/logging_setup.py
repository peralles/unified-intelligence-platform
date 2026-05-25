from __future__ import annotations

import atexit
import json
import logging
import sys
import time
from datetime import datetime, timezone
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from queue import Queue
from typing import Any

from integrator.config import settings

_CONFIGURED = False
_LOG_QUEUE: Queue[Any] | None = None
_LISTENER: QueueListener | None = None
_AUDIT_LOGGER_NAME = "integrator.audit"


class _ReadableFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        base = f"{ts}Z | {record.levelname:7} | {record.name} | {record.getMessage()}"
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            base = f"{base}\n{record.exc_text}"
        return base


class _AuditOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == _AUDIT_LOGGER_NAME


class _NonAuditFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.name != _AUDIT_LOGGER_NAME


def log_dir() -> Path:
    if settings.log_dir:
        return settings.log_dir
    return settings.root_dir / "data" / "logs"


def app_log_path() -> Path:
    return log_dir() / "integrator.log"


def error_log_path() -> Path:
    return log_dir() / "errors.log"


def shutdown_logging() -> None:
    global _LISTENER, _LOG_QUEUE, _CONFIGURED
    if _LISTENER is not None:
        _LISTENER.stop()
        _LISTENER = None
    _LOG_QUEUE = None
    _CONFIGURED = False


def reset_logging() -> None:
    shutdown_logging()
    for name in ("integrator", _AUDIT_LOGGER_NAME):
        logging.getLogger(name).handlers.clear()


def setup_logging(*, force: bool = False) -> None:
    """Logging rotativo em thread de fundo (QueueHandler) — não bloqueia tools."""
    global _CONFIGURED, _LOG_QUEUE, _LISTENER
    if _CONFIGURED and not force:
        return
    if force:
        reset_logging()

    settings.ensure_data_dirs()
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
    app_handler.addFilter(_NonAuditFilter())

    err_handler = RotatingFileHandler(
        error_log_path(),
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    err_handler.setFormatter(formatter)
    err_handler.setLevel(logging.WARNING)
    err_handler.addFilter(_NonAuditFilter())

    audit_handler = RotatingFileHandler(
        settings.audit_log_path,
        maxBytes=settings.audit_log_max_bytes,
        backupCount=settings.audit_log_backup_count,
        encoding="utf-8",
    )
    audit_handler.setFormatter(logging.Formatter("%(message)s"))
    audit_handler.setLevel(logging.INFO)
    audit_handler.addFilter(_AuditOnlyFilter())

    listener_handlers: list[logging.Handler] = [app_handler, err_handler, audit_handler]
    if settings.log_console_enabled:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        console.setLevel(level)
        console.addFilter(_NonAuditFilter())
        listener_handlers.append(console)

    _LOG_QUEUE = Queue(-1)
    _LISTENER = QueueListener(_LOG_QUEUE, *listener_handlers, respect_handler_level=True)
    _LISTENER.start()
    atexit.register(shutdown_logging)

    queue_handler = QueueHandler(_LOG_QUEUE)

    root = logging.getLogger("integrator")
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(queue_handler)
    root.propagate = False

    audit_logger = logging.getLogger(_AUDIT_LOGGER_NAME)
    audit_logger.handlers.clear()
    audit_logger.setLevel(logging.INFO)
    audit_logger.addHandler(queue_handler)
    audit_logger.propagate = False

    _CONFIGURED = True
    root.info(
        "Logging async | app=%s | audit=%s | audit_success=%s",
        app_log_path(),
        settings.audit_log_path,
        settings.audit_log_success,
    )


def get_logger(name: str) -> logging.Logger:
    if not _CONFIGURED:
        setup_logging()
    if name.startswith("integrator."):
        return logging.getLogger(name)
    return logging.getLogger(f"integrator.{name}")


# Linha JSON pré-montada para audit (evita dict+.dumps duplicado no hot path de falha)
def format_audit_line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def enqueue_audit_line(line: str) -> None:
    if not settings.audit_log_enabled:
        return
    if not _CONFIGURED:
        setup_logging()
    logging.getLogger(_AUDIT_LOGGER_NAME).info(line)


def write_audit_record(record: dict[str, Any]) -> None:
    enqueue_audit_line(format_audit_line(record))


def list_log_files() -> list[Path]:
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


def flush_logging(*, timeout: float = 2.0) -> None:
    """Aguarda a fila de log esvaziar (útil em testes)."""
    if _LOG_QUEUE is None:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _LOG_QUEUE.empty():
            return
        time.sleep(0.005)


def read_audit_failures(*, limit: int = 30) -> list[dict[str, Any]]:
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
