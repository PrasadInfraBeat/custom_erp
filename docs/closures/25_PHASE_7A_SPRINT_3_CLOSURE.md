# Phase 7a Sprint 3 — Closure (Partial — Task 3.1 SHIPPED)

**Date:** 2026-05-12
**Status:** ✅ Task 3.1 SHIPPED (PR #42). TUI wiring + live promote validation DEFERRED to Sprint 4.

## Summary

Sprint 3 launched on top of Sprint 2 close (dev tip `c0fb590`). Shipped Task 3.1 (`check_github_pat` doctor wire). Doctor now reports **9 checks** (was 8). Test suite **137 → 139**.

## PRs Shipped Sprint 3

| PR | Task | Files | LOC | Tests |
|---|---|---|---|---|
| #42 | Task 3.1: `check_github_pat` doctor wire | 3 | +148 | +2 |

## Day Recap (Sprint 2 + Sprint 3 combined)

**8 PRs merged in one session (counting this closure):**
- PR #36 — Task 1: backup MVP
- PR #37 — Task 1b: backup cleanup (dev VM + 3-tarball + --no-files)
- PR #38 — Task 1c: audit subcommand routing fix
- PR #39 — Sprint 2 checkpoint closure
- PR #40 — Task 3: promote subcommand (httpx + PAT, replaces gh CLI)
- PR #41 — Sprint 2 final closure
- PR #42 — Task 3.1: `check_github_pat` doctor wire
- PR #43 — Sprint 3 closure (this PR)

**Test suite: 102 → 139 (+36%, +37 tests)**

## Deferred to Sprint 4

| Item | Why deferred | Scope |
|---|---|---|
| Task 3.2 — TUI hotkey wiring `[B][S][P]` | Substantial (~150 LOC + Textual modals + async workers + Pilot tests) | Wire `action_backup/action_smoke/action_promote` in `tui_app.py` to call `do_backup`/smoke/`do_promote`; add `VmSelectModal` + `TargetSelectModal` + `Log` widget for streaming output |
| Task 3.3 — Live promote validation | Quick (10 min) but most efficient after Task 3.2 lands | `infrabeat-erp github-pat set` then create dummy commit then `infrabeat-erp promote staging` then verify real PR + CI + merge |
| Task 2 — Live MCP smoke on all 3 VMs | MCP HTTP 401 on staging — OAuth/auth ops issue (not code) | Parallel Phase 7 OAuth/token track |

## Lessons Captured (Sprint 3 net additions)

### L84 — `pytest 2>&1 | Select-Object -Last N` swallows pytest's non-zero exit code
PowerShell's `$LASTEXITCODE` after a pipe reflects the LAST command in the pipeline. `Select-Object` always exits 0. **Result:** broken pytest passed the `if ($LASTEXITCODE -eq 0)` gate in Step 99c, allowing a known-failing commit to be pushed. The CI failure then required several diagnostic rounds.

**Rule:** when pytest's exit code is needed for downstream guards, use one of:
- Capture exit code BEFORE the pipe: `python -m pytest ... ; $code = $LASTEXITCODE ; ... | Select-Object ; if ($code -eq 0) {...}`
- Wrap pytest in a subprocess from Python: `python -c "import subprocess, sys; sys.exit(subprocess.run([...]).returncode)"`
- Drop the Select-Object pipe entirely (full output is acceptable for non-interactive CI gates)

### L85 — Working-tree-matches-HEAD ≠ "nothing was changed"
After Step 100 reported PATCH FAILED (regex didn't match `_8_checks`), the file was already at the correct `_9_checks` state. Without checking both `git status --short` AND `git diff HEAD -- <file>`, we couldn't immediately tell whether (a) the local file had uncommitted edits, (b) an earlier amend had silently happened, or (c) the file was correct from the start.

**Rule:** when diagnosing a "is the fix in or not" question, always check **both** `git status --short` (uncommitted changes) **and** `git diff HEAD -- <path>` (working-tree vs HEAD) for the specific file before concluding state. Add `git show HEAD:<path>` for definitive committed-content inspection.

## Sprint 4 Kickoff Plan

**Branch:** `chore/phase7a-sprint4-task1-tui-wiring` off dev (Sprint 3 close tip)

**Phases (~2.5h total):**

1. **TUI structural deep-read** (~10 min) — full inspection of `tui_app.py` (213 LOC currently)
   - All action_* methods are stubs; BINDINGS already declared with `[B][S][P]` keys
   - `compose()` method renders 3 VmCard widgets — need to ADD a Log widget for output streaming
   - Async polling worker pattern already established (Sprint 1 Task 4)

2. **action handler real implementations** (~60 min):
   - `action_backup`: push VmSelectModal → on selection, `@work(exclusive=True)` spawn → await `do_backup(vm)` → stream stdout to Log widget → notify on completion
   - `action_smoke`: same pattern with smoke flow (refactor smoke from sync CLI to async function shared between CLI and TUI)
   - `action_promote`: push TargetSelectModal → on selection (with confirm gate for production) → `@work` spawn `do_promote(target)` → live CI poll progress → notify with PR URL

3. **ModalScreen subclasses** (~30 min) — `VmSelectModal` (3 buttons), `TargetSelectModal` (2 buttons + confirm checkbox for production)

4. **Tests** (~30 min) — Pilot-based TUI tests OR direct unit tests on action handlers via monkey-patched `do_backup`/`do_promote`

5. **Live promote validation** (~10 min) — `infrabeat-erp github-pat set` interactive → create dummy commit → `infrabeat-erp promote staging` → verify real PR opens + CI runs + merges from CLI flow alone

6. **Sprint 4 closure** (~20 min) — final closure doc + Phase 7a MVP shipped declaration

## Recognition

Today shipped at architect-paired velocity:
- **8 PRs across Sprints 2+3**
- **Test suite +36%** (102 → 139)
- **Audit drift fixed** (mis-logging since 6E eliminated)
- **gh CLI dependency eliminated** for promote
- **First real ops artifact:** 1.3 MB staging DB tarball with sha256 verified
- **6 architectural lessons captured** (L80 → L85)

**Architect-grade close:** ship today's wins, defer high-mental-load TUI work to fresh Sprint 4 session for quality and speed.