from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from integrator.hermes.config_merge import DEFAULT_SERVER_NAME
from integrator.hermes.doctor import CheckResult, CheckStatus

CLAUDE_APP_PATHS = (
    Path("/Applications/Claude.app"),
    Path.home() / "Applications/Claude.app",
)


@dataclass(frozen=True)
class ClaudeDesktopInstall:
    config_path: Path
    app_found: bool


def claude_desktop_config_path() -> Path:
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def discover_claude_desktop() -> ClaudeDesktopInstall:
    path = claude_desktop_config_path()
    app_found = any(p.is_dir() for p in CLAUDE_APP_PATHS)
    return ClaudeDesktopInstall(config_path=path, app_found=app_found)


def to_claude_server_block(block: dict[str, Any]) -> dict[str, Any]:
    """Hermes YAML block → Claude Desktop mcpServers entry."""
    if "url" in block:
        return {"url": str(block["url"])}
    out: dict[str, Any] = {
        "command": str(block["command"]),
        "args": [str(a) for a in block.get("args") or []],
    }
    env = block.get("env")
    if isinstance(env, dict) and env:
        out["env"] = {str(k): str(v) for k, v in env.items()}
    return out


def load_claude_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Config Claude inválido (esperado object): {path}")
    return data


def save_claude_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_claude_mcp_entry(path: Path, server_name: str) -> dict[str, Any] | None:
    data = load_claude_config(path)
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return None
    entry = servers.get(server_name)
    return entry if isinstance(entry, dict) else None


def merge_claude_mcp_server(
    config_path: Path,
    server_name: str,
    server_block: dict[str, Any],
    *,
    overwrite: bool = False,
) -> tuple[bool, str]:
    data = load_claude_config(config_path)
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("mcpServers deve ser um object no config Claude")

    if server_name in servers and not overwrite:
        return False, f"Servidor MCP '{server_name}' já existe em {config_path}"

    if config_path.is_file():
        backup = config_path.with_name(config_path.name + ".bak")
        if not backup.is_file():
            shutil.copy2(config_path, backup)

    servers[server_name] = to_claude_server_block(server_block)
    save_claude_config(config_path, data)
    return True, f"Gravado em {config_path}"


def run_claude_desktop_checks(
    *,
    server_name: str = DEFAULT_SERVER_NAME,
) -> list[CheckResult]:
    install = discover_claude_desktop()
    results: list[CheckResult] = []

    results.append(
        CheckResult(
            id="claude_app",
            label="Claude Desktop",
            status=CheckStatus.OK if install.app_found else CheckStatus.WARN,
            detail="instalado" if install.app_found else "app não encontrado",
            hint=None
            if install.app_found
            else "Instale Claude Desktop (https://claude.ai/download)",
        )
    )

    parent = install.config_path.parent
    writable = False
    try:
        parent.mkdir(parents=True, exist_ok=True)
        writable = True
    except OSError:
        writable = False

    results.append(
        CheckResult(
            id="claude_config",
            label="Config Claude Desktop",
            status=CheckStatus.OK if writable else CheckStatus.FAIL,
            detail=str(install.config_path),
            hint=None if writable else f"Não foi possível criar {parent}",
        )
    )

    existing = get_claude_mcp_entry(install.config_path, server_name)
    if existing:
        results.append(
            CheckResult(
                id="claude_mcp_entry",
                label=f"Claude MCP '{server_name}'",
                status=CheckStatus.WARN,
                detail="já configurado",
                hint="Admin ou setup reconfigura com yes=true",
            )
        )
    else:
        results.append(
            CheckResult(
                id="claude_mcp_entry",
                label=f"Claude MCP '{server_name}'",
                status=CheckStatus.OK,
                detail="ainda não configurado",
                hint="Admin → Configurar MCP (Hermes + Claude)",
            )
        )

    return results
