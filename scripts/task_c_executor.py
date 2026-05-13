"""Phase 7a Sprint 0 Task (C) executor: infrabeat console-script + tui.py stub.

Deliverables:
  1. tools/infrabeat_erp/src/infrabeat_erp/tui.py - Sprint-0 stub
  2. tools/infrabeat_erp/pyproject.toml - add `infrabeat = "infrabeat_erp.tui:main"`
                                          to [project.scripts]

Reinstalls editable so the new entry-point registers, then verifies both
console scripts (infrabeat-erp + infrabeat) are findable and runnable.

Idempotent: safe to re-run.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = REPO_ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp"
PYPROJECT = REPO_ROOT / "tools" / "infrabeat_erp" / "pyproject.toml"

TUI_PY_CONTENT = '''"""InfraBeat Console TUI - Phase 7a entry point.

Sprint 0 stub. Real Textual App implementation arrives in Sprint 1+ per
docs/12_INFRABEAT_CONSOLE_SPEC.md (B1-B5 architecture decisions locked).

The `infrabeat` console-script registered via pyproject.toml routes here.
"""
from __future__ import annotations

import sys


def main() -> int:
    """Entry point for the `infrabeat` console script.

    Sprint 0: prints a placeholder banner pointing to the CLI tools that ARE
    operational today. Sprint 1+ replaces this body with Textual App.run()
    per docs/12_INFRABEAT_CONSOLE_SPEC.md.
    """
    print("InfraBeat Console (Phase 7a Sprint 0 stub)", file=sys.stderr)
    print(
        "Full TUI arrives in Sprint 1+ per docs/12_INFRABEAT_CONSOLE_SPEC.md",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    print("For now, use the CLI:", file=sys.stderr)
    print("  infrabeat-erp doctor      (Sprint 0 Task D - pending)", file=sys.stderr)
    print("  infrabeat-erp smoke <vm>", file=sys.stderr)
    print("  infrabeat-erp login <vm>", file=sys.stderr)
    print("  infrabeat-erp register <vm>", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def write_tui() -> bool:
    tui_path = PKG_ROOT / "tui.py"
    if tui_path.exists() and tui_path.read_text(encoding="utf-8") == TUI_PY_CONTENT:
        print(f"Step 1: {tui_path.relative_to(REPO_ROOT).as_posix()} already up-to-date")
        return False
    tui_path.write_text(TUI_PY_CONTENT, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", tui_path.relative_to(REPO_ROOT).as_posix()],
        cwd=str(REPO_ROOT),
        check=True,
    )
    print(f"Step 1: wrote {tui_path.relative_to(REPO_ROOT).as_posix()}")
    return True


def patch_pyproject() -> bool:
    text = PYPROJECT.read_text(encoding="utf-8")
    if "infrabeat_erp.tui:main" in text:
        print("Step 2: pyproject.toml already has infrabeat entry (skip)")
        return False
    match = re.search(
        r"(\[project\.scripts\][^\[]*?)(\n\s*\[|\Z)",
        text,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("No [project.scripts] section found in pyproject.toml")
    section = match.group(1)
    new_section = section.rstrip() + '\n' + 'infrabeat = "infrabeat_erp.tui:main"\n'
    text_new = text.replace(section, new_section, 1)
    if text_new == text:
        raise RuntimeError("Patch produced no change (unexpected)")
    PYPROJECT.write_text(text_new, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", PYPROJECT.relative_to(REPO_ROOT).as_posix()],
        cwd=str(REPO_ROOT),
        check=True,
    )
    print("Step 2: added 'infrabeat = \"infrabeat_erp.tui:main\"' to [project.scripts]")
    return True


def reinstall_editable() -> None:
    print("Step 3: pip install -e (refresh editable + register new entry-point) ...")
    subprocess.run(
        ["pip", "install", "-e", "tools/infrabeat_erp/", "--quiet"],
        cwd=str(REPO_ROOT),
        check=True,
    )
    print("  OK")


def verify_scripts() -> bool:
    print("Step 4: verify console scripts ...")
    all_ok = True
    for script in ["infrabeat-erp", "infrabeat"]:
        path = shutil.which(script)
        if path:
            print(f"  {script}: {path}")
        else:
            print(f"  {script}: NOT FOUND on PATH")
            all_ok = False
    return all_ok


def invoke_stub() -> int:
    print("Step 5: invoke `infrabeat` (stub) to verify it runs ...")
    result = subprocess.run(
        ["infrabeat"],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"  exit code: {result.returncode}")
    out = (result.stdout + result.stderr).strip().splitlines()
    for line in out[:6]:
        print(f"  | {line}")
    return result.returncode


def main() -> int:
    print("=== Phase 7a Sprint 0 Task (C) executor ===\n")
    write_tui()
    print()
    patch_pyproject()
    print()
    reinstall_editable()
    print()
    if not verify_scripts():
        print("\nFATAL: one or more console scripts missing after install")
        return 2
    print()
    rc = invoke_stub()
    print()
    if rc != 0:
        print(f"FATAL: `infrabeat` stub exited {rc}")
        return 3
    print("=== Task (C) complete ===")
    print()
    print("Final staged state:")
    subprocess.run(["git", "status", "--short"], cwd=str(REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())