# infrabeat-erp

InfraBeat ERPNext CLI - discovery, OAuth, and MCP query bridge for Frappe Assistant Core (FAC).

Wraps the proven Phase 5 stdlib scripts (probe_fac, register_client, oauth_login, mcp_smoke_test)
into an installable Python package with a click-based CLI. Targets the dev / staging / production
ERPNext fleet over OAuth 2.1 + PKCE.

## Status

Phase 6A scaffolding in progress. Module structure and entry point are in place;
subcommands and logic relocation land in sub-phases 6B through 6E.

## Install (development)

    pip install -e tools/infrabeat_erp

## Smoke test

    infrabeat-erp --help
