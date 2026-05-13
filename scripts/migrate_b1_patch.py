"""Phase 7a Sprint 0 Task (B) patch v3: imports + string-literal module references.

Three patterns covered:
  1. `from infrabeat_erp[.infrastructure] import X, Y, Z` - splits by layer membership
  2. `import infrabeat_erp.X` - rewrites to import infrabeat_erp.infrastructure.X
  3. String literal "infrabeat_erp.X..." or 'infrabeat_erp.X...' - rewrites
     (negative lookbehind avoids double-prefixing already-correct paths)

Scope: all *.py under src/, tests/, scripts/. Walks recursively.
Idempotent: safe to re-run.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = REPO_ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp"
TESTS = REPO_ROOT / "tools" / "infrabeat_erp" / "tests"
PKG_SCRIPTS = REPO_ROOT / "tools" / "infrabeat_erp" / "scripts"

INFRA_MODULES = {"audit", "config", "http", "mcp", "oauth", "secrets_store"}

FROM_IMPORT_PATTERN = re.compile(
    r'^(?P<indent>[ \t]*)from infrabeat_erp(?:\.infrastructure)? import (?P<names>[^#\n\r]+?)(?P<trailing>[ \t]*(?:#.*)?)\r?$',
    re.MULTILINE,
)

IMPORT_PATTERN = re.compile(r'\bimport infrabeat_erp\.([a-z_]+)\b')


def make_string_pattern(module: str) -> re.Pattern:
    return re.compile(rf'(?<!infrastructure\.)\binfrabeat_erp\.{module}(?=[.\"\'])')


def transform(text: str) -> tuple[str, int]:
    changes = 0

    def repl_from(m: re.Match) -> str:
        nonlocal changes
        indent = m.group("indent")
        names_raw = m.group("names").strip()
        trailing = m.group("trailing") or ""
        if names_raw.startswith("("):
            return m.group(0)
        items = [n.strip() for n in names_raw.split(",") if n.strip()]
        if not items:
            return m.group(0)
        moved, not_moved = [], []
        for item in items:
            base = item.split()[0]
            (moved if base in INFRA_MODULES else not_moved).append(item)
        if not moved:
            return m.group(0)
        original = m.group(0)
        if "infrastructure" in original and not not_moved and all(it.split()[0] in INFRA_MODULES for it in items):
            return original
        changes += 1
        out_lines = []
        if not_moved:
            out_lines.append(f"{indent}from infrabeat_erp import {', '.join(not_moved)}{trailing}")
        out_lines.append(f"{indent}from infrabeat_erp.infrastructure import {', '.join(moved)}{trailing}")
        return "\n".join(out_lines)

    text = FROM_IMPORT_PATTERN.sub(repl_from, text)

    def repl_import(m: re.Match) -> str:
        nonlocal changes
        mod = m.group(1)
        if mod in INFRA_MODULES:
            changes += 1
            return f"import infrabeat_erp.infrastructure.{mod}"
        return m.group(0)

    text = IMPORT_PATTERN.sub(repl_import, text)

    for module in sorted(INFRA_MODULES):
        pat = make_string_pattern(module)
        matches = pat.findall(text)
        if matches:
            text = pat.sub(f"infrabeat_erp.infrastructure.{module}", text)
            changes += len(matches)

    return text, changes


def patch_file(path: Path) -> int:
    if not path.exists():
        return 0
    orig = path.read_text(encoding="utf-8")
    new, n = transform(orig)
    if n == 0:
        return 0
    path.write_text(new, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", path.relative_to(REPO_ROOT).as_posix()],
        cwd=str(REPO_ROOT),
        check=True,
    )
    return n


def main() -> int:
    print("=== B1 migration patch v3: imports + string literals ===\n")
    total_files = 0
    total_changes = 0
    for label, root in [("src", PKG_ROOT), ("tests", TESTS), ("pkg_scripts", PKG_SCRIPTS)]:
        if not root.exists():
            continue
        print(f"--- {label}/ ---")
        for f in sorted(root.rglob("*.py")):
            n = patch_file(f)
            if n:
                print(f"  UPDATED ({n} changes): {f.relative_to(REPO_ROOT).as_posix()}")
                total_files += 1
                total_changes += n
        print()
    print(f"Total: {total_files} files / {total_changes} changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
