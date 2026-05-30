from __future__ import annotations

import json
from pathlib import Path

from integrator.clients.claude_desktop import (
    merge_claude_mcp_server,
    to_claude_server_block,
    get_claude_mcp_entry,
    load_claude_config,
)
from integrator.hermes.config_merge import (
    DEFAULT_SERVER_NAME,
    build_sse_server_config,
    build_stdio_server_config,
)


def test_to_claude_server_block_sse() -> None:
    block = build_sse_server_config(host="127.0.0.1", port=17320)
    claude = to_claude_server_block(block)
    assert claude == {"url": "http://127.0.0.1:17320/sse"}
    assert "transport" not in claude


def test_to_claude_server_block_stdio(tmp_path: Path) -> None:
    block = build_stdio_server_config(repo_root=tmp_path)
    claude = to_claude_server_block(block)
    assert claude["command"] == "uv"
    assert claude["args"][-2:] == ["integrator", "serve"]


def test_merge_claude_preserves_other_servers(tmp_path: Path) -> None:
    config = tmp_path / "claude_desktop_config.json"
    config.write_text(
        json.dumps({"mcpServers": {"other": {"command": "echo"}}}),
        encoding="utf-8",
    )
    block = build_stdio_server_config(repo_root=tmp_path)
    changed, _ = merge_claude_mcp_server(
        config, DEFAULT_SERVER_NAME, block, overwrite=True
    )
    assert changed
    data = load_claude_config(config)
    assert "other" in data["mcpServers"]
    assert DEFAULT_SERVER_NAME in data["mcpServers"]
    entry = get_claude_mcp_entry(config, DEFAULT_SERVER_NAME)
    assert entry is not None
    assert entry["command"] == "uv"
