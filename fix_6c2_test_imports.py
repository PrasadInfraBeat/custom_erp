"""fix_6c2_test_imports.py — add 'from infrabeat_erp.cli import main' to test_cli.py
top, re-stage, re-run pytest. Idempotent.

Run from repo root:
    python fix_6c2_test_imports.py
"""
import subprocess
import sys
from pathlib import Path

TEST_CLI = Path("tools/infrabeat_erp/tests/test_cli.py")
IMPORT_LINE = "from infrabeat_erp.cli import main"

if not TEST_CLI.exists():
    sys.exit(f"ERROR: {TEST_CLI} not found. Run from repo root.")

content = TEST_CLI.read_text(encoding="utf-8")

if IMPORT_LINE in content:
    print(f"[SKIP] '{IMPORT_LINE}' already present in {TEST_CLI}")
else:
    # Prepend as the new first line. If existing imports collide, Python allows
    # multiple imports of the same name without conflict.
    TEST_CLI.write_text(IMPORT_LINE + "\n" + content, encoding="utf-8")
    print(f"[OK] Prepended '{IMPORT_LINE}' to {TEST_CLI}")

# Re-stage
subprocess.run(["git", "add", "-A"], check=True)
print("[OK] Re-staged via git add -A")

# Re-run pytest
print("\n[RUN] python -m pytest tools/infrabeat_erp/tests/ --tb=short")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tools/infrabeat_erp/tests/", "--tb=short"],
    capture_output=True,
    text=True,
)

output = (result.stdout or "") + (result.stderr or "")
tail = "\n".join(output.splitlines()[-15:])
print(tail)

if result.returncode != 0:
    print("\n[FAIL] pytest still failing. Inspect tail above.")
    sys.exit(result.returncode)

if "60 passed" not in output:
    print(
        "\n[WARN] pytest passed but '60 passed' not found. "
        "Verify the count manually before commit."
    )
    sys.exit(2)

print("\n[OK] 60 passed, 1 skipped. Gap closed cleanly. Ready to commit.")
