# Phase 6C Closure — Defense-in-Depth for `infrabeat-erp` CLI

> **Sealed 2026-05-09.** Phase 6C composed three architectural protections (audit log, production guards, keyring storage) onto the `infrabeat-erp` Typer/Click CLI built in Phase 6A-6B, then empirically validated the composed state against all three VMs. As a side benefit, Phase 6C.4 closure smoke also resolved the FAC version drift question carried since Phase 5 §10. All three VMs are now at perfect parity (FAC `2.0.0` / MCP `2025-06-18` / 17 tools). `dev` tip on close: `42b1d07` (Phase 6C.1) — the closure doc + reconciled docs land via this PR.

---

## §1 Sub-phase inventory

| Sub-phase | Concern | PR | Squash commit | Lines | Tests after | Date |
|---|---|---|---|---|---|---|
| 6C.3 — JSONL audit log | Forensic observability of every CLI invocation | #13 | `5184710` | +294 / −2 | 51 | 2026-05-09 |
| 6C.2 — Production guards | `--allow-production` global flag + `_confirm_deploy_or_env` helper | #14 | `c45fc38` | +414 / −1 | 60 | 2026-05-09 |
| Cleanup hotfix | Remove inadvertent helper-script commits + .gitignore protection | #15 | `fc0e7ce` | +6 / −196 | 60 | 2026-05-09 |
| 6C.1 — Keyring promotion | OS-keyring storage with Fernet-encrypted-JSON fallback + `migrate-secrets` | #16 | `42b1d07` | +622 / −71 | 70 | 2026-05-09 |
| 6C.4 — Closure smoke | Empirical end-to-end validation across all 3 VMs | (this docs PR) | TBD | docs only | 70 | 2026-05-09 |

**Net additions to `infrabeat-erp` package:** ~1,330 LoC across `cli.py` (+225), `secrets_store.py` (+380 / −71 refactor), `audit.py` (+91 new), 3 test files (+~340), and `pyproject.toml` (+5 — keyring + cryptography deps). 24 new tests added (5 audit + 9 guards + 10 keyring) on top of the 46 inherited from Phase 6B closure. Final test posture: **70 passed, 1 skipped** (the POSIX-only mode-bit test on `secrets_store` is correctly bypassed on Windows).

---

## §2 Sub-phase ordering — locked architectural decision

The Phase 6C planning doc listed sub-phases as 6C.1 (keyring) → 6C.2 (guards) → 6C.3 (audit) numerically. The architect-of-record inverted this to **6C.3 → 6C.2 → 6C.1 → 6C.4** for these reasons:

| Ordering | Rationale |
|---|---|
| Audit FIRST | Least invasive (single Group-level instrumentation), captures all subsequent Phase 6C work in audit trail, and Phase 7 Console F7 viewer's dependency. Risk-free to deploy. |
| Guards SECOND | Defense-in-depth before keyring's risky data migration. High user-visible value early. Composes additively with audit (audit captures the `--allow-production` flag in `args` field — zero new audit instrumentation needed for guard forensics). |
| Keyring LAST | Highest user-data risk (refactor of secrets_store + migration of existing files). Runs with audit + guards already protecting it. Migration is reversible thanks to `.json.migrated` rename pattern. |
| Closure validates the composition | 6C.4 re-runs everything end-to-end against all 3 VMs in one ceremony, captures evidence, resolves outstanding questions (prod FAC version), seals the phase. |

This ordering preserved a clean "each sub-phase is fully validated before the next begins" property. No sub-phase merged with known issues from a prior sub-phase.

---

## §3 Architectural decisions (committed by architect-of-record across all sub-phases)

### 6C.3 — Audit log
- **Format:** JSONL (one JSON object per line; append-only; no rotation in v1; Phase 6E adds `audit prune`)
- **Location:** `<cwd>/.audit/<YYYY-MM-DD>.jsonl` (CWD-relative; Phase 6E promotes to user-home)
- **Fields captured (9):** `timestamp_utc` (ISO 8601 Z), `user`, `cli_version`, `pid`, `subcommand`, `vm`, `args`, `exit_code`, `duration_ms`
- **Wrapped at Group `main()` not subcommand `invoke()`** — captures `--help` short-circuits + global-flag-only invocations. Minor architectural improvement over original prompt.
- **Fail-silent** on write errors with stderr `audit warning:` prefix — operational-priority over forensic completeness when disk full or permission denied.

### 6C.2 — Production guards
- **Two layers:**
  - `--allow-production` global Click option, stored in `ctx.obj["allow_production"]`
  - `_ensure_production_allowed(vm_alias)` checks the flag, exits 1 with stderr message if violated
