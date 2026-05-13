#!/usr/bin/env python
"""Sprint 5 Task 1b: Extract smoke_vm + wire TUI [S]moke.

Atomic rewriter (L83):
  1. Create application/smoke.py (SmokeResult + smoke_vm)
  2. Modify cli.py smoke command to use smoke_vm
  3. Modify tui_app.py to add real action_smoke + _run_smoke_worker
  4. Create tests/test_smoke.py
  5. Modify tests/test_tui_app.py to add action_smoke dispatch test

All edits anchored on exact strings; ast.parse verified after every write.
"""

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp"
TESTS_DIR = REPO / "tools" / "infrabeat_erp" / "tests"

SMOKE_PY = PKG / "application" / "smoke.py"
CLI_PY = PKG / "cli.py"
TUI_PY = PKG / "presentation" / "tui_app.py"
TEST_SMOKE = TESTS_DIR / "test_smoke.py"
TEST_TUI = TESTS_DIR / "test_tui_app.py"


def write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    readback = path.read_text(encoding="utf-8")
    assert readback == content, f"Read-back mismatch on {path}"
    ast.parse(readback)
    print(f"  wrote {path.relative_to(REPO)} ({len(content)} bytes, ast OK)")


SMOKE_MODULE = '''"""Smoke test orchestrator - extracted from cli.py for TUI reuse (Sprint 5 Task 1b).

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
'''


# --- cli.py anchors ---
OLD_CLI_IMPORT = (
    "from infrabeat_erp.infrastructure import config, http, mcp, oauth, secrets_store"
)
NEW_CLI_IMPORT = (
    "from infrabeat_erp.application.smoke import smoke_vm\n"
    "from infrabeat_erp.infrastructure import config, http, mcp, oauth, secrets_store"
)

OLD_SMOKE_BODY = '''def smoke(vm_alias: str, as_json: bool) -> None:
    """Initialize MCP and list tools - full-stack health check for VM_ALIAS."""
    _ensure_production_allowed(vm_alias)
    try:
        vm_config = config.get_vm(vm_alias)
    except Exception:
        click.echo(f"unknown vm: {vm_alias}", err=True)
        sys.exit(1)

    try:
        secrets = secrets_store.load_secrets(vm_alias)
    except SecretsNotFound:
        click.echo(
            f"no tokens for {vm_alias}; run login first", err=True
        )
        sys.exit(1)

    with http.make_client(
        vm_config.base_url, access_token=secrets["access_token"]
    ) as client:
        try:
            caps = mcp.initialize(client)
        except MCPProtocolError as exc:
            click.echo(f"MCP protocol error: {exc}", err=True)
            sys.exit(3)
        except MCPError as exc:
            click.echo(f"MCP error: {exc}", err=True)
            sys.exit(2)

        try:
            tools = mcp.list_tools(client)
        except MCPProtocolError as exc:
            click.echo(f"MCP protocol error: {exc}", err=True)
            sys.exit(3)
        except MCPError as exc:
            click.echo(f"MCP error: {exc}", err=True)
            sys.exit(2)

    if as_json:
        payload = {
            "vm": vm_alias,
            "server_name": caps.server_name,
            "server_version": caps.server_version,
            "protocol_version": caps.protocol_version,
            "tool_count": len(tools),
            "tools": [tool.name for tool in tools],
        }
        click.echo(json.dumps(payload, indent=2))
    else:
        click.echo(f"VM: {vm_alias}")
        click.echo(f"Server: {caps.server_name} {caps.server_version}")
        click.echo(f"Protocol: {caps.protocol_version}")
        click.echo(f"Tools available: {len(tools)}")
        for tool in tools:
            click.echo(f"  - {tool.name}")'''

NEW_SMOKE_BODY = '''def smoke(vm_alias: str, as_json: bool) -> None:
    """Initialize MCP and list tools - full-stack health check for VM_ALIAS."""
    _ensure_production_allowed(vm_alias)
    try:
        result = smoke_vm(vm_alias)
    except SecretsNotFound:
        click.echo(f"no tokens for {vm_alias}; run login first", err=True)
        sys.exit(1)
    except MCPProtocolError as exc:
        click.echo(f"MCP protocol error: {exc}", err=True)
        sys.exit(3)
    except MCPError as exc:
        click.echo(f"MCP error: {exc}", err=True)
        sys.exit(2)
    except Exception:
        click.echo(f"unknown vm: {vm_alias}", err=True)
        sys.exit(1)

    if as_json:
        payload = {
            "vm": result.vm,
            "server_name": result.server_name,
            "server_version": result.server_version,
            "protocol_version": result.protocol_version,
            "tool_count": result.tool_count,
            "tools": result.tools,
        }
        click.echo(json.dumps(payload, indent=2))
    else:
        click.echo(f"VM: {result.vm}")
        click.echo(f"Server: {result.server_name} {result.server_version}")
        click.echo(f"Protocol: {result.protocol_version}")
        click.echo(f"Tools available: {result.tool_count}")
        for tool_name in result.tools:
            click.echo(f"  - {tool_name}")'''


