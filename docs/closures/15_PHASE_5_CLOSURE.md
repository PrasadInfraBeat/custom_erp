# PHASE_5_CLOSURE — OAuth + MCP Integration with FAC v2.4.1

**Status:** COMPLETE
**Branch:** `dev` at `2f5432e`
**Date closed:** 2026-05-06
**Commit range:** `634fc50..2f5432e` (2 commits: `e872eaa`, `2f5432e`)

## 1. Mission and outcome

**Mission:** Build the foundation for InfraBeat to Frappe Assistant Core (FAC) integration. Laptop-driven, OAuth-authenticated MCP transport into ERPNext, across the dev / staging / production fleet.

**Outcome:** Mission met + one stretch goal achieved.

| Goal | Status |
|---|---|
| OAuth + MCP stack proven on at least one VM | done. Dev (10.1.0.184), 17 tools enumerated. |
| Triplicate to staging | done. 17 tools, identical to dev. |
| Triplicate to production | done. 17 tools, identical to dev. |
| Document the architecture for Phase 6 | done. This doc. |

## 2. The proven stack

```
Laptop (Win11, PowerShell, Python 3.12 stdlib only)
    |
    |  HTTP (OAuth Bearer for MCP, anonymous for registration)
    v
FAC v2.4.1 on Frappe v15 (each of 3 VMs)
    |
    +-- OIDC: /.well-known/openid-configuration
    +-- RFC 8414: /.well-known/oauth-authorization-server
    +-- RFC 7591: ...oauth_registration.register_client
    +-- OAuth: frappe.integrations.oauth2.{authorize,get_token}
    +-- MCP 2025-06-18 (StreamableHTTP): ...fac_endpoint.handle_mcp
```

Auth: OAuth 2.1 Authorization Code + PKCE (S256), public client (`token_endpoint_auth_method=none`).

Transport: MCP 2025-06-18 over StreamableHTTP, sync request/response (no SSE — FAC declares `streaming=false`).

## 3. Architecture decisions (D1 to D5)

| ID | Decision | Rationale |
|---|---|---|
| D1 | Hybrid: Python CLI engine + thin Skill wrapper | bash on Windows + dash on Ubuntu + PowerShell quoting is the wrong substrate for OAuth + token cache. Python CLI is portable, testable, and reusable from InfraBeat Console. |
| D2 | Code lives at `tools/infrabeat_erp/` inside `custom_erp` repo | Co-locates integration tooling with the ERPNext customization it integrates with. Single source of truth. |
| D3 | OAuth = AuthCode + PKCE (S256), public client | RFC-compliant, no client_secret at runtime. Frappe v15 honors `token_endpoint_auth_method=none` correctly (proven empirically). |
| D4 | Token storage: per-VM JSON in `.secrets/` (gitignored) for Phase 5; OS keyring deferred to Phase 6 | Keeps Phase 5 minimal-deps (stdlib only). Keyring complexity justified once the full CLI ships. |
| D5 | Sequence: discovery probe before OAuth Client registration | OIDC's `registration_endpoint` field reveals the RFC 7591 path. Eliminates manual Frappe Desk clicking. Idempotent and reproducible across VMs. |

## 4. Scripts delivered

All at `tools/infrabeat_erp/scripts/`, pure stdlib (no third-party deps).

| Script | Bytes | Purpose |
|---|---|---|
| `probe_fac.py` | 8038 | Probes 12 OAuth/OIDC/MCP endpoints + cookie login. Saves response shape to `docs/phase5/fac_v2.4.1_<vm>_probe.json`. |
| `register_client.py` | 8038 | RFC 7591 dynamic OAuth Client registration. Auto-falls-back to authenticated registration on 401/403. Saves to `tools/infrabeat_erp/.secrets/<vm>_client.json`. |
| `oauth_login.py` | 12439 | AuthCode + PKCE (S256) flow. Localhost callback server on `127.0.0.1:8765`. Saves to `tools/infrabeat_erp/.secrets/<vm>_tokens.json`. |
| `mcp_smoke_test.py` | 9006 | MCP JSON-RPC sequence: initialize -> notifications/initialized -> tools/list. Saves catalog to `docs/phase5/fac_<vm>_tool_catalog.json`. |

All scripts share `--vm` and `--base-url` flags. **No code changes are needed to retarget across the fleet** — only flag values change.

## 5. Per-VM proof matrix

| VM | IP | OAuth client_id | Tokens captured | MCP tools |
|---|---|---|---|---|
| dev | 10.1.0.184 | `k460ubk7bm` | yes | 17 |
| staging | 10.1.0.185 | `9ils4aefmq` | yes | 17 |
| production | 10.1.0.186 | `cvokq5ltrb` | yes | 17 |

Three independent OAuth Clients, three independent token sets, identical MCP tool surface.

## 6. FAC tool catalog (17 tools in 5 capability groups)

Identical across all 3 VMs. These will become the surface area of the `infrabeat-erp` CLI subcommands in Phase 6.

