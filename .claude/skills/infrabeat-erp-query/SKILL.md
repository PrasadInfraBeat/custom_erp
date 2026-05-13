---
name: infrabeat-erp-query
description: "Use this skill when the user asks an ERPNext data question (counts, lists, statuses, schemas, recent records, full-text search) against the Dev, Staging, or Production VM. Triggers include 'how many X on staging', 'show me recent sales orders on dev', 'list customers where ...', 'what fields does DocType X have', 'search for ABC across the ERP', 'is FAC reachable on production'. Routes the request through the local infrabeat-erp CLI (OAuth + Frappe Assistant Core MCP, 17 tools, audit-logged). Read-only by construction. Do NOT use for code generation (use direct file edits via VS Code Claude Code), VM/system operations (use Ansible/SSH or the infrabeat-* deploy/smoke skills), or any destructive operation (deletions/updates/submits) without explicit user confirmation."
---

# infrabeat-erp-query

Translate a natural-language ERPNext data question into one or more
`infrabeat-erp` CLI invocations, run them, then present a human-readable
summary AND the raw JSON response. Read-only by construction in Phase 6E:
the CLI exposes `register`, `login`, `smoke`, `query`, `get`, `describe`,
`search`, `migrate-secrets` — none of which mutate ERPNext state.

## When to use

User asks about ERPNext data on a specific VM. Examples:
- "How many active customers on staging?"
- "Show me the 10 most recent sales orders on dev"
- "What fields does the Customer Visit DocType have on dev?"
- "Search for 'ACME' across the dev ERP"
- "List all DocTypes in the Custom Erp module on dev"
- "Is FAC reachable on production?"

If the user does NOT name a VM, ASK before defaulting. Cross-VM mistakes
are the #1 cause of failed deploys (CLAUDE.md Rule 17).

## VM aliases

| Alias        | VM IP        | Site             | Notes                                            |
|--------------|--------------|------------------|--------------------------------------------------|
| `dev`        | 10.1.0.184   | `erp.local`      | Daily development, hot-reload                    |
| `staging`    | 10.1.0.185   | `erp.staging`    | UAT, pre-production validation                   |
| `production` | 10.1.0.186   | `erp.production` | Requires `--allow-production` group-level flag   |

Production targeting REQUIRES `--allow-production` BEFORE the subcommand,
e.g. `infrabeat-erp --allow-production query production Customer ...`.
Without the flag the CLI exits 1 with a clear refusal.

## Available CLI commands

All commands run from the laptop (any working directory; OAuth secrets and
audit log are CWD-relative until Phase 6E user-home migration completes).

### Health / discovery

    infrabeat-erp smoke <vm-alias> [--json]

Initializes MCP and lists tools — full-stack proof that OAuth, transport,
and FAC are healthy. Use this when the user asks "is FAC reachable" or
"is dev/staging/production up". Returns server name, server version,
protocol version, and the 17-tool catalog.

### Data queries

    infrabeat-erp query <vm-alias> <doctype> [--filter k=v]... [--limit N] [--json]
    infrabeat-erp get   <vm-alias> <doctype> <name> [--json]
    infrabeat-erp describe <vm-alias> <doctype> [--json]
    infrabeat-erp search <vm-alias> "<text>" [--limit N] [--json]

- `query`: list documents of a DocType, optional repeated equality filters.
- `get`: fetch a single document by primary name.
- `describe`: schema (fieldname, fieldtype, label) for a DocType.
- `search`: full-text search across all DocTypes.

### Setup (only if smoke fails with auth error)

    infrabeat-erp register <vm-alias>     # one-time RFC 7591 client registration
    infrabeat-erp login    <vm-alias>     # RFC 7636 PKCE authcode flow

Phase 6E.9 added transparent token auto-refresh on 401, so a routine
expired access_token does NOT require manual re-login. Re-run `login`
ONLY if the skill surfaces a `TokenRefreshFailed` (refresh_token also
expired or revoked) or the user just rotated OAuth secrets.

### Always pass `--json`

The skill should always invoke with `--json` so the parsed payload is
deterministic, then format the human summary itself. The pretty (non-JSON)
output is for ad-hoc terminal use, not skill consumption.

## Common queries (worked examples)

### 1. "How many active customers on staging?"

    infrabeat-erp query staging Customer --filter disabled=0 --limit 1000 --json

Read `count` from the response payload. If `count == limit`, warn the user
that more records exist beyond the page and offer to raise `--limit` or
add a more specific filter.

### 2. "Show me the 10 most recent sales orders on dev"

    infrabeat-erp query dev "Sales Order" --limit 10 --json

Note: the `query` subcommand does NOT expose an explicit order_by today —
results follow FAC's `list_documents` server-side default (typically
`creation desc` for most DocTypes, but verify against the response before
claiming "most recent"). If strict ordering matters, say so to the user
and recommend reviewing the returned `creation` field.

### 3. "Is FAC reachable on production?"

    infrabeat-erp --allow-production smoke production --json

