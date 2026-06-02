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
    async def endpoint(request):
        return Response("ok", status_code=200)

    app = Starlette(
        routes=[
            Route("/admin", endpoint=endpoint),
            Route("/health", endpoint=endpoint),
            Route("/sse", endpoint=endpoint),
            Route("/mcp", endpoint=endpoint),
        ]
    )
    return _BasicAuthMiddleware(app, username=username, password=password)


def _basic_header(user: str, pwd: str) -> str:
    encoded = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return f"Basic {encoded}"


def test_auth_required_for_admin() -> None:
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/admin")
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


def test_auth_required_for_sse() -> None:
    """MCP SSE endpoint must also require auth when credentials are configured."""
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/sse")
    assert resp.status_code == 401


def test_auth_required_for_mcp() -> None:
    """Streamable HTTP MCP endpoint must also require auth."""
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/mcp")
    assert resp.status_code == 401


def test_correct_credentials_pass_admin() -> None:
    client = TestClient(_make_app("admin", "secret"), raise_server_exceptions=True)
    resp = client.get("/admin", headers={"Authorization": _basic_header("admin", "secret")})
    assert resp.status_code == 200


def test_correct_credentials_pass_sse() -> None:
    client = TestClient(_make_app("admin", "secret"), raise_server_exceptions=True)
    resp = client.get("/sse", headers={"Authorization": _basic_header("admin", "secret")})
    assert resp.status_code == 200


def test_wrong_password_rejected() -> None:
    client = TestClient(_make_app("admin", "secret"), raise_server_exceptions=True)
    resp = client.get("/sse", headers={"Authorization": _basic_header("admin", "wrong")})
    assert resp.status_code == 401


def test_wrong_username_rejected() -> None:
    client = TestClient(_make_app("admin", "secret"), raise_server_exceptions=True)
    resp = client.get("/mcp", headers={"Authorization": _basic_header("other", "secret")})
    assert resp.status_code == 401


def test_health_bypasses_auth() -> None:
    """Docker health check must not require credentials."""
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/health")
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
    assert "https://myapp.coolify.io" in sec.allowed_origins


def test_allowed_hosts_empty_string(monkeypatch) -> None:
    monkeypatch.setattr(settings, "allowed_hosts", "")
    sec = _security_settings("127.0.0.1", 17320)
    assert "127.0.0.1:17320" in sec.allowed_hosts


def test_allowed_hosts_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "allowed_hosts", None)
    sec = _security_settings("127.0.0.1", 17320)
    assert "127.0.0.1:17320" in sec.allowed_hosts


def test_bind_all_interfaces_keeps_localhost(monkeypatch) -> None:
    monkeypatch.setattr(settings, "allowed_hosts", None)
    sec = _security_settings("0.0.0.0", 17320)
    assert "127.0.0.1:17320" in sec.allowed_hosts


# ─── build_sse_server_config ─────────────────────────────────────────────────


def test_sse_url_includes_credentials_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "s3cr3t")
    monkeypatch.setattr(settings, "service_host", "127.0.0.1")
    monkeypatch.setattr(settings, "service_port", 17320)
    from integrator.hermes.config_merge import build_sse_server_config
    cfg = build_sse_server_config()
    assert cfg["url"].startswith("http://admin:s3cr3t@")


def test_sse_url_no_credentials_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_username", None)
    monkeypatch.setattr(settings, "admin_password", None)
    monkeypatch.setattr(settings, "service_host", "127.0.0.1")
    monkeypatch.setattr(settings, "service_port", 17320)
    from integrator.hermes.config_merge import build_sse_server_config
    cfg = build_sse_server_config()
    assert "@" not in cfg["url"]
    assert cfg["url"] == "http://127.0.0.1:17320/sse"


def test_sse_url_special_chars_encoded(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_username", "user@name")
    monkeypatch.setattr(settings, "admin_password", "p@ss:word!")
    monkeypatch.setattr(settings, "service_host", "127.0.0.1")
    monkeypatch.setattr(settings, "service_port", 17320)
    from integrator.hermes.config_merge import build_sse_server_config
    cfg = build_sse_server_config()
    # Special chars must be URL-encoded so the URL stays valid
    assert "user%40name" in cfg["url"]
    assert "p%40ss%3Aword%21" in cfg["url"]
