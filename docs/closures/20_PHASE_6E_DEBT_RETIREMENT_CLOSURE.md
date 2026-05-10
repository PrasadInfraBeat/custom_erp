# 20 — Phase 6E.4+ Closure: Debt Retirement Track

**Status:** ✅ SEALED (debt retirement track; Phase 6E now FULLY closed end-to-end).
**Date sealed:** 2026-05-10
**Closing branch state:** `dev` advanced through 6 squash-merges (PRs #24, #25, #26, #27, #28, #29) plus this docs PR. Tip prior to docs PR: `0398e50`. `staging` and `production` untouched.
**Author:** Solo execution session, ~3 hours, AI-paired via Claude Code (`-p` mode + interactive).

---

## 1. Executive Summary

Phase 6E.4+ is the debt-retirement companion to the Phase 6E enforcement track sealed in `19_PHASE_6E_CLOSURE.md`. Where the enforcement track flipped CI from advisory to platform-blocking, this track retired seven architectural debt items that had accumulated through Phases 5 → 6D and were intentionally deferred from the enforcement work: L40 (hardcoded MCP endpoint), L49 (PR template stale `main` reference + ERPNext-only Testing Done checkboxes), L50 (CWD-relative `.audit/` polluting test runs), master-key namespace conflation with OAuth tokens, missing access-token auto-refresh on 401, missing custom Claude Code skill for ERPNext data routing, and incomplete `gh` CLI device-flow auth. Six PRs landed (#24–#29) plus one operational change (gh auth, no PR), all under the Phase 6E.3 ruleset enforcing 6 required status checks.

Three new lessons emerged, all about Claude Code `-p` mode mechanics rather than ERPNext or Frappe: L66 (`claude -p` is one-shot, no persistent session, multi-stop workflows must bake all decisions into self-contained prompts), L67 (`git add .` sweeps `.git_commit_msg.tmp` temp files; always use `git add <specific-paths>` in Claude Code prompts), and L68 (`claude -p --permission-mode bypassPermissions` does NOT bypass git commit/push permissions — output a `COMMIT_AND_PUSH` single-line PowerShell command for manual finalization). These three lessons together define a reusable "Claude Code -p prompt contract" that subsequent debt-retirement and Phase 7 PRs will follow.

Pytest baseline grew monotonically across the track: 70 → 72 (+2 from L40 discovery + fallback tests) → 72 (L49 template-only, L50 monkeypatch redirect) → 73 (+1 from master-key migration test) → 75 (+2 from auto-refresh success/failure tests) → 75 (skill is documentation, no test impact). No test was removed. All 6 PRs were squash-merged; each landed with all 6 required status checks green per the Phase 6E.3 ruleset. With the debt-retirement track closed, Phase 6E is now FULLY sealed across both tracks, and Phase 7 (InfraBeat Console TUI per `12_INFRABEAT_CONSOLE_SPEC.md`) becomes the next major scope.

---

## 2. Sub-Phase Inventory

| # | Sub-Phase | PR / Type | SHA | Description |
|---|---|---|---|---|
| 1 | 6E.4 — L40 closure | PR #24 | `14bc302` | `mcp.py` consumes `mcp_endpoint` from runtime OIDC discovery; hardcoded `MCP_ENDPOINT_PATH` retained as fallback with `DeprecationWarning` for old FAC versions. `_discover` → public `discover_oidc_metadata` with module-level `_discovery_cache`. Tests 70 → 72. |
| 2 | 6E.5 — L49 closure | PR #25 | `193b43d` | `.github/pull_request_template.md` rewritten to fit any PR type (8 Type-of-Change checkboxes; universal Testing Done items with N/A footnotes; stale `main` reference removed; explicit "no `main` branch exists" assertion). Pure template change, no source/test/CI workflow modified. |
| 3 | 6E.6 — L50 closure | PR #26 | `4c81bc7` | `audit.py` refactored to write to `~/.local/share/infrabeat-erp/audit/` (Linux/macOS) or `%APPDATA%/infrabeat-erp/audit/` (Windows) instead of `<cwd>/.audit/`. Test fixture autouse-monkeypatches `_get_audit_dir()` to `tmp_path`, eliminating repo-root pollution. `.gitignore` `.audit/` entries removed (no longer needed). |
| 4 | 6E.7 — gh device-flow auth | Operational (no PR) | n/a | `gh auth login` completed via browser device-flow on laptop. `gh pr create` no longer needs `Start-Process` browser fallback; `gh api repos/.../rulesets` available for future ruleset automation. Token persisted in OS keychain by `gh` itself. |
| 5 | 6E.8 — Master key separation | PR #27 | `909f4d5` | `secrets_store.py` master-key resolution promoted to dedicated keyring service `infrabeat-erp-master/master`. 5-step backward-compatible chain: env var → new keyring → old keyring auto-migrate → `~/.config/infrabeat-erp/master.key` file → generate fresh. Old keyring entry NOT deleted on auto-migrate (rollback safety). Tests 72 → 73. |
| 6 | 6E.9 — Token auto-refresh | PR #28 | `1a16671` | `cli.py` adds `TokenRefreshAuth(httpx.Auth)`: on 401, calls `oauth.refresh` with stored `ClientRegistration` + `refresh_token`, persists new bundle via `secrets_store.save_secrets`, replays original request with new bearer. One-shot per client lifetime. `RefreshError` re-raised as `TokenRefreshFailed` with explicit `infrabeat-erp login <vm>` hint. `mcp.py` unchanged — refresh is transparent at HTTP layer. Tests 73 → 75. |
| 7 | 6E.10 — Claude Code skill | PR #29 | `0398e50` | `.claude/skills/infrabeat-erp-query/SKILL.md` registers a custom Claude Code skill teaching Claude WHEN to invoke the `infrabeat-erp` CLI for ERPNext data questions and HOW to format calls (`smoke / query / get / describe / search`) with VM aliases, `--allow-production` gate, `--json` discipline, and Phase 6E.9 auto-refresh failure handling. Read-only by construction. |
| 8 | This PR | Docs | TBD | Phase 6E.4+ closure documentation: this file + change-log row updates in `00_1_PROJECT_FACTS.md` and `04_VM_INVENTORY.md`. |

---

## 3. File Inventory (Aggregate)

### PR #24 (6E.4 / L40) — `14bc302`
- `tools/infrabeat_erp/src/infrabeat_erp/mcp.py` — modified (+46/-10 around endpoint resolution; new `_resolve_mcp_endpoint(client)` helper)
- `tools/infrabeat_erp/src/infrabeat_erp/oauth.py` — modified (+39 around discovery API rename + cache + `DiscoveryError`)
- `tools/infrabeat_erp/tests/test_mcp.py` — modified (+69; new `_mock_discovery()` helper, autouse cache-clear fixture, 2 new tests)
- `tools/infrabeat_erp/tests/test_oauth.py` — modified (+8; same autouse cache-clear fixture)

### PR #25 (6E.5 / L49) — `193b43d`
- `.github/pull_request_template.md` — modified (+25/-19; net rewrite around universal-fit Type-of-Change + Testing Done sections)

### PR #26 (6E.6 / L50) — `4c81bc7`
- `tools/infrabeat_erp/src/infrabeat_erp/audit.py` — modified (+22/-14; new `_get_audit_dir()` helper using platform-appropriate user-home path)
- `tools/infrabeat_erp/tests/test_audit.py` — modified (+28/-13; autouse monkeypatch fixture redirects `_get_audit_dir()` to `tmp_path`)
- `.gitignore` — modified (-3; removed `.audit/` entries — no longer needed once writes leave repo CWD)

### PR #27 (6E.8) — `909f4d5`
- `tools/infrabeat_erp/src/infrabeat_erp/secrets_store.py` — modified (+57/-8; 5-step master-key resolution chain with auto-migration from old keyring service; old entry preserved for rollback safety)
- `tools/infrabeat_erp/tests/test_secrets_store.py` — modified (+42; new `test_master_key_migrates_from_legacy_service` covering auto-promote + no-delete invariant)

### PR #28 (6E.9) — `1a16671`
- `tools/infrabeat_erp/src/infrabeat_erp/cli.py` — modified (+103/-1; new `TokenRefreshAuth(httpx.Auth)` + `TokenRefreshFailed` exception; `_build_authed_client` now attaches the auth and stops setting `Authorization` at the client-header level)
- `tools/infrabeat_erp/tests/test_mcp.py` — modified (+132/-1; two new tests `test_token_autorefresh_on_401` and `test_token_autorefresh_fails_on_expired_refresh_token`)

### PR #29 (6E.10) — `0398e50`
- `.claude/skills/infrabeat-erp-query/SKILL.md` — new (+196; six worked examples; routing decision tree; auto-refresh failure-handling note tying back to PR #28)
- `docs/00_1_PROJECT_FACTS.md` — modified (+1; change-log row for skill registration)

### This closure PR
- `docs/closures/20_PHASE_6E_DEBT_RETIREMENT_CLOSURE.md` — new (this file)
- `docs/00_1_PROJECT_FACTS.md` — modified (one change-log row + Phase status flag flip from "in progress" to "FULLY SEALED")
- `docs/04_VM_INVENTORY.md` — modified (one change-log row noting VMs unchanged + new keyring service `infrabeat-erp-master` on laptop)

---

## 4. Architectural Validation Matrix

| # | Assumption / Outcome | Validated By | Status |
|---|---|---|---|
| 1 | L40 closed: MCP endpoint discovered dynamically; old FAC versions still work | PR #24 tests `test_mcp_endpoint_discovered_dynamically` (uses non-default path) and `test_mcp_endpoint_discovery_fallback_warns` (no `mcp_endpoint` key, falls back to constant + `DeprecationWarning`) both pass | ✅ |
| 2 | L49 closed: PR template fits ERPNext, CI/infra, refactor, docs, security PRs uniformly | PRs #26, #27, #28, #29 all rendered the same template cleanly with appropriate boxes ticked; no per-PR template hacks needed | ✅ |
| 3 | L50 closed: audit dir lives in user-home; tests no longer pollute repo root | PR #26 — autouse monkeypatch fixture redirects to `tmp_path`; post-merge test runs leave no `.audit/` dir under repo root | ✅ |
| 4 | Master-key auto-migration on first read from new service | PR #27 — `test_master_key_migrates_from_legacy_service` confirms (a) old service value promoted to new service, (b) old service entry NOT deleted (rollback safety net) | ✅ |
| 5 | Token auto-refresh transparently handles expired access_token | PR #28 — `test_token_autorefresh_on_401` confirms 401 → refresh → new-bearer-replay → 200 path; `save_secrets` called exactly once with new bundle | ✅ |
| 6 | Refresh-token failure surfaces explicit re-login guidance | PR #28 — `test_token_autorefresh_fails_on_expired_refresh_token` confirms `TokenRefreshFailed` carries `infrabeat-erp login <vm>` hint and no `save_secrets` call occurs | ✅ |
| 7 | Custom skill discoverable in Claude Code's available-skills list | Live verification: skill `infrabeat-erp-query` appeared in `<available-skills>` block on session restart after PR #29 merge | ✅ |
| 8 | Pytest baseline preserved monotonically (70 → 72 → 72 → 73 → 75 → 75); zero regressions | `python -m pytest tools/infrabeat_erp/tests/ -q` after each PR — final state: **75 passed, 1 skipped** | ✅ |
| 9 | All 6 PRs squash-merged under Phase 6E.3 ruleset (6 required checks each) | GitHub PR pages #24–#29 all show 6/6 checks green and squash-merge commit on `dev` | ✅ |
| 10 | Zero plaintext credentials introduced in any PR | `git grep` for legacy-admin-password and legacy-SSH-password patterns across all 6 PR diffs returns empty | ✅ |
| 11 | `gh` CLI authenticated; `gh pr create` works without browser fallback | `gh auth status` shows logged in; `gh pr list` returns repo PRs without prompt | ✅ |

---

## 5. Lessons Learned (L66+)

### L66 — `claude -p` is one-shot mode; multi-stop workflows must self-contain decisions

`claude -p "<prompt>"` (Claude Code's headless / pipe mode) is fundamentally different from interactive Claude Code: it spawns a fresh agent per invocation, with no persistent session, no continuation across stops, and no memory of prior turns. Multi-stop workflows (recon → confirm → implement → commit) cannot be done as 4 separate `claude -p` calls without losing context between calls.

**Symptom seen during PR #24 drafting:** an early attempt split work into a recon `claude -p` ("look at `mcp.py` and `oauth.py`, tell me where the hardcoded path lives") followed by an implementation `claude -p` ("now refactor it"). The implementation call had no memory of the recon findings and re-derived its own (correct, but redundant) understanding from scratch — wasting tokens and risking divergence between the two calls' mental models.

**Mitigation:** for any non-trivial debt-retirement task driven via `claude -p`, write a single self-contained prompt that bakes ALL architectural decisions in upfront — file paths, function signatures, test names, validation steps, output format. Treat the prompt as the spec, not as a conversation seed. PRs #24, #26, #27, #28 all used this pattern: each had a single `claude -p` invocation with a ~150-line prompt covering recon-derived facts (typed by the operator after a separate read-only recon turn), the exact refactor, the exact tests to add/modify, and a `COMMIT_AND_PUSH` line for the operator to run after VS Code review. **Rule of thumb:** if you cannot fit the entire task definition into one prompt, you are not ready to invoke `claude -p` yet — do the recon first, in interactive mode.

### L67 — `git add .` sweeps `.git_commit_msg.tmp` temp files

When Claude Code generates commits via templated prompts, it sometimes writes a `.git_commit_msg.tmp` (or similar) scratch file in the repo root, intending to `cat` it into `git commit -F`. A `git add .` after that sweeps the temp file into the staging area — and if the agent doesn't notice, the temp file lands in the squash commit and persists in repo history.

**Mitigation:** never use `git add .` (or `git add -A`, `git add *`) inside a Claude Code prompt. Always pass explicit paths: `git add <file1> <file2> <file3>`. The COMMIT_AND_PUSH escape hatch in this closure doc's instructions follows this rule. If a session script needs to discover modified files, do it via `git diff --name-only HEAD` filtered against an allow-list, not via wildcard add.

### L68 — `--permission-mode bypassPermissions` does NOT bypass git commit/push

`claude -p --permission-mode bypassPermissions "<prompt>"` is often presumed to mean "agent can do anything." In practice the bypass applies to file-level read/write/edit and to most Bash commands, but `git commit` and `git push` still trigger interactive permission prompts because the harness treats them as elevated operations. In headless mode there is no human to confirm, so the agent stalls or errors out at the commit step.

**Mitigation:** structure the prompt's contract so that the agent does ALL work up to and including `git status --short` verification, then OUTPUTS a single-line PowerShell `COMMIT_AND_PUSH` command for the operator to paste into a fresh terminal. The operator runs that one line after VS Code review. This preserves the Five-Stop Flow (Step 2: VS Code review remains a human checkpoint) AND keeps the commit/push action under direct operator control. This closure doc itself follows the pattern.

---

## 6. Architectural Debt Tracker

### Closed by Phase 6E.4+

| Debt | Resolved By | How |
|---|---|---|
| **L40** — `mcp.py` hardcoded `MCP_ENDPOINT_PATH` | PR #24 | Runtime OIDC discovery via `discover_oidc_metadata`; constant retained as fallback with `DeprecationWarning` for old FAC versions |
| **L49** — PR template stale `main` reference + ERPNext-only Testing Done checkboxes | PR #25 | Universal-fit template: 8 Type-of-Change checkboxes, Testing Done items with N/A footnotes, explicit "no `main` branch exists" assertion |
| **L50** — `.audit/` written CWD-relative, polluting repo root during test runs | PR #26 | `_get_audit_dir()` returns platform-appropriate user-home path; tests autouse-monkeypatch to `tmp_path` |
| **Master-key keyring conflation** — Fernet master key co-located with OAuth tokens under `infrabeat-erp` service | PR #27 | Promoted to dedicated `infrabeat-erp-master/master` service with 5-step backward-compatible resolution + auto-migration |
| **Token auto-refresh** — Phase 5 carryover; expired access_token forced manual `infrabeat-erp login <vm>` | PR #28 | `TokenRefreshAuth(httpx.Auth)`: 401 → `oauth.refresh` → `save_secrets` → replay with new bearer; one-shot per client lifetime |
| **Custom Claude Code skill** — `.claude/skills/infrabeat-erp-query` not registered | PR #29 | Skill authored per Phase 5 §9 plan; Claude Code routes ERPNext data questions through CLI subcommands |
| **`gh` CLI device-flow auth** — incomplete; `gh pr create` needed browser fallback | Operational (6E.7) | `gh auth login` completed; `gh pr create` and `gh api` now both work without fallback |

### New debt items emerged this track

**None.** No new architectural debt was introduced or surfaced during the 6E.4+ track. The three new lessons (L66/L67/L68) are all about Claude Code `-p` mode workflow mechanics, not codebase debt.

### Outstanding debt (deferred to Phase 7+)

- **Lint expansion (ruff/flake8)** — beyond current Python lint check
- **mypy integration** — type-check the typed modules
- **Legacy Phase 5 scripts deletion** — `probe_fac.py`, `register_client.py` are sanitized but may be deletion-eligible after audit
- **Audit log retention / `audit prune` subcommand** — currently no built-in pruning; manual `rm` only

---

## 7. Reusable Patterns Captured

### 7.A — Heredoc-into-variable PowerShell pattern

Bypasses file-download issues when delivering multi-line scripts via the Claude Code chat surface. Operator pastes one fenced PowerShell block; the heredoc materializes into a `$VAR` and is executed inline:

```powershell
$prompt = @'
... multi-line content ...
'@
claude -p --permission-mode bypassPermissions $prompt
```

No file write, no SCP, no clipboard quoting hazards. Used by every PR in this track.

### 7.B — `COMMIT_AND_PUSH` escape hatch (universal)

After the agent finishes its work in `claude -p` mode and prints validation output, it ends with a single-line PowerShell command:

```powershell
git add <specific-paths> ; git commit -m "<title>" -m "<body>" ; git push -u origin <branch>
```

The operator reviews diffs in VS Code Source Control panel, then pastes that one line into a fresh terminal. This preserves the Five-Stop Flow's Step 2 (human review) AND keeps the commit/push action under direct operator control (sidesteps L68).

### 7.C — Recon-then-implement (single-step recon before architectural decisions)

Before any non-trivial refactor, run a single read-only recon pass (greps, file reads, test enumeration) and bake the findings into the implementation prompt. Don't split recon and implementation into two `claude -p` calls — the second call has no memory of the first (L66). Each PR in this track was preceded by one focused recon pass; no PR required mid-flight architectural pivots.

### 7.D — Specific git-add paths (never `git add .`)

Universal rule: every COMMIT_AND_PUSH line in this track named explicit paths. Never `git add .` or `git add -A`. Eliminates the L67 temp-file leak vector.

### 7.E — Backward-compatible resolution chains

Both PR #26 (audit dir) and PR #27 (master key) introduced new canonical locations while keeping legacy-path fallbacks for transparent migration. PR #26 left existing `.audit/` dirs untouched (operator decides whether to `rm -rf`); PR #27 auto-promotes old-keyring values into new keyring on first read but does NOT delete the old entry (rollback safety net). Pattern: new code reads from the new location, falls back to legacy on miss, optionally promotes on read; never destructive on first contact.

---

## 8. Phase 6E Status

Phase 6E is now **FULLY SEALED** across both tracks:

| Track | Status | Closure Doc | Sealed |
|---|---|---|---|
| **Enforcement** (squash + sanitization + rotation + keyring + public + branch protection) | ✅ SEALED | `19_PHASE_6E_CLOSURE.md` | 2026-05-10 |
| **Debt retirement** (L40, L49, L50, master key, auto-refresh, skill, gh auth) | ✅ SEALED | `20_PHASE_6E_DEBT_RETIREMENT_CLOSURE.md` (this file) | 2026-05-10 |

PR span: #21 (enforcement) + #22 (closure docs 19) + #24, #25, #26, #27, #28, #29 (debt retirement) + this docs PR. All squash-merged on `dev` under the Phase 6E.3 ruleset. `staging` and `production` untouched throughout Phase 6E — promotion is a Phase 7 prerequisite gate.

---

## 9. Phase 7 Outline

InfraBeat Console TUI per `docs/12_INFRABEAT_CONSOLE_SPEC.md`. Phase 6E foundations now in place to be consumed by the Console:

- **Typed CLI with auto-refresh** — `infrabeat-erp` subcommands plus transparent token refresh (PR #28) become the Console's data plane primitive
- **Audit log in user-home** — Console's audit-viewer panel reads from `~/.local/share/infrabeat-erp/audit/` (PR #26), no longer fighting CWD-pollution
- **Dedicated master-key namespace** — `infrabeat-erp-master/master` (PR #27) keeps Console's runtime credentials cleanly separated from secret storage
- **Custom Claude Code skill** — `infrabeat-erp-query` (PR #29) lets Claude Code (within or outside the Console) route ERPNext data questions correctly without operator hand-holding
- **Dynamic MCP endpoint discovery** — runtime OIDC consumption (PR #24) means the Console works against any FAC version, current or future, without a code change
- **Public repo with enforced ruleset** — every Console PR will land under the same 6 required checks (Phase 6E.3)
- **Sanitized credentials** — repo history is harmless (Phase 6E.1)
- **Rotated VM passwords** — laptop OS keyring `infrabeat-vm-creds` is the single source for SSH/MariaDB/Admin (Phase 6E.1.5)
- **OS keyring posture** — two services (`infrabeat-erp` for CLI runtime, `infrabeat-vm-creds` for operator credentials, plus `infrabeat-erp-master` for master key) provide the Console's secret-access primitives

The Console becomes the Phase 7 primary interface for cross-VM operations — single-pane deploy/promote/rollback/backup actions, cross-VM log tailing, audit viewer, and GitHub PR/CI status. Estimated 25–30 hours across multiple sessions, building on the primitives sealed by Phases 6A through 6E inclusive.

---

End of `20_PHASE_6E_DEBT_RETIREMENT_CLOSURE.md`. If you read this far, Phase 6E is done. Sentinel remains `ib-7c4a9f`.
