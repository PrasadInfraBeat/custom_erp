"""InfraBeat TUI entry point - launches the Textual app (or --check no-launch)."""
from __future__ import annotations

import sys


def main() -> int:
    """Entry point for `infrabeat` console-script.

    Supports `--check` / `--version` for CI smoke tests (no TUI launch).
    Otherwise launches the Textual `InfraBeatApp` from presentation/tui_app.py.
    """
    if "--check" in sys.argv or "--version" in sys.argv:
        print("infrabeat (Phase 7a Sprint 1 C1 dashboard, importable + launchable)")
        try:
            from .presentation.tui_app import InfraBeatApp  # noqa: F401
            print("  textual app: import OK")
        except ImportError as exc:
            print(f"  textual app: import FAILED ({exc})", file=sys.stderr)
            return 1
        return 0
    try:
        from .presentation.tui_app import run
    except ImportError as exc:
        print(f"InfraBeat TUI requires textual: {exc}", file=sys.stderr)
        print("Install: pip install -e tools/infrabeat_erp", file=sys.stderr)
        return 1
    return run()


if __name__ == "__main__":
    sys.exit(main())
