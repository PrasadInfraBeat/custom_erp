"""Smoke test orchestrator - extracted from cli.py for TUI reuse (Sprint 5 Task 1b).

Pure SYNC function (matches existing sync http/mcp/oauth layers). TUI calls via
@work(thread=True) for non-blocking UI; CLI calls directly as a thin wrapper.

Phase 7b Sprint 1 Task 2 (L92): MCP calls are now wrapped by
auth_retry.call_with_relogin, which catches HTTP 401 from FAC and
triggers `infrabeat-erp login <vm>` subprocess to refresh tokens, then
retries the smoke once.
"""

from dataclasses import dataclass
from typing import List

from infrabeat_erp.application import auth_retry
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

    On HTTP 401 the auth_retry layer triggers re-login (browser flow) and
    retries the inner block once. Other errors propagate unchanged.

    Raises:
        Exception: from config.get_vm (unknown VM alias)
        SecretsNotFound: from secrets_store.load_secrets (run login first)
        MCPError, MCPProtocolError: from mcp.initialize / mcp.list_tools
        AuthRetryError: from auth_retry.trigger_relogin if relogin fails
    """
    vm_config = config.get_vm(vm_alias)

    def _do_smoke():
        secrets = secrets_store.load_secrets(vm_alias)
        with http.make_client(
            vm_config.base_url, access_token=secrets["access_token"]
        ) as client:
            caps = mcp.initialize(client)
            tools = mcp.list_tools(client)
        return caps, tools

    caps, tools = auth_retry.call_with_relogin(vm_alias, _do_smoke)

    return SmokeResult(
        vm=vm_alias,
        server_name=caps.server_name,
        server_version=caps.server_version,
        protocol_version=caps.protocol_version,
        tool_count=len(tools),
        tools=[tool.name for tool in tools],
    )