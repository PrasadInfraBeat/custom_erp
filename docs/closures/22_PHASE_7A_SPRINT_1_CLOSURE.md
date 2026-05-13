# 22 — Phase 7a Sprint 1 Closure: Live VM Status Dashboard (C1 + C2)

**Status:** ✅ SEALED (2026-05-11)
**Closing branch state:** `chore/phase7a-sprint1` branch contains 5 commits ready for squash-merge to `dev`. Pre-Sprint-1 `dev` tip: `7ae9c32` (Sprint 0 knowledge-sync merge).
**Author:** Solo execution session, AI-paired via Claude. ~6-8 hours actual elapsed (excluding diagnostic detours).

---

## 1. Executive Summary

Sprint 1 delivers the **first operationally-real Console**: a Textual TUI that polls all 3 VMs every 5 seconds via passwordless paramiko SSH and renders live branch / commit / last-deploy data per VM, with graceful degradation when a VM is unreachable. Three foundational primitives ship alongside: SSH key bootstrap (eliminating the password-paste friction class identified as L72), doctor VM-side reachability checks (3 new checks bringing doctor to 8 total), and the async SSH adapter pattern (paramiko + ThreadPoolExecutor + asyncio.run_in_executor) that becomes the canonical primitive for all future Console capabilities.

Five tasks shipped: SSH bootstrap (A), doctor expansion (B), TUI scaffold/C1 (C), live polling/C2 (D), closure doc (E). Pytest baseline grew monotonically: 86 → 90 (+4 doctor) → 94 (+4 TUI scaffold) → 102 (+8 vm-status). Six new lessons captured (L73-L78), including one architectural correction (L76: production VM is actually provisioned — third independent L71 instance this phase).

Phase 7a MVP now stands at ~50% complete: C0 (foundations, Sprint 0) + C1 (static dashboard) + C2 (live polling). Remaining MVP scope: C3 (promote), C4 (production deploy gates), C5 (backup + smoke tests), C7-audit (audit screen). Sprint 2 entry plan in §7 below.

---

## 2. Task Inventory — 5 Commits on `chore/phase7a-sprint1`

| # | Task | Spec Ref | Hours | Commit | Description |
|---|---|---|---|---|---|
| 1 | SSH key bootstrap | (foundational) | 1.5 | `5611642` | ed25519 keypair generated, distributed to dev/staging/production via paramiko one-shot password auth, then verified passwordless. All 3 VMs reachable. |
| 1b | chore: net_diag.py | (diagnostic aid) | 0.3 | `<sha>` | Raw-socket + paramiko-banner diagnostic script. Isolates routing vs SSH transport issues. |
| 2 | Doctor VM-side expansion | (foundational) | 2.0 | `a85ba4e` | Added 3 `check_vm_ssh()` checks per VM. Doctor now reports 8 checks. 4 new unit tests + assertion-count fix. |
| 3 | Textual Console scaffold | C1 | 4.0 | `9836729` | `presentation/tui_app.py` (Textual `App` + `VmCard` widget), 3-card dashboard, 13 hotkeys, `--check` CI smoke. CI workflow updated. |
| 4 | Async SSH polling | C2 | 6.0 | `857601e` | `domain/vm_status.py`, `infrastructure/ssh_adapter.py`, `application/vm_status_poller.py`, tui_app rewrite for reactive rendering. 8 unit tests using `asyncio.run`. |
| 5 | This closure doc | (housekeeping) | 0.5 | (this commit) | Sprint summary, lessons L73-L78, Sprint 2 entry plan. |

---

## 3. File Inventory

**New source files (4):**
- `tools/infrabeat_erp/src/infrabeat_erp/domain/vm_status.py` — `VmStatus` immutable dataclass
- `tools/infrabeat_erp/src/infrabeat_erp/infrastructure/ssh_adapter.py` — async SSH wrapper
- `tools/infrabeat_erp/src/infrabeat_erp/application/vm_status_poller.py` — poll orchestration
- `tools/infrabeat_erp/src/infrabeat_erp/presentation/tui_app.py` — Textual app (rewritten in Task 4 for reactive cards)

