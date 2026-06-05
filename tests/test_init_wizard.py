from __future__ import annotations

import json
from pathlib import Path
import pytest

from integrator.onboarding.google_cloud import (
    CredentialsValidationError,
    credentials_ready,
    install_credentials_from,
    validate_credentials_file,
    wait_for_credentials,
)
from integrator.onboarding.init_wizard import run_init_wizard


def _valid_oauth_json() -> str:
    return json.dumps(
        {
            "installed": {
                "client_id": "x.apps.googleusercontent.com",
                "client_secret": "secret",
                "redirect_uris": ["http://localhost"],
            }
        }
    )


def test_validate_credentials_file_ok(tmp_path: Path):
    p = tmp_path / "c.json"
    p.write_text(_valid_oauth_json(), encoding="utf-8")
    validate_credentials_file(p)


def test_validate_credentials_file_rejects_invalid(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{}", encoding="utf-8")
    with pytest.raises(CredentialsValidationError):
        validate_credentials_file(p)


def test_install_credentials_from(tmp_path: Path, monkeypatch):
    src = tmp_path / "dl" / "client_secret_1.json"
    src.parent.mkdir()
    src.write_text(_valid_oauth_json(), encoding="utf-8")
    dest_dir = tmp_path / "repo" / "data" / "credentials"
    dest = dest_dir / "credentials.json"
    monkeypatch.setattr(
        "integrator.onboarding.google_cloud.settings",
        type("S", (), {"credentials_path": dest})(),
    )
    out = install_credentials_from(src)
    assert out == dest
    validate_credentials_file(dest)


def test_wait_for_credentials_detects_file(tmp_path: Path, monkeypatch):
    dest = tmp_path / "data" / "credentials" / "credentials.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(_valid_oauth_json(), encoding="utf-8")
    monkeypatch.setattr(
        "integrator.onboarding.google_cloud.settings",
        type("S", (), {"credentials_path": dest})(),
    )
    result = wait_for_credentials(poll_interval=0.01, timeout_seconds=5, auto_yes=True)
    assert result == dest


def test_run_init_wizard_all_skipped(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "integrator.onboarding.preflight.repo_deps_ok",
        lambda: True,
    )
    monkeypatch.setattr(
        "integrator.onboarding.init_wizard.credentials_ready",
        lambda: True,
    )
    monkeypatch.setattr(
        "integrator.onboarding.init_wizard.list_accounts",
        lambda: [type("A", (), {"id": "pessoal", "has_token": True})()],
    )
    monkeypatch.setattr(
        "integrator.onboarding.init_wizard.get_mcp_server_entry",
        lambda *_a, **_k: {"command": "uv"},
    )
    monkeypatch.setattr(
        "integrator.onboarding.init_wizard.discover_hermes",
        lambda: type(
            "I",
            (),
            {"binary": None, "config_path": tmp_path / "config.yaml"},
        )(),
    )
    monkeypatch.setattr(
        "integrator.clients.mcp_setup.setup_mcp_clients",
        lambda **_: {"ok": True, "hosts": {"hermes": {"ok": False, "message": "já existe"}}},
    )
    monkeypatch.setattr(
        "integrator.onboarding.init_wizard.is_configured",
        lambda: True,
    )
    code = run_init_wizard(auto_yes=True, verbose=False)
    assert code == 0


def test_credentials_ready(tmp_path: Path, monkeypatch):
    dest = tmp_path / "credentials.json"
    monkeypatch.setattr(
        "integrator.onboarding.google_cloud.settings",
        type("S", (), {"credentials_path": dest})(),
    )
    assert not credentials_ready()
    dest.write_text(_valid_oauth_json(), encoding="utf-8")
    assert credentials_ready()
