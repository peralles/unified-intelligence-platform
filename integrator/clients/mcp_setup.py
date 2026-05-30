from __future__ import annotations

import json
from typing import Any

import yaml

from integrator.clients.claude_desktop import (
    discover_claude_desktop,
    get_claude_mcp_entry,
    merge_claude_mcp_server,
    run_claude_desktop_checks,
    to_claude_server_block,
)
from integrator.hermes.config_merge import (
    DEFAULT_SERVER_NAME,
    build_sse_server_config,
    build_stdio_server_config,
    get_mcp_server_entry,
    merge_mcp_server,
)
from integrator.hermes.discovery import discover_hermes
from integrator.hermes.doctor import CheckResult, critical_failures, run_checks
from integrator.service.macos import is_macos


def build_server_block(*, mode: str) -> dict[str, Any]:
    if mode == "sse":
        if not is_macos():
            raise ValueError("Modo SSE requer macOS")
        return build_sse_server_config()
    return build_stdio_server_config()


def run_all_client_checks(
    *,
    server_name: str = DEFAULT_SERVER_NAME,
    mode: str = "stdio",
) -> list[CheckResult]:
    results = list(run_checks(server_name=server_name, mode=mode))
    results.extend(run_claude_desktop_checks(server_name=server_name))
    return results


def setup_mcp_clients(
    *,
    mode: str = "sse",
    server_name: str = DEFAULT_SERVER_NAME,
    yes: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    checks = run_all_client_checks(server_name=server_name, mode=mode)
    crit = critical_failures(checks)
    if crit and not force:
        return {
            "ok": False,
            "error": "Pré-requisitos críticos em falta",
            "checks": [
                {
                    "id": c.id,
                    "label": c.label,
                    "status": c.status.value,
                    "detail": c.detail,
                    "hint": c.hint,
                }
                for c in crit
            ],
        }

    try:
        block = build_server_block(mode=mode)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    hermes = discover_hermes()
    claude = discover_claude_desktop()

    if dry_run:
        hermes_payload = {"mcp_servers": {server_name: block}}
        claude_payload = {
            "mcpServers": {server_name: to_claude_server_block(block)},
        }
        return {
            "ok": True,
            "dry_run": True,
            "mode": mode,
            "hermes": {
                "dest": str(hermes.config_path),
                "yaml": yaml.safe_dump(
                    hermes_payload, sort_keys=False, allow_unicode=True
                ),
            },
            "claude_desktop": {
                "dest": str(claude.config_path),
                "json": json.dumps(claude_payload, indent=2, ensure_ascii=False),
            },
        }

    hosts: dict[str, Any] = {}
    errors: list[str] = []

    hermes_existing = get_mcp_server_entry(hermes.config_path, server_name)
    if hermes_existing and not yes:
        errors.append(
            f"Hermes: entrada '{server_name}' já existe em {hermes.config_path}"
        )
    else:
        try:
            changed, msg = merge_mcp_server(
                hermes.config_path,
                server_name,
                block,
                overwrite=bool(yes or hermes_existing),
            )
            hosts["hermes"] = {
                "ok": changed,
                "message": msg,
                "config_path": str(hermes.config_path),
            }
            if not changed:
                errors.append(f"Hermes: {msg}")
        except (OSError, ValueError) as exc:
            hosts["hermes"] = {"ok": False, "error": str(exc)}
            errors.append(f"Hermes: {exc}")

    claude_existing = get_claude_mcp_entry(claude.config_path, server_name)
    if claude_existing and not yes:
        errors.append(
            f"Claude: entrada '{server_name}' já existe em {claude.config_path}"
        )
    else:
        try:
            changed, msg = merge_claude_mcp_server(
                claude.config_path,
                server_name,
                block,
                overwrite=bool(yes or claude_existing),
            )
            hosts["claude_desktop"] = {
                "ok": changed,
                "message": msg,
                "config_path": str(claude.config_path),
            }
            if not changed:
                errors.append(f"Claude: {msg}")
        except (OSError, ValueError) as exc:
            hosts["claude_desktop"] = {"ok": False, "error": str(exc)}
            errors.append(f"Claude: {exc}")

    ok = any(h.get("ok") for h in hosts.values())
    if not ok and errors:
        return {"ok": False, "error": "; ".join(errors), "hosts": hosts}

    return {
        "ok": True,
        "mode": mode,
        "server_name": server_name,
        "hosts": hosts,
        "restart_hints": [
            "Reinicie o Claude Desktop (⌘Q) para carregar o MCP",
            "No Hermes: conversa nova ou /reload-mcp",
        ],
    }
