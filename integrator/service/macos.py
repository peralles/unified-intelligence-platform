from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from integrator.config import settings

SERVICE_LABEL = "com.peralles.langchain-integrator"
DEFAULT_PORT = 17320


class MacServiceError(Exception):
    """Erro na gestão do LaunchAgent."""


def is_macos() -> bool:
    return sys.platform == "darwin"


def require_macos() -> None:
    if not is_macos():
        raise MacServiceError(
            "Gestão de serviço só está disponível no macOS (LaunchAgent). "
            "Em Linux, use integrator serve no seu gerenciador (systemd)."
        )


def launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def plist_path() -> Path:
    return launch_agents_dir() / f"{SERVICE_LABEL}.plist"


def service_log_dir() -> Path:
    path = settings.root_dir / "data" / "logs" / "service"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _launchctl_domain() -> str:
    uid = os.getuid()
    return f"gui/{uid}"


def _launchctl_target() -> str:
    return f"{_launchctl_domain()}/{SERVICE_LABEL}"


def resolve_uv() -> str:
    uv = shutil.which("uv")
    if uv:
        return uv
    for candidate in ("/opt/homebrew/bin/uv", "/usr/local/bin/uv"):
        if Path(candidate).is_file():
            return candidate
    raise MacServiceError(
        "uv não encontrado no PATH. Instale: https://docs.astral.sh/uv/"
    )


def _whatsapp_transcribe_env() -> dict[str, str]:
    """WhatsApp worker vars from Settings (.env), for LaunchAgent (no subprocess bridge)."""
    return {
        "INTEGRATOR_WHATSAPP_ENABLED": (
            "true" if settings.whatsapp_enabled else "false"
        ),
        "INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE": (
            "true" if settings.whatsapp_auto_transcribe else "false"
        ),
        "INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL": settings.whatsapp_transcribe_model,
        "INTEGRATOR_WHATSAPP_TRANSCRIBE_PREFIX": settings.whatsapp_transcribe_prefix,
        "INTEGRATOR_WHATSAPP_TRANSCRIBE_ONLY_INCOMING": (
            "true" if settings.whatsapp_transcribe_only_incoming else "false"
        ),
        "INTEGRATOR_WHATSAPP_TRANSCRIBE_PRIVATE_ONLY": (
            "true" if settings.whatsapp_transcribe_private_only else "false"
        ),
        "INTEGRATOR_WHATSAPP_MAX_CACHED_MESSAGES_PER_CHAT": str(
            settings.whatsapp_max_cached_messages_per_chat
        ),
        "INTEGRATOR_WHATSAPP_PERSIST_CACHE": (
            "true" if settings.whatsapp_persist_cache else "false"
        ),
    }


def build_program_arguments(port: int) -> list[str]:
    uv = resolve_uv()
    root = settings.root_dir.resolve()
    return [
        uv,
        "run",
        "--directory",
        str(root),
        "integrator",
        "serve-http",
        "--host",
        settings.service_host,
        "--port",
        str(port),
    ]


def write_plist(*, port: int) -> Path:
    require_macos()
    path = plist_path()
    logs = service_log_dir()
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        "HOME": str(Path.home()),
        "INTEGRATOR_ROOT": str(settings.root_dir.resolve()),
    }
    for key in (
        "INTEGRATOR_TOOL_ALLOWLIST",
        "INTEGRATOR_TOOL_DENYLIST",
        "INTEGRATOR_AUDIT_LOG_ENABLED",
    ):
        if key in os.environ:
            env[key] = os.environ[key]

    env.update(_whatsapp_transcribe_env())
    if settings.whatsapp_transcribe_language:
        env["INTEGRATOR_WHATSAPP_TRANSCRIBE_LANGUAGE"] = (
            settings.whatsapp_transcribe_language
        )
    if settings.whatsapp_session_dir:
        env["INTEGRATOR_WHATSAPP_SESSION_DIR"] = str(
            settings.whatsapp_session_dir.resolve()
        )
    env["INTEGRATOR_ADMIN_RUNTIME_FILE"] = str(settings.admin_runtime_path.resolve())

    plist = {
        "Label": SERVICE_LABEL,
        "ProgramArguments": build_program_arguments(port),
        "WorkingDirectory": str(settings.root_dir.resolve()),
        "EnvironmentVariables": env,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(logs / "stdout.log"),
        "StandardErrorPath": str(logs / "stderr.log"),
    }
    launch_agents_dir().mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(plist, fh)
    return path


def _run_launchctl(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["launchctl", *args],
        capture_output=True,
        text=True,
    )


def is_loaded() -> bool:
    require_macos()
    if not shutil.which("launchctl"):
        return False
    result = _run_launchctl(["print", _launchctl_target()], check=False)
    return result.returncode == 0


def install_service(*, port: int = DEFAULT_PORT, start: bool = True) -> Path:
    path = write_plist(port=port)
    if start:
        enable_service()
    return path


def enable_service() -> None:
    """Ativa o serviço (bootstrap + kickstart)."""
    require_macos()
    path = plist_path()
    if not path.is_file():
        raise MacServiceError(f"Plist não encontrado. Rode: integrator service install\n{path}")

    if is_loaded():
        _run_launchctl(["kickstart", "-k", _launchctl_target()])
        return

    domain = _launchctl_domain()
    result = _run_launchctl(["bootstrap", domain, str(path)])
    if result.returncode != 0 and "already" not in (result.stderr or "").lower():
        raise MacServiceError(result.stderr or result.stdout or "bootstrap falhou")
    _run_launchctl(["enable", _launchctl_target()])
    _run_launchctl(["kickstart", _launchctl_target()])


def disable_service() -> None:
    """Desativa o serviço (para o processo, mantém o plist)."""
    require_macos()
    if not plist_path().is_file():
        return
    _run_launchctl(["disable", _launchctl_target()], check=False)
    _run_launchctl(["bootout", _launchctl_domain(), str(plist_path())], check=False)


def uninstall_service() -> None:
    """Desinstala: para o serviço e remove o plist."""
    require_macos()
    disable_service()
    path = plist_path()
    if path.is_file():
        path.unlink()


def service_status(*, port: int = DEFAULT_PORT) -> dict[str, str | bool | int]:
    require_macos()
    loaded = is_loaded()
    plist = plist_path()
    return {
        "platform": "macOS",
        "label": SERVICE_LABEL,
        "plist": str(plist),
        "plist_exists": plist.is_file(),
        "loaded": loaded,
        "url_sse": f"http://{settings.service_host}:{port}/sse",
        "url_mcp": f"http://{settings.service_host}:{port}/mcp",
        "url_health": f"http://{settings.service_host}:{port}/health",
        "url_admin": f"http://{settings.service_host}:{port}/admin",
        "logs": str(service_log_dir()),
        "port": port,
    }
