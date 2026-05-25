"""Schemas MCP sem $ref/$defs quebrados (compatível com Hermes)."""

from __future__ import annotations

import json

from integrator.providers.google_tools import (
    _schema_contains_ref,
    list_all_tool_metadata,
    prepare_mcp_input_schema,
)


def test_prepare_mcp_input_schema_inlines_defs_ref():
    raw = {
        "type": "object",
        "properties": {
            "resource": {
                "$ref": "#/$defs/Resource",
                "default": "messages",
            },
        },
        "$defs": {
            "Resource": {
                "type": "string",
                "enum": ["messages", "threads"],
                "default": "messages",
            },
        },
    }
    out = prepare_mcp_input_schema(raw)
    assert "$defs" not in out
    assert not _schema_contains_ref(out)
    resource = out["properties"]["resource"]
    assert resource.get("enum") == ["messages", "threads"]
    assert resource.get("default") == "messages"


def test_all_tool_metadata_schemas_have_no_dangling_refs():
    for meta in list_all_tool_metadata():
        schema = meta["input_schema"]
        assert "$defs" not in schema, meta["name"]
        assert not _schema_contains_ref(schema), meta["name"]
        # Hermes/MCP clients must be able to serialize the schema
        json.dumps(schema)


def test_search_gmail_resource_is_inlined():
    search = next(m for m in list_all_tool_metadata() if m["name"] == "search_gmail")
    resource = search["input_schema"]["properties"]["resource"]
    assert "$ref" not in resource
    assert "enum" in resource or resource.get("type") == "string"
