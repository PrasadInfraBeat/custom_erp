"""Phase 7a Sprint 0 Task (F): inject 3 smoke-test steps into CI workflow.

Locks in:
  - infrabeat-erp CLI entry point post-B1 refactor
  - infrabeat TUI entry point (Task C)
  - doctor subcommand registration (Task D)

Idempotent: skip if marker text already present.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"

ANCHOR = "      - name: Run pytest with coverage"

SMOKE = (
    "      - name: Smoke - infrabeat-erp --help (CLI entry post-refactor)\n"
    "        run: infrabeat-erp --help\n"
    "      - name: Smoke - infrabeat (TUI stub, Task C)\n"
    "        run: infrabeat\n"
    "      - name: Smoke - infrabeat-erp doctor --help (Task D subcommand)\n"
    "        run: infrabeat-erp doctor --help\n"
)


def main() -> int:
    patched = 0
    for f in sorted(WF.glob("*.yml")):
        t = f.read_text(encoding="utf-8")
        if "Smoke - infrabeat-erp --help" in t:
            print(f"  (already patched): {f.name}")
            continue
        if ANCHOR not in t:
            print(f"  (anchor missing): {f.name}")
            continue
        new = t.replace(ANCHOR, SMOKE + ANCHOR, 1)
        f.write_text(new, encoding="utf-8", newline="\n")
        subprocess.run(
            ["git", "add", f.relative_to(ROOT).as_posix()],
            cwd=str(ROOT),
            check=True,
        )
        print(f"  PATCHED: {f.relative_to(ROOT).as_posix()}")
        patched += 1
    print(f"\n{patched} workflow file(s) patched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
