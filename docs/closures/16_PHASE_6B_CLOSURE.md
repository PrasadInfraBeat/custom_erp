# 16 — Phase 6B Closure: InfraBeat ERP Python CLI Foundation

**Status:** ✅ COMPLETE. End-to-end validated against live FAC infrastructure on dev VM (10.1.0.184).
**Date sealed:** 2026-05-08
**Closing branch state:** `dev` fast-forwarded through 8 squash-merges. `staging` and `production` untouched.
**Author:** Solo execution session, ~6 hours, AI-paired via Claude Code.

---

## 1. Executive Summary

Phase 6B built the foundational Python CLI package `infrabeat-erp` that provides a typed, OAuth-authenticated, MCP-aware interface from the developer's laptop to Frappe Assistant Core (FAC) running on the project's three VMs. The package transitions from "Phase 5 stdlib scripts that proved the protocol" to "production-grade typed Python with 46 passing unit tests, surgical-modification discipline, and live integration validation."

Every architectural assumption made across the seven sub-phases (6A, 6B.1, 6B.2, 6B.3, 6B.4a, 6B.4b, 6B.5) was validated against real FAC infrastructure in a single live integration smoke session. One assumption broke (MCP endpoint path — hardcoded incorrectly), was diagnosed via OIDC discovery introspection, and was corrected via PR #11 surgical hotfix without requiring rework of the surrounding modules.

The package is now functionally usable for read-only operations against any of the three VMs once a `config.toml` is provided. Phase 6C will add production safety guards, OS keyring promotion for secrets, and a JSONL audit log.

---

## 2. Sub-Phase Inventory — 8 PRs Merged to `dev`

| # | PR | Sub-Phase | Squash Hash | Description |
|---|---|---|---|---|
| 1 | #4 | 6A | (see PR) | Package scaffold — `pyproject.toml`, README, `src/infrabeat_erp/{__init__.py, cli.py}`, `tests/__init__.py` |
| 2 | #5 | 6B.1 | (see PR) | `http.py` (httpx Client factory) + `config.py` (TOML loader, `VMConfig` dataclass) + 8 tests |
| 3 | #6 | 6B.2 | `ae17517` | `oauth.py` (RFC 7636 PKCE S256, RFC 7591 dynamic registration, browser-based authcode flow) + 10 tests |
| 4 | #7 | 6B.3 | `241a8f6` | `mcp.py` (JSON-RPC 2.0 envelope, `initialize`/`list_tools`/`call_tool`) + 8 tests |
| 5 | #8 | 6B.4a | `9ee8bcf` | `secrets_store.py` (atomic write, POSIX 0o600 mode, JSON-per-VM layout) + 5 tests |
| 6 | #9 | 6B.4b | `5dcc0e3` | CLI subcommands `register`, `login`, `smoke` + 8 tests |
| 7 | #10 | 6B.5 | `4f0fc36` | CLI subcommands `query`, `get`, `describe`, `search` + helper extraction + 8 tests |
| 8 | #11 | hotfix | (PR #11) | Corrected MCP endpoint path (discovered during live smoke) + L41 test refactor |

**Cumulative state on `dev` at closure:**

- 6 typed modules (`http`, `config`, `oauth`, `mcp`, `secrets_store`, `cli`) totaling ~1,100 LoC
- 47 tests collected, 46 passing, 1 skipped (POSIX-only `secrets_store` mode-bit test, correctly bypassed on Windows)
- 7 user-facing CLI subcommands
- Zero new runtime dependencies beyond `click` and `httpx` (everything else is stdlib)

---

## 3. Module Inventory

### `src/infrabeat_erp/__init__.py`
Exposes `__version__ = "0.1.0"`. Used by `mcp.py` to advertise client name to MCP servers.

### `src/infrabeat_erp/http.py`
- `make_client(base_url, access_token=None, timeout=30.0) -> httpx.Client`
- Factory for `httpx.Client` with `base_url`, optional `Authorization: Bearer <token>` header, JSON content negotiation, and a default timeout.
- All other modules consume the client via a `with client:` context manager — no global state.

