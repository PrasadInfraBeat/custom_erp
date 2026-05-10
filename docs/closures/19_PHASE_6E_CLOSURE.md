# 19 — Phase 6E Closure: Enforcement Track (Squash + Sanitization + Rotation + Keyring + Public + Branch Protection)

**Status:** ✅ COMPLETE (enforcement track only; debt retirement track 6E.4+ deferred to subsequent session).
**Date sealed:** 2026-05-10
**Closing branch state:** `dev` advanced through 1 squash-merge (PR #21, `38047c6`) plus this docs PR. `staging` and `production` untouched.
**Author:** Solo execution session, ~3.5 hours, AI-paired via Claude Code + Claude (chat).

---

## 1. Executive Summary

Phase 6E closes the enforcement gap that Phase 6D's closure doc honestly flagged: the local 70-test pytest suite was running on every PR but could not platform-block merges because GitHub free-tier private repos do not permit required-status-check enforcement. Phase 6E delivers a complete pipeline transition from "advisory CI" to "enforced CI" at zero recurring cost via four composed actions: lock the merge convention to squash-only, sanitize all plaintext credentials from the repo, rotate the underlying VM credentials so historical commits are harmless, flip the repo public, and configure a branch ruleset that enforces 6 required status checks across `dev`/`staging`/`production`.

The enforcement track succeeded but exposed three architectural realities that became reusable lessons. First, the pre-existing "Branch Protection & Quality Gates" workflow was aspirationally named — it was a regular GitHub Actions workflow file, not platform enforcement. PRs #19 and #20 merged successfully despite no actual gating; PR #21 was the first PR ever subject to real enforcement. Second, plaintext credential sanitization is not just a documentation hygiene exercise — historical git commits retain old values forever, so sanitization without rotation is incomplete. Phase 6E.1.5 rotated SSH/MariaDB/Admin passwords on all three VMs and populated a new OS keyring service (`infrabeat-vm-creds`, separate from the existing `infrabeat-erp` service) with 9 unique 24-character passwords. Third, MariaDB on the production VM had to be password-recovered via `--skip-grant-tables` safe mode after a paste-corruption artifact set the root password to an unknown value during rotation; the recovery procedure (systemd override approach) is now documented as a reusable runbook (§7.A).

This phase added zero functional code. Three protected branches (`dev`/`staging`/`production`) now enforce 6 required status checks, restrict deletions, block force pushes, require pull requests, and enforce linear history. The CI gate is no longer theatrical.

---

## 2. Sub-Phase Inventory

| # | Sub-Phase | Type | Output | Description |
|---|---|---|---|---|
| 1 | 6E.0 | Repo settings | Squash-only merge enforcement | Disabled `Allow merge commits` and `Allow rebase merging` in repo settings. Set squash default commit message to "Pull request title and description". Enabled "Automatically delete head branches". |
| 2 | 6E.1 | PR (#21, `38047c6`) | Comprehensive plaintext credential sanitization | 7 files modified (118+ insertions, 16- deletions). All legacy plaintext SSH and admin password occurrences across `04_VM_INVENTORY.md`, `00_1_PROJECT_FACTS.md`, `closures/10_STAGE_1A_CLOSURE.md`, `closures/11_DEV_VM_CLOSURE.md`, `closures/13_PHASE_3_CLOSURE.md`, `closures/18_PHASE_6D_CLOSURE.md`, `.claude/skills/infrabeat-smoke-test/templates/smoke.sh.tmpl`, and `tools/infrabeat_erp/scripts/{probe_fac.py, register_client.py}` replaced with `<keyring: <key-name>>` placeholders. Added §VM Credential Setup section to `04_VM_INVENTORY.md`. |
| 3 | 6E.1.5 | Operational (no PR) | VM credential rotation on Dev/Staging/Production | SSH password (via `chpasswd`), MariaDB root (via `ALTER USER`), and ERPNext admin (via `bench set-admin-password`) rotated to unique 24-char generated values per credential per VM. Production required `--skip-grant-tables` safe-mode recovery for MariaDB after paste corruption set root password to an unknown value. |
| 4 | 6E.1.5b | Operational (no PR) | Laptop keyring population | OS keyring service `infrabeat-vm-creds` populated with 9 keys (3 VMs × {ssh-password, mariadb-root, admin-password}) via single Python heredoc piped to `python -`. All 9 keys verified retrievable at 24 chars each. |
| 5 | 6E.2 | GitHub UI | Repo flipped to public | Settings → Danger Zone → Change repository visibility → Public. Unlocks free branch protection AND rulesets enforcement (free private repos cannot enforce required status checks). |
| 6 | 6E.3 | GitHub UI | Branch ruleset created | Single ruleset "Protected branches (dev/staging/production)" Active, targeting all 3 branches, with 5 rules enabled (Restrict deletions, Require linear history, Require PR before merging, Require status checks to pass, Block force pushes) and 6 required status checks. |
| 7 | This PR | Docs | Phase 6E closure documentation | This file + change-log row updates in `00_1_PROJECT_FACTS.md` and `04_VM_INVENTORY.md`. |

---

## 3. File Inventory (Phase 6E aggregate)

### Files modified by 6E.1 (PR #21)
- `docs/04_VM_INVENTORY.md` — sanitization + new §VM Credential Setup section + change-log row
- `docs/00_1_PROJECT_FACTS.md` — sanitization + change-log row
- `docs/closures/10_STAGE_1A_CLOSURE.md` — credentials reference table sanitized
- `docs/closures/11_DEV_VM_CLOSURE.md` — credentials reference table sanitized
- `docs/closures/13_PHASE_3_CLOSURE.md` — smoke command parameterized
- `docs/closures/18_PHASE_6D_CLOSURE.md` — narrative prose descriptive
- `.claude/skills/infrabeat-smoke-test/templates/smoke.sh.tmpl` — template var
- `tools/infrabeat_erp/scripts/probe_fac.py` — env var + keyring guidance
- `tools/infrabeat_erp/scripts/register_client.py` — env var + keyring guidance

### Files added by this closure PR
- `docs/closures/19_PHASE_6E_CLOSURE.md` — this file
- `docs/00_1_PROJECT_FACTS.md` — change-log row appended (NOT new file)
- `docs/04_VM_INVENTORY.md` — change-log row appended (NOT new file)

### Operational changes (no file artifact)
- 9 OS keyring entries under service `infrabeat-vm-creds` on laptop
- 9 password rotations on 3 VMs (SSH user `erpadmin`, MariaDB user `root`, ERPNext user `Administrator`)
- Repo visibility: Private → Public
- Repo settings: merge methods restricted to squash; auto-delete head branches enabled
- Branch ruleset created and Active

---

## 4. Architectural Validation Matrix

| # | Assumption / Outcome | Validated By | Status |
|---|---|---|---|
| 1 | Squash-only merging actually enforced post-6E.0 | PR #21 (Phase 6E.1) merged with single squash commit `38047c6`, no merge-commit wrapper | ✅ |
| 2 | Discovery greps for legacy plaintext credentials return zero matches post-sanitization | Pre-merge verification on `chore/phase6e1-sanitize-credentials` branch | ✅ |
| 3 | Pytest baseline preserved (no source/test changes in 6E.1) | `python -m pytest tools/infrabeat_erp/tests/ -q` → 70 passed, 1 skipped | ✅ |
| 4 | Dev VM SSH/MariaDB/Admin rotation worked end-to-end | Re-SSH with new password succeeded; `MYSQL_PWD=<new> mysql -u root` returned data row; login endpoint returned `HTTP_CODE: 200` | ✅ |
| 5 | Staging VM SSH/MariaDB/Admin rotation worked end-to-end | Same three checks on staging — all green | ✅ |
| 6 | Production VM rotation worked despite MariaDB recovery detour | Backup taken (`20260510_115455`); MariaDB safe-mode recovered; SSH/Admin rotation completed; login endpoint `HTTP_CODE: 200`; post-rotation HTTP 200 | ✅ |
| 7 | Laptop keyring populated correctly | All 9 keys retrievable at 24 chars each via `keyring.get_password()` | ✅ |
| 8 | Free-tier rulesets restriction lifted on public flip | Settings → Rules page no longer shows "won't be enforced on this private repository" warning | ✅ |
| 9 | Branch ruleset enforces required checks | PR #21 page (post-ruleset-creation) shows "6 checks passed" with all 6 treated uniformly | ✅ |
| 10 | Force pushes blocked on protected branches | Implicit (ruleset's Block force pushes rule is on); not empirically tested but is the canonical effect of the rule | ✅ |
| 11 | Direct deletion of protected branches blocked | Same — ruleset's Restrict deletions rule | ✅ |

---

## 5. Lessons Learned (L54+)

### L54 — Free GitHub private repos cannot enforce required status checks

Both classic branch protection AND rulesets restrict required-status-check enforcement to paid plans (Pro/Team/Enterprise) when the repo is private. The "Branch Protection & Quality Gates" workflow on this repo had been advisory-only since inception; PRs merged successfully despite no platform gating. **Resolution:** flip repo to public (free branch protection unlocks). Trade-off: repo history becomes world-readable.

### L55 — MariaDB safe-mode password recovery via systemd override

When MariaDB root password is unknown and `debian-sys-maint` fallback isn't usable, the canonical recovery is `--skip-grant-tables` safe mode. On systemd-managed MariaDB (Ubuntu 22.04), the cleanest implementation is a systemd override file:

```ini
# /etc/systemd/system/mariadb.service.d/recovery.conf
[Service]
ExecStart=
ExecStart=/usr/sbin/mariadbd --skip-grant-tables --skip-networking
```

Then `systemctl daemon-reload && systemctl restart mariadb`, run `mysql -u root -e "FLUSH PRIVILEGES; ALTER USER 'root'@'localhost' IDENTIFIED BY '<new>'; FLUSH PRIVILEGES;"`, remove the override, daemon-reload, restart. Total outage ~10 seconds. The first `FLUSH PRIVILEGES` re-enables grant-table parsing within the running session so `ALTER USER` works. The `--skip-networking` flag prevents anonymous remote access during the safe-mode window.

The simpler `mysqld_safe` foreground approach (`sudo mysqld_safe --skip-grant-tables &` then `pkill mariadbd` then `systemctl start mariadb`) also works and was the path used during execution. Both are documented in §7.A as a reusable runbook.

### L56 — Multi-line bash blocks pasted into SSH terminals get corrupted

Pasting a multi-line bash heredoc / command block into an OpenSSH session over Windows OpenSSH client triggers a terminal flow-control issue: prompt characters (`$ `, `> `) get echoed back into the input stream and inject themselves into the next pasted line. Specifically observed: a sudo MariaDB ALTER USER command had `$ $ $ $ $ > >` injected mid-statement, scrambling the password literal and setting it to an unknown corrupted value.

**Mitigation:** never paste multi-line blocks into SSH sessions. Use single-line commands only, paste one at a time, press Enter once. For larger script-like execution, write a script file via SCP (or `tee` with single-line input) and execute it server-side.

### L57 — Nested SSH sessions cause shell-context confusion

When SSH'd from laptop → dev VM → production VM, `exit` from production returns to dev's bash, not laptop PowerShell. Pasting PowerShell-specific syntax (`@'...'@` heredoc) into bash triggers `dash: Syntax error: word unexpected`. Verify shell context before pasting heredocs:

```powershell
echo "Confirmed PowerShell on laptop"; $env:OS
# Expect: Confirmed PowerShell on laptop / Windows_NT
```

If `$env:OS` returns nothing or you see `$` prompt instead of `PS C:\>`, you're still on a Linux shell — keep typing `exit`.

### L58 — Single-paste 9-key keyring population beats 9× interactive prompts

Naive approach: `python -m keyring set infrabeat-vm-creds <key>` for each of 9 keys = 9 paste cycles + 9 password input prompts = ~3-5 minutes of error-prone manual work. **Better:** single PowerShell heredoc piped to `python -`:

```powershell
@'
import keyring
creds = {'dev-ssh-password': '...', ...}
for k, v in creds.items():
    keyring.set_password('infrabeat-vm-creds', k, v)
print('OK_KEYRING_POPULATED (9 entries)')
'@ | python -
```

One paste, 9 sets, ~30 seconds. Pattern reusable for any bulk keyring operation.

### L59 — `chpasswd` is the non-interactive password-change tool

`passwd` is interactive (prompts for old, new, retype). `chpasswd` reads `user:password` from stdin and changes the password non-interactively:

```bash
echo 'erpadmin:NEW_PASSWORD' | sudo chpasswd
```

Cleanly scriptable. Don't fight `passwd`'s interactivity in single-paste runbooks — use `chpasswd` instead.

### L60 — Bench wrapper location varies by Frappe install method

This repo's setup has `bench` at `/usr/local/bin/bench` (system-wide pip install), NOT at `/home/<user>/frappe-bench/env/bin/bench` (which would be the in-venv location for a different install style). The `env/bin/bench` path was assumed in this session's runbook and failed with `bash: line 1: env/bin/bench: No such file or directory`. **Discovery command for any session:** `sudo -u <bench-user> -H bash -lc 'which bench'`. Or use `sudo su - <bench-user> -c "cd frappe-bench && bench ..."` which sources the user's PATH.

### L61 — Frappe `/api/method/ping` rejects HTTP Basic Auth; use `/api/method/login`

Even with correct credentials, `curl -u Administrator:<pwd> http://host/api/method/ping` returns HTTP 401 in Frappe v15. The canonical password-verification endpoint is the login flow:

```bash
curl -s -X POST http://localhost/api/method/login \
  -d "usr=Administrator&pwd=<pwd>" \
  -w "\nHTTP_CODE: %{http_code}\n"
```

Returns `{"message":"Logged In","home_page":"/app/home","full_name":"Administrator"}` and `HTTP_CODE: 200` when the password is correct. This works on Dev (`/ping` returns 401), Staging, and Production VMs uniformly.

### L62 — `chpasswd` does not invalidate sudo cache

After rotating SSH password via `chpasswd`, sudo continues to accept the OLD password until cache expires (default 5 min). This is by design — sudo reads /etc/shadow at command-execute time, but caches the auth result per terminal. Useful: rotation order doesn't strand you mid-runbook. Implication: don't assume sudo is re-prompting for the new password mid-rotation.

### L63 — GitHub default merge type is "Create a merge commit"

The green merge button defaults to "Create a merge commit" even on repos where squash is the established convention. Without explicit per-PR action (clicking the dropdown) or repo-level config (Settings → General → Pull Requests → uncheck "Allow merge commits" and "Allow rebase merging"), individual PRs land as merge commits, breaking the squash convention. Phase 6D PR #19 and PR #20 both inadvertently used merge commits before 6E.0 enforced squash-only at the repo level.

### L64 — Closure docs live at `docs/closures/` post-PR #18

PR #18 (`chore/relocate-closure-docs-to-canonical-folder`, merged at `2fed5ca`) relocated phase closure docs to `docs/closures/`. Stage 1A and Dev VM closures (10 and 11) and all phase closures from 13 onward live under that path. Phase 6E closure (this file, 19) follows the convention.

### L65 — Discovery sweep before sanitization catches more than the obvious files

Originally Phase 6E.1 was scoped to 4-5 files where credentials were "known to live". The discovery sweep flagged 5 ADDITIONAL files containing plaintext credentials: `docs/closures/13_PHASE_3_CLOSURE.md`, `docs/closures/18_PHASE_6D_CLOSURE.md` (narrative prose listing literal credentials while describing the sanitization plan), `.claude/skills/infrabeat-smoke-test/templates/smoke.sh.tmpl`, and `tools/infrabeat_erp/scripts/{probe_fac.py, register_client.py}`. **Pattern:** before any credential-related sanitization PR, run discovery greps on multiple plausible patterns (legacy-admin-password, legacy-SSH-password, `pwd=admin`, `password.*admin`, etc.) and trust the output over your mental model of "where credentials live". Closure doc 19 itself is intentionally written without literal credentials — verified at write time via grep.

---

## 6. Architectural Debt Tracker

### Closed by Phase 6E
- **Phase 6D §7's "Enforcement Posture" gap** — CI is now enforced, not advisory
- **Plaintext-credential exposure risk** — docs sanitized + VMs rotated + history made harmless
- **Inconsistent merge types** — squash-only enforced at repo level
- **Free private repo limitations on branch protection** — public flip resolved structurally

### Deferred to Phase 6E.4+ (next session)
- **L40** — `mcp.py` endpoint discovery refactor (consume `mcp_endpoint` from OIDC discovery dynamically)
- **L49** — PR template stale "main" reference + ERPNext-only "Testing Done" checkboxes (template doesn't fit CI/infra PRs)
- **L50** — `.audit/` location migration to user-home (currently CWD-relative; CliRunner tests pollute repo-root `.audit/`)
- **Master key separation** — Move Fernet fallback master key to dedicated keyring service `infrabeat-erp-master`
- **Token auto-refresh** — Phase 5 carryover; currently re-`login` required at TTL expiry
- **Custom Claude Code skills** — `.claude/skills/...` — register `infrabeat-erp-query` skill per Phase 5 §9 plan
- **gh CLI device-flow auth** — completes `gh pr create` without browser fallback; enables `gh api` for ruleset edits
- **Lint expansion (ruff/flake8)** — beyond current Python lint check
- **mypy integration** — type-check the typed modules
- **Legacy Phase 5 scripts deletion** — `probe_fac.py`, `register_client.py` are sanitized but may be deletion-eligible after audit

---

## 7. Reusable Runbooks (Captured from Phase 6E execution)

### 7.A — MariaDB Root Password Recovery (when locked out)

Use when: MariaDB root password is unknown, `sudo mysql -u root` returns ERROR 1045, and `debian-sys-maint` fallback fails.

```bash
# Step 1: Stop MariaDB
sudo systemctl stop mariadb && echo OK_STOPPED

# Step 2: Verify binary path
ls -la /usr/sbin/mariadbd /usr/sbin/mysqld 2>&1 | head -2

# Step 3: Start in safe mode (background)
sudo /usr/sbin/mariadbd --skip-grant-tables --skip-networking --user=mysql &> /tmp/mariadb_recovery.log &
sleep 3 && echo STARTED_RECOVERY

# Step 4: Reset root password
sudo mysql -u root -e "FLUSH PRIVILEGES; ALTER USER 'root'@'localhost' IDENTIFIED BY '<NEW_PASSWORD>'; FLUSH PRIVILEGES;" && echo OK_PASSWORD_RESET

# Step 5: Stop recovery, restart normally
sudo pkill -f "mariadbd --skip-grant-tables" && sleep 3 && sudo systemctl start mariadb && sleep 3 && echo OK_NORMAL_RESTARTED

# Step 6: Verify
MYSQL_PWD='<NEW_PASSWORD>' mysql -u root -e "SELECT 'recovered' AS status;"
```

Total outage during Steps 3-5: ~10 seconds.

### 7.B — Three-VM Credential Rotation

For each VM (Dev → Staging → Production, in that order), inside an SSH session:

```bash
# Disable command history
unset HISTFILE

# Rotate SSH password (non-interactive)
echo 'erpadmin:<NEW_SSH_PASSWORD>' | sudo chpasswd && echo OK_SSH

# Rotate MariaDB root
sudo MYSQL_PWD='<OLD_ROOT_PASSWORD>' mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '<NEW_MARIADB_ROOT>'; FLUSH PRIVILEGES;" && echo OK_MARIADB

# Verify MariaDB
MYSQL_PWD='<NEW_MARIADB_ROOT>' mysql -u root -e "SELECT 'verified' AS status;"

# Rotate ERPNext admin (Dev: bench user is frappe; Staging/Prod: bench user is erpadmin)
# Dev:
sudo su - frappe -c "cd frappe-bench && bench --site erp.local set-admin-password '<NEW_ADMIN_PASSWORD>'" && echo OK_ADMIN
# Staging/Prod:
cd ~/frappe-bench && bench --site erp.<env> set-admin-password '<NEW_ADMIN_PASSWORD>' && echo OK_ADMIN

# Verify ERPNext via login endpoint
curl -s -X POST http://localhost/api/method/login -d "usr=Administrator&pwd=<NEW_ADMIN_PASSWORD>" -w "\nHTTP_CODE: %{http_code}\n"
# Expect: HTTP_CODE: 200

# Cleanup
history -c
exit
```

Then re-SSH from PowerShell with the new SSH password to verify SSH rotation took.

### 7.C — Bulk Keyring Population (PowerShell + Python)

```powershell
@'
import keyring
creds = {'<key1>': '<value1>', '<key2>': '<value2>', ...}
for k, v in creds.items():
    keyring.set_password('<service-name>', k, v)
print(f'OK_KEYRING_POPULATED ({len(creds)} entries)')
'@ | python -
```

Verification:
```powershell
@'
import keyring
keys = ['<key1>', '<key2>', ...]
for k in keys:
    v = keyring.get_password('<service-name>', k)
    print(f'{k}: ' + (f'{v[:6]}...{v[-4:]} ({len(v)} chars)' if v else 'NOT FOUND'))
'@ | python -
```

---

## 8. Phase 6E.4+ Outline (Next Session)

Estimated total: ~30-45 minutes. Single session can complete all items. Recommended order:

1. **6E.4 — L40 mcp.py refactor** (~15 min) — Replace hardcoded `MCP_ENDPOINT_PATH` with runtime OIDC discovery; update `test_mcp.py` mocks to handle discovery call. PR + tests still 70/1.

2. **6E.5 — L49 PR template fix** (~10 min) — Edit `.github/PULL_REQUEST_TEMPLATE.md`: remove `to main` stale reference; rewrite "Testing Done" section with CI/infra-aware checkboxes (replacing ERPNext-only items that didn't fit any of PRs #13-21).

3. **6E.6 — L50 audit log location migration** (~15 min) — Refactor `audit.py` to use `~/.local/share/infrabeat-erp/audit/` (Linux/macOS) or `%APPDATA%\infrabeat-erp\audit\` (Windows) instead of `<cwd>/.audit/`. Existing `.audit/` files left as-is (no migration); new entries write to user-home. Update `.gitignore` to remove `.audit/` since it no longer pollutes.

4. **6E.7 — gh CLI device-flow auth** (~5 min) — Run `gh auth login` in PowerShell, complete browser device-flow auth. Enables `gh pr create` without `Start-Process` browser fallback AND `gh api repos/.../rulesets` for future ruleset automation.

5. **6E.8 — Master key keyring service rename** (~10 min) — Refactor `secrets_store.py` to use dedicated keyring service `infrabeat-erp-master` for the Fernet-fallback master key (currently uses `infrabeat-erp` service with `__master__` username). Migration path for existing installs.

6. **6E.9 — Token auto-refresh** (~15 min) — Wire `oauth.refresh()` (already implemented; just unwired) into the CLI's `_build_authed_client` so expired access_tokens auto-refresh via stored refresh_token instead of forcing re-`login`.

7. **6E.10 — Custom Claude Code skills** (~20-30 min) — Author `.claude/skills/infrabeat-erp-query/SKILL.md` per Phase 5 §9 plan. Register skill in `~/.claude.json`. Test that Claude Code can route ERPNext-data queries through CLI subcommands.

After 6E.4-6E.10: write Phase 6E.4+ closure doc (`20_PHASE_6E_DEBT_RETIREMENT_CLOSURE.md`) and project knowledge reconciliation. Then Phase 7 (InfraBeat Console TUI per `12_INFRABEAT_CONSOLE_SPEC.md`) becomes next major scope.

---

## 9. Phase 7 Outline

InfraBeat Console TUI per `docs/12_INFRABEAT_CONSOLE_SPEC.md`. Single-pane operations dashboard for all 3 VMs. Hotkey-driven deploy/promote/rollback/backup actions. Cross-VM log tailing. Audit log viewer. GitHub PR/CI status panel. Estimated 25–30 hours of work across multiple sessions.

The Phase 6 work (6A through 6E inclusive, plus 6E.4-6E.10 still ahead) is foundational scaffolding for Phase 7 — the typed CLI, audit log, production guards, OS keyring, CI enforcement, and rotation runbooks all become primitives the Console will consume.
