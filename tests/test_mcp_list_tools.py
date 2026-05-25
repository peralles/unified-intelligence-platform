import pytest

from integrator.mcp.server import handle_list_tools


@pytest.mark.asyncio
async def test_list_tools_handler_returns_twelve():
    tools = await handle_list_tools()
    assert len(tools) == 12
    assert all(t.name and t.description is not None for t in tools)