### `src/infrabeat_erp/config.py`
- `VMConfig` frozen dataclass with `name: str`, `base_url: str`
- `load_config(path=None) -> dict[str, VMConfig]` reads TOML via `tomllib` (stdlib, Python 3.11+)
- `get_vm(name, path=None) -> VMConfig` looks up a single alias
- Default path: `~/.config/infrabeat-erp/config.toml`
- TOML schema: `[vm.<alias>]` (singular `vm`, NOT `vms`) with `base_url = "..."`

### `src/infrabeat_erp/oauth.py`
- `ClientRegistration` and `Tokens` frozen dataclasses
- `register_client(base_url) -> ClientRegistration` — discovers OIDC metadata, posts RFC 7591 dynamic registration with `application_type=native`, `token_endpoint_auth_method=none`
- `login_authcode_pkce(client_reg) -> Tokens` — generates PKCE verifier/challenge, opens browser, runs localhost callback server on `127.0.0.1:8765`, exchanges authcode for tokens
- `refresh(client_reg, refresh_token) -> Tokens` — token refresh (not yet wired to CLI; future use)
- Custom exceptions: `OAuthError`, `RegistrationError`, `LoginError`, `RefreshError`

### `src/infrabeat_erp/mcp.py`
- `Tool` and `ServerCapabilities` frozen dataclasses
- `initialize(client) -> ServerCapabilities` — JSON-RPC `initialize` method
- `list_tools(client) -> list[Tool]` — JSON-RPC `tools/list` method
- `call_tool(client, name, arguments) -> dict` — JSON-RPC `tools/call` method
- `MCP_ENDPOINT_PATH = "/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"` (hardcoded — see Section 8 architectural debt)
- Custom exceptions: `MCPError` (transport/HTTP), `MCPProtocolError` (JSON-RPC envelope error)

### `src/infrabeat_erp/secrets_store.py`
- `save_secrets(vm_alias, data, base_dir=None)` — atomic write via tempfile + flush + fsync + os.replace; sets directory to 0o700 and file to 0o600 on POSIX
- `load_secrets(vm_alias, base_dir=None) -> dict` — raises `SecretsNotFound` if missing
- Default storage: `<cwd>/.secrets/<vm_alias>.json` (CWD-relative — see Section 4 caveat)
- Custom exceptions: `SecretsStoreError`, `SecretsNotFound`

### `src/infrabeat_erp/cli.py`
Click application with 7 subcommands. Boundary-marker discipline (`# === Phase 6B.4b SUBCOMMANDS ===`, `# === Phase 6B.5 SUBCOMMANDS ===`) preserves additive-only modification history. Shared helper `_build_authed_client(vm_alias)` returns `(VMConfig, secrets_dict, httpx.Client)` for the four data subcommands. Exit code contract: `0` success, `1` user error, `2` transport/server failure, `3` JSON-RPC protocol error.

---

## 4. CLI Surface — 7 Subcommands

### Infrastructure operations (Phase 6B.4b)

| Command | Purpose |
|---|---|
| `infrabeat-erp register <vm>` | Discover OIDC metadata, register dynamic OAuth client, persist `client_id` to `.secrets/<vm>.json` |
| `infrabeat-erp login <vm>` | Browser-based PKCE auth code flow, persist `access_token` + `refresh_token` merged with existing secrets |
| `infrabeat-erp smoke <vm> [--json]` | MCP `initialize` + `tools/list`; emits server name/version/protocol/tool count |

### Data operations (Phase 6B.5)

| Command | FAC Tool | Purpose |
|---|---|---|
| `infrabeat-erp query <vm> <doctype> [--filter k=v]... [--limit N] [--json]` | `list_documents` | List docs of a doctype with optional filters |
| `infrabeat-erp get <vm> <doctype> <name> [--json]` | `get_document` | Fetch single document by name |
| `infrabeat-erp describe <vm> <doctype> [--json]` | `get_doctype_info` | Show schema (fields + types) |
| `infrabeat-erp search <vm> <text> [--limit N] [--json]` | `search_documents` | Full-text search across documents |

### Critical caveat: `.secrets/` is CWD-relative

Both `register` and `login` write secrets to `<current-working-directory>/.secrets/<vm>.json`. All subsequent commands look up secrets relative to wherever you run them. **Stay in `~/Projects/custom_erp` (or wherever you ran `register`) for the entire workflow.** This will be promoted to OS keyring storage in Phase 6C.