def patch_cli():
    content = CLI_PY.read_text(encoding="utf-8")
    assert OLD_CLI_IMPORT in content, "MISSING anchor: cli.py import line"
    assert OLD_SMOKE_BODY in content, "MISSING anchor: cli.py smoke body"
    content = content.replace(OLD_CLI_IMPORT, NEW_CLI_IMPORT)
    content = content.replace(OLD_SMOKE_BODY, NEW_SMOKE_BODY)
    assert "from infrabeat_erp.application.smoke import smoke_vm" in content
    assert OLD_SMOKE_BODY not in content
    write_file(CLI_PY, content)


# --- tui_app.py anchors ---
OLD_TUI_IMPORTS = (
    "from infrabeat_erp.application.backup import do_backup\n"
    "from infrabeat_erp.application.promote import do_promote"
)
NEW_TUI_IMPORTS = (
    "from infrabeat_erp.application.backup import do_backup\n"
    "from infrabeat_erp.application.promote import do_promote\n"
    "from infrabeat_erp.application.smoke import smoke_vm"
)

OLD_ACTION_SMOKE = '''    def action_smoke(self) -> None:
        self.notify("Smoke tests (Sprint 2 C5)", severity="information")'''

NEW_ACTION_SMOKE = '''    def action_smoke(self) -> None:
        """[S] -> VM picker -> spawn smoke worker (thread, since smoke_vm is sync)."""
        def _on_vm_selected(vm: Optional[str]) -> None:
            if vm:
                self._run_smoke_worker(vm)

        self.push_screen(VmSelectModal("Smoke"), _on_vm_selected)'''

OLD_PROMOTE_END = '''            self.notify(f"Promote to {target} failed: {e}", severity="error", timeout=10)

    # ====== Action handlers (LIVE for [B][P], stubs for others) ======'''

NEW_PROMOTE_END_WITH_SMOKE = '''            self.notify(f"Promote to {target} failed: {e}", severity="error", timeout=10)

    @work(exclusive=True, group="ops", thread=True)
    def _run_smoke_worker(self, vm: str) -> None:
        """Run smoke_vm(vm) in thread; UI updates via call_from_thread."""
        log = self.query_one("#output_log", RichLog)
        self.call_from_thread(log.write, f"[bold cyan][smoke][/bold cyan] starting on [bold]{vm}[/bold]...")
        self.call_from_thread(self.notify, f"Smoke on {vm} started", severity="information", timeout=3)
        try:
            result = smoke_vm(vm)
            self.call_from_thread(log.write, "[bold green][smoke][/bold green] complete:")
            self.call_from_thread(log.write, f"  server = {result.server_name} {result.server_version}")
            self.call_from_thread(log.write, f"  protocol = {result.protocol_version}")
            self.call_from_thread(log.write, f"  tools = {result.tool_count}")
            self.call_from_thread(self.notify, f"Smoke {vm}: {result.tool_count} tools OK", severity="information", timeout=5)
        except Exception as e:
            self.call_from_thread(log.write, f"[bold red][smoke ERROR][/bold red] {type(e).__name__}: {e}")
            self.call_from_thread(self.notify, f"Smoke {vm} failed: {e}", severity="error", timeout=10)

    # ====== Action handlers (LIVE for [B][S][P], stubs for others) ======'''


def patch_tui():
    content = TUI_PY.read_text(encoding="utf-8")
    assert OLD_TUI_IMPORTS in content, "MISSING anchor: tui imports block"
    assert OLD_ACTION_SMOKE in content, "MISSING anchor: action_smoke stub"
    assert OLD_PROMOTE_END in content, "MISSING anchor: promote worker end + comment"
    content = content.replace(OLD_TUI_IMPORTS, NEW_TUI_IMPORTS)
    content = content.replace(OLD_PROMOTE_END, NEW_PROMOTE_END_WITH_SMOKE)
    content = content.replace(OLD_ACTION_SMOKE, NEW_ACTION_SMOKE)
    assert "_run_smoke_worker" in content
    assert "smoke_vm" in content
    assert OLD_ACTION_SMOKE not in content
    write_file(TUI_PY, content)


