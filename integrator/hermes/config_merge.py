from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from integrator.config import settings

DEFAULT_SERVER_NAME = "langchain-integrator"


def build_stdio_server_config(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Bloco MCP stdio para Hermes spawnar `integrator serve` via uv."""
    root = (repo_root or settings.root_dir).resolve()
    env: dict[str, str] = {
        "INTEGRATOR_AUDIT_LOG_ENABLED": "true",
    }
    if settings.tool_denylist:
        env["INTEGRATOR_TOOL_DENYLIST"] = settings.tool_denylist
    if settings.tool_allowlist:
        env["INTEGRATOR_TOOL_ALLOWLIST"] = settings.tool_allowlist

    return {
        "command": "uv",
        "args": [
            "run",
            "--directory",
            str(root),
            "integrator",
            "serve",
        ],
        "env": env,
    }


def build_sse_server_config(
    *,
    host: str | None = None,
    port: int | None = None,
) -> dict[str, Any]:
    """Bloco MCP HTTP/SSE (serviço macOS ou serve-http)."""
    h = host or settings.service_host
    p = port if port is not None else settings.service_port
    return {
        "url": f"http://{h}:{p}/sse",
        "transport": "sse",
    }


def load_hermes_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Config Hermes inválido (esperado mapping): {path}")
    return data


def save_hermes_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def merge_mcp_server(
    config_path: Path,
    server_name: str,
    server_block: dict[str, Any],
    *,
    overwrite: bool = False,
) -> tuple[bool, str]:
    """
    Mescla entrada em mcp_servers.

    Returns:
        (changed, message) — changed False se já existia e overwrite False.
    """
    data = load_hermes_config(config_path)
    servers = data.setdefault("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ValueError("mcp_servers deve ser um mapping no config Hermes")

    if server_name in servers and not overwrite:
        return False, f"Servidor MCP '{server_name}' já existe em {config_path}"

    if config_path.is_file() and not config_path.with_suffix(".yaml.bak").is_file():
        backup = config_path.with_name(config_path.name + ".bak")
        shutil.copy2(config_path, backup)

    servers[server_name] = server_block
    save_hermes_config(config_path, data)
    return True, f"Gravado em {config_path}"


def get_mcp_server_entry(
    config_path: Path, server_name: str
) -> dict[str, Any] | None:
    data = load_hermes_config(config_path)
    servers = data.get("mcp_servers")
    if not isinstance(servers, dict):
        return None
    entry = servers.get(server_name)
    return entry if isinstance(entry, dict) else None
