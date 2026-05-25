from __future__ import annotations

import asyncio
import logging

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import Server

from integrator.auth.google_oauth import GoogleAuthError
from integrator.mcp.schema import metadata_to_mcp_tool
from integrator.providers.google_tools import invoke_tool, list_all_tool_metadata
from integrator.security.policy import (
    ConfirmationRequiredError,
    ToolPolicyError,
)

logger = logging.getLogger(__name__)

server = Server("langchain-hermes-integrator")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [metadata_to_mcp_tool(m) for m in list_all_tool_metadata()]


def _mcp_error(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)],
        isError=True,
    )


def _mcp_success(text: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        isError=False,
    )


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> types.CallToolResult:
    try:
        text = invoke_tool(name, arguments)
        return _mcp_success(text)
    except GoogleAuthError as exc:
        return _mcp_error(f"[integrator] Autenticação necessária: {exc}")
    except ToolPolicyError as exc:
        return _mcp_error(f"[integrator] Política: {exc}")
    except ConfirmationRequiredError as exc:
        return _mcp_error(f"[integrator] Confirmação: {exc}")
    except KeyError as exc:
        return _mcp_error(str(exc))
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return _mcp_error(f"[integrator] Erro ao executar '{name}': {exc}")


async def run_stdio_server() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_stdio_server())
