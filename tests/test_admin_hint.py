from __future__ import annotations

from integrator.cli.admin_hint import admin_console_url
from integrator.config import settings


def test_admin_url_uses_service_settings() -> None:
    url = admin_console_url()
    assert url.startswith("http://")
    assert str(settings.service_port) in url
    assert url.endswith("/admin")
