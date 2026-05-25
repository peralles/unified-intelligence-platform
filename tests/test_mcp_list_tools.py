import pytest

from integrator.mcp.server import handle_list_tools
from integrator.providers.tools import TOTAL_TOOL_COUNT


@pytest.mark.asyncio
async def test_list_tools_handler_returns_all_providers():
    tools = await handle_list_tools()
    assert len(tools) == TOTAL_TOOL_COUNT
    assert all(t.name and t.description is not None for t in tools)
