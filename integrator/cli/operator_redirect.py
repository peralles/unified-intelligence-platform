"""Redirect operator-facing CLI commands to the local admin console."""

from __future__ import annotations

import sys

from integrator.config import settings

OPERATOR_COMMANDS = frozenset(
    {
        "status",
        "login",
        "accounts",
        "use",
        "logout",
        "tools",
        "logs",
        "whatsapp",
        "hermes",
    }
)

_ADMIN_HINT = (
    "Operação diária migrou para o console web local.\n"
    "\n"
    "  {url}\n"
    "\n"
    "Suba o serviço se ainda não estiver ativo:\n"
    "  uv run integrator service install    # macOS LaunchAgent\n"
    "  uv run integrator serve-http         # foreground\n"
    "\n"
    "Atalho: ./setup.sh admin\n"
    "\n"
    "CLI legado (scripts/CI): INTEGRATOR_CLI_LEGACY=true uv run integrator …"
)


def admin_console_url() -> str:
    return f"http://{settings.service_host}:{settings.service_port}/admin"


def maybe_redirect_operator_command(command: str | None) -> None:
    """Exit 0 with admin hint when command is operator-facing and legacy CLI is off."""
    if not command or settings.cli_legacy:
        return
    if command not in OPERATOR_COMMANDS:
        return
    print(_ADMIN_HINT.format(url=admin_console_url()), file=sys.stderr)
    raise SystemExit(0)
