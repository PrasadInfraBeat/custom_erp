"""Tests for infrabeat_erp.application.smoke."""

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
