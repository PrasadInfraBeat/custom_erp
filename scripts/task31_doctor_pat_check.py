"""Sprint 3 Task 3.1: add check_github_pat to doctor's CHECKS list.

Atomic, self-verifying (L81). Run: python scripts/task31_doctor_pat_check.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCTOR = REPO / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "application" / "doctor.py"
TEST_DOCTOR = REPO / "tools" / "infrabeat_erp" / "tests" / "test_doctor.py"


def main():
    src = DOCTOR.read_text(encoding="utf-8")

    if "def check_github_pat" in src:
        print("ALREADY PATCHED (idempotent skip)")
        return

    # Insert new check function BEFORE CHECKS = [ block
    new_fn = (
        'def check_github_pat() -> CheckResult:\n'
        '    """Check if a GitHub PAT is stored for promote subcommand (Sprint 3 Task 3.1)."""\n'
        '    try:\n'
        '        from ..infrastructure.pat_store import has_pat\n'
        '    except ImportError as exc:\n'
        '        return CheckResult("github-pat", "FAIL", f"pat_store import failed: {exc}")\n'
        '    if has_pat():\n'
        '        return CheckResult(\n'
        '            "github-pat", "PASS",\n'
        '            "PAT stored in keyring (service=infrabeat-erp-github)",\n'
        '        )\n'
        '    return CheckResult(\n'
        '        "github-pat", "INFO",\n'
        '        "PAT not stored (run \'infrabeat-erp github-pat set\' before promote)",\n'
        '    )\n'
        '\n'
        '\n'
    )

    m = re.search(r"^CHECKS\s*=\s*\[", src, re.MULTILINE)
    if not m:
        print("FAIL: CHECKS = [ anchor not found")
        sys.exit(2)
    src = src[:m.start()] + new_fn + src[m.start():]

    # Add check_github_pat to CHECKS list (append before closing bracket)
    m2 = re.search(r"(CHECKS\s*=\s*\[)(.*?)(\])", src, re.DOTALL)
    if not m2:
        print("FAIL: CHECKS list body not found")
        sys.exit(2)
    head, body, tail = m2.group(1), m2.group(2).rstrip(), m2.group(3)
    if not body.endswith(","):
        body += ","
    new_checks = head + body + "\n    check_github_pat,\n" + tail
    src = src[:m2.start()] + new_checks + src[m2.end():]

    DOCTOR.write_text(src, encoding="utf-8")
    after = DOCTOR.read_text(encoding="utf-8")
    assert "def check_github_pat" in after, "function write failed"
    assert "check_github_pat,\n]" in after or "check_github_pat,\n    ]" in after, "CHECKS list update failed"
    ast.parse(after)
    print(f"[1/2] doctor.py: check_github_pat function + CHECKS entry added ({len(after)} bytes)")

    # Append 2 tests to test_doctor.py
    new_tests = (
        "\n\n"
        "# === Sprint 3 Task 3.1: check_github_pat tests ===\n\n\n"
        "def test_check_github_pat_returns_info_when_no_pat(monkeypatch):\n"
        '    monkeypatch.setattr(\n'
        '        "infrabeat_erp.infrastructure.pat_store.has_pat", lambda: False\n'
        '    )\n'
        "    from infrabeat_erp.application.doctor import check_github_pat\n"
        "    r = check_github_pat()\n"
        '    assert r.name == "github-pat"\n'
        '    assert r.status == "INFO"\n'
        "\n\n"
        "def test_check_github_pat_returns_pass_when_pat_stored(monkeypatch):\n"
        '    monkeypatch.setattr(\n'
        '        "infrabeat_erp.infrastructure.pat_store.has_pat", lambda: True\n'
        '    )\n'
        "    from infrabeat_erp.application.doctor import check_github_pat\n"
        "    r = check_github_pat()\n"
        '    assert r.status == "PASS"\n'
    )

    existing = TEST_DOCTOR.read_text(encoding="utf-8")
    if "test_check_github_pat" in existing:
        print("[2/2] test already present (idempotent)")
    else:
        TEST_DOCTOR.write_text(existing + new_tests, encoding="utf-8")
        after_t = TEST_DOCTOR.read_text(encoding="utf-8")
        assert "test_check_github_pat_returns_info_when_no_pat" in after_t
        assert "test_check_github_pat_returns_pass_when_pat_stored" in after_t
        ast.parse(after_t)
        print(f"[2/2] test_doctor.py: 2 tests appended ({len(after_t)} bytes)")

    print("\nAll files written + verified. Run pytest next.")


if __name__ == "__main__":
    main()