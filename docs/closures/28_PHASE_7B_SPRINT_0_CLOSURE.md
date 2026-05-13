# Phase 7b Sprint 0 Closure

**Date:** 2026-05-13
**Duration:** Single session (~5 hours)
**Outcome:** SHIPPED 4 of 6 substantive tasks (A, B, C, D) + F (this doc); E deferred per below.

---

## Tasks Shipped

### Task A — VM provisioning automation (PR #50, dev: 870a5f1 -> 6e13db3)
Greenfield Ansible bootstrap. 9 files under `infra/ansible/` (1 cfg, 3 inventories, 3 playbooks, 1 README, 1 test file with 20 cases). All inventory entries match `04_VM_INVENTORY.md` exactly. Bench user differs dev (frappe) vs staging/production (erpadmin) - asserted in test. Node 18 pinned in bootstrap playbook. SSH keys via ed25519. Test suite: 154 -> 174 (+20).

### Task B — Rollback workflow (PR #51, dev: 6e13db3 -> 6a1fc92)
PR-based revert via GitHub Git Data API (no force-push, audit-trail-preserving). Self-contained `application/rollback.py` (~200 LOC, own httpx async helpers, no `github_api.py` coupling) + CLI subcommand `infrabeat-erp rollback {staging|production}` with `--confirm`/`--dry-run`/`--no-admin` flags + 11 pytest tests via respx covering find_rollback_target paths, dry-run short-circuit, happy-path orchestration, merge-conflict edge, PAT-missing edge. Strategy: walks env tip C2 to first parent C1, creates synthetic commit (tree=C1.tree, parents=[C2]), opens rollback branch + PR, admin-squash-merges. Test suite: 174 -> 185 (+11). Production requires `--confirm` gate.

### Task C — MCP authentication resolution (operational, no code changes)
Root cause: stale OAuth Bearer access_tokens (~1hr TTL). Fixed via existing `infrabeat-erp login <vm>` subcommand from Phase 7a Sprint 2. All 3 VMs validated: dev/staging/production each returning `frappe-assistant-core 2.0.0`, protocol `2025-06-18`, **17 MCP tools** (create_document, get_document, update_document, list_documents, delete_document, submit_document, search_documents, search_doctype, search_link, search, fetch, get_doctype_info, generate_report, report_list, report_requirements, run_workflow, get_pending_approvals). Doctor: **8 PASS, 0 FAIL, 0 WARN, 1 INFO** (up from Phase 7a baseline 4 PASS / 3 FAIL).

### Task D — Production promote dress rehearsal (PR #52, production: 388b6dd -> d32c577)
**First-ever live production promote since Phase 3.** ~6 months of accumulated Phase 4-7a changes landed in one squash commit on production. Mechanism: orchestrator opened PR #52 with `--confirm`; orchestrator CI poll failed on `Block direct pushes to protected branches` ruleset gate (L94); admin-squash-merge via `gh pr merge 52 --admin --squash` bypassed the gate cleanly. Post-merge required `register production` (new client_id `rfg318jtj0`) before `login` + `smoke` succeeded (L95). Final smoke confirms 17 MCP tools live on production - core FAC undisturbed by code update.

### Task E — Console screenshots (DEFERRED)
Decision: defer to Phase 7b Sprint 1 polish cycle. Rationale: (a) screenshots are nice-to-have stakeholder documentation per kickoff, not blocking Sprint 0 success criteria; (b) TUI may evolve in Sprint 1 alongside L94/L95 fixes making early captures stale; (c) prioritizes shipping the headline production promote over secondary documentation in a single session. `docs/phase7b/screenshots/` dir reserved with `.gitkeep` for Sprint 1 captures.

### Task F — This closure document

---

## Lessons Captured (L89-L95)

**L89 — Verify imported project-module APIs before writing client code.**
Memory-name mismatch (assumed `get_pat`, actual `load_pat`) cost 3 patch cycles in Task B. Rule: `Select-String -Pattern '^def |^class '` on target module BEFORE writing imports. Module `infrastructure/pat_store.py` has: `load_pat()` (raises `PatNotFound`), `store_pat`, `has_pat`, `clear_pat`. Service `infrabeat-erp-github`, username `pat`.

**L90 — Sleep 10-15s between `git push` and `gh pr checks --watch`.**
Immediately after push, GitHub Actions workflows have not registered yet, so `--watch` returns "no checks reported" with exit 1. Admin merge is CI-independent so scripts still succeed (PR ships), but the "CI_GREEN" intermediate output line is misleading. `Start-Sleep -Seconds 15` between push and watch closes the race.

**L91 — `throw` in PowerShell does NOT abort subsequent pasted commands in conhost.**
When commands are pasted line-by-line into PS console (as opposed to executed from a .ps1 file), each statement runs independently; `throw` raises an exception for THAT line only, then subsequent lines continue. For atomic abort on paste-style execution: wrap the full sequence in `try { ... } catch { Write-Host .Exception.Message; return }` at the top level, OR save to .ps1 + execute, OR use `if (0 -ne 0) { Write-Host "FAIL"; return }` per gate (note `exit` kills the PS session - avoid in console mode).

