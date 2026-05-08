"""Tests for infrabeat_erp.mcp (Phase 6B.3)."""

import json

import httpx
import pytest
import respx

from infrabeat_erp.mcp import (
    MCP_ENDPOINT_PATH,
    MCPError,
    MCPProtocolError,
    ServerCapabilities,
    Tool,
    call_tool,
    initialize,
    list_tools,
)

BASE_URL = "http://erp.test"
MCP_URL = BASE_URL + MCP_ENDPOINT_PATH


def _ok(result: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "result": result},
    )


def _err(code: int, message: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": code, "message": message},
        },
    )


@respx.mock
def test_initialize_success() -> None:
    respx.post(MCP_URL).mock(
        return_value=_ok(
            {
                "serverInfo": {
                    "name": "frappe-assistant-core",
                    "version": "2.4.1",
                },
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "streaming": False},
            }
        )
    )
    with httpx.Client(base_url=BASE_URL) as client:
        caps = initialize(client)
    assert isinstance(caps, ServerCapabilities)
    assert caps.server_name == "frappe-assistant-core"
    assert caps.server_version == "2.4.1"
    assert caps.protocol_version == "2024-11-05"
    assert caps.tools_supported is True
    assert caps.streaming is False


@respx.mock
def test_initialize_protocol_error() -> None:
    respx.post(MCP_URL).mock(
        return_value=_err(-32601, "Method not found")
    )
    with httpx.Client(base_url=BASE_URL) as client:
        with pytest.raises(MCPProtocolError) as exc:
            initialize(client)
    msg = str(exc.value)
    assert "Method not found" in msg
    assert "-32601" in msg


@respx.mock
def test_list_tools_returns_three() -> None:
    respx.post(MCP_URL).mock(
        return_value=_ok(
            {
                "tools": [
                    {
                        "name": "alpha",
                        "description": "first tool",
                        "inputSchema": {"type": "object"},
                    },
                    {
                        "name": "bravo",
                        "description": "second tool",
                        "inputSchema": {},
                    },
                    {
                        "name": "charlie",
                        "description": "third tool",
                        "inputSchema": {"x": 1},
                    },
                ]
            }
        )
    )
    with httpx.Client(base_url=BASE_URL) as client:
        tools = list_tools(client)
    assert len(tools) == 3
    assert tools[0] == Tool(
        name="alpha",
        description="first tool",
        input_schema={"type": "object"},
    )
    assert tools[1].name == "bravo"
    assert tools[2].input_schema == {"x": 1}


@respx.mock
def test_list_tools_empty() -> None:
    respx.post(MCP_URL).mock(return_value=_ok({"tools": []}))
    with httpx.Client(base_url=BASE_URL) as client:
        tools = list_tools(client)
    assert tools == []


@respx.mock
def test_call_tool_success() -> None:
    expected = {"content": [{"type": "text", "text": "hello"}]}
    respx.post(MCP_URL).mock(return_value=_ok(expected))
    with httpx.Client(base_url=BASE_URL) as client:
        out = call_tool(client, "echo_tool", {"message": "hi"})
    assert out == expected


@respx.mock
def test_call_tool_protocol_error() -> None:
    respx.post(MCP_URL).mock(return_value=_err(-32602, "Invalid params"))
    with httpx.Client(base_url=BASE_URL) as client:
        with pytest.raises(MCPProtocolError) as exc:
            call_tool(client, "any_tool", {})
    assert "Invalid params" in str(exc.value)


@respx.mock
def test_call_tool_passes_arguments() -> None:
    route = respx.post(MCP_URL).mock(return_value=_ok({}))
    with httpx.Client(base_url=BASE_URL) as client:
        call_tool(client, "my_tool", {"x": 1, "y": "abc"})
    body = json.loads(route.calls.last.request.read())
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "my_tool"
    assert body["params"]["arguments"] == {"x": 1, "y": "abc"}


@respx.mock
def test_jsonrpc_ids_unique() -> None:
    route = respx.post(MCP_URL).mock(return_value=_ok({"tools": []}))
    with httpx.Client(base_url=BASE_URL) as client:
        list_tools(client)
        list_tools(client)
    body_a = json.loads(route.calls[0].request.read())
    body_b = json.loads(route.calls[1].request.read())
    assert body_a["id"] != body_b["id"]
