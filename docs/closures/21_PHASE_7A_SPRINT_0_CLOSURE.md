
| 2026-05-11 | **Task E COMPLETE**: F1 resolved via `gh auth login --web` (browser OAuth, token in keyring). F3 retraction: doctor confirms all 9 VM creds present. `infrabeat-erp doctor` reports `4 PASS, 0 FAIL, 0 WARN, 1 INFO`. | Task E execution |
# 21 — Phase 7a Sprint 0 Closure: InfraBeat Console MVP Foundations

**Status:** ⏳ IN PROGRESS (Sprint 0 of Phase 7a — InfraBeat Console MVP).
**Date opened:** 2026-05-11
**Working branch:** `chore/phase7a-sprint0` (off `dev` tip `324573f` from PR #31).
**PR target:** Single PR delivering Sprint 0 Tasks (A)-(G) per Phase 7 kickoff scope (~6h estimate).
**Author:** Solo execution session, AI-paired via Claude (chat).

> This is a **running closure doc**. Each Sprint 0 task appends its outcome here as it completes. The final commit before merging the Sprint 0 PR flips status from `⏳ IN PROGRESS` to `✅ SEALED`.

---

## 1. Executive Summary

*(Filled at Sprint 0 close.)*

Sprint 0 establishes the foundations for the InfraBeat Console TUI: resolves the H3 architectural decision (Ansible vs shell-over-SSH), refactors `tools/infrabeat_erp/` source layout to support both the existing CLI and the new TUI per B1, adds the `infrabeat` console-script entry point, builds the `infrabeat doctor` pre-flight check subcommand consuming the 7 P0/P1 findings discovered in Task A, repairs gh CLI device-flow auth (new debt from Phase 7 kickoff), extends CI for the new package layout, and adds `.git_commit_msg.tmp` to `.gitignore`.

---

## 2. Architectural Decisions Resolved

### H3 RESOLVED — shell-over-SSH wins over Ansible

**Date:** 2026-05-11 (Sprint 0 Task A)
**Decision:** All VM orchestration in InfraBeat (CLI + Console) uses **paramiko-over-SSH** with credentials sourced from Windows OS keyring. Ansible is NOT adopted in Phase 7a.

**Empirical evidence** — 10-section staging VM survey via paramiko (Task A recon, `scripts/survey_staging.py`):

| Signal | Reading |
|---|---|
| `ansible` / `ansible-playbook` installed | YES (`ansible-core 2.17.14` at `/usr/local/bin/`) |
| `.ansible/` runtime dir present | YES (touched once, never used in anger) |
| User-created `ansible.cfg` files | **0** (all hits inside `dist-packages/ansible_collections/` examples) |
| User-created playbook `*.yml` files | **0** anywhere on the VM |
| `/home/erpadmin/custom_erp/infra/` directory | **does not exist** (phantom path in kickoff) |
| `infra/` directory anywhere on VM | **does not exist** |
| `roles/` ecosystem | **none** |
| Inventory file | **none** |
| Existing automation pattern | rsync-style via `~/sync-staging/` + `git pull` |

**Rationale:**

1. No existing playbook ecosystem to integrate or preserve — Ansible adoption would mean building from zero.
2. paramiko is already required by Task (B) refactor and Task (D) `infrabeat doctor` — single primitive minimizes dependency surface.
3. Lower cognitive load: no YAML DSL, no inventory maintenance, no Ansible-specific debugging.
4. Decision is **reversible** — Ansible can be adopted incrementally in Phase 7b if a concrete multi-step orchestration use case emerges that paramiko makes painful. The burden of proof for adopting Ansible later must be a specific need, not a doc reference.

**Implications:**

- `tools/infrabeat_erp/src/infrabeat_erp/infrastructure/` houses `ssh.py` (paramiko wrapper) and `keyring_store.py` (credential adapter). **No `ansible/` subpackage created.**
- Task (D) `infrabeat doctor` SSH connectivity check uses `paramiko.SSHClient.exec_command` with timeout; no `ansible -m ping` health check.
- `scripts/survey_staging.py` (Task A artifact) is the canonical pattern reference for paramiko + keyring composition.

---

## 3. P0/P1 Findings (Sprint 0 Discovery)

All findings empirically verified during Task (A) recon. These constitute the **concrete scope for Task (D) `infrabeat doctor`** checks — every P0 finding should be a doctor test that runs in <1s.

| # | Finding | Source of drift | Severity | `doctor` check? |
|---|---|---|---|---|
| F1 | `gh` CLI device-flow auth is NOT operational on this laptop. Phase 6E.7 closure claim that it works is empirically false (PR #31 had to use browser fallback). | Kickoff prompt + `20_PHASE_6E_DEBT_RETIREMENT_CLOSURE.md` §6E.7 | P0 | yes — `gh auth status` exit code |
| F2 | Keyring username convention is `<vm>-<purpose>-password` suffix (verified via `cmdkey /list` ground truth), NOT `<vm>-<purpose>` as `04_VM_INVENTORY.md` claims. Affects all 9 expected credential rows. | `04_VM_INVENTORY.md` Phase 6E.1.5 lines | P0 | yes — credential lookup by exact canonical name |
| F3 | **RETRACTED (Task D doctor run confirms all 9 present; earlier cmdkey output was display-truncated):** Only 5 of claimed "9 VM passwords" present in laptop keyring `infrabeat-vm-creds`: `staging-ssh-password`, `staging-mariadb-root`, `production-mariadb-root`, `dev-admin-password`, plus one anomalous `infrabeat-vm-creds/production-admin-password`. **MISSING:** `dev-ssh-password`, `production-ssh-password`, `staging-admin-password`, `dev-mariadb-root`, `production-admin-password` (under standard naming). | `04_VM_INVENTORY.md` Phase 6E.1.5 + kickoff prompt | **P0** | yes — enumerate all 9 expected credentials by name and report missing |
| F4 | `/home/erpadmin/custom_erp/infra/` directory does not exist on staging VM. Kickoff Task A description references a phantom path. | Phase 7 session kickoff prompt | P0 | n/a — H3 resolution makes this moot |
| F5 | Six (!) stray `custom_erp` clone paths on staging VM: `~/frappe-bench/custom_erp` (suspicious top-level, NOT under `apps/`), `~/frappe-bench/apps/custom_erp` (canonical), `~/frappe-bench/apps/custom_erp/custom_erp` (Frappe v15 module folder — expected), `~/sync-staging/custom_erp`, `~/sync-staging/custom_erp/custom_erp`, `~/sync-staging/custom_erp/custom_erp/custom_erp`. The bench-root clone and the sync-staging tree warrant investigation. | Discovered in Task A survey | P1 | optional — disk-hygiene check |
| F6 | Orphan `claude_doctype.py` + `claude_doctype.py.backup` at top of `apps/custom_erp/` on staging (provenance unclear, predates Sprint 0). Not present in repo `dev` branch. | Discovered in Task A survey | P1 | n/a |
| F7 | Python version mismatch: staging VM runs Python 3.10.12, laptop runs 3.12. `infrabeat` package must target lower bound (3.10) for any VM-side scripts; laptop-side TUI can target 3.12. | Discovered in Task A survey | P2 | yes — Python version reporting |

---

## 4. Task Outcomes (per kickoff scope)

### (A) Ansible inventory recon ✅ COMPLETE (2026-05-11)
- **H3 resolved** → shell-over-SSH (see Section 2)
- Transitional artifact: `scripts/survey_staging.py` (paramiko + keyring + 10-section comprehensive survey). Moves to `tools/infrabeat_erp/scripts/` during Task (B) refactor or is deleted if subsumed by `infrabeat doctor`.
- 7 findings logged (see Section 3)
- Time spent: ~1.5h (vs 0.5h estimate — overage attributable to doc-drift discovery cascade)

### (B) Source layout refactor for B1 — ⏳ TODO
### (C) `infrabeat` console-script entry point + stub `tui.py` — ⏳ TODO
### (D) `infrabeat doctor` subcommand — ⏳ TODO
### (E) gh CLI device-flow auth repair ✅ COMPLETE (2026-05-11)
- Phase 6E.7 closure claimed device-flow auth was operational; empirically false (PR #31 used browser fallback, F1)
- Resolution: `gh auth login --hostname github.com --web --git-protocol https` (browser-based OAuth)
- Token stored in OS keyring (`gh auth status` reports `Logged in ... (keyring)`)
- Verified: `infrabeat-erp doctor` post-auth reports `4 PASS, 0 FAIL, 0 WARN, 1 INFO`
- Long-term plan (H4): replace gh CLI with httpx + PAT-in-keyring for PR/issue ops in Sprint 1+
### (F) CI extension for new package layout — ⏳ TODO
### (G) `.git_commit_msg.tmp` to `.gitignore` — ⏳ TODO

---

## 5. Lessons Learned (Phase 7a additions to L1-L70)

### L71 — Kickoff-prompt operational claims are unreliable

This session: 4 out of 4 verifiable claims in the Phase 7 kickoff prompt were empirically false:

1. `gh` CLI device-flow auth "operational" (F1)
2. Keyring username convention `<vm>-<purpose>` (F2)
3. Keyring entry count "9 VM passwords" (F3)
4. Path `/home/erpadmin/custom_erp/infra/ansible/` exists (F4)

**Meta-lesson reinforced:** empirical verification beats documented state every time. The first action of any new phase session should be an `infrabeat doctor` invocation (Task D scope) that surfaces all drift in <5s.

### L72 — Long terminal paste is structurally unreliable on Windows; use VS Code editor for any content >2KB

PowerShell + Windows Terminal cannot reliably absorb single-line content beyond roughly 3-4KB; the buffer truncates, mangles, or refuses execution. The base64+gzip pattern (L70) extended this ceiling but did not eliminate it.

**Mandatory primitive selection going forward:**
- Content <2KB → PowerShell paste is OK (with base64+gzip if it's a file write)
- Content >2KB or any multi-paragraph markdown → **open the file in VS Code (`code <path>`) and paste into the editor**, then save
- PowerShell is the right tool for git operations, command execution, and short pre-flight queries — not for file content delivery

PowerShell `python -c "..."` with mixed inner quotes is ALSO unsalvageable (separate finding); backslash-escaping does not work because PowerShell uses backtick. The base64+gzip → file → `python script.py` pattern remains correct for Python invocations.

---

## 6. Change Log

| Date | Change | Reference |
|---|---|---|
| 2026-05-11 | Sprint 0 opened. **H3 decision locked: shell-over-SSH wins over Ansible** (Task A complete). 7 P0/P1 findings logged. Lessons L71-L72 captured. Foundation set for Tasks B-G. | Task A survey output via `scripts/survey_staging.py` |