from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from integrator.whatsapp.bridge_client import WhatsAppBridgeClient, _read_rpc_response
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


@patch("integrator.whatsapp.bridge_client.subprocess.Popen")
def test_bridge_reaps_dead_worker_before_restart(mock_popen: MagicMock) -> None:
    dead = MagicMock()
    dead.poll.return_value = 1
    dead.stdin = MagicMock()
    dead.wait.return_value = 1

    alive = MagicMock()
    alive.poll.return_value = None
    alive.stdin = MagicMock()
    alive.stdout = io.StringIO(json.dumps({"id": "1", "ok": True, "result": {}}) + "\n")

    mock_popen.return_value = alive

    client = WhatsAppBridgeClient(Path("/tmp/wa-reap-test"))
    client._proc = dead
    client.call("status")
    dead.wait.assert_called()
    mock_popen.assert_called_once()
    assert client._proc is alive
    client.close()
    alive.wait.assert_called()
