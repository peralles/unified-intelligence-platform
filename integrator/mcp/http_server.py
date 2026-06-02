"""MCP HTTP/SSE server — runs as background service (macOS LaunchAgent or Docker)."""

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
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

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


class _BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic Auth protecting all routes; only /health is exempt for Docker health checks."""

    def __init__(self, app: ASGIApp, username: str, password: str) -> None:
        super().__init__(app)
        self._username = username
        self._password = password

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if path in _AUTH_BYPASS_PATHS:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8", errors="replace")
                user, _, pwd = decoded.partition(":")
                if secrets.compare_digest(user, self._username) and secrets.compare_digest(
                    pwd, self._password
                ):
                    return await call_next(request)
            except Exception:
                pass

        return Response(
            "Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Integrator Admin"'},
        )


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
    return Response('{"ok":true}', media_type="application/json")


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
        return Response()

    @asynccontextmanager
    async def lifespan(_app: Starlette):
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

    return app  # type: ignore[return-value]


def run_http_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    setup_logging()
    app = create_starlette_app(host, port)
    logger.info(
        "MCP HTTP/SSE em http://%s:%s (sse=/sse, mcp=/mcp, admin=/admin)",
        host,
        port,
    )
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    asyncio.run(uvicorn.Server(config).serve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor MCP HTTP/SSE")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    run_http_server(args.host, args.port)
