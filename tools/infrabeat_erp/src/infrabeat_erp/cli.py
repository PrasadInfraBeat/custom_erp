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
@click.option(
    "--allow-production",
    is_flag=True,
    default=False,
    help=(
        "Required to target the 'production' VM alias. Per-invocation only. "
        "See Phase 6C.2 production guards."
    ),
)
@click.pass_context
def main(ctx: click.Context, allow_production: bool) -> None:
    """Root command group. Subcommands appear in sub-phase 6B."""
    ctx.ensure_object(dict)
    ctx.obj["allow_production"] = allow_production


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
    _ensure_production_allowed(vm_alias)
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
    _ensure_production_allowed(vm_alias)
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


# === Phase 6C.3 AUDIT LOG ===
# Single Group-level instrumentation point. Wraps BaseCommand.main on the
# Group instance so every dispatch path (subcommands AND short-circuiting
# eager options like --help) yields exactly one audit record with no
# per-subcommand decoration.

import time as _audit_time

from infrabeat_erp import audit as _audit

_AUDIT_SUBCOMMANDS = frozenset(
    ["register", "login", "smoke", "query", "get", "describe", "search"]
)
_AUDIT_VM_ALIASES = frozenset(["dev", "staging", "production"])


def _audit_resolve(argv_tail: list) -> tuple:
    positionals = [str(a) for a in argv_tail if not str(a).startswith("-")]
    if not positionals or positionals[0] not in _AUDIT_SUBCOMMANDS:
        return "help", None
    vm = None
    if len(positionals) > 1 and positionals[1] in _AUDIT_VM_ALIASES:
        vm = positionals[1]
    return positionals[0], vm


_audit_original_main = main.main


def _audit_wrapped_main(*a, **kw):
    start = _audit_time.monotonic()
    cli_args = kw.get("args")
    if cli_args is None and a:
        cli_args = a[0]
    if cli_args is None:
        cli_args = sys.argv[1:]
    argv_tail = list(cli_args)
    subcommand, vm = _audit_resolve(argv_tail)
    exit_code = 0
    try:
        return _audit_original_main(*a, **kw)
    except SystemExit as exc:
        code = exc.code
        exit_code = code if isinstance(code, int) else (0 if code is None else 1)
        raise
    except click.exceptions.Exit as exc:
        exit_code = int(getattr(exc, "exit_code", 1) or 0)
        raise
    except BaseException:
        exit_code = 1
        raise
    finally:
        duration_ms = int((_audit_time.monotonic() - start) * 1000)
        _audit.write_audit_record(
            _audit.build_audit_record(
                subcommand=subcommand,
                vm=vm,
                args=argv_tail,
                exit_code=exit_code,
                duration_ms=duration_ms,
            )
        )


main.main = _audit_wrapped_main


# === Phase 6C.2 PRODUCTION GUARDS ===
# Two distinct guard mechanisms for production-targeted operations:
#
# 1. --allow-production: Group-level Click flag that gates access to
#    vm_alias 'production'. Per-invocation only; not a session toggle.
#    Enforced via _ensure_production_allowed(), called as the first
#    line of _build_authed_client (catches query/get/describe/search)
#    AND as the first line of smoke (smoke does not flow through
#    _build_authed_client). register/login intentionally remain
#    ungated in 6C.2 - those are setup commands not covered by the
#    6C.2 test contract; revisit in a later sub-phase if needed.
#
# 2. _confirm_deploy_or_env: helper for FUTURE mutating subcommands
#    (none exist today; reserved for Phase 7+). Reads INFRABEAT_CONFIRM
#    env var for CI/scripted use, otherwise prompts interactively for
#    the literal string 'DEPLOY'.
#
# Refusal yields exit code 1 (user-error per the closure-doc exit-code
# contract: 0 success / 1 user error / 2 transport / 3 protocol).
#
# Audit interaction (Phase 6C.3, already merged): the Group main
# wrapper records argv verbatim, so whether --allow-production was
# passed is captured automatically as forensic proof of guard
# engagement. No 6C.2 changes to the audit module needed.
#
# Cross-cutting touchpoints intentionally diverge from the strict
# single-hunk discipline because group-level flags inherently span
# multiple sites: the @click.group() decorator gains an option,
# _build_authed_client gains a first-line guard call, and smoke
# gains a first-line guard call. All additions are additive; existing
# lines remain byte-identical to their post-6C.3 state.

import os as _guards_os