**L92 — Frappe OAuth access tokens default ~1hr TTL.**
After any extended dev gap, `infrabeat-erp login <vm>` is the refresh path before any FAC operation. Phase 7b Sprint 1 enhancement candidates: (a) add pre-flight refresh-on-401 retry to `smoke`/`query`/`get`/`describe` subcommands; (b) doctor surface "access_token expiring in <X>m" info check.

**L93 — Production-targeting subcommands require `--allow-production` flag.**
Position: BEFORE subcommand. Pattern: `infrabeat-erp --allow-production <subcmd> production`. Applies to `smoke`, `login`, `register`, `promote`, `rollback`. The flag is a top-level gate at click's root command, not a per-subcommand option. Doctor could surface "production gate flag" as an INFO check.

**L94 — Promote orchestrator's CI-poll filter is incomplete.**
The L87 fix shipped in PR #48 skips `Require approving review` policy gate. It does NOT skip `Block direct pushes to protected branches` (a SECOND ruleset gate that always shows as "failing" on PRs into protected branches by design, regardless of admin bypass). Result: orchestrator-driven promote to production fails CI poll even though admin merge would succeed. Phase 7b Sprint 1 fix: extend the filter list in `application/promote.py` to include all non-actionable policy gate names. Workaround proven during Task D: `gh pr merge <N> --admin --squash` directly (same path as PR #50/#51).

**L95 — Post-merge to production may invalidate OAuth client registration.**
After a production code merge that triggers FAC redeploy on the target VM, the previously-registered OAuth client may stop authenticating ("unknown vm: production" from smoke, ConnectTimeout from login). Recovery: `infrabeat-erp --allow-production register production` mints a new client_id (e.g. `rfg318jtj0`), then `infrabeat-erp --allow-production login production` mints a fresh token. Phase 7b Sprint 1 enhancement candidates: (a) auto-detect post-deploy state and re-register transparently; (b) add `register --force` flag for explicit refresh; (c) doctor "OAuth client liveness" check.

---

## Statistics

| Metric | Phase 7a Close | Phase 7b Sprint 0 Close | Delta |
|---|---|---|---|
| Tests passing | 154 | 185 | +31 (+20%) |
| Doctor health | 4 PASS / 3 FAIL | 8 PASS / 0 FAIL / 1 INFO | +4 PASS / -3 FAIL |
| Lessons captured | L1-L88 | L1-L95 | +7 |
| dev tip | 870a5f1 | 6a1fc92 | +2 PRs (#50, #51) |
| staging tip | 0b32b51 | 0b32b51 | unchanged |
| production tip | 388b6dd | d32c577 | +1 PR (#52) - first promote since Phase 3 |
| PRs shipped | 49 | 53 (this closure PR) | +4 (#50, #51, #52, closure PR) |

---

## Phase 7b Sprint 1 Plan (queued followups)

Priority-ordered, decomposed into shippable units:

1. **L94 fix (highest priority, 1-line)** — extend `application/promote.py` CI-poll filter to include `Block direct pushes to protected branches`. Closes orchestrator path so future promotes don't require manual `gh` fallback. Estimated: 15 min code + 1 test.

2. **L92 enhancement (high)** — pre-flight token refresh on 401 in `smoke`/`query`/`get`/`describe` (auto-retry once after login). Doctor adds "access_token TTL remaining" info check. Estimated: 1 hour.

3. **L95 enhancement (medium)** — `register --force` flag for stale OAuth clients; doctor "OAuth client liveness" probe (HEAD against discovery endpoint). Estimated: 45 min.

4. **Promote 63ms-exit-without-confirm (medium)** — diagnose pre-flight rejection path; improve error message so users know to add `--confirm` for production targets. Likely a 2-3 line fix in CLI argument validation. Estimated: 30 min.

5. **Task E catch-up (low)** — TUI screenshots for stakeholder docs once L94/L95 fixes are merged and TUI is in its Sprint 1 final state. Estimated: 30 min.

---

## Files Changed (Phase 7b Sprint 0 cumulative)

- `infra/ansible/ansible.cfg`
- `infra/ansible/inventory/{dev,staging,production}.yml`
- `infra/ansible/playbooks/{preflight,ssh_keys,bootstrap}.yml`
- `infra/ansible/README.md`
- `tools/infrabeat_erp/src/infrabeat_erp/application/rollback.py`
- `tools/infrabeat_erp/src/infrabeat_erp/cli.py` (rollback subcommand append)
- `tools/infrabeat_erp/tests/test_ansible_inventory.py`
- `tools/infrabeat_erp/tests/test_rollback.py`
- `docs/phase7b/screenshots/.gitkeep`
- `docs/closures/28_PHASE_7B_SPRINT_0_CLOSURE.md` (this doc)

---

## Acknowledgments

Single-session execution mode. Three rounds of paste-corruption recovery validated the L82 gz+b64+SHA pattern and the L86 direct-VS-Code paste fallback. Iteration cycle time reduced ~50% from Phase 7a Sprint 1 despite Phase 7b Sprint 0's higher operational complexity (3 VMs, 3 protected branches, OAuth + 2 ruleset gates, post-deploy state quirks).

**Phase 7b Sprint 0: CLOSED** as of 2026-05-13.