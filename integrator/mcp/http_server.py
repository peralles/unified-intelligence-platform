"""MCP HTTP/SSE server — Docker/Coolify or integrator serve-http."""

from __future__ import annotations

import argparse
import asyncio
import base64
import secrets
from contextlib import asynccontextmanager

import uvicorn
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from integrator.admin.routes import admin_routes
from integrator.config import settings
from integrator.logging_setup import get_logger, setup_logging
from integrator.mcp.server import server as mcp_server

logger = get_logger("http")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17320

# Only the health probe bypasses auth — everything else (admin AND MCP) requires credentials.
# Hermes/Claude connect to /sse or /mcp using credentials embedded in the URL:
#   http://user:pass@host:port/sse
_AUTH_BYPASS_PATHS = frozenset({"/health"})


class _AlreadySentResponse(Response):
    """No-op response — SSE EventSourceResponse already sent http.response.start."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        return


def _header(scope: Scope, name: str) -> str:
    key = name.lower().encode()
    for header, value in scope.get("headers", []):
        if header.lower() == key:
            return value.decode("latin-1")
    return ""


def _basic_auth_ok(scope: Scope, username: str, password: str) -> bool:
    auth = _header(scope, "authorization")
    if not auth.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8", errors="replace")
        user, _, pwd = decoded.partition(":")
        return secrets.compare_digest(user, username) and secrets.compare_digest(
            pwd, password
        )
    except Exception:
        return False


class _BasicAuthMiddleware:
    """HTTP Basic Auth for all routes except /health.

    Pure ASGI middleware — ``BaseHTTPMiddleware`` breaks SSE/streaming because
    MCP ``/sse`` sends the response via ``request._send`` before returning.
    """

    def __init__(self, app: ASGIApp, username: str, password: str) -> None:
        self.app = app
        self._username = username
        self._password = password

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _AUTH_BYPASS_PATHS or _basic_auth_ok(
            scope, self._username, self._password
        ):
            await self.app(scope, receive, send)
            return

        response = Response(
            "Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Integrator Admin"'},
        )
        await response(scope, receive, send)


def _security_settings(host: str, port: int) -> TransportSecuritySettings:
    base_hosts = [f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"]
    base_origins = [
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
        f"http://[::1]:{port}",
    ]

    # Accept extra hosts/origins configured for VPS/reverse-proxy deployment.
    # INTEGRATOR_ALLOWED_HOSTS=myapp.coolify.io,myapp.example.com
    if settings.allowed_hosts:
        for entry in settings.allowed_hosts.split(","):
            entry = entry.strip()
            if not entry:
                continue
            # entry may be "domain.com" or "domain.com:port"
            base_hosts.append(entry)
            base_origins.extend([f"http://{entry}", f"https://{entry}"])

    # When not binding to localhost, also accept host:port of the bind address.
    if host not in ("127.0.0.1", "::1", "localhost"):
        base_hosts.append(f"{host}:{port}")
        base_origins.append(f"http://{host}:{port}")

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=base_hosts,
        allowed_origins=base_origins,
    )


async def _health(_: Request) -> Response:
    from integrator.persistence import check_data_persistence

    report = check_data_persistence()
    return JSONResponse(
        {
            "ok": report.status != "error",
            "persistence": report.to_dict(),
        }
    )


def _startup_persistence_check() -> None:
    from integrator.persistence import ensure_volume_marker

    ensure_volume_marker()


def _warm_whatsapp_for_auto_transcribe() -> None:
    """Keep neonize connected so MessageEv handlers can transcribe without an MCP call."""
    if not settings.whatsapp_enabled or not settings.whatsapp_auto_transcribe:
        return
    from integrator.whatsapp.session import WhatsAppSession

    WhatsAppSession.get().ensure_background_connection()
    logger.info(
        "whatsapp worker connected | auto_transcribe | private_only=%s | only_incoming=%s",
        settings.whatsapp_transcribe_private_only,
        settings.whatsapp_transcribe_only_incoming,
    )


def create_starlette_app(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Starlette:
    security = _security_settings(host, port)

    session_manager = StreamableHTTPSessionManager(
        mcp_server,
        stateless=True,
        security_settings=security,
    )
    http_asgi = StreamableHTTPASGIApp(session_manager)

    sse = SseServerTransport("/messages/", security_settings=security)

    async def handle_sse(request: Request) -> Response:
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )
        return _AlreadySentResponse()

    @asynccontextmanager
    async def lifespan(_app: Starlette):
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, _startup_persistence_check)
        except Exception as exc:
            logger.warning("persistence check failed: %s", exc)
        async with session_manager.run():
            if settings.whatsapp_enabled and settings.whatsapp_auto_transcribe:
                loop = asyncio.get_running_loop()
                try:
                    await loop.run_in_executor(None, _warm_whatsapp_for_auto_transcribe)
                except Exception as exc:
                    logger.warning("whatsapp warm connect failed: %s", exc)
            yield

    app: ASGIApp = Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
            Route("/mcp", endpoint=http_asgi, methods=["GET", "POST", "DELETE"]),
            Route("/health", endpoint=_health, methods=["GET"]),
            *admin_routes(),
        ],
        lifespan=lifespan,
    )

    if settings.admin_username and settings.admin_password:
        app = _BasicAuthMiddleware(app, settings.admin_username, settings.admin_password)
        logger.info("admin basic auth enabled | user=%s", settings.admin_username)

    if host in ("0.0.0.0", "::") and not (settings.allowed_hosts or "").strip():
        logger.warning(
            "INTEGRATOR_ALLOWED_HOSTS vazio com bind público — defina o domínio do proxy "
            "(ex.: mcp.example.com) ou Hermes/MCP pode falhar por DNS rebinding"
        )

    return app  # type: ignore[return-value]


def run_http_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    setup_logging()
    app = create_starlette_app(host, port)
    logger.info(
        "MCP HTTP/SSE em http://%s:%s (sse=/sse, mcp=/mcp, admin=/admin)",
        host,
        port,
    )
    # proxy_headers=True trusts X-Forwarded-For/Proto from Caddy/Nginx so that
    # client IPs appear correctly in logs when running behind a reverse proxy.
    config = uvicorn.Config(app, host=host, port=port, log_level="info", proxy_headers=True)
    asyncio.run(uvicorn.Server(config).serve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor MCP HTTP/SSE")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    run_http_server(args.host, args.port)
