from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from integrator.config import settings
from integrator.logging_setup import enqueue_audit_line, format_audit_line, get_logger

_tools_logger_instance = None


def _get_tools_logger():
    global _tools_logger_instance
    if _tools_logger_instance is None:
        _tools_logger_instance = get_logger("tools")
    return _tools_logger_instance


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
    Registro leve: fila assíncrona: não bloqueia invoke_tool.

    - Sucesso: sem audit por padrão (INTEGRATOR_AUDIT_LOG_SUCCESS=true para gravar tudo)
    - Falha: uma linha JSON no audit + WARNING no app log
    """
    if success and not settings.audit_log_success:
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

    line = format_audit_line(record)
    enqueue_audit_line(line)

    if success:
        if settings.log_tool_success:
            _get_tools_logger().info(
                "tool OK | %s | account=%s | %.1fms",
                tool_name,
                account_id or "-",
                duration_ms,
            )
        return

    _get_tools_logger().warning(
        "tool FAIL | %s | account=%s | error=%s | blocked=%s | %.1fms",
        tool_name,
        account_id or "-",
        error_kind or "unknown",
        blocked,
        duration_ms,
    )
