"""Admin console URL for bootstrap CLI messages."""

from __future__ import annotations

from integrator.config import settings


def admin_console_url() -> str:
    return f"http://{settings.service_host}:{settings.service_port}/admin"
