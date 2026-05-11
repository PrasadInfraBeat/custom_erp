"""MCP JSON-RPC 2.0 client for infrabeat-erp.

Ports the Phase 5 mcp_smoke_test.py script into a typed, packaged module.
The protocol envelope, endpoint path, and error semantics are preserved
exactly as proven against Frappe Assistant Core (FAC) on dev / staging /
production VMs.

The MCP endpoint path (/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp)
is the concrete Frappe whitelisted method that FAC routes JSON-RPC calls to.
The base URL and Bearer token come from the httpx.Client passed in, so this
module never hardcodes a VM name.

As of Phase 6E.4, the endpoint is resolved at runtime via OIDC discovery
(``mcp_endpoint`` key in /.well-known/openid-configuration). The hardcoded
MCP_ENDPOINT_PATH is retained as a fallback when the key is absent or
discovery fails, accompanied by a DeprecationWarning.
"""

import itertools
import warnings
from dataclasses import dataclass
from typing import Iterator

import httpx

from infrabeat_erp import __version__
from .oauth import discover_oidc_metadata

MCP_ENDPOINT_PATH = "/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
"""Fallback path used when OIDC discovery does not advertise mcp_endpoint."""

PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "infrabeat-erp"


# === Dataclasses ==========================================================
@dataclass(frozen=True)
class Tool:
    """Immutable record of one tool advertised by the MCP server."""

    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class ServerCapabilities:
    """Immutable view of MCP server identity and advertised capabilities."""

    server_name: str
    server_version: str
    protocol_version: str
    tools_supported: bool
    streaming: bool


# === Exceptions ===========================================================
class MCPError(Exception):
    """Base class for MCP failures (HTTP transport and protocol errors)."""


class MCPProtocolError(MCPError):
    """Server replied with a JSON-RPC error object instead of a result."""


# === Private helpers ======================================================
_id_counter: Iterator[int] = itertools.count(1)


def _next_id() -> int:
    """Return the next monotonically-increasing JSON-RPC request id."""
    return next(_id_counter)


def _unwrap(body: object) -> dict:
    """Frappe sometimes wraps JSON-RPC in {"message": {...}}; unwrap once."""
    if isinstance(body, dict) and isinstance(body.get("message"), dict):
        inner = body["message"]
        if any(k in inner for k in ("jsonrpc", "result", "error")):
            return inner
    if isinstance(body, dict):
        return body
    return {}


def _resolve_mcp_endpoint(client: httpx.Client) -> str:
    """Resolve the MCP endpoint path via OIDC discovery, falling back on miss.

    Reads ``mcp_endpoint`` from the OIDC metadata at the client's base_url.
    If the key is missing or discovery raises, emits a DeprecationWarning
    and returns the hardcoded MCP_ENDPOINT_PATH.
    """
    base_url = str(client.base_url).rstrip("/")
    try:
        metadata = discover_oidc_metadata(base_url)
    except Exception:
        warnings.warn(
            "OIDC discovery failed; falling back to hardcoded mcp_endpoint. "
            "Upgrade Frappe Assistant Core to advertise mcp_endpoint in "
            "/.well-known/openid-configuration.",
            DeprecationWarning,
            stacklevel=2,
        )
        return MCP_ENDPOINT_PATH
    endpoint = metadata.get("mcp_endpoint")
    if endpoint:
        return endpoint
    warnings.warn(
        "OIDC metadata did not advertise mcp_endpoint; falling back to "
        "hardcoded MCP_ENDPOINT_PATH. Upgrade Frappe Assistant Core to "
        "advertise mcp_endpoint in /.well-known/openid-configuration.",
        DeprecationWarning,
        stacklevel=2,
    )
    return MCP_ENDPOINT_PATH


def _rpc(client: httpx.Client, method: str, params: dict) -> dict:
    """POST a JSON-RPC 2.0 envelope and return the parsed ``result`` dict.

    Raises:
        MCPError: On non-2xx HTTP status from the MCP endpoint.
        MCPProtocolError: On a JSON-RPC error response.
    """
    envelope = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": method,
        "params": params,
    }
    endpoint = _resolve_mcp_endpoint(client)
    response = client.post(endpoint, json=envelope)
    if not (200 <= response.status_code < 300):
        raise MCPError(
            f"HTTP {response.status_code} from MCP endpoint: "
            f"{response.text[:200]}"
        )
    body = _unwrap(response.json())
    if "error" in body:
        err = body["error"]
        raise MCPProtocolError(
            f"JSON-RPC error {err['code']}: {err['message']}"
        )
    return body.get("result", {})


# === Public API ===========================================================
def initialize(client: httpx.Client) -> ServerCapabilities:
    """Send the MCP ``initialize`` request and parse server capabilities.

    Args:
        client: httpx.Client whose base_url targets the FAC VM and whose
            headers include a Bearer Authorization token.

    Returns:
        A frozen ServerCapabilities record reflecting the server's
        identity, protocol version, and advertised capabilities.

    Raises:
        MCPError: On non-2xx HTTP status from the MCP endpoint.
        MCPProtocolError: On a JSON-RPC error response.
    """
    params = {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": CLIENT_NAME, "version": __version__},
    }
    result = _rpc(client, "initialize", params)
    server_info = result.get("serverInfo", {})
    capabilities = result.get("capabilities", {})
    return ServerCapabilities(
        server_name=server_info.get("name", ""),
        server_version=server_info.get("version", ""),
        protocol_version=result.get("protocolVersion", ""),
        tools_supported="tools" in capabilities,
        streaming=bool(capabilities.get("streaming") or False),
    )


def list_tools(client: httpx.Client) -> list[Tool]:
    """Send ``tools/list`` and return the advertised tool catalog.

    Args:
        client: httpx.Client whose base_url targets the FAC VM and whose
            headers include a Bearer Authorization token.

    Returns:
        A list of frozen Tool records, in the order the server returned
        them. May be empty.

    Raises:
        MCPError: On non-2xx HTTP status from the MCP endpoint.
        MCPProtocolError: On a JSON-RPC error response.
    """
    result = _rpc(client, "tools/list", {})
    tools: list[Tool] = []
    for item in result.get("tools", []):
        tools.append(
            Tool(
                name=item["name"],
                description=item.get("description", ""),
                input_schema=item.get("inputSchema", {}),
            )
        )
    return tools


def call_tool(
    client: httpx.Client,
    name: str,
    arguments: dict | None = None,
) -> dict:
    """Send ``tools/call`` for one tool and return the raw result dict.

    Args:
        client: httpx.Client whose base_url targets the FAC VM and whose
            headers include a Bearer Authorization token.
        name: Tool name to invoke; must be advertised by tools/list.
        arguments: Optional argument dict; defaults to {} when None.

    Returns:
        The JSON-RPC ``result`` dict as returned by the server, unwrapped
        once from any Frappe ``{"message": ...}`` envelope but otherwise
        unmodified.

    Raises:
        MCPError: On non-2xx HTTP status from the MCP endpoint.
        MCPProtocolError: On a JSON-RPC error response.
    """
    params = {"name": name, "arguments": arguments or {}}
    return _rpc(client, "tools/call", params)
