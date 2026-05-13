"""Phase 7a Sprint 0 Task (D) cli.py patch: append doctor Click command.

cli.py uses Click, not argparse. Pattern: @main.command() decorators.
Doctor command imports from .application.doctor and delegates.
Idempotent: skip if 'def doctor(' already present.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "cli.py"

DOCTOR_BLOCK = '''

@main.command()
@click.option("--verbose", "-v", is_flag=True, help="Show remediation hints for all checks")
def doctor(verbose: bool) -> None:
    """Run pre-flight checks for InfraBeat operational state.

    Sprint 0 MVP: 5 checks (Python, keyring backend, VM credentials, gh CLI, audit dir).
    Reports drift surfaced in docs/closures/21_PHASE_7A_SPRINT_0_CLOSURE.md.
    """
    from .application.doctor import main as _doctor_main
    import sys as _sys
    _sys.exit(_doctor_main(verbose=verbose))
'''


def main() -> int:
    text = CLI.read_text(encoding="utf-8")
    if "def doctor(" in text:
        print("cli.py already has doctor command - skip")
        return 0
    text = text.rstrip() + DOCTOR_BLOCK
    CLI.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", CLI.relative_to(REPO_ROOT).as_posix()],
        cwd=str(REPO_ROOT),
        check=True,
    )
    print("Appended doctor Click command to cli.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
