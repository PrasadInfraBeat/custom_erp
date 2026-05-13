"""Smoke test orchestrator - extracted from cli.py for TUI reuse (Sprint 5 Task 1b).

Pure SYNC function (matches existing sync http/mcp/oauth layers). TUI calls via
@work(thread=True) for non-blocking UI; CLI calls directly as a thin wrapper.
"""

from dataclasses import dataclass
from typing import List

from infrabeat_erp.infrastructure import config, http, mcp, secrets_store


@dataclass
class SmokeResult:
    """Result of a successful MCP smoke test against one VM."""

    vm: str
    server_name: str
    server_version: str
    protocol_version: str
    tool_count: int
    tools: List[str]


def smoke_vm(vm_alias: str) -> SmokeResult:
    """Run MCP smoke test against vm_alias.

    Raises:
        Exception: from config.get_vm (unknown VM alias)
        SecretsNotFound: from secrets_store.load_secrets (run login first)
        MCPError, MCPProtocolError: from mcp.initialize / mcp.list_tools
    """
    vm_config = config.get_vm(vm_alias)
    secrets = secrets_store.load_secrets(vm_alias)
    with http.make_client(
        vm_config.base_url, access_token=secrets["access_token"]
    ) as client:
        caps = mcp.initialize(client)
        tools = mcp.list_tools(client)
    return SmokeResult(
        vm=vm_alias,
        server_name=caps.server_name,
        server_version=caps.server_version,
        protocol_version=caps.protocol_version,
        tool_count=len(tools),
        tools=[tool.name for tool in tools],
    )
