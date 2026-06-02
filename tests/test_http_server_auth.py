"""Tests for admin HTTP Basic Auth middleware and allowed-hosts config."""

from __future__ import annotations

import base64

from starlette.testclient import TestClient

from integrator.config import settings
from integrator.mcp.http_server import _BasicAuthMiddleware, _security_settings
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route


# ─── _BasicAuthMiddleware ────────────────────────────────────────────────────


def _make_app(username: str = "user", password: str = "pass") -> Starlette:
    async def protected(request):
        return Response("ok", status_code=200)

    async def public(request):
        return Response("pub", status_code=200)

    app = Starlette(
        routes=[
            Route("/admin", endpoint=protected),
            Route("/health", endpoint=public),
            Route("/sse", endpoint=public),
        ]
    )
    return _BasicAuthMiddleware(app, username=username, password=password)


def _basic_header(user: str, pwd: str) -> str:
    encoded = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return f"Basic {encoded}"


def test_auth_required_for_admin() -> None:
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/admin", headers={})
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


def test_correct_credentials_pass() -> None:
    client = TestClient(_make_app("admin", "secret"), raise_server_exceptions=True)
    resp = client.get("/admin", headers={"Authorization": _basic_header("admin", "secret")})
    assert resp.status_code == 200


def test_wrong_password_rejected() -> None:
    client = TestClient(_make_app("admin", "secret"), raise_server_exceptions=True)
    resp = client.get("/admin", headers={"Authorization": _basic_header("admin", "wrong")})
    assert resp.status_code == 401


def test_wrong_username_rejected() -> None:
    client = TestClient(_make_app("admin", "secret"), raise_server_exceptions=True)
    resp = client.get("/admin", headers={"Authorization": _basic_header("other", "secret")})
    assert resp.status_code == 401


def test_health_bypasses_auth() -> None:
    client = TestClient(_make_app(), raise_server_exceptions=True)
    # No Authorization header — /health should still succeed
    resp = client.get("/health")
    assert resp.status_code == 200


def test_sse_bypasses_auth() -> None:
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/sse")
    assert resp.status_code == 200


def test_malformed_auth_header_rejected() -> None:
    client = TestClient(_make_app("u", "p"), raise_server_exceptions=True)
    resp = client.get("/admin", headers={"Authorization": "Basic !!not-base64!!"})
    assert resp.status_code == 401


# ─── _security_settings ─────────────────────────────────────────────────────


def test_localhost_always_in_allowed_hosts() -> None:
    sec = _security_settings("127.0.0.1", 17320)
    assert "127.0.0.1:17320" in sec.allowed_hosts
    assert "localhost:17320" in sec.allowed_hosts


def test_extra_allowed_hosts_from_config(monkeypatch) -> None:
    monkeypatch.setattr(settings, "allowed_hosts", "myapp.coolify.io,myapp.example.com")
    sec = _security_settings("0.0.0.0", 17320)
    assert "myapp.coolify.io" in sec.allowed_hosts
    assert "myapp.example.com" in sec.allowed_hosts
    # https origins should be in allowed_origins
    assert "https://myapp.coolify.io" in sec.allowed_origins


def test_allowed_hosts_empty_string(monkeypatch) -> None:
    monkeypatch.setattr(settings, "allowed_hosts", "")
    sec = _security_settings("127.0.0.1", 17320)
    # Should not crash; still has localhost
    assert "127.0.0.1:17320" in sec.allowed_hosts


def test_allowed_hosts_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "allowed_hosts", None)
    sec = _security_settings("127.0.0.1", 17320)
    assert "127.0.0.1:17320" in sec.allowed_hosts


def test_bind_all_interfaces_adds_display_host() -> None:
    sec = _security_settings("0.0.0.0", 17320)
    # 0.0.0.0 itself should NOT be the only allowed host
    # (localhost entries are always present)
    assert "127.0.0.1:17320" in sec.allowed_hosts