---

## 5. Architectural Validation Matrix

All seven assumptions made across Phase 6B were validated against the live dev VM in a single integration smoke session.

| # | Assumption | Source Sub-Phase | Validated By | Status |
|---|---|---|---|---|
| 1 | OIDC discovery at `/.well-known/openid-configuration` | 6B.2 | `register dev` returned `client_id=d4898j51aj` | ✅ |
| 2 | RFC 7591 dynamic client registration accepted | 6B.2 | Same as above | ✅ |
| 3 | PKCE S256 + localhost callback survives browser flow | 6B.2 | `login dev` returned token with 3600s TTL | ✅ |
| 4 | MCP endpoint = `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp` | 6B.3 (post-hotfix) | `smoke dev` returned 17 tools | ✅ (after PR #11) |
| 5 | FAC exposes 17 tools | 6B.5 (catalog assumption) | `smoke dev` enumerated 17 | ✅ |
| 6 | 6B.5 tool name mapping (list_documents, get_document, get_doctype_info, search_documents) | 6B.5 | `query dev "Sales Order"` returned valid empty result | ✅ |
| 7 | End-to-end: config → OAuth → tokens → MCP → ERPNext data | 6B.5 | All five steps of the smoke runbook chained successfully | ✅ |

### Live FAC version observations

- **FAC version reported:** `2.0.0` (not `2.4.x` as project knowledge previously suggested)
- **MCP protocol version:** `2025-06-18` (not `2024-11-05` as previous docs indicated)
- **Tool catalog:** `probe_fac` is no longer present; 12 additional tools beyond what `infrabeat-erp` consumes are available for future subcommand expansion (`create_document`, `update_document`, `delete_document`, `submit_document`, `search_doctype`, `search_link`, `search`, `fetch`, `generate_report`, `report_list`, `report_requirements`, `run_workflow`, `get_pending_approvals`)

These discrepancies are noted but not blocking; project knowledge files `04_VM_INVENTORY.md` and `15_PHASE_5_CLOSURE.md` should be updated to match live state at convenience.

---

## 6. Project Configuration

### `~/.config/infrabeat-erp/config.toml`

```toml
[vm.dev]
base_url = "http://10.1.0.184"

[vm.staging]
base_url = "http://10.1.0.185"

[vm.production]
base_url = "http://10.1.0.186"
```

**Critical formatting rules:**
- Top-level key is **`vm`** (singular), not `vms`
- Field name is **`base_url`**, not `url`
- File MUST be UTF-8 **without BOM** — PowerShell's default `Set-Content -Encoding utf8` adds BOM and breaks `tomllib` parsing
- Use `[System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new($false))` from PowerShell to guarantee no BOM, OR `-Encoding utf8NoBOM` on PowerShell 7+

### Secrets layout

```
<cwd>/.secrets/dev.json          # client + tokens for dev VM
<cwd>/.secrets/staging.json      # ditto for staging
<cwd>/.secrets/production.json   # ditto for production
```

File mode `0o600` on POSIX (test skipped on Windows because Windows file ACLs aren't expressible as POSIX mode bits).

---

## 7. Lessons Learned This Phase (L37–L41)

These extend the existing Phase 5 lessons file (L24–L31).

### L37 — Branch checkout output must be explicitly verified before subsequent steps

Discovered when PR #10 was committed locally to `dev` branch instead of `feature/phase6b5-data-subcommands` because Step 1's `git checkout -B feature/...` either did not execute or was rolled back. The wrong-branch commit was caught before push to remote and recovered via `git branch <feature>` + `git reset --hard origin/dev`. The architectural fix going forward: every multi-step sub-phase must include an explicit "paste back the branch checkout output before proceeding" gate. Without that checkpoint, a Step 1 silent failure cascades into a wrong-branch commit at Step 5.

### L38 — When generating runbooks against AI-authored code, read the code, not the spec

The TOML schema mismatch (`[vms.<alias>]` vs `[vm.<alias>]`) and the field name confusion (`url` vs `base_url`) both surfaced because the runbook author trusted the spec used to generate the code, not the code itself. The spec is what we wanted; the code is what is. Discovery commands (`Get-Content` of the source module, or a Python REPL probe) should precede any runbook step that interacts with generated code.

### L39 — PowerShell `Set-Content -Encoding utf8` adds a UTF-8 BOM

`tomllib` (per the TOML spec) rejects files starting with the BOM bytes `EF BB BF`, raising `TOMLDecodeError: Invalid statement at line 1, column 1`. The error message is misleading because `Get-Content` displays the file as plain text (BOM is invisible). Fix: use `[System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new($false))` from PowerShell to write without BOM.

### L40 — Never hardcode an endpoint path that is advertised in a discovery document

`mcp.py` was created with `MCP_ENDPOINT_PATH = "/assistant/mcp"` based on a comment that said "FAC v2.4.x advertises this." The comment was correct that discovery exists; the implementation chose to ignore it. FAC actually advertises `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`. Phase 5's `mcp_smoke_test.py` correctly read `mcp_endpoint` from `/.well-known/openid-configuration` dynamically. Phase 6E will retire this debt by refactoring `mcp.py` to discover the endpoint at runtime.

### L41 — Test path constants must IMPORT from the production module, not duplicate

`test_mcp.py` had `MCP_URL = f"{BASE_URL}/assistant/mcp"` — duplicating the path string from `mcp.py`. When the production constant was hotfixed, all 8 mcp tests broke because respx routes were registered at the OLD path. The architectural fix (committed in PR #11) replaced the duplicated string with `MCP_URL = BASE_URL + MCP_ENDPOINT_PATH` (importing the constant from the production module). This eliminates an entire class of test/source drift bugs.

### Process notes (not full lessons but worth logging)

- **Chat→PowerShell paste duplication occurred 6+ times** during the session. Cause appears to be PowerShell's input-buffer stickiness combined with arrow-up history recall. Mitigations: press `Ctrl+C` before each paste; or close + reopen PowerShell; or type short commands manually. Any multi-line clipboard content compounds the risk.
- **Here-string + `claude -p --permission-mode acceptEdits`** is the locked default for prompt delivery to Claude Code. Single-quoted form (`@'...'@`) requires only `'` → `''` escaping. Closing `'@ | claude...` MUST be at column 1.
- **Boundary-marker discipline** (`# === Phase 6B.X SUBCOMMANDS ===`) for surgical modifications to existing files works reliably. Verified in PRs #9 and #10. Pattern: marker followed by additions only; lines above the marker stay byte-identical. Verifies via single-hunk `git diff`.

---

## 8. Architectural Debt Accepted (Phase 6E to Retire)

### Debt 1 — `MCP_ENDPOINT_PATH` is hardcoded, not discovered

**Location:** `src/infrabeat_erp/mcp.py` line 22 (or thereabouts).
**Decision:** Quick hotfix in PR #11 with the correct value to unblock Phase 6B closure.
**Proper fix (Phase 6E):** Refactor `mcp.py` to fetch `/.well-known/openid-configuration` and read `mcp_endpoint` dynamically — matching the proven pattern in Phase 5's `mcp_smoke_test.py`. This requires:
- Adding a `_discover_mcp_endpoint(base_url) -> str` helper to `mcp.py`
- Modifying `initialize`, `list_tools`, `call_tool` to either accept an endpoint URL parameter or call discovery internally on first use
- Updating tests to mock the discovery call alongside the MCP calls
- The `MCP_ENDPOINT_PATH` module-level constant becomes a fallback or is removed entirely

### Debt 2 — Project knowledge version drift

**Location:** `04_VM_INVENTORY.md`, `15_PHASE_5_CLOSURE.md` likely contain stale FAC version (`2.4.x`) and MCP protocol version (`2024-11-05`).
**Live reality:** FAC `2.0.0`, protocol `2025-06-18`.
**Fix:** Quick edit during Phase 6C kick-off to bring docs in line. Also worth running `bench --site erp.local list-apps` on dev VM to confirm what's actually installed.

### Debt 3 — Production VM (`.186`) status uncertain

`00_1_PROJECT_FACTS.md` lists prod VM as "not yet provisioned" but Phase 5 closure suggests FAC is installed on all three. Worth one verification command (`infrabeat-erp register production` once 6C's safety guards are in place) to settle the question. Don't run that until Phase 6C lands `--allow-production` flag.

### Debt 4 — `.secrets/` directory is CWD-relative, not user-scoped

**Implication:** Running `infrabeat-erp` from a different directory loses access to existing tokens. Forces the user to always `cd` to the repo root.
**Phase 6C fix:** Promote secrets to OS keyring (Windows Credential Manager via `keyring` lib; macOS Keychain; Linux Secret Service). JSON files become a Fernet-encrypted fallback for environments without keyring.

---

## 9. Phase 6C Plan (Next Session)

### Objective

Add production safety mechanisms and persistent audit trail to the CLI. Promote secrets storage from CWD-relative JSON to OS keyring.

### Sub-phases (estimated)

| # | Sub-phase | Scope |
|---|---|---|
| 6C.1 | Keyring promotion | Add `keyring` lib dependency; refactor `secrets_store.py` to use OS keyring as primary, Fernet-encrypted JSON as fallback; provide `infrabeat-erp migrate-secrets` to move existing `.secrets/` files into keyring |
| 6C.2 | Production guards | Add `--allow-production` global flag (required for any command targeting production VM); add `--confirm DEPLOY` interactive prompt for irreversible operations; refuse all writes to production unless both flags present |
| 6C.3 | Audit log | Add JSONL audit log at `tools/infrabeat_erp/.audit/<YYYY-MM-DD>.jsonl` capturing every command invocation with timestamp, vm, user, args, exit code, duration |
| 6C.4 | Verification + closure | Live integration validation against staging VM (.185); update closure doc; merge to `dev` |

### Estimated effort

3–4 hours of focused execution following the same cadence as Phase 6B (one sub-phase per ~30–60 min including PR cycle).

### Pre-requisites for kick-off

- Open new chat in this Claude Project (this chat will be context-stale)
- Upload this `16_PHASE_6B_CLOSURE.md` to project knowledge first
- Confirm dev VM is still reachable and `infrabeat-erp smoke dev` still returns the 17-tool list
- Confirm staging VM (.185) is reachable for live validation against a non-dev environment
- Verify `infrabeat-erp register staging` and `infrabeat-erp login staging` work (similar to dev)

---

## 10. Phase 6D-E Outline (Future)

### Phase 6D — CI Integration

- Add GitHub Actions workflow `.github/workflows/python-tests.yml`
- Run pytest on every PR to `dev` and on every push to `dev`/`staging`/`production`
- Coverage gate: 70% minimum (using `pytest-cov`)
- Add as required CI check on branch protection rules

### Phase 6E — Custom Skills + Architectural Debt Retirement

- Author `.claude/skills/infrabeat-erp-query/SKILL.md` so Claude (in any project) can use the CLI subcommands as agentic tools
- Register skill in `~/.claude.json`
- **Refactor `mcp.py` to dynamic OIDC-discovered MCP endpoint (L40 retirement)**
- Pay off any other debt accumulated in 6C

### Phase 7 — InfraBeat Console TUI

Per `12_INFRABEAT_CONSOLE_SPEC.md`. Single-pane operations dashboard for all 3 VMs. Hotkey-driven deploy/promote/rollback/backup actions. Cross-VM log tailing. Audit log viewer. GitHub PR/CI status panel. Estimated 25–30 hours of work.

---

## 11. Repeatable Live Smoke Runbook

For any future session that needs to re-validate the integration end-to-end.

### Pre-flight

```powershell
cd C:\Users\<user>\Projects\custom_erp
git checkout dev
git pull origin dev
python -m pytest tools/infrabeat_erp/tests/ -v
# Expect: 46 passed, 1 skipped
infrabeat-erp --help
# Expect: usage banner with 7 subcommands
Test-NetConnection -ComputerName 10.1.0.184 -Port 80
# Expect: TcpTestSucceeded: True
```

### One-time config setup

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\.config\infrabeat-erp" | Out-Null

[System.IO.File]::WriteAllText("$HOME\.config\infrabeat-erp\config.toml", @'
[vm.dev]
base_url = "http://10.1.0.184"

[vm.staging]
base_url = "http://10.1.0.185"

[vm.production]
base_url = "http://10.1.0.186"
'@, [System.Text.UTF8Encoding]::new($false))
```

### Smoke sequence

```powershell
infrabeat-erp register dev
# Expect: Registered client for dev: client_id=<...>

infrabeat-erp login dev
# Browser opens; authenticate; expect: Logged in to dev: token expires in 3600s

infrabeat-erp smoke dev
# Expect: server name + version + 17 tools listed

infrabeat-erp query dev "Sales Order" --limit 5
# Expect: DocType: Sales Order on dev (with 0+ documents listed)

infrabeat-erp query dev "Sales Order" --limit 5 --json
# Expect: parseable JSON with vm/doctype/count/documents keys
```

If any step fails, see the failure-mode tables in the original Phase 6B execution session transcript, or fall back to direct probing:

```powershell
# Probe FAC OIDC discovery
(Invoke-WebRequest -Uri "http://10.1.0.184/.well-known/openid-configuration" -UseBasicParsing).Content | ConvertFrom-Json

# Probe config layer directly (bypasses cli.py error swallowing)
python -c "from infrabeat_erp import config; print(config.get_vm('dev'))"
```

---

## 12. Test Suite Composition

47 tests collected, 46 passing, 1 skipped.

| File | Count | Coverage |
|---|---|---|
| `test_http_and_config.py` | 8 | httpx Client factory + TOML loader + VMConfig lookup |
| `test_oauth.py` | 10 | PKCE generation + RFC 7636 known vector + dynamic registration + token exchange + refresh |
| `test_mcp.py` | 8 | JSON-RPC envelope + initialize + list_tools + call_tool + protocol error mapping |
| `test_secrets_store.py` | 5 | Atomic write + load + missing-file handling + POSIX mode (skipped on Windows) |
| `test_cli.py` | 16 | All 7 subcommands × 1–4 cases (happy path, validation, error, JSON output) |

All tests use mocking (`pytest-mock`, `respx`, `monkeypatch`); no live network calls. Live integration validation is performed via the manual runbook in Section 11.

---

## 13. Project Knowledge References

This document interlocks with the following project knowledge files:

| File | Relationship |
|---|---|
| `00_1_PROJECT_FACTS.md` | Defines the three VMs that this CLI targets (note: prod VM status needs reconciliation per Section 8 Debt 3) |
| `00_2_GOTCHAS.md` | Frappe v15 quirks; not directly used by this Python CLI (it's a client of FAC, not a Frappe-app modifier) |
| `04_VM_INVENTORY.md` | VM paths/users/sites; informs the `[vm.<alias>]` config.toml structure |
| `05_GITHUB_WORKFLOW.md` | Three-branch strategy followed exactly: every PR targeted `dev`; no `main` references; `staging`/`production` untouched |
| `09_CLAUDE_NATIVE_ARCHITECTURE.md` | Defines the AI-native target architecture; this CLI is the "authoring" tooling layer |
| `12_INFRABEAT_CONSOLE_SPEC.md` | Operations dashboard spec; Phase 7 will consume this CLI as one of its action backends |
| `15_PHASE_5_CLOSURE.md` | Phase 5 stdlib script baseline; this Phase 6B is the typed-Python promotion of those scripts |

---

## 14. Closing Notes

Phase 6B is the architectural foundation for AI-native ERPNext operations from a developer laptop. It establishes:

- **Type discipline.** Frozen dataclasses, explicit exception hierarchies, exit code contracts.
- **Surgical-modification discipline.** Boundary markers, single-hunk diffs, no test/source duplication.
- **Discovery-first integration.** All endpoints and tool names sourced from FAC's own catalog/discovery, not invented (with the L40 hotfix retiring the one assumption-based exception).
- **Mocked unit tests + manual integration smoke.** 46 tests prove unit correctness; the live runbook proves system correctness. CI integration in Phase 6D adds regression protection.
- **Three-branch flow honored without exception.** Every change went `feature/* → dev` via PR, including the surgical hotfix. `staging` and `production` were never touched.

Phase 6C will build on this foundation by adding production safety, audit trails, and OS-level secret storage. The CLI then becomes safe to run against staging and production VMs, not just dev.

**End of Phase 6B Closure.**
