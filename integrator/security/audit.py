from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from integrator.logging_setup import get_logger, write_audit_record

logger = get_logger("audit")


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
    Grava em audit.jsonl com rotação automática.
    """
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

    try:
        write_audit_record(record)
    except OSError:
        logger.exception("Falha ao escrever auditoria")

    app_logger = get_logger("tools")
    if success:
        app_logger.info(
            "tool ok | %s | account=%s | %.1fms",
            tool_name,
            account_id or "-",
            duration_ms,
        )
    else:
        app_logger.warning(
            "tool FAIL | %s | account=%s | error=%s | blocked=%s | %.1fms",
            tool_name,
            account_id or "-",
            error_kind or "unknown",
            blocked,
            duration_ms,
        )
