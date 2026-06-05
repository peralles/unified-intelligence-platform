from __future__ import annotations

from integrator.logging_setup import app_log_path, flush_logging, get_logger, setup_logging
from integrator.ops_log import log_event, redact_jid, truncate


def test_redact_jid_masks_user_part() -> None:
    assert redact_jid("161044295061648@lid") == "***1648@lid"
    assert redact_jid("5511999999999@s.whatsapp.net") == "***9999@s.whatsapp.net"
    assert redact_jid(None) == "-"


def test_truncate_long_error() -> None:
    assert truncate("x" * 300, limit=20).endswith("...")
    assert len(truncate("x" * 300, limit=20)) == 20


def test_log_event_format(tmp_path, monkeypatch) -> None:
    from integrator.config import settings
    from integrator.logging_setup import reset_logging

    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(settings, "log_dir", tmp_path / "logs")
    monkeypatch.setattr(settings, "log_console_enabled", False)
    reset_logging()
    setup_logging(force=True)
    logger = get_logger("test.ops")
    log_event(logger, "whatsapp.transcribe.ok", chat=redact_jid("123@lid"), chars=64)
    flush_logging()
    text = app_log_path().read_text(encoding="utf-8")
    assert "event=whatsapp.transcribe.ok" in text
    assert "chars=64" in text
    assert "123@lid" not in text
