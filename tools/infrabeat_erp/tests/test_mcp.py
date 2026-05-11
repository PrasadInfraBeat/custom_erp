"""Tests for infrabeat_erp.mcp (Phase 6B.3)."""

import json

import httpx
import pytest
import respx

from infrabeat_erp import cli
from infrabeat_erp.infrastructure import mcp, secrets_store
from infrabeat_erp.infrastructure.mcp import (
    MCP_ENDPOINT_PATH,
    MCPError,
    MCPProtocolError,
    ServerCapabilities,
    Tool,
    call_tool,
    initialize,
    list_tools,
)
from infrabeat_erp.infrastructure.oauth import clear_discovery_cache

BASE_URL = "http://erp.test"
MCP_URL = BASE_URL + MCP_ENDPOINT_PATH
DISCOVERY_URL = BASE_URL + "/.well-known/openid-configuration"


def _mock_discovery(mcp_path: str = MCP_ENDPOINT_PATH) -> None:
    """Stub OIDC discovery to advertise mcp_endpoint=mcp_path."""
    respx.get(DISCOVERY_URL).mock(
        return_value=httpx.Response(200, json={"mcp_endpoint": mcp_path})
    )


@pytest.fixture(autouse=True)
def _clear_discovery_cache_between_tests():
    clear_discovery_cache()
    yield
    clear_discovery_cache()


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
    _mock_discovery()
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
    _mock_discovery()
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
    _mock_discovery()
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
    _mock_discovery()
    respx.post(MCP_URL).mock(return_value=_ok({"tools": []}))
    with httpx.Client(base_url=BASE_URL) as client:
        tools = list_tools(client)
    assert tools == []


@respx.mock
def test_call_tool_success() -> None:
    _mock_discovery()
    expected = {"content": [{"type": "text", "text": "hello"}]}
    respx.post(MCP_URL).mock(return_value=_ok(expected))
    with httpx.Client(base_url=BASE_URL) as client:
        out = call_tool(client, "echo_tool", {"message": "hi"})
    assert out == expected


@respx.mock
def test_call_tool_protocol_error() -> None:
    _mock_discovery()
    respx.post(MCP_URL).mock(return_value=_err(-32602, "Invalid params"))
    with httpx.Client(base_url=BASE_URL) as client:
        with pytest.raises(MCPProtocolError) as exc:
            call_tool(client, "any_tool", {})
    assert "Invalid params" in str(exc.value)


@respx.mock
def test_call_tool_passes_arguments() -> None:
    _mock_discovery()
    route = respx.post(MCP_URL).mock(return_value=_ok({}))
    with httpx.Client(base_url=BASE_URL) as client:
        call_tool(client, "my_tool", {"x": 1, "y": "abc"})
    body = json.loads(route.calls.last.request.read())
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "my_tool"
    assert body["params"]["arguments"] == {"x": 1, "y": "abc"}


@respx.mock
def test_jsonrpc_ids_unique() -> None:
    _mock_discovery()
    route = respx.post(MCP_URL).mock(return_value=_ok({"tools": []}))
    with httpx.Client(base_url=BASE_URL) as client:
        list_tools(client)
        list_tools(client)
    body_a = json.loads(route.calls[0].request.read())
    body_b = json.loads(route.calls[1].request.read())
    assert body_a["id"] != body_b["id"]


@respx.mock
def test_mcp_endpoint_discovered_dynamically() -> None:
    """Discovery advertises a non-default mcp_endpoint; client honors it."""
    different_path = "/api/method/different.path"
    _mock_discovery(mcp_path=different_path)
    different_url = BASE_URL + different_path
    fallback_route = respx.post(MCP_URL).mock(return_value=_ok({}))
    discovered_route = respx.post(different_url).mock(
        return_value=_ok(
            {
                "serverInfo": {"name": "fac", "version": "9.9.9"},
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "streaming": False},
            }
        )
    )
    with httpx.Client(base_url=BASE_URL) as client:
        caps = initialize(client)
    assert caps.server_name == "fac"
    assert discovered_route.called
    assert not fallback_route.called


