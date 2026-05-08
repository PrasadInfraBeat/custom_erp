"""Tests for infrabeat_erp.cli subcommands (Phase 6B.4b)."""

import json
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from infrabeat_erp import cli, config, http, mcp, oauth, secrets_store
from infrabeat_erp.config import VMConfig
from infrabeat_erp.mcp import MCPProtocolError, ServerCapabilities, Tool
from infrabeat_erp.oauth import ClientRegistration, Tokens
from infrabeat_erp.secrets_store import SecretsNotFound


def _vm() -> VMConfig:
    """Return a fake VMConfig for tests."""
    return VMConfig(name="dev", base_url="http://erp.test")


def test_register_persists_client_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    monkeypatch.setattr(config, "get_vm", lambda name: _vm())
    monkeypatch.setattr(
        oauth,
        "register_client",
        lambda url: ClientRegistration(
            client_id="abc",
            client_secret=None,
            redirect_uri="http://127.0.0.1:8765/callback",
            registration_endpoint="http://erp.test/register",
        ),
    )
    monkeypatch.setattr(
        secrets_store,
        "save_secrets",
        lambda vm, data: captured.update(args=(vm, data)),
    )

    result = CliRunner().invoke(cli.main, ["register", "dev"])
    assert result.exit_code == 0
    assert captured["args"][0] == "dev"
    assert captured["args"][1]["client_id"] == "abc"


def test_register_unknown_vm(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_key(name: str) -> VMConfig:
        raise KeyError("unknown")

    monkeypatch.setattr(config, "get_vm", raise_key)

    result = CliRunner().invoke(cli.main, ["register", "nonexistent"])
    assert result.exit_code == 1
    assert "unknown" in result.output


def test_login_persists_tokens_merged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    monkeypatch.setattr(config, "get_vm", lambda name: _vm())
    monkeypatch.setattr(
        secrets_store,
        "load_secrets",
        lambda vm: {
            "client_id": "abc",
            "client_secret": None,
            "redirect_uri": "http://127.0.0.1:8765/callback",
            "registration_endpoint": "http://erp.test/register",
        },
    )
    monkeypatch.setattr(
        oauth,
        "login_authcode_pkce",
        lambda url, client: Tokens(
            access_token="t1",
            refresh_token="r1",
            token_type="Bearer",
            expires_in=3600,
            issued_at=1234.0,
            scope="read",
        ),
    )
    monkeypatch.setattr(
        secrets_store,
        "save_secrets",
        lambda vm, data: captured.update(args=(vm, data)),
    )

    result = CliRunner().invoke(cli.main, ["login", "dev"])
    assert result.exit_code == 0
    saved = captured["args"][1]
    assert saved["client_id"] == "abc"
    assert saved["access_token"] == "t1"


def test_login_without_register(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_not_found(vm: str) -> dict:
        raise SecretsNotFound("no client")

    monkeypatch.setattr(config, "get_vm", lambda name: _vm())
    monkeypatch.setattr(secrets_store, "load_secrets", raise_not_found)

    result = CliRunner().invoke(cli.main, ["login", "dev"])
    assert result.exit_code == 1
    assert "register" in result.output


def _wire_smoke_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wire up monkeypatches shared by the smoke success-path tests."""
    monkeypatch.setattr(config, "get_vm", lambda name: _vm())
    monkeypatch.setattr(
        secrets_store, "load_secrets", lambda vm: {"access_token": "tok"}
    )
    monkeypatch.setattr(
        http, "make_client", lambda *a, **k: MagicMock()
    )
    monkeypatch.setattr(
        mcp,
        "initialize",
        lambda c: ServerCapabilities(
            server_name="frappe-assistant-core",
            server_version="2.4.1",
            protocol_version="2024-11-05",
            tools_supported=True,
            streaming=False,
        ),
    )
    monkeypatch.setattr(
        mcp,
        "list_tools",
        lambda c: [
            Tool(name="list_documents", description="...", input_schema={}),
            Tool(name="get_document", description="...", input_schema={}),
        ],
    )


def test_smoke_emits_human_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_smoke_chain(monkeypatch)
    result = CliRunner().invoke(cli.main, ["smoke", "dev"])
    assert result.exit_code == 0
    assert "frappe-assistant-core" in result.output
    assert "Tools available: 2" in result.output


def test_smoke_emits_json_when_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_smoke_chain(monkeypatch)
    result = CliRunner().invoke(cli.main, ["smoke", "dev", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["vm"] == "dev"
    assert payload["tool_count"] == 2
    assert "list_documents" in payload["tools"]


def test_smoke_handles_mcp_protocol_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "get_vm", lambda name: _vm())
    monkeypatch.setattr(
        secrets_store, "load_secrets", lambda vm: {"access_token": "tok"}
    )
    monkeypatch.setattr(http, "make_client", lambda *a, **k: MagicMock())

    def raise_proto(c: object) -> None:
        raise MCPProtocolError("JSON-RPC error -32601: Method not found")

    monkeypatch.setattr(mcp, "initialize", raise_proto)

    result = CliRunner().invoke(cli.main, ["smoke", "dev"])
    assert result.exit_code == 3


def test_smoke_without_login(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_not_found(vm: str) -> dict:
        raise SecretsNotFound("no tokens")

    monkeypatch.setattr(config, "get_vm", lambda name: _vm())
    monkeypatch.setattr(secrets_store, "load_secrets", raise_not_found)

    result = CliRunner().invoke(cli.main, ["smoke", "dev"])
    assert result.exit_code == 1
    assert "login" in result.output