Note the `--allow-production` flag goes BEFORE the subcommand (it is a
group-level option, not a smoke-level option). Report `server_name`,
`server_version`, `protocol_version`, and `tool_count` from the JSON.
If `tool_count != 17`, flag the drift — staging and dev are at 17 tools
(`2.0.0`); production claims `2.4.1` per Phase 5 closure but may be stale.

### 4. "List all DocTypes in the Custom Erp module on dev"

    infrabeat-erp query dev DocType --filter module="Custom Erp" --limit 200 --json

Note the EXACT module casing: `Custom Erp` (capital C, capital E,
lowercase rp, single space — CLAUDE.md Rule 1). Quote it on the shell
because it contains a space.

### 5. "What fields does the Customer Visit DocType have on dev?"

    infrabeat-erp describe dev "Customer Visit" --json

Render the `fields` array as a fieldname / fieldtype / label table. If
the user is debugging a "Page not found" symptom, also recommend running
`infrabeat-erp query dev "Customer Visit" --limit 1 --json` — a 200 with
the DocType in the list confirms module folder nesting is correct (the
classic gotcha #2 trap).

### 6. "Find every record mentioning 'ACME' on dev"

    infrabeat-erp search dev "ACME" --limit 50 --json

Group results by `doctype` in the human summary so the user can see which
modules the term landed in.

## Output handling

The CLI emits JSON when `--json` is passed. The skill MUST:

1. Run the CLI, capture stdout.
2. Parse the JSON.
3. Compute and present a 1–3 line human-readable summary FIRST
   (e.g. "Staging has 247 active Customer records").
4. Include the raw JSON response in a fenced ```json``` code block AFTER
   the summary, so the user can audit the exact bytes the CLI returned.
5. If the JSON is large (>200 lines), still show the full block — never
   silently truncate. Offer a follow-up `get` / tighter filter if the
   user wants narrower data.

Never paraphrase a number or status without quoting the underlying JSON
field — the user must be able to verify the claim against the response.

## Failure modes

| Symptom from CLI                                       | What it means                                                    | What to suggest                                                                  |
|--------------------------------------------------------|------------------------------------------------------------------|----------------------------------------------------------------------------------|
| `unknown vm: <alias>` (exit 1)                         | Alias not in `config.toml`                                       | List the three valid aliases; ask the user to clarify                            |
| `no tokens for <vm>; run login first` (exit 1)         | First-ever use OR keyring entry was wiped                        | `infrabeat-erp register <vm>` then `infrabeat-erp login <vm>`                    |
| `no client for <vm>; run register first` (exit 1)      | Never registered an OAuth client for this VM                     | `infrabeat-erp register <vm>`                                                    |
| `TokenRefreshFailed: ... Run: infrabeat-erp login <vm>`| Phase 6E.9 auto-refresh attempted but `refresh_token` also expired/revoked | Run `infrabeat-erp login <vm>` (browser will open for PKCE)                      |
| `MCP error: ...` (exit 2)                              | Transport layer reached FAC but FAC returned an error            | Inspect the error string; usually a permission or DocType-name typo              |
| `MCP protocol error: ...` (exit 3)                     | FAC returned a response that violated MCP framing                | Capture the error and escalate; likely a FAC bug or version drift                |
| `refusing to target production VM without --allow-production` | Forgot the group flag                                       | Re-run with `--allow-production` BEFORE the subcommand                           |
| Connection timeout / refused                           | VPN down, VM down, or SSH/network tunnel broken                  | Ask the user to verify VPN to `10.1.0.0/24` and that the target VM is reachable  |

Phase 6E.9 transparent refresh handles routine 1-hour token expiry with
no user action — a re-prompt for `login` should be RARE.

## Non-scope (do NOT use this skill for)

- **Code generation** for new DocTypes / scripts / hooks / web forms —
  use `infrabeat-doctype`, `infrabeat-script`, `infrabeat-webform`. AI
  code lands in VS Code first per CLAUDE.md Rule 12.
- **VM-level operations** — bench commands, supervisor restarts,
  package installs. Use SSH or the `infrabeat-deploy` /
  `infrabeat-smoke-test` skills.
- **Destructive operations** — `delete_document`, `update_document`,
  `submit_document`, `run_workflow`. The `query`-class CLI subcommands
  are read-only by design; even if a future subcommand exposes mutations,
  this skill MUST require explicit user confirmation per CLAUDE.md
  Rule 19 (Production fragility) and the Five-Stop Flow.
- **Bulk data operations** — covered by `infrabeat-database-op` with
  parameterized queries and audit-log requirements.
- **Schema-touching DDL** — covered by `bench` patches via
  `infrabeat-deploy`.
- **Cross-VM joins / reports** — this skill is per-VM; orchestration is
  the caller's job (or a future `infrabeat-promote` query layer).

## Five-Stop Flow honored

This skill is read-only. It runs the laptop CLI against an ERPNext VM and
returns data — it does NOT generate code, modify files, push to git,
or change ERPNext state. The Five-Stop Flow (PROMPT → VS CODE → DEV →
STAGING → PROD) does not apply because no code is produced. Every CLI
invocation is auto-recorded to `<cwd>/.audit/<YYYY-MM-DD>.jsonl` per
Phase 6C.3, providing forensic-grade observability for every query.