**Document CRUD (6):**
`create_document`, `get_document`, `update_document`, `list_documents`, `delete_document`, `submit_document`

**Search (5):**
`search_documents` (global), `search_doctype` (scoped), `search_link` (link picker), `search` (**OpenAI Vector Store semantic search**), `fetch`

**Metadata (1):**
`get_doctype_info`

**Reports (3):**
`report_list`, `report_requirements`, `generate_report`

**Workflow (2):**
`run_workflow`, `get_pending_approvals`

**Notable absence:** No raw SQL tool. FAC v2.4.1 does not expose `execute_sql` or similar. Architecturally cleaner — structured tools only, no SQL injection vector. Production safety surface is correspondingly simpler.

## 7. Architectural findings

### F1: FAC source provenance is non-functional

FAC v2.4.1 across the fleet came from two different sources:

- `clinu/mirror` on dev and production
- `buildswithpaul/upstream` on staging

Phase 5 proved both are **functionally identical** at every observable layer: RFC 7591 registration, PKCE token exchange, MCP handshake, tool catalog. Implication: the source-consistency concern flagged in earlier phases (kickoff TODO F1) is non-blocking for OAuth + MCP integration. Re-installing dev/prod from upstream remains desirable for hygiene, but is no longer urgent.

### F2: Frappe v15 correctly honors `token_endpoint_auth_method=none`

PKCE-only token exchange returns HTTP 200 across all 3 VMs. No client_secret is needed at runtime. Frappe v15 nonetheless **always** issues a `client_secret` field at registration time, even for public clients (vestigial, harmless, ignored at runtime).

Implication: the future `infrabeat-erp` CLI does NOT need to manage client secrets. PKCE is the only secret material. Token caching is correspondingly simpler.

### F3: FAC declares streaming=false in capabilities

FAC v2.4.1's MCP capabilities advertise `tools=true, prompts=false, resources=false, streaming=false`. Sync request/response, no SSE event streams. The smoke test handles SSE defensively but did not encounter it in practice.

Implication: the Phase 6 CLI's MCP client can use plain `httpx.Client` (sync) for all tool calls. No SSE state machine, no async streaming complexity, no progress-event handling.

### F4: Built-in OpenAI vector search

The `search` tool (distinct from `search_documents`) wraps an OpenAI vector store. The CLI gets semantic search "for free" — without us building any embedding infrastructure.

Implication: Phase 6 CLI's `search` subcommand should expose both `--keyword` (using `search_documents`) and `--semantic` (using `search`) modes.

## 8. Lessons learned (L24 to L31)

Continuing the project's running lessons-learned log:

| ID | Lesson |
|---|---|
| L24 | Chat link auto-formatter mangles dot-md and dot-py path strings into fake markdown links — in BOTH directions (chat output and pastes back). Workaround: use code fences for path discussion, or use string concatenation like `"name" + ".md"` in commands so `.md` never appears adjacent to the name in the source. |
| L25 | PowerShell `[IO.File]::WriteAllBytes` + `[Convert]::FromBase64String` is reliable for SMALL files (< ~5KB), but PowerShell terminal silently fails or corrupts for very long single-line commands (> ~10K chars). For larger files, use VS Code paste of source content directly, or chunk the base64 across multiple `$b += "..."` lines. |
| L26 | Frappe v15's OAuth Client schema unconditionally generates `client_secret` even for `token_endpoint_auth_method=none` clients. Vestigial secret is fine, ignored at runtime. |
| L27 | Frappe's `authorize` endpoint returns HTTP 500 with `KeyError: 'redirect_uri'` for missing-param requests instead of 400. Cosmetic quirk, not a blocker. |
| L28 | FAC's `mcp_discovery` endpoint at `/api/method/frappe_assistant_core.api.oauth_discovery.mcp_discovery` is the canonical "where is MCP" lookup. URL guessing wastes time. |
| L29 | PowerShell here-string + ssh + dash + backslash-pipe risk (per L23 precedent) — base64 single-line approach sidesteps entirely (when within line-length limits). |
| L30 | When file content transit through chat fails repeatedly, pivot to defensive script implementation based on standards (RFC 7591 in this case) and let live response drive iteration. |
| L31 | Closure doc numbering convention: sequential per phase. Phase 3 = `13_`, Phase 4 = `14_`, Phase 5 = `15_`. Filename uses `# UPPERCASE_NAME — Subtitle` H1 style matching `10_STAGE_1A_CLOSURE.md` and `11_DEV_VM_CLOSURE.md`. |

## 9. What is deferred to Phase 6

