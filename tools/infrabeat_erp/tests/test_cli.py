from infrabeat_erp.cli import main
"""Tests for infrabeat_erp.cli subcommands (Phase 6B.4b)."""

import json
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from infrabeat_erp import cli
from infrabeat_erp.infrastructure import config, http, mcp, oauth, secrets_store
from infrabeat_erp.infrastructure.config import VMConfig
from infrabeat_erp.infrastructure.mcp import MCPProtocolError, ServerCapabilities, Tool
from infrabeat_erp.infrastructure.oauth import ClientRegistration, Tokens
from infrabeat_erp.infrastructure.secrets_store import SecretsNotFound


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


# === Phase 6B.5 TESTS ===


def _wire_data_chain(
    monkeypatch: pytest.MonkeyPatch, call_tool_result: object
) -> dict:
    """Wire monkeypatches for data subcommands; capture call_tool args."""
    captured: dict = {}
    monkeypatch.setattr(config, "get_vm", lambda name: _vm())
    monkeypatch.setattr(
        secrets_store, "load_secrets", lambda vm: {"access_token": "tok"}
    )
    monkeypatch.setattr(http, "make_client", lambda *a, **k: MagicMock())

    def fake_call_tool(client: object, name: str, args: dict) -> object:
        captured["name"] = name
        captured["arguments"] = args
        if isinstance(call_tool_result, Exception):
            raise call_tool_result
        return call_tool_result

    monkeypatch.setattr(mcp, "call_tool", fake_call_tool)
    return captured


def test_query_emits_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_data_chain(
        monkeypatch,
        {
            "documents": [
                {"name": "SO-001", "status": "Open"},
                {"name": "SO-002", "status": "Closed"},
            ]
        },
    )
    result = CliRunner().invoke(cli.main, ["query", "dev", "Sales Order"])
    assert result.exit_code == 0
    assert "SO-001" in result.output
    assert "SO-002" in result.output


def test_query_with_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _wire_data_chain(monkeypatch, {"documents": []})
    result = CliRunner().invoke(
        cli.main,
        ["query", "dev", "Sales Order", "--filter", "status=Open"],
    )
    assert result.exit_code == 0
    assert captured["arguments"]["filters"] == {"status": "Open"}


def test_query_invalid_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_data_chain(monkeypatch, {"documents": []})
    result = CliRunner().invoke(
        cli.main,
        ["query", "dev", "Sales Order", "--filter", "noequalsign"],
    )
    assert result.exit_code == 1
    assert "invalid filter" in result.output


