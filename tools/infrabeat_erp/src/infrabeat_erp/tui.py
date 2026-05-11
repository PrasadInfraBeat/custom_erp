"""InfraBeat Console TUI - Phase 7a entry point.

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
