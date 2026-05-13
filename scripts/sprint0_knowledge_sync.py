"""Phase 7a Sprint 0 -> Project Knowledge reconciliation.

Updates three Project-Knowledge docs to reflect Sprint 0 SEALED state:
  1. docs/phase7_session_kickoff_prompt.md - dev tip, test baseline, inject Sprint 0 section
  2. docs/00_1_PROJECT_FACTS.md             - dev tip, change-log row
  3. docs/04_VM_INVENTORY.md                - change-log row (keyring confirmation)

Idempotent: skip cleanly if file missing or already patched.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

NEW_DEV_TIP = "cf3a83c"
OLD_DEV_TIPS = ["982c0ba", "324573f"]
NEW_TEST_BASELINE = "86 passed, 1 skipped"
OLD_TEST_BASELINES = ["75 passed, 1 skipped", "70 passed, 1 skipped"]

CHANGE_LOG_FACTS = (
    "| 2026-05-11 | **Phase 7a Sprint 0 SEALED.** All 7 tasks complete in PR #32 squash-merge "
    "(dev tip now `cf3a83c`). H3 architectural decision locked: shell-over-SSH via paramiko wins "
    "over Ansible (staging VM had ansible-core installed but zero user-created playbooks/inventory/config "
    "per 10-section empirical survey). B1 source layout refactored: 6 modules moved into `infrastructure/` "
    "package, 4 new layer packages added (`application/`, `domain/`, `presentation/`, `infrastructure/`). "
    "New `infrabeat-erp doctor` subcommand with 5 pre-flight checks shipped. New `infrabeat` TUI "
    "entry-point stubbed for Sprint 1. F1 resolved: gh CLI auth via browser OAuth works (token in OS "
    "keyring). Pytest baseline: 75 -> 86 passed (+11 doctor tests). Lessons L71-L72 captured in "
    "`docs/closures/21_PHASE_7A_SPRINT_0_CLOSURE.md`. | PR #32 |\n"
)

CHANGE_LOG_VM = (
    "| 2026-05-11 | **Phase 7a Sprint 0 verification.** `infrabeat-erp doctor` confirms all 9 VM "
    "credentials present in `infrabeat-vm-creds` keyring service. Naming convention canonical: "
    "`<vm>-ssh-password`, `<vm>-admin-password`, `<vm>-mariadb-root` (where `<vm>` is `dev`/`staging`/"
    "`production`). Earlier F3 finding (claimed missing entries) RETRACTED post-doctor verification. "
    "Doctor live: `4 PASS, 0 FAIL, 0 WARN, 1 INFO`. | `21_PHASE_7A_SPRINT_0_CLOSURE.md` |\n"
)

SPRINT_0_SECTION_KICKOFF = """
### Phase 7a Sprint 0 status: SEALED (2026-05-11)

All 7 Sprint-0 tasks complete via PR #32 (`cf3a83c`):

| Task | Outcome | Commit |
|---|---|---|
| A | H3 locked: shell-over-SSH wins over Ansible | `ef1d391` |
| B | B1 source layout: 6 modules into `infrastructure/`, 4 new layer packages | `c2f1ab8` |
| C | `infrabeat` console-script + Sprint-0 TUI stub | `ab05a43` |
| D | `infrabeat-erp doctor` subcommand with 5 pre-flight checks + 11 unit tests | `29b87df` |
| E | F1 resolved: gh CLI auth via browser OAuth | `c3bd73b` |
| F | CI extended with 3 smoke tests for new entry points + doctor | `22c8655` |
| G | `.git_commit_msg.tmp` added to .gitignore (L67) | `5c09fdf` |

**New entry points (post B1 refactor):** `infrabeat-erp` (CLI) + `infrabeat` (TUI stub).
**New subcommand:** `infrabeat-erp doctor` — pre-flight checks for Python version, keyring backend,
9 VM credentials, gh CLI auth, audit dir writability. **Run this FIRST at any future session start**
to ground operational assumptions in empirical reality (L71).
**New lessons:** L71 (kickoff-prompt operational claims need empirical verification — 4/4 false this
sprint), L72 (Windows Terminal paste corrupts past ~1500 chars; VS Code editor primitive mandatory
for content >2KB).

"""


def patch_kickoff(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    for old_sha in OLD_DEV_TIPS:
        bt = f"`{old_sha}`"
        if bt in text:
            text = text.replace(bt, f"`{NEW_DEV_TIP}`")
            applied.append(f"dev tip {old_sha} -> {NEW_DEV_TIP}")
    for old_baseline in OLD_TEST_BASELINES:
        bt = f"`{old_baseline}`"
        if bt in text:
            text = text.replace(bt, f"`{NEW_TEST_BASELINE}`")
            applied.append(f"test baseline {old_baseline} -> {NEW_TEST_BASELINE}")
    if "Phase 7a Sprint 0 status: SEALED" not in text:
        for anchor in (
            "**Debt retirement track** (PRs #24-#29 + closure doc #30):",
            "### Phase 6E status: ✅ FULLY SEALED",
            "## Current state",
        ):
            idx = text.find(anchor)
            if idx > -1:
                sep = text.find("\n---\n", idx)
                if sep > -1:
                    text = text[:sep] + "\n" + SPRINT_0_SECTION_KICKOFF + text[sep:]
                    applied.append("Sprint 0 SEALED section injected")
                    break
    return text, applied


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
    for old_sha in OLD_DEV_TIPS:
        bt = f"`{old_sha}`"
        if bt in text:
            text = text.replace(bt, f"`{NEW_DEV_TIP}`")
            applied.append(f"dev tip {old_sha} -> {NEW_DEV_TIP}")
    text, log_applied = append_change_log(text, CHANGE_LOG_FACTS, "Phase 7a Sprint 0 SEALED")
    applied.extend(log_applied)
    return text, applied


def patch_vm(text: str) -> tuple[str, list[str]]:
    text, applied = append_change_log(text, CHANGE_LOG_VM, "Phase 7a Sprint 0 verification")
    return text, applied


def update_file(path: Path, patcher) -> None:
    if not path.exists():
        print(f"  SKIP (not found): {path.relative_to(ROOT)}")
        return
    orig = path.read_text(encoding="utf-8")
    new, applied = patcher(orig)
    if not applied or new == orig:
        print(f"  no changes: {path.relative_to(ROOT)}")
        return
    path.write_text(new, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", path.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    print(f"  PATCHED: {path.relative_to(ROOT)}")
    for a in applied:
        print(f"    - {a}")


def main() -> int:
    print("Phase 7a Sprint 0 -> Project Knowledge reconciliation\n")
    update_file(DOCS / "phase7_session_kickoff_prompt.md", patch_kickoff)
    update_file(DOCS / "00_1_PROJECT_FACTS.md", patch_facts)
    update_file(DOCS / "04_VM_INVENTORY.md", patch_vm)
    print("\nDone. Review with: git diff --cached")
    return 0


if __name__ == "__main__":
    sys.exit(main())