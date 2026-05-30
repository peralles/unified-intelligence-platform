"""Whether the integrator is configured — independent of CLI presentation."""

from __future__ import annotations

from integrator.accounts.registry import list_accounts
from integrator.config import settings
from integrator.onboarding.google_cloud import credentials_ready
from integrator.whatsapp.session_store import has_persisted_session

ADMIN_URL = "./setup.sh admin"


def is_configured() -> bool:
    """True when Google credentials exist and at least one account has a token."""
    if not credentials_ready():
        return False
    return any(a.has_token for a in list_accounts())


def configuration_summary() -> tuple[str, str | None]:
    """
    Returns:
        (status_label, next_step_hint_or_none)
    """
    if not credentials_ready():
        return "incompleta", ADMIN_URL
    accounts = list_accounts()
    if not any(a.has_token for a in accounts):
        return "incompleta", ADMIN_URL
    if settings.whatsapp_enabled and not has_persisted_session():
        return "completa (Google)", f"{ADMIN_URL} (WhatsApp → Parear)"
    return "completa", None
