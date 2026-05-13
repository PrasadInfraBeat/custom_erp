"""Phase 7a Sprint 0 Task (E) closure doc update.

Three targeted edits:
  1. Section 4 Task (E): TODO -> COMPLETE with resolution details
  2. Section 3 F3 row: prepend RETRACTED note (doctor confirms all 9 creds present)
  3. Section 6 Change Log: append row for Task E completion

Idempotent: each edit is gated on text-presence check.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs" / "closures" / "21_PHASE_7A_SPRINT_0_CLOSURE.md"

TASK_E_NEW = (
    "### (E) gh CLI device-flow auth repair ✅ COMPLETE (2026-05-11)\n"
    "- Phase 6E.7 closure claimed device-flow auth was operational; empirically false (PR #31 used browser fallback, F1)\n"
    "- Resolution: `gh auth login --hostname github.com --web --git-protocol https` (browser-based OAuth)\n"
    "- Token stored in OS keyring (`gh auth status` reports `Logged in ... (keyring)`)\n"
    "- Verified: `infrabeat-erp doctor` post-auth reports `4 PASS, 0 FAIL, 0 WARN, 1 INFO`\n"
    "- Long-term plan (H4): replace gh CLI with httpx + PAT-in-keyring for PR/issue ops in Sprint 1+"
)

F3_OLD = "| F3 | Only 5 of claimed"
F3_NEW = (
    "| F3 | **RETRACTED (Task D doctor run confirms all 9 present; earlier cmdkey output was display-truncated):** "
    "Only 5 of claimed"
)

CHANGE_LOG_ANCHOR = "| 2026-05-11 | Sprint 0 opened."
CHANGE_LOG_NEW_ROW = (
    "\n| 2026-05-11 | **Task E COMPLETE**: F1 resolved via `gh auth login --web` "
    "(browser OAuth, token in keyring). F3 retraction: doctor confirms all 9 VM creds present. "
    "`infrabeat-erp doctor` reports `4 PASS, 0 FAIL, 0 WARN, 1 INFO`. | Task E execution |"
)


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    original = text
    changes = 0

    pattern = r"### \(E\) gh CLI device-flow auth repair[^\n]*"
    if re.search(pattern, text) and "Task E COMPLETE" not in text:
        text = re.sub(pattern, TASK_E_NEW, text, count=1)
        changes += 1
        print("  edit 1: Task (E) status -> COMPLETE")

    if F3_OLD in text and "RETRACTED" not in text:
        text = text.replace(F3_OLD, F3_NEW, 1)
        changes += 1
        print("  edit 2: F3 row prepended with RETRACTED note")

    if "Task E COMPLETE" not in text or CHANGE_LOG_NEW_ROW.strip() not in text:
        idx = text.find(CHANGE_LOG_ANCHOR)
        if idx > -1 and CHANGE_LOG_NEW_ROW.strip() not in text:
            line_end = text.find("\n", idx)
            text = text[: line_end + 1] + CHANGE_LOG_NEW_ROW + "\n" + text[line_end + 1:]
            changes += 1
            print("  edit 3: change log row appended")

    if text == original:
        print("No changes needed (already up-to-date)")
        return 0

    DOC.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", DOC.relative_to(REPO_ROOT).as_posix()],
        cwd=str(REPO_ROOT),
        check=True,
    )
    print(f"\nApplied {changes} edits to {DOC.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())