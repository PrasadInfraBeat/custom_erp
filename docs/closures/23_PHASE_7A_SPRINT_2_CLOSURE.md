# Phase 7a Sprint 2 — Checkpoint Closure

**Date:** 2026-05-12
**Status:** Mid-Sprint 2 reconciliation. Tasks 1, 1b, 1c SHIPPED. Task 2 framework PRE-BUILT (verified). Task 3 DEFERRED to next session.

## Summary

3 PRs merged today (#36, #37, #38). Test suite **102 → 117 (+15)**. One critical audit-routing bug fixed.

## Shipped Today

### PR #36 — Sprint 2 Task 1: infrabeat-erp backup subcommand (MVP)
- `application/backup.py` (NEW, 147 LOC) — bench backup + SFTP + sha256
- `infrastructure/ssh_adapter.py` (+44 LOC) — async SFTP download via paramiko
- `cli.py` (+37 LOC) — `backup <vm>` Click subcommand
- `tests/test_backup.py` (NEW, 7 tests)
- **First real ops artifact:** 1.3 MB database backup tarball at `~/.infrabeat-erp/backups/staging/.../20260512_114941-erp_staging-database.sql.gz` with sha256 verified

### PR #37 — Sprint 2 Task 1b: Backup cleanup (dev VM + 3-tarball + --no-files)
- Dev VM support via `sudo -n -u frappe bash -c '...'` (SSH user erpadmin ≠ bench user frappe)
- 3-tarball download: database + files-tar + private-files-tar (via `bench backup --with-files`)
- `--no-files` flag preserves Task 1 db-only behavior
- `BackupResult` dataclass +8 fields (files/private-files paths + sha256s)
- 6 new helpers: `_needs_sudo`, `_wrap_for_sudo`, `_build_bench_command`, `_build_ls_command`, `_build_chmod_command`, `_locate_and_download`
- Defensive `chmod 644` on dev (handles 640 perms post-bench-backup-as-frappe)
- Tests: 7 → 12. Suite: 110 → 115

### PR #38 — Sprint 2 Task 1c: Fix audit subcommand routing
- **Bug:** Phase 6C.3 static `_AUDIT_SUBCOMMANDS = frozenset([...])` went stale post-6D/6E/7a. Subcommands registered later (`doctor`, `backup`) fell through to `"help"` default in `_audit_resolve`.
- **Fix:** `_audit_resolve` now checks `main.commands` directly — resolves at invocation time after all `@main.command` decorators have run. Self-correcting going forward.
- 3 new tests in `test_cli.py`
- **Live verified:** `[2026-05-12T07:25:01Z] subcommand=smoke vm=staging exit=2` — smoke now correctly logged as `smoke` (was `help`).
- Suite: 115 → 117

## Architectural Discoveries

### Smoke framework is PRE-BUILT (cli.py L122-160+)
The `smoke <vm>` subcommand was built in an earlier phase. Full MCP handshake (`mcp.initialize`) + `mcp.list_tools` + JSON output mode. Original Sprint 2 Task 2 scope ("smoke test framework") **collapses to live validation only** — gated on Phase 7 OAuth/MCP enablement (HTTP 401 on staging currently — operational issue, not code defect).

### Audit drift bug (Phase 6C.3 → Sprint 2 Task 1c)
Static hard-coded subcommand allowlist silently broke every time a new subcommand was registered. Mis-audit period: from when `doctor` was first registered until 2026-05-12 (Task 1c ship). All `doctor` and `backup` invocations in this window were logged as `subcommand=help`.

**Forensic recovery?** Audit JSONL retains `user`, `args`, `exit_code`, `duration_ms` — only `subcommand` and `vm` were mis-resolved. Re-derivation possible by scanning `args` field. Not done; low value.

## Deferred

| Item | Why | When |
|---|---|---|
| Task 2 live validation | MCP HTTP 401 on staging — OAuth token/auth (ops, not code) | Phase 7 OAuth/MCP enablement track |
| Task 3 (promote action) | Substantial work (~3h) — single coherent PR | Next session |
| Final Sprint 2 closure doc | Combine with Task 3 ship | After Task 3 merges |

## Test Suite Progression

| Milestone | Tests | Delta |
|---|---|---|
| Sprint 1 close | 102 | — |
| Task 1 (PR #36 ship) | 110 | +8 |
| Task 1b (PR #37 ship) | 115 | +5 |
| Task 1c (PR #38 ship) | 117 | +2 |

## Lessons Captured

### L80 — `exit 1` in interactive PowerShell pipeline KILLS THE HOST SESSION
Inside an `if/else` block or pipeline in interactive PowerShell, calling PS builtin `exit` exits the host. `sys.exit(1)` from a Python script piped via `python -` is fine — sets `$LASTEXITCODE` without killing PS. **Use `sys.exit` inside scripts; never `exit` from interactive PS chains.**

### L81 — Patch script "success exit code" without file verification is UNSAFE
Step 61 mock-routing fix script reported success but never wrote to disk. Detected only via Step 66 `Get-Content` inspection after pytest failed in CI. **Going forward, every patch script ends with: (1) re-read modified file region, (2) `print()` showing new content written, (3) `ast.parse()` for Python files (catches all syntax errors, not just nesting/escaping).**

### L82 — PowerShell `Out-File -Encoding utf8` adds UTF-8 BOM by default (PS 5.x)
PR #37 commit message landed with `﻿feat(...)` (U+FEFF BOM). Git accepted but cosmetically ugly in `git log`. **Use `[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))` for BOM-free UTF-8 on any PowerShell version.** PR #38 used this pattern; commit message clean.

## Next Session Kickoff: Task 3 (Promote Action)

**Branch:** `chore/phase7a-sprint2-task3-promote` off latest dev tip

**Phase plan (single PR, ~3h):**

- **A: pat_store** (~30 min) — `infrastructure/pat_store.py` mirroring `secrets_store.py` API without Fernet (PAT is single token; OS keyring is sufficient). Keyring service: `infrabeat-erp-github`, username: `pat`. CLI: `infrabeat-erp github-pat set/get/clear`. Doctor check: `check_github_pat`. ~4 tests.
- **B: github_api** (~60 min) — `infrastructure/github_api.py` using httpx (already dep). Functions: `create_pull_request`, `get_check_runs`, `merge_pull_request`. Error classes: `GitHubError`, `GitHubAuthError`, `GitHubRateLimitError`. Mock-tested via respx (already dev-dep). ~6 tests.
- **C: promote orchestrator** (~60 min) — `application/promote.py` with `do_promote(target: Literal["staging","production"])`. Validates source branch, creates PR, polls CI 5s intervals (10min timeout), squash-merges on green. Production gate: `--confirm` required. `PromoteResult` dataclass. Audit-wrapped automatically by CLI layer (Task 1c fix now correct). ~3 tests.
- **D: CLI + doctor** (~30 min) — `@main.command() def promote(target):` subcommand + `check_github_pat` joins doctor (becomes 9-check).
- **E: live validation** (~10 min) — trivial commit on test branch → `infrabeat-erp promote staging` → verify PR opens + CI runs + merges from CLI flow.
- **F: ship** (~10 min) — commit + push + PR + auto-merge + CI watch.

**End-state goal after Task 3 + Sprint 2 final closure:** Phase 7a MVP "operational layer" complete from code perspective. Smoke + backup + promote all CLI-invokable. TUI hotkeys `[B][S][P]` wired in Sprint 3.

## PRs This Sprint (Open Tracking)

- PR #36 (Task 1) — MERGED 2026-05-12T06:34:36Z
- PR #37 (Task 1b) — MERGED 2026-05-12 (after CI green)
- PR #38 (Task 1c) — MERGED 2026-05-12 (after CI green)
- PR #?? (this checkpoint closure) — opening now
- PR #?? (Task 3) — next session
- PR #?? (final Sprint 2 closure) — bundled with Task 3 ship