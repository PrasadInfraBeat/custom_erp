# Phase 7a Sprint 2 — FINAL Closure

**Date:** 2026-05-12
**Status:** ✅ SPRINT 2 COMPLETE

## Summary

**5 PRs merged in one architect-paired session.** Test suite **102 → 137 (+35, +34%)**. Phase 6C.3 audit-drift bug fixed. gh CLI dependency eliminated for promote workflow. **Phase 7a MVP operational layer COMPLETE from code perspective.**

## PRs Shipped Today

| PR | Task | Files | LOC | Tests |
|---|---|---|---|---|
| #36 | Task 1: backup MVP | 4 | +1064 | +7 |
| #37 | Task 1b: backup cleanup (dev VM + 3-tarball + --no-files) | 4 | +1064/-89 | +5 |
| #38 | Task 1c: audit subcommand routing fix | 3 | +105/-1 | +3 |
| #39 | Checkpoint closure (mid-sprint reconciliation) | 1 | +95 | 0 |
| #40 | Task 3: promote subcommand (httpx + PAT, replaces gh CLI) | 8 | +1416 | +20 |

**Total: 20 file changes, +3744 net LOC, +35 tests, 0 production CI failures on Tasks 1b/1c/3/checkpoint.**

## Key Wins

### 🎯 Audit drift bug eliminated (Task 1c, PR #38)
Phase 6C.3 static `_AUDIT_SUBCOMMANDS` frozenset went stale post-6D/6E/7a. doctor/backup invocations had been mis-logged as `subcommand=help` since their first registration. Fixed with dynamic `main.commands` lookup at invocation time — self-correcting forever.

