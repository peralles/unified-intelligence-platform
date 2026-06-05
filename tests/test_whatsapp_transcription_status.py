from __future__ import annotations

from unittest.mock import MagicMock, patch

from integrator.whatsapp.session import WhatsAppSession


def test_transcription_status_local_without_worker() -> None:
    session = WhatsAppSession.__new__(WhatsAppSession)
    session._bridge = MagicMock()
    session._bridge.is_worker_alive.return_value = False

    with patch("integrator.whatsapp.session.RuntimeStore") as store_cls:
        store = store_cls.return_value
        store.load.return_value = {}
        store.effective_whatsapp.return_value = {
            "auto_transcribe": True,
            "transcribe_model": "small",
            "transcribe_language": "pt",
            "transcribe_prefix": "[audio]",
            "transcribe_only_incoming": False,
            "transcribe_private_only": True,
            "transcribe_ignore_numbers": ["5511999999999"],
        }
        data = session.transcription_status()

    session._bridge.call.assert_not_called()
    assert data["auto_transcribe"] is True
    assert data["model"] == "small"
    assert data["transcriber_ready"] is False
    assert data["ignore_count"] == 1
