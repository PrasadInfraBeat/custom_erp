"""Phase 7a Sprint 0 SEAL: mark Tasks F + G complete, status -> SEALED, fill exec summary."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "closures" / "21_PHASE_7A_SPRINT_0_CLOSURE.md"

REPLACEMENTS = [
    (
        "**Status:** ⏳ IN PROGRESS (Sprint 0 of Phase 7a — InfraBeat Console MVP).",
        "**Status:** ✅ SEALED (2026-05-11) — all 7 tasks complete on `chore/phase7a-sprint0`.",
    ),
    (
        "*(Filled at Sprint 0 close.)*\n\nSprint 0 establishes",
        (
            "Sprint 0 is **SEALED**. All 7 tasks complete in 7 commits on `chore/phase7a-sprint0`:\n\n"
            "| Task | Outcome | Commit |\n"
            "|---|---|---|\n"
            "| A | H3 locked: shell-over-SSH wins over Ansible (zero playbook ecosystem on staging) | `ef1d391` |\n"
            "| B | B1 source layout migration: 6 modules into `infrastructure/`, 4 new layer packages | `c2f1ab8` |\n"
            "| C | `infrabeat` console-script + Sprint-0 TUI stub | `ab05a43` |\n"
            "| D | `infrabeat-erp doctor` subcommand with 5 pre-flight checks + 11 unit tests | `29b87df` |\n"
            "| E | F1 resolved: gh CLI auth via browser OAuth, token stored in OS keyring | `c3bd73b` |\n"
            "| F | CI extended with 3 smoke tests for new entry points + doctor | `22c8655` |\n"
            "| G | `.git_commit_msg.tmp` added to .gitignore (L67) | `5c09fdf` |\n\n"
            "**Test baseline:** 75 passed/1 skipped at Sprint open → **86 passed/1 skipped at Sprint close** "
            "(+11 new doctor tests). **Live doctor:** `4 PASS, 0 FAIL, 0 WARN, 1 INFO`.\n\n"
            "**Phase 7a Sprint 1 opens next:** SSH key-based auth bootstrap (eliminates password-paste "
            "friction surfaced in L72), replace gh CLI with httpx+PAT (H4 long-term plan), expand doctor "
            "with VM-side checks (SSH connectivity, FAC service status, sudoers, Python version probe per VM).\n\n"
            "Sprint 0 establishes"
        ),
    ),
    (
        "### (F) CI extension for new package layout — ⏳ TODO",
        (
            "### (F) CI extension for new package layout ✅ COMPLETE (2026-05-11)\n"
            "- Added 3 smoke-test steps to `.github/workflows/python-tests.yml`:\n"
            "  - `infrabeat-erp --help` (locks the CLI entry post-B1 refactor)\n"
            "  - `infrabeat` (locks the TUI stub entry from Task C)\n"
            "  - `infrabeat-erp doctor --help` (locks the doctor subcommand from Task D)\n"
            "- Smoke tests run between install and pytest in CI matrix\n"
            "- Doctor uses `--help` (not bare invocation) since CI env lacks keyring + gh auth\n"
            "- Helper: `scripts/task_f_ci_patch.py`"
        ),
    ),
    (
        "### (G) `.git_commit_msg.tmp` to `.gitignore` — ⏳ TODO",
        (
            "### (G) `.git_commit_msg.tmp` to `.gitignore` ✅ COMPLETE (2026-05-11)\n"
            "- Added L67-mitigation entry to `.gitignore`\n"
            "- Prevents accidental commit of gh CLI's commit-message temp file (origin: Phase 6E debt)"
        ),
    ),
]

CHANGE_LOG_SEAL = (
    "\n| 2026-05-11 | **Sprint 0 SEALED**. All 7 tasks complete. "
    "Final state: 86 passed/1 skipped, `infrabeat-erp doctor` reports `4 PASS, 0 FAIL, 0 WARN, 1 INFO`. "
    "Ready for PR review + merge to `dev`. | Sprint 0 closure |"
)


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    orig = text
    applied = 0
    for old, new in REPLACEMENTS:
        if old in text:
            text = text.replace(old, new, 1)
            applied += 1
            print(f"  applied: {old[:55]}...")
        else:
            print(f"  SKIP (not found or already replaced): {old[:55]}...")
    if "Sprint 0 SEALED" not in text:
        anchor = "| 2026-05-11 | **Task E COMPLETE**"
        idx = text.find(anchor)
        if idx > -1:
            le = text.find("\n", idx)
            text = text[: le + 1] + CHANGE_LOG_SEAL + "\n" + text[le + 1 :]
            applied += 1
            print("  applied: change log SEAL row")
    if text == orig:
        print("No changes (already sealed?)")
        return 0
    DOC.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", DOC.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    print(f"\nSEALED {DOC.relative_to(ROOT).as_posix()} ({applied} edits)")
    return 0


if __name__ == "__main__":
    sys.exit(main())