TEST_SMOKE_CONTENT = '''"""Tests for infrabeat_erp.application.smoke."""

from dataclasses import is_dataclass
from unittest.mock import MagicMock

import pytest

from infrabeat_erp.application import smoke as smoke_module
from infrabeat_erp.application.smoke import SmokeResult, smoke_vm
from infrabeat_erp.infrastructure.mcp import MCPError


def test_smoke_result_is_dataclass():
    assert is_dataclass(SmokeResult)


def test_smoke_result_fields():
    result = SmokeResult(
        vm="staging",
        server_name="frappe-assistant-core",
        server_version="2.4.1",
        protocol_version="2024-11-05",
        tool_count=2,
        tools=["tool_a", "tool_b"],
    )
    assert result.vm == "staging"
    assert result.tool_count == 2
    assert "tool_a" in result.tools


def test_smoke_vm_happy_path(monkeypatch):
    fake_vm_config = MagicMock()
    fake_vm_config.base_url = "https://staging.example.com"
    monkeypatch.setattr(smoke_module.config, "get_vm", lambda vm: fake_vm_config)
    monkeypatch.setattr(
        smoke_module.secrets_store,
        "load_secrets",
        lambda vm: {"access_token": "token_xyz"},
    )

    http_ctx = MagicMock()
    http_ctx.__enter__ = MagicMock(return_value=MagicMock())
    http_ctx.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(smoke_module.http, "make_client", lambda *a, **kw: http_ctx)

    fake_caps = MagicMock()
    fake_caps.server_name = "fac"
    fake_caps.server_version = "2.4.1"
    fake_caps.protocol_version = "2024-11-05"
    monkeypatch.setattr(smoke_module.mcp, "initialize", lambda client: fake_caps)

    tool1 = MagicMock(); tool1.name = "ping"
    tool2 = MagicMock(); tool2.name = "list"
    monkeypatch.setattr(smoke_module.mcp, "list_tools", lambda client: [tool1, tool2])

    result = smoke_vm("staging")
    assert result.vm == "staging"
    assert result.server_name == "fac"
    assert result.server_version == "2.4.1"
    assert result.protocol_version == "2024-11-05"
    assert result.tool_count == 2
    assert result.tools == ["ping", "list"]


def test_smoke_vm_propagates_mcp_error(monkeypatch):
    fake_vm_config = MagicMock()
    fake_vm_config.base_url = "https://staging.example.com"
    monkeypatch.setattr(smoke_module.config, "get_vm", lambda vm: fake_vm_config)
    monkeypatch.setattr(
        smoke_module.secrets_store,
        "load_secrets",
        lambda vm: {"access_token": "token_xyz"},
    )

    http_ctx = MagicMock()
    http_ctx.__enter__ = MagicMock(return_value=MagicMock())
    http_ctx.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(smoke_module.http, "make_client", lambda *a, **kw: http_ctx)

    def boom(client):
        raise MCPError("server down")

    monkeypatch.setattr(smoke_module.mcp, "initialize", boom)

    with pytest.raises(MCPError, match="server down"):
        smoke_vm("staging")
'''


TEST_TUI_NEW = '''


def test_action_smoke_pushes_vm_modal(monkeypatch):
    """action_smoke pushes a VmSelectModal screen with a callback."""
    from infrabeat_erp.presentation import tui_app

    app = tui_app.InfraBeatApp()
    pushed = []

    def fake_push(screen, callback=None):
        pushed.append((type(screen).__name__, callback))

    monkeypatch.setattr(app, "push_screen", fake_push)
    app.action_smoke()

    assert len(pushed) == 1
    assert pushed[0][0] == "VmSelectModal"
    assert pushed[0][1] is not None
'''


def patch_test_tui():
    content = TEST_TUI.read_text(encoding="utf-8")
    content = content.rstrip() + TEST_TUI_NEW
    write_file(TEST_TUI, content)


def main() -> int:
    print("=== Sprint 5 Task 1b: smoke_vm extraction + TUI [S] wiring ===\n")
    print("1. Creating application/smoke.py...")
    write_file(SMOKE_PY, SMOKE_MODULE)
    print()
    print("2. Patching cli.py (smoke -> thin wrapper)...")
    patch_cli()
    print()
    print("3. Patching tui_app.py (action_smoke + worker)...")
    patch_tui()
    print()
    print("4. Creating tests/test_smoke.py...")
    write_file(TEST_SMOKE, TEST_SMOKE_CONTENT)
    print()
    print("5. Patching tests/test_tui_app.py (action_smoke test)...")
    patch_test_tui()
    print()
    print("=== SUCCESS ===")
    print("Next: cd tools/infrabeat_erp; python -m pytest -v")
    return 0


if __name__ == "__main__":
    sys.exit(main())