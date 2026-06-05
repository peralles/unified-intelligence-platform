from __future__ import annotations

from unittest.mock import MagicMock, patch

from integrator.admin import handlers


def test_whatsapp_snapshot_uses_non_blocking_status() -> None:
    session = MagicMock()
    session.status.return_value = {"state": "qr", "logged_in": False}
    session.transcription_status.side_effect = RuntimeError("bridge down")

    with (
        patch("integrator.admin.handlers.settings") as mock_settings,
        patch("integrator.admin.handlers.local_status_snapshot", return_value={"has_session": False}),
        patch("integrator.admin.handlers.WhatsAppSession.get", return_value=session),
    ):
        mock_settings.whatsapp_enabled = True
        out = handlers.whatsapp_snapshot()

    session.status.assert_called_once_with(live=False)
    assert out["live"]["state"] == "qr"
    assert "transcription_error" in out
    assert "error" not in out