def test_get_emits_document(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_data_chain(
        monkeypatch,
        {"name": "SO-001", "customer": "ACME", "status": "Open"},
    )
    result = CliRunner().invoke(
        cli.main, ["get", "dev", "Sales Order", "SO-001"]
    )
    assert result.exit_code == 0
    assert "ACME" in result.output


def test_get_handles_protocol_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_data_chain(
        monkeypatch,
        MCPProtocolError("JSON-RPC error -32602: Invalid params"),
    )
    result = CliRunner().invoke(
        cli.main, ["get", "dev", "Sales Order", "SO-999"]
    )
    assert result.exit_code == 3


def test_describe_emits_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_data_chain(
        monkeypatch,
        {
            "fields": [
                {"fieldname": "name", "fieldtype": "Data"},
                {"fieldname": "status", "fieldtype": "Select"},
            ]
        },
    )
    result = CliRunner().invoke(
        cli.main, ["describe", "dev", "Sales Order"]
    )
    assert result.exit_code == 0
    assert "name" in result.output
    assert "status" in result.output


def test_search_emits_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_data_chain(
        monkeypatch,
        {
            "results": [
                {
                    "doctype": "Sales Order",
                    "name": "SO-001",
                    "snippet": "ACME order",
                }
            ]
        },
    )
    result = CliRunner().invoke(cli.main, ["search", "dev", "ACME"])
    assert result.exit_code == 0
    assert "SO-001" in result.output
    assert "ACME" in result.output


def test_query_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_data_chain(
        monkeypatch,
        {
            "documents": [
                {"name": "SO-001", "status": "Open"},
            ]
        },
    )
    result = CliRunner().invoke(
        cli.main, ["query", "dev", "Sales Order", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["vm"] == "dev"
    assert "documents" in payload


# === Phase 6C.2 PRODUCTION GUARDS TESTS ===

import click


def _vm_named(name: str) -> VMConfig:
    return VMConfig(name=name, base_url=f"http://erp.{name}.test")


def test_allow_production_blocks_production_without_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "get_vm", lambda name: _vm_named(name))
    monkeypatch.setattr(
        secrets_store, "load_secrets", lambda vm: {"access_token": "tok"}
    )
    monkeypatch.setattr(http, "make_client", lambda *a, **k: MagicMock())

    result = CliRunner().invoke(
        cli.main, ["smoke", "production"]
    )
    assert result.exit_code == 1
    assert "--allow-production" in result.stderr


def test_allow_production_permits_production_with_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_smoke_chain(monkeypatch)
    monkeypatch.setattr(config, "get_vm", lambda name: _vm_named(name))

    result = CliRunner().invoke(
        cli.main, ["--allow-production", "smoke", "production"]
    )
    assert result.exit_code == 0
    assert "--allow-production" not in result.stderr
    assert "frappe-assistant-core" in result.output


def test_allow_production_irrelevant_for_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_smoke_chain(monkeypatch)
    result = CliRunner().invoke(cli.main, ["smoke", "dev"])
    assert result.exit_code == 0
    assert "--allow-production" not in result.stderr


def test_allow_production_irrelevant_for_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_smoke_chain(monkeypatch)
    monkeypatch.setattr(config, "get_vm", lambda name: _vm_named(name))
    result = CliRunner().invoke(
        cli.main, ["smoke", "staging"]
    )
    assert result.exit_code == 0
    assert "--allow-production" not in result.stderr


def test_confirm_deploy_via_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFRABEAT_CONFIRM", "DEPLOY")
    prompt_called: list = []

    def fake_prompt(*args: object, **kwargs: object) -> str:
        prompt_called.append(True)
        return "DEPLOY"

    monkeypatch.setattr(click, "prompt", fake_prompt)
    assert cli._confirm_deploy_or_env() is None
    assert prompt_called == []


def test_confirm_deploy_interactive_correct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INFRABEAT_CONFIRM", raising=False)
    monkeypatch.setattr(click, "prompt", lambda *a, **k: "DEPLOY")
    assert cli._confirm_deploy_or_env() is None


def test_confirm_deploy_interactive_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INFRABEAT_CONFIRM", raising=False)
    monkeypatch.setattr(click, "prompt", lambda *a, **k: "NOPE")
    with pytest.raises(SystemExit) as exc_info:
        cli._confirm_deploy_or_env()
    assert exc_info.value.code == 1



def test_allow_production_blocks_register_without_flag(monkeypatch, tmp_path):
    """register production refuses without --allow-production (closes 6C.2 coverage gap)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["register", "production"])
    assert result.exit_code == 1
    assert "allow-production" in result.output.lower()


def test_allow_production_blocks_login_without_flag(monkeypatch, tmp_path):
    """login production refuses without --allow-production (closes 6C.2 coverage gap)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["login", "production"])
    assert result.exit_code == 1
    assert "allow-production" in result.output.lower()


# === Phase 6C.1 KEYRING PROMOTION TESTS ===


def test_migrate_secrets_dev_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_migrate(vm: str, base_dir=None) -> str:
        captured["vm"] = vm
        return "migrated"

    monkeypatch.setattr(secrets_store, "migrate", fake_migrate)

    result = CliRunner().invoke(cli.main, ["migrate-secrets", "--vm", "dev"])
    assert result.exit_code == 0
    assert captured["vm"] == "dev"
    assert "dev" in result.output
    assert "migrated" in result.output


def test_migrate_secrets_production_requires_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        secrets_store,
        "migrate",
        lambda vm, base_dir=None: pytest.fail(
            "migrate must not run for production without --allow-production"
        ),
    )

    result = CliRunner().invoke(
        cli.main, ["migrate-secrets", "--vm", "production"]
    )
    assert result.exit_code == 1
    assert "allow-production" in result.stderr.lower()


def test_migrate_secrets_all_skips_production_without_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        config,
        "load_config",
        lambda path=None: {
            "dev": VMConfig(name="dev", base_url="http://erp.dev.test"),
            "staging": VMConfig(
                name="staging", base_url="http://erp.staging.test"
            ),
            "production": VMConfig(
                name="production", base_url="http://erp.prod.test"
            ),
        },
    )

    migrated: list[str] = []

    def fake_migrate(vm: str, base_dir=None) -> str:
        migrated.append(vm)
        return "migrated"

    monkeypatch.setattr(secrets_store, "migrate", fake_migrate)

    result = CliRunner().invoke(cli.main, ["migrate-secrets", "--all"])
    assert result.exit_code == 0
    assert "production" not in migrated
    assert set(migrated) == {"dev", "staging"}
    assert "production: skipped" in result.output


# === Task 1c: audit subcommand routing (post-6C.3 fix) ===


def test_audit_resolve_doctor():
    from infrabeat_erp.cli import _audit_resolve
    assert _audit_resolve(["doctor"]) == ("doctor", None)


def test_audit_resolve_backup_with_vm():
    from infrabeat_erp.cli import _audit_resolve
    assert _audit_resolve(["backup", "staging"]) == ("backup", "staging")


def test_audit_resolve_unknown_falls_back_to_help():
    from infrabeat_erp.cli import _audit_resolve
    assert _audit_resolve(["unknown-cmd"]) == ("help", None)
