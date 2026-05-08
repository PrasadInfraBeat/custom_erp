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


# === Phase 6B.5 SUBCOMMANDS ===

import httpx


def _build_authed_client(
    vm_alias: str,
) -> tuple[config.VMConfig, dict, httpx.Client]:
    """Resolve VM, load OAuth secrets, and build an authenticated HTTP client.

    Exits with code 1 on unknown VM or missing secrets, mirroring the
    register/login/smoke contract from Phase 6B.4b. The caller owns the
    returned httpx.Client and is expected to close it (typically via
    ``with client: ...``).
    """
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

    client = http.make_client(
        vm_config.base_url, access_token=secrets.get("access_token")
    )
    return vm_config, secrets, client


@main.command()
@click.argument("vm_alias")
@click.argument("doctype")
@click.option(
    "--filter",
    "filters",
    multiple=True,
    help=(
        "Field=value filter (repeatable, e.g. --filter status=Open "
        "--filter customer=ACME)"
    ),
)
@click.option(
    "--limit",
    type=int,
    default=20,
    help="Max results to return (default 20)",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
def query(
    vm_alias: str,
    doctype: str,
    filters: tuple,
    limit: int,
    as_json: bool,
) -> None:
    """List documents of DOCTYPE on VM_ALIAS, optionally filtered."""
    filters_dict: dict = {}
    for raw in filters:
        if "=" not in raw:
            click.echo(
                f"invalid filter: {raw}; expected key=value", err=True
            )
            sys.exit(1)
        key, value = raw.split("=", 1)
        filters_dict[key] = value

    _, _, client = _build_authed_client(vm_alias)
    with client:
        try:
            result = mcp.call_tool(
                client,
                "list_documents",
                {
                    "doctype": doctype,
                    "filters": filters_dict,
                    "limit": limit,
                },
            )
        except MCPProtocolError as exc:
            click.echo(f"MCP protocol error: {exc}", err=True)
            sys.exit(3)
        except MCPError as exc:
            click.echo(f"MCP error: {exc}", err=True)
            sys.exit(2)

    documents = (
        result.get("documents", []) if isinstance(result, dict) else []
    )

    if as_json:
        payload = {
            "vm": vm_alias,
            "doctype": doctype,
            "count": len(documents),
            "documents": documents,
        }
        click.echo(json.dumps(payload, indent=2))
        return

    click.echo(f"DocType: {doctype} on {vm_alias}")
    for doc in documents:
        if isinstance(doc, dict):
            summary = ", ".join(
                f"{k}={doc[k]}" for k in list(doc.keys())[:4]
            )
            click.echo(f"  - {summary}")
        else:
            click.echo(f"  - {doc}")


@main.command()
@click.argument("vm_alias")
@click.argument("doctype")
@click.argument("name")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
def get(
    vm_alias: str,
    doctype: str,
    name: str,
    as_json: bool,
) -> None:
    """Get a single document by NAME from DOCTYPE on VM_ALIAS."""
    _, _, client = _build_authed_client(vm_alias)
    with client:
        try:
            result = mcp.call_tool(
                client,
                "get_document",
                {"doctype": doctype, "name": name},
            )
        except MCPProtocolError as exc:
            click.echo(f"MCP protocol error: {exc}", err=True)
            sys.exit(3)
        except MCPError as exc:
            click.echo(f"MCP error: {exc}", err=True)
            sys.exit(2)

    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    click.echo(f"DocType: {doctype}")
    click.echo(f"Name: {name}")
    if isinstance(result, dict):
        for key, value in result.items():
            rendered = str(value)
            if len(rendered) > 80:
                rendered = rendered[:77] + "..."
            click.echo(f"  {key}: {rendered}")


@main.command()
@click.argument("vm_alias")
@click.argument("doctype")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
def describe(vm_alias: str, doctype: str, as_json: bool) -> None:
    """Show the schema (fields and types) of DOCTYPE on VM_ALIAS.

    Sources the schema from FAC's get_doctype_info tool, which returns
    DocType metadata including the field list with fieldname/fieldtype/label.
    """
    _, _, client = _build_authed_client(vm_alias)
    with client:
        try:
            result = mcp.call_tool(
                client,
                "get_doctype_info",
                {"doctype": doctype},
            )
        except MCPProtocolError as exc:
            click.echo(f"MCP protocol error: {exc}", err=True)
            sys.exit(3)
        except MCPError as exc:
            click.echo(f"MCP error: {exc}", err=True)
            sys.exit(2)

    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    click.echo(f"DocType: {doctype}")
    fields = result.get("fields") if isinstance(result, dict) else None
    if isinstance(fields, list):
        click.echo("Fields:")
        for field in fields:
            if isinstance(field, dict):
                fname = field.get("fieldname", "?")
                ftype = field.get("fieldtype", "?")
                flabel = field.get("label", "")
                click.echo(f"  {fname} ({ftype}): {flabel}")
    else:
        click.echo(json.dumps(result, indent=2))


@main.command()
@click.argument("vm_alias")
@click.argument("text")
@click.option(
    "--limit",
    type=int,
    default=20,
    help="Max results to return (default 20)",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
def search(
    vm_alias: str,
    text: str,
    limit: int,
    as_json: bool,
) -> None:
    """Full-text search for TEXT across all documents on VM_ALIAS."""
    _, _, client = _build_authed_client(vm_alias)
    with client:
        try:
            result = mcp.call_tool(
                client,
                "search_documents",
                {"query": text, "limit": limit},
            )
        except MCPProtocolError as exc:
            click.echo(f"MCP protocol error: {exc}", err=True)
            sys.exit(3)
        except MCPError as exc:
            click.echo(f"MCP error: {exc}", err=True)
            sys.exit(2)

    results = (
        result.get("results", []) if isinstance(result, dict) else []
    )

    if as_json:
        payload = {
            "vm": vm_alias,
            "query": text,
            "count": len(results),
            "results": results,
        }
        click.echo(json.dumps(payload, indent=2))
        return

    click.echo(f"Search: {text}")
    for item in results:
        if isinstance(item, dict):
            dtype = item.get("doctype", "?")
            iname = item.get("name", "?")
            snippet = item.get("snippet") or item.get("title") or ""
            click.echo(f"  - {dtype}/{iname}: {snippet}")