**Modified source files (3):**
- `tools/infrabeat_erp/src/infrabeat_erp/application/doctor.py` — +3 imports, +constants, +`check_vm_ssh()` function, run_all extension
- `tools/infrabeat_erp/src/infrabeat_erp/tui.py` — rewrote to support `--check` flag for CI smoke + launch Textual app
- `tools/infrabeat_erp/pyproject.toml` — added `textual>=0.50` to dependencies

**Modified CI (1):**
- `.github/workflows/python-tests.yml` — `infrabeat` smoke test changed to `infrabeat --check` (avoids CI hanging on TUI launch)

**New tests (2 files, 12 tests total):**
- `tools/infrabeat_erp/tests/test_tui_app.py` — 4 tests (title, hotkeys, VmCard fields, run() return)
- `tools/infrabeat_erp/tests/test_vm_status.py` — 8 tests (dataclass, parser, poll error handling, poll_all)

**Modified tests (1):**
- `tools/infrabeat_erp/tests/test_doctor.py` — +4 vm-ssh tests, extended imports, `_5_checks` → `_8_checks` rename + assertion update

**Operational scripts (7 in `scripts/`):** `bootstrap_ssh_keys.py`, `net_diag.py`, `task2_doctor_vm_expansion.py`, `task2_doctor_amend.py`, `task2_test_count_fix.py`, `task3_tui_scaffold.py`, `task4_live_polling.py`. Retained as ops debugging aids and reproducible-build records.

---

## 4. Test Progression

| Checkpoint | Pytest | Doctor live checks |
|---|---|---|
| Sprint 0 close | 86 passed, 1 skipped | 5 (Python, keyring, VM creds, gh CLI, audit dir) |
| Task 2 close | 90 passed, 1 skipped | 8 (+ vm-ssh-dev/staging/production) |
| Task 3 close | 94 passed, 1 skipped | 8 |
| Task 4 close | **102 passed, 1 skipped** | 8 |

**Net Sprint 1 delta: +16 passing tests, no regressions.** Live doctor on this laptop: `7 PASS, 0 FAIL, 0 WARN, 1 INFO` (was 4 PASS / 1 INFO at Sprint 0).

---

## 5. Architectural Decisions Locked

- **A1: paramiko + asyncio.run_in_executor wins over asyncssh.** paramiko is already a dep (used by bootstrap + doctor); asyncssh would be a second SSH stack. `ThreadPoolExecutor(max_workers=6)` shared across all VM polls. Single-cost decision validated by 8 passing tests with mocked adapter.
- **A2: Composite SSH query (one round-trip per poll cycle).** Each `poll_vm()` issues one `cd <repo> && echo BRANCH=$(...) && echo COMMIT=$(...)` command, parsed via `k=v` lines. Avoids 3-roundtrip-per-VM × 3 VMs × every-5-seconds noise.
- **A3: VmStatus dataclass is immutable per-snapshot.** New `VmStatus(timestamp=now, ...)` each poll cycle rather than mutating existing object. Enables `is_stale()` computation against fresh time + clean handoff to UI thread.
- **A4: Reactive UI via `_status` attribute + `self.refresh()`.** Avoided Textual's `reactive()` descriptor due to its strict-typing constraints with `Optional[VmStatus]`. Simpler pattern: card stores latest status, `update_status()` triggers `refresh()`. 
- **A5: 5-second poll interval, configurable via `POLL_INTERVAL_SECONDS` class attribute.** Tradeoff: faster (1s) shows transient state but loads VMs; slower (15s) feels sluggish. 5s matches k9s/Lens convention.
- **A6: Doctor is THE canonical pre-flight tool.** 8 checks cover: Python version, keyring backend, all 9 VM credentials, gh CLI auth, audit dir writability, SSH reachability per VM (× 3). Sprint 0's L71 lesson institutionalized as a runnable contract.
- **A7: SSH key bootstrap is the right ops primitive, not password-per-operation.** L77 below. After single bootstrap, every future operation is passwordless. Massive ergonomic win compounding across the remaining sprints.

---

## 6. Lessons Learned (L73-L78)

### L73 — Test imports must match the existing module's pattern

When extending an existing test file, match the existing import style (function-level `from X import (a, b)` vs module-level `from X.Y import M`). Mixing breaks NameError on the new tests. Diagnosis: read first 20 lines of test file before drafting new tests.

### L74 — Verbatim string replacement beats regex anchors for surgical patches

