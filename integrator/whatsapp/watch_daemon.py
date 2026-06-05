"""
Watch daemon for WhatsApp audio auto-transcription.

Runs the neonize worker in watch mode (INTEGRATOR_WHATSAPP_WATCH_MODE=true)
as a standalone background process that requires no active Hermes session.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from integrator.config import settings
from integrator.whatsapp.logging_whatsapp import LOGGER


class WatchDaemonError(Exception):
    """Error managing the watch daemon."""


def _bridge_root() -> Path:
    return settings.root_dir / "bridges" / "whatsapp-neonize"


def _resolve_uv() -> str:
    uv = shutil.which("uv")
    if uv:
        return uv
    for candidate in ("/opt/homebrew/bin/uv", "/usr/local/bin/uv"):
        if Path(candidate).is_file():
            return candidate
    raise WatchDaemonError(
        "uv não encontrado no PATH. Instale: https://docs.astral.sh/uv/"
    )


def _build_watch_env() -> dict[str, str]:
    """Environment for the watch worker subprocess."""
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    session_dir = settings.whatsapp_session_path.resolve()
    env["INTEGRATOR_WHATSAPP_SESSION_DIR"] = str(session_dir)
    env["INTEGRATOR_WHATSAPP_WATCH_MODE"] = "true"
    env["INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE"] = "true"
    env["INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL"] = settings.whatsapp_transcribe_model
    if settings.whatsapp_transcribe_language:
        env["INTEGRATOR_WHATSAPP_TRANSCRIBE_LANGUAGE"] = (
            settings.whatsapp_transcribe_language
        )
    env["INTEGRATOR_WHATSAPP_TRANSCRIBE_PREFIX"] = settings.whatsapp_transcribe_prefix
    env["INTEGRATOR_WHATSAPP_TRANSCRIBE_ONLY_INCOMING"] = (
        "true" if settings.whatsapp_transcribe_only_incoming else "false"
    )
    env["INTEGRATOR_WHATSAPP_TRANSCRIBE_PRIVATE_ONLY"] = (
        "true" if settings.whatsapp_transcribe_private_only else "false"
    )
    env["INTEGRATOR_WHATSAPP_MAX_CACHED_MESSAGES_PER_CHAT"] = str(
        settings.whatsapp_max_cached_messages_per_chat
    )
    from integrator.whatsapp.session_store import WHATSAPP_CLIENT_NAME

    env["INTEGRATOR_WHATSAPP_CLIENT_NAME"] = WHATSAPP_CLIENT_NAME
    return env


def _build_watch_cmd(uv: str | None = None) -> list[str]:
    uv = uv or _resolve_uv()
    bridge = _bridge_root()
    return [
        uv,
        "run",
        "--directory",
        str(bridge),
        "python",
        "worker.py",
    ]


def run_watch_foreground(*, model: str | None = None, language: str | None = None) -> int:
    """
    Start watch daemon in the foreground.  Blocks until the worker exits.
    Returns the worker exit code.
    """
    bridge = _bridge_root()
    if not (bridge / "pyproject.toml").is_file():
        raise WatchDaemonError(
            f"Bridge neonize ausente em {bridge}. Verifique o repositório."
        )

    env = _build_watch_env()
    if model:
        env["INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL"] = model
    if language:
        env["INTEGRATOR_WHATSAPP_TRANSCRIBE_LANGUAGE"] = language

    cmd = _build_watch_cmd()
    LOGGER.debug(
        "watch foreground | model=%s | lang=%s",
        env.get("INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL"),
        env.get("INTEGRATOR_WHATSAPP_TRANSCRIBE_LANGUAGE", "auto"),
    )
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=None,  # inherited → terminal
        stderr=None,  # inherited → terminal (shows QR / logs)
        env=env,
        cwd=str(bridge),
    )
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 130