- **Wired into:**
  - `_build_authed_client` (covers `query`, `get`, `describe`, `search` — they all use the shared helper)
  - Direct call inside `register`, `login`, `smoke` (these don't use the helper)
- **Coverage gap discovered + fixed mid-execution:** Initial Claude Code run gated only `smoke` + `_build_authed_client`. Architect-reviewer caught that `register` + `login` were ungated, generated `apply_6c2_gap_fix.py` script (later cleaned in PR #15) to add coverage. Lesson L42 below.
- **`_confirm_deploy_or_env` forward infrastructure:** Reads `INFRABEAT_CONFIRM=DEPLOY` env var (CI/scripted path) OR interactive `click.prompt` requiring literal `DEPLOY`. Wired into NO existing subcommand (current 7 are all read-only); reserved for Phase 7 mutating subcommands.
- **Production-only by design:** Dev and staging unaffected. Staging is the UAT proving ground — gating it would add friction without safety value.

### 6C.1 — Keyring promotion
- **Library:** `keyring>=24,<26` + `cryptography>=42,<46` (semver upper bound — prevent accidental major version drift)
- **Backend per OS:** keyring's auto-detection. Windows → Credential Manager. macOS → Keychain. Linux desktop → Secret Service. Linux headless / CI → falls through to encrypted JSON.
- **Storage chain (load order):**
  1. Keyring (primary)
  2. Fernet-encrypted JSON at `<cwd>/.secrets/<vm>.json.enc` (fallback when keyring unavailable)
  3. Plaintext JSON at `<cwd>/.secrets/<vm>.json` (legacy compat for users who haven't migrated)
- **Save semantics:** ALWAYS to primary backend (keyring or encrypted-JSON fallback), NEVER to legacy plaintext. After 6C.1 ships, future register/login updates flow into keyring without further user action.
- **Master key for Fernet fallback:** keyring service `infrabeat-erp` username `__master__`. Fallback to `~/.config/infrabeat-erp/master.key` (mode 0o600 POSIX) if keyring unavailable. Lazy-generated 32 random bytes base64-urlsafe.
- **Service identifier:** `infrabeat-erp` (the package name) + username = VM alias.
- **`migrate-secrets` subcommand:** `--vm <alias>` for single, `--all` for everything. Renames original to `.json.migrated` (forensic trail, NOT delete). Idempotent. Production targeting requires `--allow-production`.
- **New exception:** `SecretsBackendUnavailable` when neither keyring nor encrypted-JSON path is writable.

### Cleanup hotfix
- **Trigger:** Helper Python scripts (`apply_6c2_gap_fix.py`, `fix_6c2_test_imports.py`) at repo root got committed in PR #14 because they ran `git add -A` inside themselves. Self-contamination loop.
- **Fix:** PR #15 — `git rm` both files + add `.gitignore` patterns:
  - `/apply_*.py` (one-off fix scripts at repo root)
  - `/fix_*.py` (one-off fix scripts at repo root)
  - `/phase*_prompt.md` (Claude Code prompt files at repo root)
- Patterns anchored to repo root with leading `/` so they don't false-match legitimate code in `tools/`, `src/`, etc.
- **Architectural payoff:** Phase 6C.1's helper scripts (none ended up needed, but the protection was in place) and any future phase's helper artifacts stay out of the repo by design.

---

## §4 Validation matrix

### §4.1 Test posture progression

| Phase | Tests passed | Tests skipped | Delta | Reason for delta |
|---|---|---|---|---|
| Pre-6C (Phase 6B closure) | 46 | 1 | — | baseline (POSIX-only secrets_store mode-bit test skipped on Windows) |
| Post-6C.3 | 51 | 1 | +5 | audit module: timestamp format, fields, fail-silent on disk full, append semantics, idempotency under concurrency |
| Post-6C.2 (initial) | 58 | 1 | +7 | 7 guards tests from Claude Code (covered guard helper + group flag + smoke + ensure-helper paths) |
| Post-6C.2 (gap-fix) | 60 | 1 | +2 | 2 architect-reviewer tests for register + login direct-guard coverage |
| Post-6C.1 | 70 | 1 | +10 | 7 secrets_store (keyring round-trip, fallback chains, migration, idempotency) + 3 cli (migrate-secrets dev/prod-flag/all) |

### §4.2 Live smoke results (Phase 6C.4 evidence)

| VM | FAC version | MCP protocol | Tool count | Audit captured | Guard refusal exit |
|---|---|---|---|---|---|
| dev (`10.1.0.184`) | `2.0.0` | `2025-06-18` | 17 | ✓ | N/A (dev unguarded) |
| staging (`10.1.0.185`) | `2.0.0` | `2025-06-18` | 17 | ✓ | N/A (staging unguarded — UAT proving ground) |
| production (`10.1.0.186`) | **`2.0.0`** | **`2025-06-18`** | **17** | ✓ | ✓ exit 1 in 16ms (fires before any network I/O) |

**Production keyring engagement empirically proven:**
- `register --allow-production production` → `client_id=cvngll9k67` issued, secrets saved direct-to-keyring (zero plaintext touch — `.secrets/` directory contained NO `production.json` after register, confirming Phase 6C.1 keyring-primary save semantics)
- `migrate-secrets --vm production` → 14ms execution, `no-source` outcome (no plaintext to migrate; idempotent path validated)
- `smoke production` WITHOUT `--allow-production` → 16ms execution, exit 1, stderr names the flag (guard fires before any network I/O — fail-fast)

**Audit log forensic completeness empirically proven:** All 3 production-targeted invocations recorded with `args` field containing `["--allow-production", ...]` verbatim. Guard refusal recorded with `args: ["smoke", "production"]` (no `--allow-production`) and `exit_code: 1`. Zero new audit instrumentation needed for guard forensics — the args verbatim capture from 6C.3 was sufficient by design.

### §4.3 Composed-state validation

The three protections compose **additively, not multiplicatively**:

| Layer | Engages | Composes with |
|---|---|---|
| Audit | Always (every CLI invocation) | All other layers automatically — args capture exposes flag presence/absence |
| Guard | Production-targeted invocations only | Audit captures both successful pass-through and refusal |
| Keyring | All credential read/write | Audit captures the subcommand; guard runs first if production-targeted; legacy plaintext fallback preserves backwards compat |

No layer interferes with another. Each can be reasoned about independently. Each can be modified or replaced independently in a future phase without regression risk to the others.

---

## §5 Lessons learned

Extending the lesson series from 16_PHASE_6B_CLOSURE.md (which ended at L41).

| ID | Lesson | Mitigation in place |
|---|---|---|
| L42 | Helper Python scripts at repo root get accidentally committed by `git add -A` inside themselves (self-contamination loop). | `.gitignore` patterns from PR #15 protect future phases. Scripts can also be placed outside repo root (e.g., `~/Documents/runbooks/`) to eliminate the failure mode entirely. |
| L43 | Claude Code `--permission-mode bypassPermissions` accepts file edits AND shell commands but doesn't always cover commit (saw a permission pause on 6C.2 commit step). | Architect-reviewer finishes git operations manually when Claude Code stops at commit. Pattern: pytest summary + diff stat from Claude Code → manual `git add -A; git commit; git push` from terminal. |
| L44 | API stream idle timeouts on long Claude Code prompts (15-25 min runs hit Anthropic's stream-idle threshold). | Diagnostic-then-retry pattern: `git status` after timeout → revert if partial → retry from clean state. If it fails twice, fall back to architect-generated deterministic Python script with file-by-file edits. |
| L45 | PowerShell 5.x doesn't support `&&` for fail-fast chaining. | Use `;` for unconditional sequential or `if($?) { ... }` for fail-fast. Most session commands use `;` (chained always-run) since each step's output is paste-back evidence anyway. |
| L46 | Claude Code rate limits (per-window quota) hit during long sub-phases. Phase 6C.1 hit limit AFTER pytest passed but BEFORE git commit. | Architect-reviewer commits + pushes manually using the verification evidence (pytest summary, diff stat, live smoke output) Claude Code already produced. Zero loss of work. |
| L47 | Token TTL is 3600s (no auto-refresh in v1). Multi-hour sessions hit HTTP 401 on `smoke` after sufficient idle time. | Standard recovery: re-run `infrabeat-erp login <vm>` for the affected VM. Phase 7+ Console may add a "token expiring soon" indicator. Phase 6E auto-refresh remains a separate carryover concern. |
| L48 | Inter-subnet router (laptop `10.1.1.0/24` ↔ VMs `10.1.0.0/24`) produces transient `httpx.ConnectTimeout` independent of VM health. | Documented in `04_VM_INVENTORY.md` Network Topology. No code mitigation needed — these are infrastructure flaps the user retries past. |
| L49 | `.github/PULL_REQUEST_TEMPLATE.md` references stale "main" branch (deleted per `05_GITHUB_WORKFLOW.md` v2). | Phase 6E candidate for cleanup. Non-blocking — affects only template-display text on PR creation page. |
| L50 | Test pollution: existing `CliRunner` tests don't `chdir` to `tmp_path`, so they write audit records to repo-root `.audit/` during test runs. | `.gitignore` covers it (cosmetic-only). Phase 6E user-home migration of `.audit/` eliminates structurally. |
| L51 | "5 of 5 checks passed" vs "5 in progress / 2 skipped" UI state is a normal lifecycle artifact, not a CI bug. The "Require approving review" check shows skipped on PR creation, transitions when self-approval happens (or remains skipped if branch protection allows merge anyway). | Documented: PR creation → wait for 3 active checks → self-approve → merge. Solo-dev branch protection rules accept self-approval as the "review" gate. |
| L52 | FAC version drift question — Phase 5 §10 claimed production at `2.4.1` while dev was empirically at `2.0.0`. Drift was a STALE DOC ARTIFACT, not real environmental drift. All 3 VMs at `2.0.0`/`2025-06-18`/17 tools at parity. | Documentation now reflects empirical state. No Phase 6E reconciliation needed. Lesson reinforces the principle: prefer empirical capture over historical doc claims when they disagree. |

---

## §6 Forward outline — what unlocks after Phase 6C

### Phase 6D — CI integration (next session)
- Add `.github/workflows/python-tests.yml`
- Triggers: PRs to `dev`, `staging`, `production`
- Steps: checkout → Python 3.12 setup → `pip install -e tools/infrabeat_erp[test]` → pytest with coverage → fail if coverage < 70%
- Coverage threshold start at 70% (current actual is higher — gives headroom for Phase 7+ feature additions without immediate gate violation)
- Estimated scope: ~50 LoC of YAML + small `pyproject.toml` test-extras section. ~30 minutes.

### Phase 6E — Polish + debt retirement
- L40 endpoint discovery debt: refactor `mcp.py` to use OIDC-discovered `mcp_endpoint` field dynamically instead of hardcoded path
- `.secrets/` and `.audit/` user-home migration (eliminate L50 test pollution structurally)
- Master key separation into its own keyring service (currently uses same `infrabeat-erp` service with `__master__` username — minor architectural cleanup)
- Custom Claude Code skills: `.claude/skills/infrabeat-erp-query/SKILL.md`, etc. (dogfood the CLI from Claude Code via skill)
- L49 PR template stale "main" reference cleanup
- `audit prune` subcommand for log rotation
- Token auto-refresh (carryover from Phase 5 — currently re-`login` required per L47)
- Estimated scope: 3-5 small PRs, ~1-2 hours total

### Phase 7 — InfraBeat Console TUI
- Per `12_INFRABEAT_CONSOLE_SPEC.md` — single-pane dashboard with audit log viewer pane (F7 reading from 6C.3's JSONL files), live VM health pings, production deploy ceremony with mandatory `DEPLOY` confirm gate (uses `_confirm_deploy_or_env` from 6C.2), keyring-backed credential picker
- Mutating operations (deploy, rollback, backup-orchestrate) — these are the consumers of `_confirm_deploy_or_env` reserved by 6C.2
- Estimated scope: significant — multi-day. Specced separately.

---

## §7 Architectural state at Phase 6C close

**Three-VM landscape:** all at FAC `2.0.0` / MCP `2025-06-18` / 17 tools. Byte-equivalent catalog. Zero drift.

**`infrabeat-erp` CLI capabilities (read-only, all auto-audited, production-targeted ops gated):**
- `register <vm>` — RFC 7591 OAuth client registration
- `login <vm>` — RFC 7636 PKCE auth code flow
- `smoke <vm> [--json]` — MCP `initialize` + `tools/list`
- `query <vm> <doctype> [--filter k=v]... [--limit N] [--json]`
- `get <vm> <doctype> <name> [--json]`
- `describe <vm> <doctype> [--json]`
- `search <vm> <text> [--limit N] [--json]`
- `migrate-secrets [--all | --vm <alias>]` — keyring promotion (Phase 6C.1)

**Global flags:**
- `--allow-production` (Phase 6C.2) — required for any subcommand targeting `production` alias

**Storage:**
- Secrets: keyring (primary) → Fernet-encrypted JSON (fallback) → legacy plaintext (compat)
- Audit log: `<cwd>/.audit/<YYYY-MM-DD>.jsonl` append-only, fail-silent on write errors

**Test posture:** 70 passed, 1 skipped (10.97s on dev laptop). 24 new tests added across Phase 6C.

**`dev` tip on Phase 6C close:** `42b1d07` (Phase 6C.1 keyring squash merge). The closure-doc + reconciliation PR (this PR) lands shortly after.

---

## §8 Document Change Log

| Date | Change | Source of truth |
|---|---|---|
| 2026-05-09 | Phase 6C closure doc created. | Live empirical data + sub-phase PR records |
| 2026-05-09 | Sub-phase inventory recorded with PR/commit/line-count/test-after metadata. | `git log --oneline`, `gh pr view #13/14/15/16` |
| 2026-05-09 | Lessons L42-L52 added (extending L37-L41 from 16_PHASE_6B_CLOSURE.md). | Real session experience 2026-05-09 |
| 2026-05-09 | FAC version drift question (carried since Phase 5 §10) RESOLVED at `2.0.0` parity across all 3 VMs. | `infrabeat-erp --allow-production smoke production` empirical capture |

---
