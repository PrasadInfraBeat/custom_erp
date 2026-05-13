"""Phase 7a Sprint 0 Task (B): B1 source layout migration.

Migrates tools/infrabeat_erp/src/infrabeat_erp/ flat layout to layered B1:
  - <name>.py -> infrastructure/<name>.py for: audit, config, http, mcp, oauth, secrets_store
  - Creates: presentation/, application/, domain/, infrastructure/ packages (empty __init__.py)
  - Updates imports in cli.py, tests/, tools/infrabeat_erp/scripts/

Uses `git mv` for file moves (preserves rename history). Idempotent: safe to re-run.
Must run from repo root with a clean working tree.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = REPO_ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp"
TESTS_ROOT = REPO_ROOT / "tools" / "infrabeat_erp" / "tests"
SCRIPTS_ROOT = REPO_ROOT / "tools" / "infrabeat_erp" / "scripts"

INFRASTRUCTURE_MODULES = ["audit", "config", "http", "mcp", "oauth", "secrets_store"]
NEW_PACKAGES = ["presentation", "application", "domain", "infrastructure"]


def run(*args, check=True, capture_output=False):
    print(f"  $ {' '.join(str(a) for a in args)}")
    return subprocess.run(
        list(args),
        check=check,
        capture_output=capture_output,
        text=True,
        cwd=str(REPO_ROOT),
    )


def ensure_package(pkg_dir: Path) -> bool:
    """Create pkg_dir/__init__.py if missing. Returns True if created."""
    pkg_dir.mkdir(parents=True, exist_ok=True)
    init_py = pkg_dir / "__init__.py"
    if init_py.exists():
        return False
    init_py.touch()
    run("git", "add", init_py.relative_to(REPO_ROOT).as_posix())
    return True


def git_mv(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not (dst.parent / "__init__.py").exists():
        ensure_package(dst.parent)
    rel_src = src.relative_to(REPO_ROOT).as_posix()
    rel_dst = dst.relative_to(REPO_ROOT).as_posix()
    run("git", "mv", rel_src, rel_dst)


def update_imports(path: Path, replacements: dict) -> bool:
    if not path.exists():
        return False
    original = path.read_text(encoding="utf-8")
    content = original
    for old, new in replacements.items():
        content = content.replace(old, new)
    if content == original:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    run("git", "add", path.relative_to(REPO_ROOT).as_posix())
    return True


def main() -> int:
    print("=== Phase 7a Sprint 0 Task (B) - B1 source layout migration ===\n")

    print("Step 1: verify clean working tree ...")
    result = run("git", "status", "--porcelain", capture_output=True)
    if result.stdout.strip():
        print("FATAL: working tree is not clean. Commit or stash first.\n")
        print(result.stdout)
        return 1
    print("  OK\n")

    print("Step 2: create new packages (presentation, application, domain, infrastructure)...")
    for pkg in NEW_PACKAGES:
        created = ensure_package(PKG_ROOT / pkg)
        marker = "created" if created else "already present"
        print(f"  {pkg}/ {marker}")
    print()

    print("Step 3: git mv modules into infrastructure/ ...")
    for module in INFRASTRUCTURE_MODULES:
        src = PKG_ROOT / f"{module}.py"
        dst = PKG_ROOT / "infrastructure" / f"{module}.py"
        if src.exists():
            git_mv(src, dst)
        elif dst.exists():
            print(f"  (already moved: infrastructure/{module}.py)")
        else:
            print(f"  WARNING: neither src nor dst exists for module '{module}'")
    print()

    print("Step 4: update relative imports in cli.py ...")
    cli_repl = {}
    for module in INFRASTRUCTURE_MODULES:
        cli_repl[f"from .{module} import"] = f"from .infrastructure.{module} import"
        cli_repl[f"from . import {module}"] = f"from .infrastructure import {module}"
        cli_repl[f"from .{module} "] = f"from .infrastructure.{module} "
    changed = update_imports(PKG_ROOT / "cli.py", cli_repl)
    print(f"  cli.py {'UPDATED' if changed else 'unchanged'}")
    print()

    print("Step 5: update absolute imports in tests/ ...")
    test_repl = {}
    for module in INFRASTRUCTURE_MODULES:
        test_repl[f"from infrabeat_erp.{module} import"] = f"from infrabeat_erp.infrastructure.{module} import"
        test_repl[f"import infrabeat_erp.{module}"] = f"import infrabeat_erp.infrastructure.{module}"
    if TESTS_ROOT.exists():
        for test_file in sorted(TESTS_ROOT.glob("test_*.py")):
            changed = update_imports(test_file, test_repl)
            print(f"  {test_file.name} {'UPDATED' if changed else 'unchanged'}")
    print()

    print("Step 6: update imports in tools/infrabeat_erp/scripts/ ...")
    script_repl = test_repl
    if SCRIPTS_ROOT.exists():
        for script_file in sorted(SCRIPTS_ROOT.glob("*.py")):
            changed = update_imports(script_file, script_repl)
            print(f"  {script_file.name} {'UPDATED' if changed else 'unchanged'}")
    print()

    print("=== Final git status ===")
    run("git", "status", "--short")

    print("\n=== Migration complete ===")
    print("Next: review `git status` + `git diff --stat`, then:")
    print("  1. pip install -e tools/infrabeat_erp/   (refresh egg-info)")
    print("  2. pytest tools/infrabeat_erp/tests/      (verify baseline still passes)")
    print("  3. git commit                              (per L67: specific paths only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())