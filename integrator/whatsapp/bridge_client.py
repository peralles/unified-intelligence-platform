from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from integrator.config import settings
from integrator.whatsapp.errors import WhatsAppApiError, WhatsAppNotConnectedError
from integrator.whatsapp.logging_whatsapp import LOGGER

def _read_rpc_response(
    stdout: Any,
    req_id: str,
    *,
    method: str,
) -> dict[str, Any]:
    """Read lines until a JSON-RPC response for req_id (skip library noise on stdout)."""
    while True:
        raw = stdout.readline()
        if not raw:
            raise WhatsAppApiError(
                "Worker WhatsApp encerrou sem resposta (verifique logs no terminal)."
            )
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            resp = json.loads(stripped)
        except json.JSONDecodeError:
            LOGGER.debug("bridge skip non-json stdout | method=%s | %r", method, stripped[:80])
            continue
        if resp.get("id") != req_id:
            continue
        return resp


def resolve_session_dir(explicit: Path | None = None) -> Path:
    """Caminho da sessão; nunca None (usa whatsapp_session_path quando dir opcional não está setado)."""
    return explicit or settings.whatsapp_session_path


class WhatsAppBridgeClient:
    """JSON-RPC over stdin/stdout to bridges/whatsapp-neonize worker."""

    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._req_id = 0

    @staticmethod
    def bridge_root() -> Path:
        return settings.root_dir / "bridges" / "whatsapp-neonize"

    def _next_id(self) -> str:
        self._req_id += 1
        return str(self._req_id)

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        bridge = self.bridge_root()
        if not (bridge / "pyproject.toml").is_file():
            raise WhatsAppApiError(
                f"Bridge neonize ausente em {bridge}. Verifique o repositório."
            )
        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)
        env["INTEGRATOR_WHATSAPP_SESSION_DIR"] = str(self.session_dir.resolve())
        from integrator.whatsapp.session_store import WHATSAPP_CLIENT_NAME

        env["INTEGRATOR_WHATSAPP_CLIENT_NAME"] = WHATSAPP_CLIENT_NAME
        env["INTEGRATOR_WHATSAPP_MAX_CACHED_MESSAGES_PER_CHAT"] = str(
            settings.whatsapp_max_cached_messages_per_chat
        )
        env["INTEGRATOR_WHATSAPP_PERSIST_CACHE"] = (
            "true" if settings.whatsapp_persist_cache else "false"
        )
        cmd = [
            "uv",
            "run",
            "--directory",
            str(bridge),
            "python",
            "worker.py",
        ]
        try:
            LOGGER.debug(
                "bridge start | session=%s | bridge=%s",
                self.session_dir,
                bridge,
            )
            # stderr inherited so pair QR (worker writes to stderr) is visible in the terminal
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
                env=env,
                cwd=str(bridge),
            )
        except OSError as exc:
            LOGGER.warning("bridge start FAIL | %s", exc)
            raise WhatsAppApiError(f"Não foi possível iniciar worker WhatsApp: {exc}") from exc
        if self._proc.stdin is None or self._proc.stdout is None:
            raise WhatsAppApiError("Worker WhatsApp sem stdin/stdout")
        return self._proc

    def is_worker_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        with self._lock:
            proc = self._ensure_process()
            assert proc.stdin is not None
            assert proc.stdout is not None
            req_id = self._next_id()
            line = json.dumps(
                {"id": req_id, "method": method, "params": params},
                ensure_ascii=False,
            )
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            resp = _read_rpc_response(proc.stdout, req_id, method=method)
            if not resp.get("ok"):
                msg = str(resp.get("error", "erro desconhecido"))
                LOGGER.warning("bridge RPC FAIL | method=%s | %s", method, msg[:200])
                if "não conectado" in msg.lower() or "not connected" in msg.lower():
                    raise WhatsAppNotConnectedError(f"[integrator] {msg}")
                raise WhatsAppApiError(f"[integrator] {msg}")
            return resp.get("result")

    def close(self) -> None:
        with self._lock:
            if self._proc is None:
                return
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except OSError:
                pass
            LOGGER.debug("bridge stop | session=%s", self.session_dir)
            self._proc.terminate()
            self._proc = None


def run_bridge_command(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    session_dir: Path | None = None,
) -> Any:
    """One-shot bridge invocation (CLI pair/status live)."""
    root = resolve_session_dir(session_dir)
    root.mkdir(parents=True, exist_ok=True)
    LOGGER.debug("bridge one-shot | method=%s", method)
    client = WhatsAppBridgeClient(root)
    try:
        return client.call(method, params)
    finally:
        if method in ("pair", "connect"):
            try:
                client.call("shutdown", {})
            except WhatsAppApiError:
                LOGGER.debug("bridge graceful shutdown skipped | method=%s", method)
        client.close()
