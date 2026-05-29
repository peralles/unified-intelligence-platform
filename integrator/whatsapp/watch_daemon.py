"""
Watch daemon for WhatsApp audio auto-transcription.

Runs the neonize worker in watch mode (INTEGRATOR_WHATSAPP_WATCH_MODE=true)
as a standalone background process that requires no active Hermes session.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from integrator.config import settings
from integrator.whatsapp.logging_whatsapp import LOGGER

WATCH_SERVICE_LABEL = "com.peralles.langchain-integrator-whatsapp-watch"


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


# ------------------------------------------------------------------ #
# macOS LaunchAgent for watch mode
# ------------------------------------------------------------------ #

def _watch_launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def watch_plist_path() -> Path:
    return _watch_launch_agents_dir() / f"{WATCH_SERVICE_LABEL}.plist"


def _watch_log_dir() -> Path:
    path = settings.root_dir / "data" / "logs" / "watch"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _launchctl_domain() -> str:
    return f"gui/{os.getuid()}"


def _launchctl_target() -> str:
    return f"{_launchctl_domain()}/{WATCH_SERVICE_LABEL}"


def _run_launchctl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args],
        capture_output=True,
        text=True,
    )


def watch_service_is_loaded() -> bool:
    if sys.platform != "darwin":
        return False
    if not shutil.which("launchctl"):
        return False
    result = _run_launchctl(["print", _launchctl_target()])
    return result.returncode == 0


def write_watch_plist(*, model: str | None = None, language: str | None = None) -> Path:
    if sys.platform != "darwin":
        raise WatchDaemonError(
            "LaunchAgent só disponível no macOS. "
            "Em Linux, use systemd ou nohup integrator whatsapp watch."
        )
    uv = _resolve_uv()
    root = settings.root_dir.resolve()
    logs = _watch_log_dir()
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        "HOME": str(Path.home()),
        "INTEGRATOR_WHATSAPP_WATCH_MODE": "true",
        "INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE": "true",
        "INTEGRATOR_WHATSAPP_SESSION_DIR": str(
            settings.whatsapp_session_path.resolve()
        ),
        "INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL": (
            model or settings.whatsapp_transcribe_model
        ),
        "INTEGRATOR_WHATSAPP_TRANSCRIBE_PREFIX": settings.whatsapp_transcribe_prefix,
        "INTEGRATOR_WHATSAPP_TRANSCRIBE_ONLY_INCOMING": (
            "true" if settings.whatsapp_transcribe_only_incoming else "false"
        ),
        "INTEGRATOR_WHATSAPP_MAX_CACHED_MESSAGES_PER_CHAT": str(
            settings.whatsapp_max_cached_messages_per_chat
        ),
    }
    if language or settings.whatsapp_transcribe_language:
        env["INTEGRATOR_WHATSAPP_TRANSCRIBE_LANGUAGE"] = (
            language or settings.whatsapp_transcribe_language or ""
        )

    bridge = _bridge_root()
    program_args = [
        uv,
        "run",
        "--directory",
        str(bridge),
        "python",
        "worker.py",
    ]
    plist: dict[str, Any] = {
        "Label": WATCH_SERVICE_LABEL,
        "ProgramArguments": program_args,
        "WorkingDirectory": str(root),
        "EnvironmentVariables": env,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(logs / "stdout.log"),
        "StandardErrorPath": str(logs / "stderr.log"),
    }
    _watch_launch_agents_dir().mkdir(parents=True, exist_ok=True)
    path = watch_plist_path()
    with path.open("wb") as fh:
        plistlib.dump(plist, fh)
    return path


def install_watch_service(
    *, model: str | None = None, language: str | None = None, start: bool = True
) -> Path:
    path = write_watch_plist(model=model, language=language)
    if start:
        enable_watch_service()
    return path


def enable_watch_service() -> None:
    if sys.platform != "darwin":
        raise WatchDaemonError("LaunchAgent só disponível no macOS.")
    path = watch_plist_path()
    if not path.is_file():
        raise WatchDaemonError(
            f"Plist não encontrado. Rode: integrator whatsapp watch-service install\n{path}"
        )
    if watch_service_is_loaded():
        _run_launchctl(["kickstart", "-k", _launchctl_target()])
        return
    domain = _launchctl_domain()
    result = _run_launchctl(["bootstrap", domain, str(path)])
    if result.returncode != 0 and "already" not in (result.stderr or "").lower():
        raise WatchDaemonError(result.stderr or result.stdout or "bootstrap falhou")
    _run_launchctl(["enable", _launchctl_target()])
    _run_launchctl(["kickstart", _launchctl_target()])


def disable_watch_service() -> None:
    if sys.platform != "darwin":
        return
    if not watch_plist_path().is_file():
        return
    _run_launchctl(["disable", _launchctl_target()])
    _run_launchctl(
        ["bootout", _launchctl_domain(), str(watch_plist_path())]
    )


def uninstall_watch_service() -> None:
    if sys.platform != "darwin":
        raise WatchDaemonError("LaunchAgent só disponível no macOS.")
    disable_watch_service()
    path = watch_plist_path()
    if path.is_file():
        path.unlink()


def watch_service_status() -> dict[str, Any]:
    loaded = watch_service_is_loaded() if sys.platform == "darwin" else False
    plist = watch_plist_path()
    return {
        "platform": sys.platform,
        "label": WATCH_SERVICE_LABEL,
        "plist": str(plist),
        "plist_exists": plist.is_file(),
        "loaded": loaded,
        "logs": str(_watch_log_dir()),
        "model": settings.whatsapp_transcribe_model,
        "language": settings.whatsapp_transcribe_language or "auto",
        "prefix": settings.whatsapp_transcribe_prefix,
    }