def _ensure_production_allowed(vm_alias: str) -> None:
    """Refuse production access unless --allow-production was passed.

    Dev and staging are unaffected. Reads the flag from the current
    Click context (set by the Group callback into ctx.obj). Emits a
    clear stderr refusal naming --allow-production and exits with
    code 1 if the flag is missing on a production-targeted call.
    """
    if vm_alias != "production":
        return
    ctx = click.get_current_context(silent=True)
    allowed = False
    if ctx is not None and isinstance(ctx.obj, dict):
        allowed = bool(ctx.obj.get("allow_production"))
    if not allowed:
        click.echo(
            "refusing to target production VM without --allow-production "
            "flag; pass --allow-production before the subcommand to proceed",
            err=True,
        )
        sys.exit(1)


def _confirm_deploy_or_env(env_var: str = "INFRABEAT_CONFIRM") -> None:
    """Require explicit DEPLOY confirmation for mutating production ops.

    If the env var (default INFRABEAT_CONFIRM) is set to the literal
    string 'DEPLOY', proceed silently - intended for CI/scripted use.
    Otherwise prompt interactively and require the user to type
    'DEPLOY' verbatim. Wrong input or KeyboardInterrupt aborts with
    exit code 1.

    Reserved for future mutating subcommands (Phase 7+). No existing
    6C.2 subcommand calls this helper - current 7 are all read-only.
    """
    if _guards_os.environ.get(env_var) == "DEPLOY":
        return
    try:
        answer = click.prompt(
            "Type DEPLOY to confirm this production-impacting action",
            default="",
            show_default=False,
        )
    except (click.Abort, KeyboardInterrupt):
        click.echo(
            "aborted: DEPLOY confirmation not received", err=True
        )
        sys.exit(1)
    if answer != "DEPLOY":
        click.echo(
            "aborted: DEPLOY confirmation not received", err=True
        )
        sys.exit(1)


# === Phase 6C.1 KEYRING PROMOTION ===
# migrate-secrets subcommand: moves <cwd>/.secrets/<vm>.json plaintext
# into the keyring-primary backend (or Fernet-encrypted JSON fallback
# when keyring is unavailable). Renames the original to .json.migrated
# for forensic trail. Idempotent: re-running on a migrated VM is a
# no-op. --vm <alias> targets one VM; --all (default behavior when
# --vm is omitted) iterates every alias in config.toml.
#
# Production targeting still flows through _ensure_production_allowed
# (Phase 6C.2): an explicit --vm production aborts without
# --allow-production at the Group level; --all silently skips
# production with a warning instead of aborting the whole batch.

# Extend the 6C.3 audit subcommand allow-list so migrate-secrets
# records as 'migrate-secrets' rather than the 'help' fall-through.
_AUDIT_SUBCOMMANDS = _AUDIT_SUBCOMMANDS | frozenset(["migrate-secrets"])


@main.command("migrate-secrets")
@click.option(
    "--vm",
    "vm_alias",
    default=None,
    help="Migrate only this VM alias (mutually exclusive with --all).",
)
@click.option(
    "--all",
    "do_all",
    is_flag=True,
    default=False,
    help="Migrate every VM in config.toml. Default when --vm omitted.",
)
@click.pass_context
def migrate_secrets(
    ctx: click.Context,
    vm_alias: str | None,
    do_all: bool,
) -> None:
    """Migrate plaintext .secrets/<vm>.json into keyring (or encrypted JSON).

    After verifying the new backend works, manually delete the
    .json.migrated files left behind for the forensic trail.
    """
    if vm_alias and do_all:
        click.echo(
            "--vm and --all are mutually exclusive", err=True
        )
        sys.exit(1)

    if vm_alias:
        targets = [vm_alias]
    else:
        try:
            targets = sorted(config.load_config())
        except FileNotFoundError as exc:
            click.echo(f"config error: {exc}", err=True)
            sys.exit(1)

    allow_production = bool(
        ctx.obj.get("allow_production")
        if isinstance(ctx.obj, dict)
        else False
    )

    for target in targets:
        if target == "production" and not allow_production:
            if vm_alias:
                _ensure_production_allowed(target)
            click.echo(
                f"{target}: skipped (pass --allow-production to migrate)"
            )
            continue
        try:
            status = secrets_store.migrate(target)
        except secrets_store.SecretsStoreError as exc:
            click.echo(f"{target}: error: {exc}", err=True)
            sys.exit(1)
        click.echo(f"{target}: {status}")
