"""Tests for integrator.setup.status."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from integrator.setup.status import configuration_summary, is_configured


def test_is_configured_false_without_credentials() -> None:
    with patch("integrator.setup.status.credentials_ready", return_value=False):
        assert is_configured() is False


def test_is_configured_true_with_token() -> None:
    account = MagicMock(has_token=True)
    with (
        patch("integrator.setup.status.credentials_ready", return_value=True),
        patch("integrator.setup.status.list_accounts", return_value=[account]),
    ):
        assert is_configured() is True


def test_configuration_summary_incomplete() -> None:
    with patch("integrator.setup.status.credentials_ready", return_value=False):
        label, next_step = configuration_summary()
    assert label == "incompleta"
    assert next_step is not None
    assert "admin" in next_step


def test_configuration_summary_complete_google_only() -> None:
    account = MagicMock(has_token=True)
    with (
        patch("integrator.setup.status.credentials_ready", return_value=True),
        patch("integrator.setup.status.list_accounts", return_value=[account]),
        patch("integrator.setup.status.settings") as mock_settings,
        patch("integrator.setup.status.has_persisted_session", return_value=False),
    ):
        mock_settings.whatsapp_enabled = True
        label, next_step = configuration_summary()
    assert label == "completa (Google)"
    assert next_step is not None
