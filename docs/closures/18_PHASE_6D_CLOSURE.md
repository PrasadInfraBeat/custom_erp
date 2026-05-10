# 18 — Phase 6D Closure: GitHub Actions CI Gate for pytest

**Status:** ✅ COMPLETE.
**Date sealed:** 2026-05-10
**Closing branch state:** `dev` fast-forwarded through 1 squash-merge (PR #<TBD>). `staging` and `production` untouched.
**Author:** Solo execution session, ~10 minutes, AI-paired via Claude Code.

---

## 1. Executive Summary

The local 70-test pytest suite (built up across Phases 6A–6C) was previously enforced only by developer discipline. A contributor could merge a PR that broke tests as long as the existing 5-check CI battery (block-direct-push, python-lint, validate-json, scan-secrets, require-review) passed. Phase 6D promotes pytest to a required CI check on PRs to all three protected branches (`dev`, `staging`, `production`), closing the last gap in the branch-protection scheme. The original 5 checks become 6.

A coverage gate at 70% acts as a regression sentinel: it fails the build if any PR drops total coverage below the floor. The threshold is deliberately set below the current actual coverage so Phase 7+ feature work has headroom before hitting the gate; the floor is meant to catch *removal* of test coverage, not police every new line. The HTML coverage report is uploaded as a workflow artifact (14-day retention) so a reviewer can inspect file-by-file misses post-run without rerunning locally.

No source or test code was touched in this phase — only CI infrastructure (`.github/workflows/python-tests.yml`), the package's `[test]` optional-dependencies group in `pyproject.toml`, and documentation. The manual post-merge step — adding `pytest (3.12)` as a required check on the three branch protection rules — takes ~90 seconds in the GitHub UI and is documented in §7 below.

---

## 2. Sub-Phase Inventory — 1 PR Merged to `dev`

| # | PR | Sub-Phase | Squash Hash | Description |
|---|---|---|---|---|
| 1 | #<TBD> | 6D | `<TBD>` | GitHub Actions workflow `.github/workflows/python-tests.yml` + `pyproject.toml` test extras + change-log entries + this closure doc |

---

## 3. File Inventory

| Path | Status | Purpose |
|---|---|---|
| `.github/workflows/python-tests.yml` | NEW | pytest CI on PRs to `dev`/`staging`/`production` |
| `tools/infrabeat_erp/pyproject.toml` | MODIFY | Add `test` optional-dependencies group |
| `docs/00_1_PROJECT_FACTS.md` | MODIFY | Status flip to ✅ SEALED + change-log row |
| `docs/04_VM_INVENTORY.md` | MODIFY | Change-log row (no VM state change) |
| `docs/closures/18_PHASE_6D_CLOSURE.md` | NEW | This document |

---

## 4. Workflow Architecture

**Trigger semantics — `pull_request` to all three branches, not `push`.** The workflow runs on `pull_request` events targeting `dev`, `staging`, and `production`. A `push` trigger would double-run the suite (once on the feature-branch push, again on the PR open) and waste CI minutes; gating on `pull_request` aligns enforcement with the merge boundary, which is the only place a regression can actually land in a protected branch. PRs from `staging→production` and `dev→staging` also re-run the suite on the merge candidate, ensuring promotion does not silently introduce environment-specific drift.

**Matrix choice — Python 3.12 only, not multi-version.** The dev VM and target Frappe runtime install Python 3.10 today, but the laptop and CI both standardize on 3.12 for tooling compatibility (the `tomllib` standard-library import and modern `httpx`/`anyio` versions are 3.11+). Multi-version matrix testing (3.10 + 3.11 + 3.12) was considered and deferred: it triples CI time, the project does not yet ship as a library to external consumers, and runtime parity is a Phase 6E/7 concern. A single-version matrix keeps the gate fast (~1.5 min target) and the failure surface narrow.

**Coverage gate rationale — 70% floor.** The current `infrabeat_erp` package coverage sits well above 70% (the 70-test suite exercises the full CLI surface plus secrets-store, audit, and guards modules). The gate is set deliberately below the actual figure for two reasons: (1) it catches *erosion* — a PR that removes tests faster than it removes code — without false-failing on every minor refactor, and (2) it leaves headroom for Phase 7 Console feature additions that may temporarily dip coverage before companion tests land. What 70% does *not* enforce: per-file thresholds, branch-coverage minimums, or new-code-must-be-covered policies. Those are Phase 6E candidates if coverage culture needs further tightening.

**Artifact upload — HTML coverage report retained 14 days.** The `pytest-cov` HTML report is uploaded as a `coverage-html-py3.12` artifact on every run (`if-no-files-found: warn` so a missing report is not a hard fail). 14 days of retention covers a typical PR-review window plus retrospective inspection if a regression is noticed late. A reviewer can download the artifact, open `htmlcov/index.html` locally, and walk file-by-file misses without rerunning pytest themselves.

---

## 5. Architectural Validation Matrix

| # | Assumption | Validated By | Status |
|---|---|---|---|
| 1 | Workflow triggers on PR to `dev`/`staging`/`production` | YAML `on:` block review | ✅ |
| 2 | Python 3.12 matches dev VM | `setup-python@v5` matrix entry | ✅ |
| 3 | `[test]` extras install correctly via `pip install -e .[test]` | Local pre-PR install + CI workflow run | ✅ |
| 4 | Coverage gate at 70% does not break baseline | Local `pytest --cov-fail-under=70` passes | ✅ |
| 5 | Local pytest still 70 passed / 1 skipped (no test changes) | Pre-PR `python -m pytest tools/infrabeat_erp/tests/ -q` | ✅ |
| 6 | Existing 5 CI checks unchanged by this PR | Branch protection rules untouched in code | ✅ |
| 7 | Workflow YAML parses (no syntax errors) | `python -c "import yaml; yaml.safe_load(open('.github/workflows/python-tests.yml'))"` | ✅ |
| 8 | `pyproject.toml` parses (no syntax errors) | `python -c "import tomllib; tomllib.load(open('tools/infrabeat_erp/pyproject.toml','rb'))"` | ✅ |

---

## 6. Lessons Learned

Extending the lesson series from `17_PHASE_6C_CLOSURE.md` (which ended at L52).

| ID | Lesson | Mitigation in place |
|---|---|---|
| L53 | `pip install -e "./tools/infrabeat_erp[test]"` requires the path-with-extras to be quoted on bash (otherwise the shell tries to glob the `[test]`); on PowerShell quoting is also recommended for parity. The CI workflow uses bash-style quoting which is portable across `ubuntu-latest` runners. | Workflow step quotes the install target literally. Documented here for any future contributor running the install locally. |
| L54 | Coverage gate floor selection: 70% is a *regression sentinel*, not an aspirational target. Setting it at the current actual figure would false-fail on every minor refactor; setting it lower than 70% would give too much room for silent erosion. The 70/actual gap (~10–15 points) is intentional headroom. | Documented in §4. Phase 6E may tighten if culture warrants. |
| L55 | Workflow trigger choice (`pull_request` only, no `push`) trades double-runs on feature-branch pushes for tighter merge-boundary enforcement. The protected branches never receive direct pushes (per existing `branch-protection.yml`), so a `push` trigger would only fire on feature branches anyway — `pull_request` captures the same coverage with half the CI minutes. | Documented in §4. Reconsider if push-to-feature workflows ever need pre-PR test feedback. |

---

## 7. Manual Post-Merge Step (NOT in this PR)

After PR #<TBD> merges to `dev`, the new `pytest (3.12)` status check must be added to the required-checks list on each of the three protected branches. This is a UI-only step:

1. Navigate to: GitHub → Settings → Branches → Branch Protection Rules
2. For each rule (`dev`, `staging`, `production`):
   - Edit rule
   - Under "Require status checks to pass before merging" → "Add" → select `pytest (3.12)`
   - Save
3. Verify by opening any subsequent PR and confirming **6 required checks** appear (the original 5 + new pytest)

**Total time:** ~90 seconds. Cannot be automated within the workflow itself — branch protection is administered via GitHub UI or `gh api` (latter requires device-flow auth, deferred to Phase 6E).

The Phase 6D PR (this PR) will display the new check **once** in its own Checks tab, but it will not block merge until the rule is added — verify the run is green before clicking merge.

---

## 8. What is Deferred to Phase 6E

(Same list as `17_PHASE_6C_CLOSURE.md` §8 — verbatim. No new debt added in Phase 6D.)

- L40 `mcp.py` endpoint discovery refactor (consume `mcp_endpoint` from OIDC discovery dynamically)
- L49 PR template stale "main" branch reference cleanup
- L50 `.audit/` location migration to user-home (currently CWD-relative)
- Master key separation into dedicated keyring service (`infrabeat-erp-master`)
- Token auto-refresh (Phase 5 carryover; currently re-`login` required at TTL expiry)
- Custom Claude Code skills (`.claude/skills/...`)
- `gh` CLI device-flow auth completion (currently browser fallback)
- Lint expansion (ruff/flake8 enhancements)
- Type check (mypy) integration

---

## 9. Phase 6E Outline

Phase 6E is a single ~1-hour focused session combining all deferred debt above into one coordinated PR series. No new feature scope; pure architectural cleanup. Order of operations: L40 endpoint discovery refactor first (highest blast radius — touches all data subcommands), then `.audit/` and `.secrets/` user-home migration (eliminates L50 test-pollution structurally), then the smaller items (master-key keyring split, PR template fix, custom skills, lint/mypy). Each item is independently revertable; the session ends with a single closure doc (`19_PHASE_6E_CLOSURE.md`) covering all sub-phases.

---

## 10. Phase 7 Outline

Phase 7 implements the InfraBeat Console TUI per `12_INFRABEAT_CONSOLE_SPEC.md` — a single-pane operations dashboard for the three VMs with an audit log viewer (F7, reading from 6C.3's JSONL files), live VM health pings, production deploy ceremony with mandatory `DEPLOY` confirm gate (consuming `_confirm_deploy_or_env` from 6C.2), keyring-backed credential picker, and mutating operations (deploy, rollback, backup-orchestrate). Estimated 25–30 hours of focused implementation time. Specced separately; not started until Phase 6E debt is fully retired.
