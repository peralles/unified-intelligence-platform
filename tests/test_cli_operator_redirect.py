from __future__ import annotations

import pytest

from integrator.cli.operator_redirect import (
    OPERATOR_COMMANDS,
    admin_console_url,
    maybe_redirect_operator_command,
)
from integrator.config import settings


def test_admin_url_uses_service_settings() -> None:
    url = admin_console_url()
    assert url.startswith("http://")
    assert str(settings.service_port) in url


def test_redirect_status_when_not_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cli_legacy", False)
    with pytest.raises(SystemExit) as exc:
        maybe_redirect_operator_command("status")
    assert exc.value.code == 0


def test_no_redirect_serve() -> None:
    maybe_redirect_operator_command("serve")


def test_legacy_skips_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cli_legacy", True)
    maybe_redirect_operator_command("whatsapp")


def test_operator_command_set() -> None:
    assert "hermes" in OPERATOR_COMMANDS
    assert "serve" not in OPERATOR_COMMANDS
    assert "init" not in OPERATOR_COMMANDS