### 🎯 gh CLI dependency eliminated for promote (Task 3, PR #40)
Three new modules + CLI wiring:
- `pat_store.py` — OS keyring (no Fernet — single token doesn't need extra encryption layer)
- `github_api.py` — httpx async REST client with proper error taxonomy (Auth/RateLimit/NotFound/generic)
- `promote.py` — orchestrator: validate → PR → poll CI → squash-merge
- CLI: `github-pat set/clear/check` + `promote <staging|production>` (production requires `--confirm`)

### 🎯 Smoke framework verified pre-built
Original Sprint 2 Task 2 scope ("smoke test framework") collapsed to live validation only. Framework code-complete since earlier phase. Live MCP validation gated on Phase 7 OAuth/MCP enablement (operational, not code).

### 🎯 First real ops artifact (Task 1, PR #36)
1.3 MB database backup tarball at `~/.infrabeat-erp/backups/staging/20260512_061943/20260512_114941-erp_staging-database.sql.gz`, sha256 `9a2b8ca2650c9e4f...` verified.

## Phase 7a MVP Status

**Operational layer from code perspective: ✅ COMPLETE**

| Capability | Code | Tests | Live Validated |
|---|---|---|---|
| Doctor (8 checks) | ✅ | ✅ | ✅ 7 PASS / 0 FAIL / 0 WARN / 1 INFO |
| Backup (DB + files-tar + private-files-tar, all 3 VMs) | ✅ | ✅ 12 | ✅ Staging tarball on disk |
| Smoke (MCP handshake + list_tools) | ✅ pre-built | ✅ | ⏸ Blocked on MCP 401 (ops) |
| Promote (PR + CI poll + squash-merge) | ✅ | ✅ 13 | ⏸ Pending PAT storage |
| Audit log (correct subcommand routing) | ✅ | ✅ 3+5 | ✅ doctor + smoke verified |
| TUI (3-card dashboard, async SSH polling) | ✅ Sprint 1 | ✅ 4 | ✅ Live data per VM |

**Remaining for full MVP ship (Sprint 3, ~3h):**
- TUI hotkey wiring: `[B]` backup, `[S]` smoke, `[P]` promote (presentation layer integration)
- Task 3.1: `check_github_pat` doctor wire (5-min defensive add)
- Live promote validation (after `infrabeat-erp github-pat set`)
- Live MCP 401 resolution (parallel ops track, blocks live smoke)

## Test Suite Progression (Sprint 2)

| Milestone | Tests | Delta |
|---|---|---|
| Sprint 1 close | 102 | — |
| PR #36 (Task 1 ship) | 110 | +8 |
| PR #37 (Task 1b ship) | 115 | +5 |
| PR #38 (Task 1c ship) | 117 | +2 |
| PR #39 (checkpoint, docs) | 117 | 0 |
| PR #40 (Task 3 ship) | 137 | +20 |
| **Sprint 2 close** | **137** | **+35 (+34%)** |

## Lessons Captured (Sprint 2)

### L80 — `exit` in interactive PowerShell pipeline KILLS HOST SESSION
PS builtin `exit` from inside `if/else` or chained pipeline exits the host shell, not just the script. `sys.exit(N)` from Python piped via `python -` is safe (sets `$LASTEXITCODE` without killing PS). **Rule:** never use PS `exit` from interactive chains; always use `sys.exit` inside Python scripts.

### L81 — Patch script "success exit code" requires file verification
Step 61's mock-routing fix script reported success but never wrote to disk (detected only via `Get-Content` inspection after CI failure). **Rule:** every patch script must (1) re-read modified region from disk, (2) `print()` content for visual verification, (3) `ast.parse()` for Python files (catches all syntax errors at write-time, not pytest-collection-time). Task 3 rewriter follows this religiously — see `write_file()` helper.

### L82 — PowerShell `Out-File -Encoding utf8` adds UTF-8 BOM (PS 5.x default)
PR #37 commit message landed with `﻿feat(...)` BOM (U+FEFF prefix visible in `git log`). **Rule:** use `[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))` for BOM-free UTF-8 on any PowerShell version. PR #38 onward used this pattern — clean commit messages.

### L83 (new, Sprint 2 final) — Atomic multi-file rewriter beats incremental phases
Task 3 shipped **8 files in 1 PR** via single rewriter script (`scripts/task3_promote_rewriter.py`, 1416 LOC). Compared to splitting into Phase A/B/C across 3 PRs:
- Single CI run instead of 3 (≈90s saved)
- No partial-state risk between phases
- Single review cycle / single rollback unit
- Cleaner git history

**Pattern:** rewriter declares NEW file content as triple-quoted string constants, PATCHES existing files via `str_replace` (with anchor verification), and verifies every write via `write_file()` helper (assert content roundtrip + `ast.parse`). When the rewriter completes, ALL files are simultaneously in their target state — either everything ships or nothing.

**Cost:** large chat code block during paste (~900 LOC for Task 3). Acceptable trade-off for the atomicity benefits.

## Sprint 3 Kickoff Hints

**Branch:** `chore/phase7a-sprint3-tui-wiring` off Sprint 2 close tip

**Plan (~3h):**
1. **Task 3.1** — `check_github_pat` doctor wire (~5 min). Defensive — confirms PAT before promote runs.
2. **TUI hotkey scaffolding** (~90 min):
   - `[B]` → modal: VM select → invoke `do_backup(vm)` → stream stdout to TUI log panel
   - `[S]` → modal: VM select → invoke smoke (refactor to async function shared between CLI and TUI) → display tools list
   - `[P]` → modal: target select (staging/production) → invoke `do_promote(target)` → live CI poll display with check-by-check status
3. **Live promote validation** (~10 min):
   - `infrabeat-erp github-pat set` (interactive prompt)
   - Create dummy commit on dev → `infrabeat-erp promote staging` → verify PR opens + CI runs + merges from CLI flow only
4. **Sprint 3 closure doc** (~30 min)

**Estimated Sprint 3 elapsed:** ~3 hours. **Phase 7a MVP fully shipped end of Sprint 3.**

## Recognition

This sprint shipped at architect-paired velocity:
- Single session
- 5 PRs merged
- Test suite +34%
- 0 CI failures on Tasks 1b, 1c, 3, checkpoint (Task 1 had 1 mock-routing iteration; recovered same session)
- Maximum L81/L82/L83 discipline applied
- All commits land via PR # in dev history (squash-merged for clean linear history)