Sprint 1 Task 2's first executor used regex (`results.append(check_\w+\(\))`) that didn't match the actual code (which used a `CHECKS` constant + loop pattern). Patch silently failed, test file was modified anyway, broken commit landed. Lesson: always use full-context verbatim string replacement, and FAIL the executor (non-zero exit) if any required edit doesn't apply. Marker-based idempotency uses a unique string from `new` content that isn't in `old`.

### L75 — Windows dual-NIC + paramiko first-connect may briefly time out

Laptop has both Ethernet (10.1.1.2) + Wi-Fi (192.168.1.101). Sometimes the first paramiko process briefly tries the wrong interface for routing to 10.1.0.x VMs. Recovers on retry (sub-second). Diagnostic primitive: raw `socket.socket().connect((host, 22))` + banner read in <0.2s confirms transport healthy; if then paramiko also works, the original timeout was transient. `net_diag.py` codifies this check.

### L76 — Production VM (10.1.0.186) IS provisioned

Third L71 instance this phase. Sprint 0 closure doc + kickoff prompt + 04_VM_INVENTORY all claim `production: not yet provisioned`. Empirical reality: SSH lands and `hostname` returns `erp1-virtual-machine`. Naming convention noted: production=erp1, staging=erp2 (counterintuitive — most teams put prod=1, but this deployment reversed it).

### L77 — SSH key bootstrap is the correct ops architecture

Sprint 0 had every operation fetch passwords from `infrabeat-vm-creds` keyring at runtime. This caused: (a) keyring access latency × N operations; (b) password-paste corruption in interactive scripts (L72); (c) inability to compose ops across multiple VMs without re-fetching. After Task 1's bootstrap, every future operation uses key auth — passwordless, fast, paste-free. The bootstrap is one-shot (re-run on key rotation only). Sprint 1's velocity in Tasks 2-4 directly traces to this primitive.

### L78 — paramiko + ThreadPoolExecutor + asyncio.run_in_executor is canonical async SSH

For asyncio code that needs to do SSH: don't reach for asyncssh (different code, different transport quirks, larger surface). Wrap paramiko in `ThreadPoolExecutor(max_workers=N)` and use `loop.run_in_executor(executor, sync_fn, *args)` to bridge. Works across all 8 Sprint 1 tests with simple mock adapters. Pattern documented in `infrastructure/ssh_adapter.py`.

---

## 7. Phase 7a Sprint 2 Entry Plan

Sprint 2 targets **C3 (promote use case) + C5 (backup + smoke tests)** = ~10h scope.

Recommended task ordering:
1. **`infrabeat-erp backup <vm>` subcommand** (~3h, closes H2) — wraps `bench backup --with-files` via SSH, copies tarball to laptop, verifies checksum, stores in `~/.infrabeat-erp/backups/`. Unblocks F3 Gate 2-3 in Sprint 3.
2. **Smoke test framework + Console wiring (`[S]` action)** (~3h, C5 partial) — `infrabeat-erp smoke <vm>` runs HTTP GET + auth check + DB ping; Console `[S]` key calls it and renders pass/fail per VM.
3. **`[P]` Promote dev→staging action wiring** (~4h, C3) — Console `[P]` triggers PR creation via `httpx + PAT-in-keyring` (closes H4, retires gh CLI dependency), waits for CI checks via polling, merges on green. Full pipeline visible in TUI with progress indicators.

**Deferred to Sprint 3:** C4 (production deploy gates), C7-audit (audit screen). Sprint 3 close = Phase 7a MVP fully shipped.

**Open architectural questions** (decide during Sprint 2 design):
- **Backup file location strategy** — laptop only? laptop + cloud (S3)? Trade-off: laptop disk pressure vs cross-laptop recovery.
- **PR auto-merge vs manual** — Sprint 1 used `gh pr merge --auto`. Sprint 2 should pick one path and standardize.
- **Console-from-Console restart** — currently `q` quits the app; should there be a hot-reload mechanism for development?

---

## 8. Change Log

| Date | Event | Reference |
|---|---|---|
| 2026-05-11 | **Phase 7a Sprint 1 SEALED.** All 5 tasks complete. Final state: 102 passed/1 skipped, doctor 7 PASS/1 INFO. Live Console operationally real. Ready for PR review + merge to `dev`. | This document |