@respx.mock
def test_mcp_endpoint_discovery_fallback_warns() -> None:
    """Discovery without mcp_endpoint key triggers DeprecationWarning + fallback."""
    respx.get(DISCOVERY_URL).mock(
        return_value=httpx.Response(200, json={"issuer": BASE_URL})
    )
    respx.post(MCP_URL).mock(
        return_value=_ok(
            {
                "serverInfo": {"name": "fac", "version": "1.0"},
                "protocolVersion": "2024-11-05",
                "capabilities": {},
            }
        )
    )
    with httpx.Client(base_url=BASE_URL) as client:
        with pytest.warns(DeprecationWarning, match="mcp_endpoint"):
            caps = mcp.initialize(client)
    assert caps.server_name == "fac"


# === Phase 6E.9 TOKEN AUTO-REFRESH TESTS ==================================

TOKEN_PATH = "/api/method/frappe.integrations.oauth2.get_token"
TOKEN_URL = BASE_URL + TOKEN_PATH


def _mock_discovery_with_token_endpoint() -> None:
    """OIDC discovery stub advertising both mcp_endpoint and token_endpoint."""
    respx.get(DISCOVERY_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "mcp_endpoint": MCP_ENDPOINT_PATH,
                "token_endpoint": TOKEN_URL,
            },
        )
    )


def _seeded_secrets() -> dict:
    """Return a secrets dict shaped like a post-login keyring entry."""
    return {
        "access_token": "old_access",
        "refresh_token": "old_refresh",
        "token_type": "Bearer",
        "expires_in": 3600,
        "issued_at": 0.0,
        "scope": "all openid",
        "client_id": "abc-client",
        "client_secret": None,
        "redirect_uri": "http://127.0.0.1:8765/callback",
        "registration_endpoint": BASE_URL + "/register",
    }


@respx.mock
def test_token_autorefresh_on_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First MCP POST 401 -> auth refreshes, persists, replays with new bearer."""
    _mock_discovery_with_token_endpoint()
    mcp_route = respx.post(MCP_URL).mock(
        side_effect=[
            httpx.Response(401, json={"error": "expired_token"}),
            _ok(
                {
                    "serverInfo": {"name": "fac", "version": "9.9.9"},
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "streaming": False},
                }
            ),
        ]
    )
    refresh_route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "all openid",
            },
        )
    )

    saved: list = []
    monkeypatch.setattr(
        secrets_store,
        "save_secrets",
        lambda vm, data: saved.append((vm, dict(data))),
    )

    auth = cli.TokenRefreshAuth("dev", BASE_URL, _seeded_secrets())
    with httpx.Client(base_url=BASE_URL) as client:
        client.auth = auth
        caps = mcp.initialize(client)

    assert caps.server_name == "fac"
    assert refresh_route.called
    assert refresh_route.call_count == 1
    assert mcp_route.call_count == 2
    second_request = mcp_route.calls[1].request
    assert second_request.headers["Authorization"] == "Bearer new_access"
    assert saved == [
        (
            "dev",
            {
                **_seeded_secrets(),
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "token_type": "Bearer",
                "expires_in": 3600,
                "issued_at": saved[0][1]["issued_at"],
                "scope": "all openid",
            },
        )
    ]


@respx.mock
def test_token_autorefresh_fails_on_expired_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refresh endpoint 401 -> TokenRefreshFailed with 'login' hint."""
    _mock_discovery_with_token_endpoint()
    respx.post(MCP_URL).mock(
        return_value=httpx.Response(401, json={"error": "expired_token"})
    )
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            401, json={"error": "invalid_grant"}
        )
    )

    monkeypatch.setattr(
        secrets_store,
        "save_secrets",
        lambda vm, data: pytest.fail(
            "save_secrets must not run when refresh itself fails"
        ),
    )

    auth = cli.TokenRefreshAuth("dev", BASE_URL, _seeded_secrets())
    with httpx.Client(base_url=BASE_URL) as client:
        client.auth = auth
        with pytest.raises(cli.TokenRefreshFailed, match="login") as exc:
            mcp.initialize(client)
    assert "infrabeat-erp login dev" in str(exc.value)
