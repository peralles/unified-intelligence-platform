"""Servidor MCP HTTP/SSE para execução em background (macOS LaunchAgent)."""

from __future__ import annotations

import argparse
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

from integrator.mcp.server import server as mcp_server

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17320


def _security_settings(host: str, port: int) -> TransportSecuritySettings:
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"],
        allowed_origins=[
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
            f"http://[::1]:{port}",
        ],
    )


async def _health(_: Request) -> Response:
    return Response('{"ok":true}', media_type="application/json")


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
            yield

    return Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
            Route("/mcp", endpoint=http_asgi, methods=["GET", "POST", "DELETE"]),
            Route("/health", endpoint=_health, methods=["GET"]),
        ],
        lifespan=lifespan,
    )


def run_http_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    logging.basicConfig(level=logging.INFO)
    app = create_starlette_app(host, port)
    logger.info("MCP HTTP/SSE em http://%s:%s (sse=/sse, mcp=/mcp)", host, port)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    asyncio.run(uvicorn.Server(config).serve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor MCP HTTP/SSE")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    run_http_server(args.host, args.port)
