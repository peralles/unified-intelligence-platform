import time

import pytest

from integrator.config import settings
from integrator.logging_setup import (
    app_log_path,
    read_audit_failures,
    setup_logging,
    write_audit_record,
)
from integrator.security.audit import log_tool_invocation


@pytest.fixture
def log_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(settings, "log_dir", tmp_path / "logs")
    monkeypatch.setattr(settings, "audit_log_file", tmp_path / "logs" / "audit.jsonl")
    monkeypatch.setattr(settings, "log_max_bytes", 2000)
    monkeypatch.setattr(settings, "audit_log_max_bytes", 500)
    monkeypatch.setattr(settings, "audit_log_backup_count", 2)
    from integrator.logging_setup import reset_logging

    reset_logging()
    setup_logging(force=True)
    return tmp_path


def test_app_log_created(log_env):
    assert app_log_path().is_file()


def test_audit_failure_visible_in_failures_reader(log_env):
    from integrator.logging_setup import flush_logging

    log_tool_invocation(
        "search_gmail",
        success=False,
        duration_ms=1.0,
        error_kind="auth",
        account_id="pessoal",
    )
    flush_logging()
    failures = read_audit_failures(limit=10)
    assert len(failures) >= 1
    assert failures[0]["tool"] == "search_gmail"
    assert failures[0]["error"] == "auth"


def test_success_skips_audit_by_default(log_env):
    from integrator.logging_setup import flush_logging

    log_tool_invocation(
        "search_gmail",
        success=True,
        duration_ms=1.0,
        account_id="pessoal",
    )
    flush_logging()
    assert settings.audit_log_path.read_text(encoding="utf-8").strip() == ""


def test_audit_rotation(log_env):
    from integrator.logging_setup import flush_logging

    for i in range(30):
        write_audit_record(
            {
                "ts": f"2026-01-01T00:00:{i:02d}Z",
                "tool": "t",
                "success": False,
                "duration_ms": 1,
                "error": "x",
            }
        )
    flush_logging()
    audit_files = list((settings.root_dir / "logs").glob("audit.jsonl*"))
    assert len(audit_files) >= 2


def test_log_invoke_overhead_bounded(log_env, monkeypatch):
    """Caminho de sucesso (sem audit) deve ser muito rápido."""
    from integrator.logging_setup import flush_logging
    from integrator.security.audit import log_tool_invocation

    iterations = 500
    start = time.perf_counter()
    for _ in range(iterations):
        log_tool_invocation("search_gmail", success=True, duration_ms=0.5)
    elapsed_ms = (time.perf_counter() - start) * 1000
    flush_logging()
    assert elapsed_ms < 50.0, f"logging success path slow: {elapsed_ms:.1f}ms for {iterations}"
