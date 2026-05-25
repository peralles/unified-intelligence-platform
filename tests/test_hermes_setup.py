from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
import yaml

from integrator.hermes.config_merge import (
    DEFAULT_SERVER_NAME,
    build_stdio_server_config,
    get_mcp_server_entry,
    load_hermes_config,
    merge_mcp_server,
)
from integrator.hermes.discovery import HermesInstall, discover_hermes
from integrator.hermes.doctor import critical_failures, run_checks


def test_build_stdio_server_config_uses_repo_root(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    block = build_stdio_server_config(repo_root=tmp_path)
    assert block["command"] == "uv"
    assert "--directory" in block["args"]
    idx = block["args"].index("--directory")
    assert block["args"][idx + 1] == str(tmp_path.resolve())
    assert block["args"][-2:] == ["integrator", "serve"]


def test_merge_mcp_server_preserves_other_servers(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "mcp_servers": {
                    "other": {"command": "echo"},
                }
            }
        ),
        encoding="utf-8",
    )
    block = build_stdio_server_config(repo_root=tmp_path)
    changed, _ = merge_mcp_server(
        config, DEFAULT_SERVER_NAME, block, overwrite=True
    )
    assert changed
    data = load_hermes_config(config)
    assert "other" in data["mcp_servers"]
    assert DEFAULT_SERVER_NAME in data["mcp_servers"]


def test_merge_refuses_without_overwrite(tmp_path: Path):
    config = tmp_path / "config.yaml"
    block = {"command": "uv", "args": []}
    merge_mcp_server(config, "srv", block, overwrite=True)
    changed, msg = merge_mcp_server(config, "srv", {"command": "x"}, overwrite=False)
    assert not changed
    assert "já existe" in msg


def test_merge_yes_replaces_entry(tmp_path: Path):
    config = tmp_path / "config.yaml"
    merge_mcp_server(config, "srv", {"command": "old"}, overwrite=True)
    merge_mcp_server(config, "srv", {"command": "new"}, overwrite=True)
    entry = get_mcp_server_entry(config, "srv")
    assert entry["command"] == "new"


def test_discover_hermes_config_path(monkeypatch, tmp_path: Path):
    home = tmp_path / "hermes_home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("PATH", raising=False)

    def fake_which(_name: str):
        return None

    monkeypatch.setattr("integrator.hermes.discovery.shutil.which", fake_which)
    install = discover_hermes()
    assert install.binary is None
    assert install.config_path == home / "config.yaml"


def test_doctor_critical_without_credentials(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "integrator.hermes.doctor.settings",
        type(
            "S",
            (),
            {
                "root_dir": tmp_path,
                "credentials_path": tmp_path / "missing.json",
                "service_host": "127.0.0.1",
                "service_port": 17320,
            },
        )(),
    )
    monkeypatch.setattr(
        "integrator.hermes.doctor.list_accounts",
        lambda: [],
    )
    monkeypatch.setattr(
        "integrator.hermes.doctor.shutil.which",
        lambda name: "/usr/bin/uv" if name == "uv" else None,
    )
    monkeypatch.setattr(
        "integrator.hermes.doctor._repo_deps_ok",
        lambda: True,
    )
    monkeypatch.setattr(
        "integrator.hermes.doctor.discover_hermes",
        lambda: HermesInstall(
            binary=None,
            home=tmp_path / ".hermes",
            config_path=tmp_path / ".hermes" / "config.yaml",
        ),
    )

    results = run_checks()
    crit = critical_failures(results)
    ids = {r.id for r in crit}
    assert "credentials" in ids
    assert "oauth" in ids


def test_setup_dry_run_cli(tmp_path: Path, monkeypatch):
    hermes_cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(
        "integrator.hermes.setup_cmd.discover_hermes",
        lambda: HermesInstall(None, tmp_path, hermes_cfg),
    )
    monkeypatch.setattr(
        "integrator.hermes.setup_cmd.run_checks",
        lambda **_: [],
    )
    monkeypatch.setattr(
        "integrator.hermes.setup_cmd.critical_failures",
        lambda _: [],
    )
    monkeypatch.setattr(
        "integrator.hermes.setup_cmd.build_stdio_server_config",
        lambda: build_stdio_server_config(repo_root=tmp_path),
    )

    from integrator.cli.main import main

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    with pytest.raises(SystemExit) as exc:
        main(["hermes", "setup", "--dry-run", "--skip-test"])
    assert exc.value.code == 0
    out = buf.getvalue()
    assert "langchain-integrator" in out
    assert "integrator" in out
    assert not hermes_cfg.exists()
