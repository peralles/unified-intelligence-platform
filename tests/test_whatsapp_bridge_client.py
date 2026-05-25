from __future__ import annotations

import io
import json

import pytest

from integrator.whatsapp.bridge_client import _read_rpc_response
from integrator.whatsapp.errors import WhatsAppApiError


def test_read_rpc_response_skips_empty_and_noise() -> None:
    payload = {"id": "7", "ok": True, "result": {"logged_in": True}}
    stdout = io.StringIO("\n\nPress Ctrl+C to exit\n" + json.dumps(payload) + "\n")
    resp = _read_rpc_response(stdout, "7", method="pair")
    assert resp["ok"] is True
    assert resp["result"]["logged_in"] is True


def test_read_rpc_response_eof_raises() -> None:
    stdout = io.StringIO("\n")
    with pytest.raises(WhatsAppApiError, match="encerrou sem resposta"):
        _read_rpc_response(stdout, "1", method="pair")
