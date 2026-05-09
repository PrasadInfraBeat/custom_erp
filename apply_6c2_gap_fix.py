"""apply_6c2_gap_fix.py — close production-guard coverage gap on register + login.

Run from repo root:
    python apply_6c2_gap_fix.py

What this does:
1. Edits tools/infrabeat_erp/src/infrabeat_erp/cli.py to add
   _ensure_production_allowed(vm_alias) as the first line of register and login
   subcommand bodies (matching the pattern Claude Code already used for smoke).
2. Appends 2 tests to tools/infrabeat_erp/tests/test_cli.py covering the gap.
3. Re-stages all changes via git add -A.
4. Runs pytest expecting 60 passed, 1 skipped.

Idempotent: safe to run twice. If the guards are already in place, it skips.
"""
import re
import subprocess
import sys
from pathlib import Path

CLI_PY = Path("tools/infrabeat_erp/src/infrabeat_erp/cli.py")
TEST_CLI = Path("tools/infrabeat_erp/tests/test_cli.py")

GUARD_LINE = "    _ensure_production_allowed(vm_alias)"

# Pattern matches: def register(vm_alias: str) -> None:
#                      """...optional docstring (single or multi-line)..."""
# and captures everything up to and including the closing docstring + newline.
PATTERN_TEMPLATE = (
    r'(def {name}\(vm_alias: str\)[^:]*:\s*\n'  # function signature
    r'(?:\s*"""[^"]*"""\s*\n)?)'                 # optional docstring (group 1 ends here)
)


def patch_subcommand(content: str, name: str) -> tuple[str, bool]:
    """Insert guard line after the docstring of subcommand `name`. Returns (new_content, changed)."""
    pattern = re.compile(PATTERN_TEMPLATE.format(name=name), re.DOTALL)
    match = pattern.search(content)
    if not match:
        sys.exit(
            f"ERROR: could not locate `def {name}(vm_alias: str)` in {CLI_PY}. "
            f"Manual edit required."
        )

    # Idempotency check: is the guard already on the line right after the match?
    next_chunk = content[match.end():match.end() + 200]
    if "_ensure_production_allowed(vm_alias)" in next_chunk.split("\n")[0]:
        return content, False  # already patched

    new_content = (
        content[:match.end()]
        + GUARD_LINE + "\n"
        + content[match.end():]
    )
    return new_content, True


# ---------- 1. Patch cli.py ----------
if not CLI_PY.exists():
    sys.exit(f"ERROR: {CLI_PY} not found. Run this script from repo root.")

cli_content = CLI_PY.read_text(encoding="utf-8")

cli_content, changed_register = patch_subcommand(cli_content, "register")
cli_content, changed_login = patch_subcommand(cli_content, "login")

if changed_register or changed_login:
    CLI_PY.write_text(cli_content, encoding="utf-8")
    print(f"[OK] Patched {CLI_PY} "
          f"(register: {'added' if changed_register else 'already-guarded'}, "
          f"login: {'added' if changed_login else 'already-guarded'})")
else:
    print(f"[SKIP] {CLI_PY} already has guards on register and login")


# ---------- 2. Append tests to test_cli.py ----------
GAP_TESTS = '''


def test_allow_production_blocks_register_without_flag(monkeypatch, tmp_path):
    """register production refuses without --allow-production (closes 6C.2 coverage gap)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["register", "production"])
    assert result.exit_code == 1
    assert "allow-production" in result.output.lower()


def test_allow_production_blocks_login_without_flag(monkeypatch, tmp_path):
    """login production refuses without --allow-production (closes 6C.2 coverage gap)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["login", "production"])
    assert result.exit_code == 1
    assert "allow-production" in result.output.lower()
'''

if not TEST_CLI.exists():
    sys.exit(f"ERROR: {TEST_CLI} not found.")

test_content = TEST_CLI.read_text(encoding="utf-8")

if "test_allow_production_blocks_register_without_flag" in test_content:
    print(f"[SKIP] {TEST_CLI} already has gap-closure tests")
else:
    with TEST_CLI.open("a", encoding="utf-8") as fh:
        fh.write(GAP_TESTS)
    print(f"[OK] Appended 2 gap-closure tests to {TEST_CLI}")


# ---------- 3. Re-stage everything ----------
subprocess.run(["git", "add", "-A"], check=True)
print("[OK] Re-staged via git add -A")


# ---------- 4. Run pytest, expect 60 passed, 1 skipped ----------
print("\n[RUN] python -m pytest tools/infrabeat_erp/tests/ --tb=short")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tools/infrabeat_erp/tests/", "--tb=short"],
    capture_output=True,
    text=True,
)

# Print only the last ~20 lines (summary tail)
output = (result.stdout or "") + (result.stderr or "")
tail = "\n".join(output.splitlines()[-20:])
print(tail)

if result.returncode != 0:
    print("\n[FAIL] pytest exited non-zero. Inspect tail above for failure details.")
    sys.exit(result.returncode)

if "60 passed" not in output:
    print("\n[WARN] pytest passed but '60 passed' not found in output. "
          "Verify the count manually before commit.")
    sys.exit(2)

print("\n[OK] 60 passed, 1 skipped. Gap closed. Ready to commit.")
print("\nNext steps:")
print("  git commit -m '...' (use the multi-line message from the chat)")
print("  git push -u origin feature/phase6c2-production-guards")
print("  Open the PR URL printed by the push (or run gh pr create --base dev --fill if gh is authed)")