| Item | Description |
|---|---|
| Full `infrabeat-erp` Python package | `src/` layout, `pyproject.toml`, click-based CLI, proper module structure. Wraps the 4 stdlib scripts as cohesive subcommands. |
| OS keyring integration | Replace `tools/infrabeat_erp/.secrets/*.json` with `keyring` lib (Windows Credential Manager / macOS Keychain / Linux libsecret). Fernet-encrypted JSON fallback for systems without keyring. |
| Production safety guards | `--allow-production` flag, `--confirm DEPLOY` for mutating tools, distinct exit codes for read vs write operations. |
| pytest test suite | Smoke matrix per VM, mocked MCP responses, regression coverage on the 4 scripts. |
| Audit log | Every CLI invocation logged to `tools/infrabeat_erp/.audit/<date>.jsonl` with VM, tool, args (redacted), result, timestamp. |
| `infrabeat-erp-query` Claude Code skill | Thin `SKILL.md` at `.claude/skills/infrabeat-erp-query/` describing the CLI's tools to Claude Code. |
| Skill registration | Register skill in `~/.claude.json` so Claude Code can route ERPNext queries to the CLI. |
| Token refresh logic | Auto-refresh access_token when expired (using captured refresh_token). Currently scripts assume fresh tokens. |
| Cosmetic fix | `mcp_smoke_test.py`'s closure print line hardcodes "dev" instead of using the `--vm` arg. Trivial 1-line fix. |

## 10. Stale facts to update

The system prompt's `00_1_PROJECT_FACTS.md` claims `Prod (.186 not yet provisioned)`. **This is stale.** Phase 5 confirmed:

- Production VM 10.1.0.186 is reachable from the laptop
- FAC v2.4.1 is installed and operational
- OAuth registration accepts anonymous requests (HTTP 201)
- MCP `tools/list` returns 17 tools

**Action:** update `00_1_PROJECT_FACTS.md` to reflect that production is provisioned and operational.

## 11. Carryover TODOs from kickoff (status as of Phase 5 closure)

| ID | Description | Status |
|---|---|---|
| T1 | `infrabeat-deploy` skill template sudo block needs rework | Pending — Phase 6 |
| T2 | Migrate `infrabeat-smoke-test` to cookie auth | **Resolved.** Cookie auth verified working in probe; Bearer also works for FAC tools. Future skill implementations can use either. |
| T3 | Audit hooks env var capture untested | Pending — Phase 6 (covered by audit log work) |
| D1 | Vendor Invoice DocType lost during cleanup PR; restore from feature branch | Pending — DocType track |
| D2 | Ping Check needs rebase from `feature/phase-3-test-doctype` onto new dev tip | Pending — DocType track |
| D3 | Customer Feedback has only stub controller | Pending — DocType track |
| F1 | Re-install FAC on dev/prod from buildswithpaul upstream for source consistency | **Lower priority.** Phase 5 finding F1 proves divergence is non-functional. |
| H1 | Production hardening (SSL/TLS, ufw, backups, monitoring) | Pending — Phase 6 |
| A1 | Convert bash provisioning to Ansible | Pending — Phase 6 |

## 12. Standards referenced

- **RFC 7591** — OAuth 2.0 Dynamic Client Registration Protocol
- **RFC 7636** — Proof Key for Code Exchange (PKCE) for OAuth Public Clients
- **RFC 8252** — OAuth 2.0 for Native Apps
- **RFC 8414** — OAuth 2.0 Authorization Server Metadata
- **OpenID Connect Discovery 1.0** — `.well-known/openid-configuration`
- **MCP 2025-06-18** — Model Context Protocol specification

## 13. Reproducing Phase 5 from a fresh laptop

```powershell
# 1. Clone repo on dev branch
git clone https://github.com/PrasadInfraBeat/custom_erp.git
cd custom_erp
git checkout dev

# 2. For each VM, run the 3-step flow
foreach ($vm in @(
    @{ name = 'dev';        url = 'http://10.1.0.184' },
    @{ name = 'staging';    url = 'http://10.1.0.185' },
    @{ name = 'production'; url = 'http://10.1.0.186' }
)) {
    python tools\infrabeat_erp\scripts\register_client.py --vm $vm.name --base-url $vm.url
    python tools\infrabeat_erp\scripts\oauth_login.py     --vm $vm.name --base-url $vm.url
    python tools\infrabeat_erp\scripts\mcp_smoke_test.py  --vm $vm.name --base-url $vm.url
}
```

Roughly 5 minutes per VM, mostly browser interaction during OAuth consent.

## 14. Sign-off

**Functional state:** OAuth + MCP proven end-to-end across all 3 VMs.

**Repo state:** dev branch at `2f5432e`. Two clean commits (`e872eaa` + `2f5432e`) capture the work.

**Artifacts produced:**
- 4 Python scripts at `tools/infrabeat_erp/scripts/`
- 3 tool catalog JSONs at `docs/phase5/fac_<vm>_tool_catalog.json`
- 1 probe artifact at `docs/phase5/fac_v2.4.1_dev_probe.json`
- 6 per-VM credential files at `tools/infrabeat_erp/.secrets/` (gitignored)
- This closure doc

**Next phase:** Phase 6 — wrap the proven scripts into a polished `infrabeat-erp` Python package, integrate with Claude Code via skill, add production safety guards, OS keyring storage, audit log.

---

*Phase 5 closed 2026-05-06.*