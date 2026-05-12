"""Task 1c: fix audit subcommand routing - resolve at invocation time via main.commands.

Bug: Phase 6C.3 hard-coded _AUDIT_SUBCOMMANDS frozenset went stale; doctor/backup
got mis-audited as 'help'. Fix: delete the frozenset, look up main.commands at
invocation time (after all @main.command decorators have run).

Self-verifying. Run from repo root: python scripts/task1c_audit_routing_fix.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI_P = REPO / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "cli.py"
TEST_P = REPO / "tools" / "infrabeat_erp" / "tests" / "test_cli.py"


def main():
    src = CLI_P.read_text(encoding="utf-8")

    # Patch 1: Remove _AUDIT_SUBCOMMANDS frozenset (3 lines collapse to 1 comment)
    old1 = (
        '_AUDIT_SUBCOMMANDS = frozenset(\n'
        '    ["register", "login", "smoke", "query", "get", "describe", "search"]\n'
        ')\n'
    )
    new1 = (
        '# _AUDIT_SUBCOMMANDS removed in Task 1c: replaced by direct main.commands '
        'lookup in\n# _audit_resolve (resolved at invocation time after all '
        '@main.command decorators run).\n'
    )
    if old1 not in src:
        print("PATCH 1 ANCHOR NOT FOUND (frozenset)")
        sys.exit(2)
    src = src.replace(old1, new1, 1)
    print("  PATCH 1 OK: frozenset removed")

    # Patch 2: Update _audit_resolve to use main.commands
    old2 = "if not positionals or positionals[0] not in _AUDIT_SUBCOMMANDS:"
    new2 = "if not positionals or positionals[0] not in main.commands:"
    if old2 not in src:
        print("PATCH 2 ANCHOR NOT FOUND (resolve check)")
        sys.exit(2)
    src = src.replace(old2, new2, 1)
    print("  PATCH 2 OK: resolve check now uses main.commands")

    CLI_P.write_text(src, encoding="utf-8")

    # Re-read to verify writes (per L81)
    after = CLI_P.read_text(encoding="utf-8")
    assert "_AUDIT_SUBCOMMANDS = frozenset" not in after, "frozenset still present"
    assert "positionals[0] not in main.commands" in after, "main.commands lookup missing"
    print(f"[1/2] cli.py patched and verified ({len(after)} bytes)")

    # Append 3 tests to test_cli.py
    tests = (
        "\n\n"
        "# === Task 1c: audit subcommand routing (post-6C.3 fix) ===\n\n\n"
        "def test_audit_resolve_doctor():\n"
        "    from infrabeat_erp.cli import _audit_resolve\n"
        "    assert _audit_resolve([\"doctor\"]) == (\"doctor\", None)\n\n\n"
        "def test_audit_resolve_backup_with_vm():\n"
        "    from infrabeat_erp.cli import _audit_resolve\n"
        "    assert _audit_resolve([\"backup\", \"staging\"]) == (\"backup\", \"staging\")\n\n\n"
        "def test_audit_resolve_unknown_falls_back_to_help():\n"
        "    from infrabeat_erp.cli import _audit_resolve\n"
        "    assert _audit_resolve([\"unknown-cmd\"]) == (\"help\", None)\n"
    )

    existing = TEST_P.read_text(encoding="utf-8")
    if "test_audit_resolve_doctor" in existing:
        print("[2/2] tests already appended (idempotent)")
    else:
        TEST_P.write_text(existing + tests, encoding="utf-8")
        print(f"[2/2] 3 tests appended to test_cli.py (now {len(existing + tests)} bytes)")

    # Final ast.parse verification
    ast.parse(CLI_P.read_text(encoding="utf-8"))
    ast.parse(TEST_P.read_text(encoding="utf-8"))
    print("[OK] Both files parse cleanly")


if __name__ == "__main__":
    main()