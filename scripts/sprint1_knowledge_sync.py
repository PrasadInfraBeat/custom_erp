"""Phase 7a Sprint 1 -> Project Knowledge reconciliation.

Updates:
  - docs/00_1_PROJECT_FACTS.md (dev tip refs, pytest baseline, Sprint 1 SEALED change-log)
  - docs/04_VM_INVENTORY.md (production hostname correction L76, Sprint 1 row)
  - Any phase7_session_kickoff_prompt.md found via glob (dev tip + baseline refresh)

Idempotent: skip if marker phrase already present.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FACTS = DOCS / "00_1_PROJECT_FACTS.md"
VM_INV = DOCS / "04_VM_INVENTORY.md"

NEW_DEV_TIP = "3819535"
OLD_DEV_TIPS = ["cf3a83c", "7ae9c32"]
NEW_TEST_BASELINE = "102 passed, 1 skipped"
OLD_TEST_BASELINES = ["86 passed, 1 skipped", "94 passed, 1 skipped"]


CHANGE_LOG_FACTS = (
    "| 2026-05-11 | **Phase 7a Sprint 1 SEALED.** All 5 tasks complete via PR #34 squash-merge "
    "(dev tip now `3819535`). C1 (static dashboard) + C2 (live SSH polling) shipped. New primitives: "
    "ed25519 SSH key bootstrap eliminates password-paste friction class (L72 resolved permanently); "
    "doctor expanded to 8 checks (+3 vm-ssh reachability per VM); paramiko + ThreadPoolExecutor + "
    "asyncio.run_in_executor as canonical async SSH pattern. `infrabeat` console-script now launches "
    "a Textual TUI that polls all 3 VMs every 5s rendering branch/commit/age per card. Lessons L73-L78 "
    "captured plus L79 candidate (always update pyproject.toml when adding new imports - Sprint 1's "
    "paramiko-missing-from-deps gap caught only by fresh-Ubuntu CI runner). Pytest baseline: 86 -> 102 "
    "passed (+16 tests). Phase 7a MVP at ~50% (C0+C1+C2 done; C3+C4+C5+C7-audit remaining for "
    "Sprints 2-3). | PR #34 |\n"
)

CHANGE_LOG_VM = (
    "| 2026-05-11 | **Phase 7a Sprint 1 VM-state corrections (L76 + bootstrap).** Production VM "
    "(10.1.0.186) IS provisioned: hostname `erp1-virtual-machine`. Earlier `not yet provisioned` "
    "claim retracted as 3rd L71 instance this phase. Naming convention noted (counterintuitive): "
    "production=erp1, staging=erp2. All 3 VMs verified reachable via passwordless ed25519 SSH "
    "(`~/.ssh/infrabeat_ed25519`) per `scripts/bootstrap_ssh_keys.py`. Canonical hostnames: "
    "dev=`erp-vm` (10.1.0.184), staging=`erp2-virtual-machine` (10.1.0.185), "
    "production=`erp1-virtual-machine` (10.1.0.186). | `22_PHASE_7A_SPRINT_1_CLOSURE.md` |\n"
)


def append_change_log(text: str, new_row: str, marker: str) -> tuple[str, list[str]]:
    if marker in text:
        return text, []
    lines = text.splitlines(keepends=True)
    last = -1
    for i, line in enumerate(lines):
        if line.startswith("| 2026-"):
            last = i
    if last == -1:
        return text, []
    lines.insert(last + 1, new_row)
    return "".join(lines), ["change log row appended"]


def patch_facts(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    for old in OLD_DEV_TIPS:
        if f"`{old}`" in text:
            text = text.replace(f"`{old}`", f"`{NEW_DEV_TIP}`")
            applied.append(f"dev tip {old} -> {NEW_DEV_TIP}")
    for old in OLD_TEST_BASELINES:
        if f"`{old}`" in text:
            text = text.replace(f"`{old}`", f"`{NEW_TEST_BASELINE}`")
            applied.append(f"test baseline {old} -> {NEW_TEST_BASELINE}")
    text, log_applied = append_change_log(text, CHANGE_LOG_FACTS, "Phase 7a Sprint 1 SEALED")
    applied.extend(log_applied)
    return text, applied


def patch_vm(text: str) -> tuple[str, list[str]]:
    return append_change_log(text, CHANGE_LOG_VM, "Phase 7a Sprint 1 VM-state corrections")


def patch_kickoff(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    for old in OLD_DEV_TIPS:
        if f"`{old}`" in text:
            text = text.replace(f"`{old}`", f"`{NEW_DEV_TIP}`")
            applied.append(f"dev tip {old} -> {NEW_DEV_TIP}")
    for old in OLD_TEST_BASELINES:
        if f"`{old}`" in text:
            text = text.replace(f"`{old}`", f"`{NEW_TEST_BASELINE}`")
            applied.append(f"test baseline {old} -> {NEW_TEST_BASELINE}")
    return text, applied


def update_file(path: Path, patcher) -> bool:
    if not path.exists():
        print(f"  SKIP (not found): {path.relative_to(ROOT)}")
        return False
    orig = path.read_text(encoding="utf-8")
    new, applied = patcher(orig)
    if not applied or new == orig:
        print(f"  no changes: {path.relative_to(ROOT)}")
        return False
    path.write_text(new, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", path.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    print(f"  PATCHED: {path.relative_to(ROOT)}")
    for a in applied:
        print(f"    - {a}")
    return True


def main_entry() -> int:
    print("Phase 7a Sprint 1 -> Project Knowledge reconciliation\n")
    print("Patching 00_1_PROJECT_FACTS.md...")
    update_file(FACTS, patch_facts)
    print("\nPatching 04_VM_INVENTORY.md...")
    update_file(VM_INV, patch_vm)

    print("\nSearching for kickoff prompt(s) via glob...")
    candidates = list(ROOT.glob("**/phase7_session_kickoff_prompt*.md"))
    candidates = [c for c in candidates if ".git" not in str(c)]
    if not candidates:
        print("  Not found anywhere (skip)")
    else:
        for kickoff in candidates:
            print(f"  Found: {kickoff.relative_to(ROOT)}")
            update_file(kickoff, patch_kickoff)

    print("\nDone. Review: git diff --cached")
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())