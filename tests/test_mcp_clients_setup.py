from __future__ import annotations

import json
from pathlib import Path

import pytest

from integrator.clients.mcp_setup import setup_mcp_clients
from integrator.hermes.config_merge import DEFAULT_SERVER_NAME, load_hermes_config


def test_setup_mcp_clients_stdio_writes_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    hermes_cfg = tmp_path / "hermes" / "config.yaml"
    claude_cfg = tmp_path / "claude" / "claude_desktop_config.json"
    monkeypatch.setattr(
        "integrator.clients.mcp_setup.discover_hermes",
        lambda: __import__(
            "integrator.hermes.discovery", fromlist=["HermesInstall"]
        ).HermesInstall(None, tmp_path / "hermes", hermes_cfg),
    )
    monkeypatch.setattr(
        "integrator.clients.mcp_setup.discover_claude_desktop",
        lambda: __import__(
            "integrator.clients.claude_desktop", fromlist=["ClaudeDesktopInstall"]
        ).ClaudeDesktopInstall(claude_cfg, False),
    )
    monkeypatch.setattr(
        "integrator.clients.mcp_setup.run_all_client_checks",
        lambda **_: [],
    )
    (tmp_path / "credentials").mkdir()
    (tmp_path / "credentials" / "credentials.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".venv").mkdir()

    result = setup_mcp_clients(mode="stdio", yes=True, force=True)
    assert result["ok"] is True
    hermes = load_hermes_config(hermes_cfg)
    assert DEFAULT_SERVER_NAME in hermes["mcp_servers"]
    assert claude_cfg.is_file()
    assert DEFAULT_SERVER_NAME in json.loads(claude_cfg.read_text())["mcpServers"]


def test_setup_mcp_clients_sse_remote_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hermes_cfg = tmp_path / "hermes" / "config.yaml"
    claude_cfg = tmp_path / "claude" / "claude_desktop_config.json"
    monkeypatch.setattr(
        "integrator.clients.mcp_setup.discover_hermes",
        lambda: __import__(
            "integrator.hermes.discovery", fromlist=["HermesInstall"]
        ).HermesInstall(None, tmp_path / "hermes", hermes_cfg),
    )
    monkeypatch.setattr(
        "integrator.clients.mcp_setup.discover_claude_desktop",
        lambda: __import__(
            "integrator.clients.claude_desktop", fromlist=["ClaudeDesktopInstall"]
        ).ClaudeDesktopInstall(claude_cfg, False),
    )
    monkeypatch.setattr(
        "integrator.clients.mcp_setup.run_all_client_checks",
        lambda **_: [],
    )

    remote = "https://user:pass@mcp.example.com/sse"
    result = setup_mcp_clients(
        mode="sse",
        yes=True,
        force=True,
        sse_url=remote,
    )
    assert result["ok"] is True
    entry = load_hermes_config(hermes_cfg)["mcp_servers"][DEFAULT_SERVER_NAME]
    assert entry["url"] == remote
    assert entry["transport"] == "sse"
    claude_entry = json.loads(claude_cfg.read_text())["mcpServers"][DEFAULT_SERVER_NAME]
    assert claude_entry["command"] == "npx"
    assert claude_entry["args"][2] == "https://mcp.example.com/sse"
    assert "url" not in claude_entry
    assert claude_entry["env"]["INTEGRATOR_MCP_AUTHORIZATION"].startswith("Basic ")
