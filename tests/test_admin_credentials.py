from __future__ import annotations

import json
from pathlib import Path

from integrator.admin import handlers
from integrator.config import Settings, settings


def test_save_credentials_json_writes_under_data(tmp_path: Path, monkeypatch) -> None:
    cfg = Settings(root_dir=tmp_path)
    monkeypatch.setattr(handlers, "settings", cfg)

    payload = {
        "web": {
            "client_id": "cid.apps.googleusercontent.com",
            "client_secret": "secret",
            "redirect_uris": ["https://example.com/admin/oauth/google/callback"],
        }
    }
    result = handlers.save_credentials_json(json.dumps(payload))
    assert result["ok"] is True
    dest = tmp_path / "data" / "credentials" / "credentials.json"
    assert dest.is_file()
    saved = json.loads(dest.read_text(encoding="utf-8"))
    assert saved["web"]["client_id"] == payload["web"]["client_id"]


def test_save_credentials_json_rejects_invalid_type(tmp_path: Path, monkeypatch) -> None:
    cfg = Settings(root_dir=tmp_path)
    monkeypatch.setattr(handlers, "settings", cfg)

    result = handlers.save_credentials_json('{"foo": "bar"}')
    assert result["ok"] is False
    assert "installed" in result["error"] or "web" in result["error"]


def test_setup_credentials_api_requires_json(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_username", None)
    monkeypatch.setattr(settings, "admin_password", None)
    from starlette.testclient import TestClient

    from integrator.mcp.http_server import create_starlette_app

    client = TestClient(create_starlette_app(), raise_server_exceptions=True)
    resp = client.post("/admin/api/setup/credentials", json={})
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert "json" in body["error"].lower()


def test_bootstrap_copies_readonly_bind_mount(tmp_path: Path) -> None:
    legacy = tmp_path / "credentials" / "credentials.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "x.apps.googleusercontent.com",
                    "client_secret": "y",
                }
            }
        ),
        encoding="utf-8",
    )
    cfg = Settings(root_dir=tmp_path)
    cfg.ensure_data_dirs()
    dest = cfg.credentials_path
    assert dest.is_file()
    assert json.loads(dest.read_text())["web"]["client_id"].startswith("x.")
