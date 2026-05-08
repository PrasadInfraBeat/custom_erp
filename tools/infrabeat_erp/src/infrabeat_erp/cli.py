"""infrabeat-erp CLI entry point.

Phase 6A: minimal click root group. Subcommands (register, login, smoke,
query, get, describe, search) wire up in sub-phase 6B.
"""

import click

from infrabeat_erp import __version__


@click.group(
    help="InfraBeat ERPNext CLI - discovery, OAuth, and MCP query bridge for FAC."
)
@click.version_option(version=__version__, prog_name="infrabeat-erp")
def main() -> None:
    """Root command group. Subcommands appear in sub-phase 6B."""


if __name__ == "__main__":
    main()

# === Phase 6B.4b SUBCOMMANDS ===

import json
import sys
from dataclasses import asdict

from infrabeat_erp import config, http, mcp, oauth, secrets_store
from infrabeat_erp.mcp import MCPError, MCPProtocolError
from infrabeat_erp.oauth import ClientRegistration, LoginError, RegistrationError
from infrabeat_erp.secrets_store import SecretsNotFound


@main.command()
@click.argument("vm_alias")
def register(vm_alias: str) -> None:
    """Discover OAuth metadata and register a dynamic client for VM_ALIAS."""
    try:
        vm_config = config.get_vm(vm_alias)
    except Exception:
        click.echo(f"unknown vm: {vm_alias}", err=True)
        sys.exit(1)

    try:
        client_reg = oauth.register_client(vm_config.base_url)
    except RegistrationError as exc:
        click.echo(f"registration failed: {exc}", err=True)
        sys.exit(2)

    secrets_store.save_secrets(vm_alias, asdict(client_reg))
    click.echo(
        f"Registered client for {vm_alias}: client_id={client_reg.client_id}"
    )


@main.command()
@click.argument("vm_alias")
def login(vm_alias: str) -> None:
    """Run OAuth authorization code + PKCE flow for VM_ALIAS."""
    try:
        vm_config = config.get_vm(vm_alias)
    except Exception:
        click.echo(f"unknown vm: {vm_alias}", err=True)
        sys.exit(1)

    try:
        existing = secrets_store.load_secrets(vm_alias)
    except SecretsNotFound:
        click.echo(
            f"no client for {vm_alias}; run register first", err=True
        )
        sys.exit(1)

    client_reg = ClientRegistration(
        client_id=existing["client_id"],
        client_secret=existing.get("client_secret"),
        redirect_uri=existing["redirect_uri"],
        registration_endpoint=existing["registration_endpoint"],
    )

    try:
        tokens = oauth.login_authcode_pkce(vm_config.base_url, client_reg)
    except LoginError as exc:
        click.echo(f"login failed: {exc}", err=True)
        sys.exit(2)

    combined = {**existing, **asdict(tokens)}
    secrets_store.save_secrets(vm_alias, combined)
    click.echo(
        f"Logged in to {vm_alias}: token expires in {tokens.expires_in}s"
    )


@main.command()
@click.argument("vm_alias")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
def smoke(vm_alias: str, as_json: bool) -> None:
    """Initialize MCP and list tools - full-stack health check for VM_ALIAS."""
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
            click.echo(f"  - {tool.name}")
