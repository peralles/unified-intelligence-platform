from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from integrator.config import settings

logger = logging.getLogger(__name__)


def _audit_path():
    settings.ensure_data_dirs()
    path = settings.audit_log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def log_tool_invocation(
    tool_name: str,
    *,
    success: bool,
    duration_ms: float,
    error_kind: str | None = None,
    blocked: bool = False,
    account_id: str | None = None,
) -> None:
    """
    Registro estruturado sem argumentos nem conteúdo de e-mail/eventos (sem PII).
    """
    if not settings.audit_log_enabled:
        return

    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "success": success,
        "duration_ms": round(duration_ms, 2),
        "blocked": blocked,
    }
    if account_id:
        record["account"] = account_id
    if error_kind:
        record["error"] = error_kind

    path = _audit_path()
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("Falha ao escrever auditoria em %s", path)
