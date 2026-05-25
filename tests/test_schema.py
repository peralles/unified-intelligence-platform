from integrator.mcp.schema import metadata_to_mcp_tool
from integrator.providers.google_tools import list_all_tool_metadata


def test_all_twelve_tools_exposed():
    meta = list_all_tool_metadata()
    names = {m["name"] for m in meta}
    assert len(meta) == 12
    assert "search_gmail" in names
    assert "create_calendar_event" in names
    assert "get_current_datetime" in names


def test_metadata_to_mcp_tool():
    meta = list_all_tool_metadata()[0]
    tool = metadata_to_mcp_tool(meta)
    assert tool.name == meta["name"]
    assert tool.inputSchema["type"] == "object"
