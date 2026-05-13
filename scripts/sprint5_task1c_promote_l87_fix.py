#!/usr/bin/env python
"""Sprint 5 Task 1c: L87 fix - filter 'Require approving review' from promote CI poll.

Atomic rewriter:
  1. Modify promote.py: add SKIP_CHECKS_PROMOTE constant + _filter_failed_checks
     helper + replace inline filter with helper call
  2. Modify test_promote.py: append 5 unit tests
"""

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROMOTE_PY = REPO / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "application" / "promote.py"
TEST_PROMOTE = REPO / "tools" / "infrabeat_erp" / "tests" / "test_promote.py"


def write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    readback = path.read_text(encoding="utf-8")
    assert readback == content, f"Read-back mismatch on {path}"
    ast.parse(readback)
    print(f"  wrote {path.relative_to(REPO)} ({len(content)} bytes, ast OK)")


OLD_POLL_CONSTANTS = '''POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 600


class PromoteError(Exception):'''

NEW_POLL_CONSTANTS = '''POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 600

# L87: Solo-dev cannot self-approve PRs. The GHA "Require approving review" check
# always fails for self-promotes. Filter it out so real CI failures still block
# the promote, but the policy gate does not.
SKIP_CHECKS_PROMOTE: frozenset = frozenset({"require approving review"})


def _filter_failed_checks(check_runs: list[dict]) -> list[dict]:
    """Return failed check_runs excluding policy gates that cannot pass via CI alone.

    A check_run is "failed" when:
      - status == "completed"
      - conclusion NOT in {"success", "skipped", "neutral"}
      - name (case-insensitive) NOT in SKIP_CHECKS_PROMOTE
    """
    return [
        cr for cr in check_runs
        if cr.get("status") == "completed"
        and cr.get("conclusion") not in ("success", "skipped", "neutral")
        and (cr.get("name") or "").lower() not in SKIP_CHECKS_PROMOTE
    ]


class PromoteError(Exception):'''


OLD_INLINE_FILTER = '''        non_success = [
            cr for cr in check_runs
            if cr.get("status") == "completed"
            and cr.get("conclusion") not in ("success", "skipped", "neutral")
        ]'''

NEW_INLINE_FILTER = '''        non_success = _filter_failed_checks(check_runs)'''


def patch_promote():
    content = PROMOTE_PY.read_text(encoding="utf-8")
    assert OLD_POLL_CONSTANTS in content, "MISSING anchor: poll constants"
    assert OLD_INLINE_FILTER in content, "MISSING anchor: inline filter"
    content = content.replace(OLD_POLL_CONSTANTS, NEW_POLL_CONSTANTS)
    content = content.replace(OLD_INLINE_FILTER, NEW_INLINE_FILTER)
    assert "SKIP_CHECKS_PROMOTE" in content
    assert "_filter_failed_checks" in content
    assert OLD_INLINE_FILTER not in content
    write_file(PROMOTE_PY, content)


TEST_APPEND = '''


# === L87 fix: _filter_failed_checks tests ===

from infrabeat_erp.application.promote import _filter_failed_checks


def test_filter_returns_empty_when_all_success():
    runs = [
        {"name": "lint", "status": "completed", "conclusion": "success"},
        {"name": "pytest", "status": "completed", "conclusion": "success"},
    ]
    assert _filter_failed_checks(runs) == []


def test_filter_passes_through_real_failures():
    runs = [
        {"name": "lint", "status": "completed", "conclusion": "success"},
        {"name": "pytest", "status": "completed", "conclusion": "failure"},
    ]
    result = _filter_failed_checks(runs)
    assert len(result) == 1
    assert result[0]["name"] == "pytest"


def test_filter_excludes_require_approving_review():
    runs = [
        {"name": "lint", "status": "completed", "conclusion": "success"},
        {"name": "Require approving review", "status": "completed", "conclusion": "failure"},
    ]
    assert _filter_failed_checks(runs) == []


def test_filter_excludes_review_check_case_insensitive():
    runs = [
        {"name": "REQUIRE APPROVING REVIEW", "status": "completed", "conclusion": "failure"},
        {"name": "require approving review", "status": "completed", "conclusion": "failure"},
    ]
    assert _filter_failed_checks(runs) == []


def test_filter_combines_real_failure_with_policy_gate():
    runs = [
        {"name": "Require approving review", "status": "completed", "conclusion": "failure"},
        {"name": "pytest", "status": "completed", "conclusion": "failure"},
    ]
    result = _filter_failed_checks(runs)
    assert len(result) == 1
    assert result[0]["name"] == "pytest"
'''


def patch_test_promote():
    content = TEST_PROMOTE.read_text(encoding="utf-8")
    content = content.rstrip() + TEST_APPEND
    write_file(TEST_PROMOTE, content)


def main() -> int:
    print("=== Sprint 5 Task 1c: L87 fix - filter 'Require approving review' ===\n")
    print("1. Patching promote.py...")
    patch_promote()
    print()
    print("2. Patching test_promote.py (+5 unit tests)...")
    patch_test_promote()
    print()
    print("=== SUCCESS ===")
    print("Next: cd tools/infrabeat_erp; python -m pytest tests/test_promote.py -v")
    return 0


if __name__ == "__main__":
    sys.exit(main())