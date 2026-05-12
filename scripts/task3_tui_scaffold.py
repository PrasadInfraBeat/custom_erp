"""Phase 7a Sprint 1 Task 3: Textual Console scaffold (spec C1).

Creates the static 3-VM dashboard with hotkey grid per
docs/12_INFRABEAT_CONSOLE_SPEC.md Section 3.

Live data is NOT wired here - that's Task 4 (C2 spec).

Modifies:
  - tools/infrabeat_erp/src/infrabeat_erp/presentation/tui_app.py (NEW)
  - tools/infrabeat_erp/src/infrabeat_erp/tui.py                  (rewrite: --check + launch)
  - tools/infrabeat_erp/pyproject.toml                            (add textual dep)
  - tools/infrabeat_erp/tests/test_tui_app.py                     (NEW)
  - .github/workflows/python-tests.yml                            (smoke test --check)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TUI_APP = ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "presentation" / "tui_app.py"
TUI_STUB = ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "tui.py"
TESTS = ROOT / "tools" / "infrabeat_erp" / "tests" / "test_tui_app.py"
PYPROJECT = ROOT / "tools" / "infrabeat_erp" / "pyproject.toml"
CI = ROOT / ".github" / "workflows" / "python-tests.yml"


TUI_APP_CONTENT = '''"""InfraBeat Console - Textual TUI application.

Phase 7a Sprint 1 Task 3 (spec C1): static 3-VM dashboard with hotkey grid.
Live data wiring comes in Sprint 1 Task 4 (spec C2): async SSH polling.

Spec reference: docs/12_INFRABEAT_CONSOLE_SPEC.md Section 3 (Visual Design).
"""
from __future__ import annotations

import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static


class VmCard(Static):
    """Card displaying status of one VM. Static placeholders for Sprint 1 Task 3."""

    DEFAULT_CSS = """
    VmCard {
        width: 1fr;
        height: 100%;
        border: solid $accent;
        padding: 1;
    }
    """

    def __init__(self, name: str, ip: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.vm_name = name
        self.ip = ip

    def render(self) -> str:
        return (
            f"[bold]{self.vm_name.upper()}[/bold]\\n"
            f"[dim]{self.ip}[/dim]\\n"
            f"\\n"
            f"Branch:    [yellow]-[/yellow]\\n"
            f"Commit:    [yellow]-[/yellow]\\n"
            f"Status:    [yellow]Loading...[/yellow]\\n"
            f"\\n"
            f"Services:  [yellow]-/7[/yellow]\\n"
            f"Site:      [yellow]-[/yellow]\\n"
            f"MCP:       [yellow]-[/yellow]\\n"
            f"Disk:      [yellow]-[/yellow]\\n"
            f"\\n"
            f"Last deploy: [yellow]-[/yellow]"
        )


class InfraBeatApp(App):
    """InfraBeat Control Center: single-pane TUI for 3-VM ERPNext."""

    TITLE = "INFRABEAT CONTROL CENTER"
    SUB_TITLE = "Phase 7a Sprint 1 (C1: static dashboard)"

    CSS = """
    #vm_grid {
        height: 1fr;
        layout: horizontal;
    }
    """

    BINDINGS = [
        Binding("p", "promote", "[P]romote", show=True),
        Binding("d", "deploy", "[D]eploy", show=True),
        Binding("b", "backup", "[B]ackup", show=True),
        Binding("s", "smoke", "[S]moke", show=True),
        Binding("l", "logs", "[L]ogs", show=True),
        Binding("g", "github", "[G]itHub", show=True),
        Binding("r", "rollback", "[R]ollback", show=True),
        Binding("a", "audit", "[A]udit", show=True),
        Binding("m", "mcp", "[M]CP", show=True),
        Binding("v", "provision", "[V]Provision", show=True),
        Binding("slash", "search", "[/]Search", show=True),
        Binding("question_mark", "help", "[?]Help", show=True),
        Binding("q", "quit", "[Q]uit", show=True, priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="vm_grid"):
            yield VmCard("dev", "10.1.0.184")
            yield VmCard("staging", "10.1.0.185")
            yield VmCard("production", "10.1.0.186")
        yield Footer()

    # ====== Action handlers (placeholders, wired in later C-phases) ======

    def action_promote(self) -> None:
        self.notify("Promote dev->staging (Task 4 C3)", severity="information")

    def action_deploy(self) -> None:
        self.notify("Deploy staging->prod (Sprint 2 C4)", severity="information")

    def action_backup(self) -> None:
        self.notify("Backup (Sprint 2 C5)", severity="information")

    def action_smoke(self) -> None:
        self.notify("Smoke tests (Sprint 2 C5)", severity="information")

    def action_logs(self) -> None:
        self.notify("Live logs (Phase 7b C6)", severity="information")

    def action_github(self) -> None:
        self.notify("GitHub status (Sprint 3 C7)", severity="information")

    def action_rollback(self) -> None:
        self.notify("Rollback (Phase 7b C9)", severity="information")

    def action_audit(self) -> None:
        self.notify("Audit log (Sprint 3 C7)", severity="information")

    def action_mcp(self) -> None:
        self.notify("MCP health (Phase 7b C8)", severity="information")

    def action_provision(self) -> None:
        self.notify("Provision VM (deferred)", severity="warning")

    def action_search(self) -> None:
        self.notify("Search (Phase 7b C10)", severity="information")

    def action_help(self) -> None:
        self.notify("Help (placeholder)", severity="information")


def run() -> int:
    """Entry point for `infrabeat` console-script when not --check mode."""
    app = InfraBeatApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(run())
'''


TUI_STUB_CONTENT = '''"""InfraBeat TUI entry point - launches the Textual app (or --check no-launch)."""
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
'''


TESTS_CONTENT = '''"""Tests for InfraBeat Console TUI (Sprint 1 Task 3, spec C1).

Static layout tests only. Live-data tests come in Task 4 (C2 spec).
"""
from __future__ import annotations

import pytest


def test_app_class_title_correct():
    from infrabeat_erp.presentation.tui_app import InfraBeatApp

    assert InfraBeatApp.TITLE == "INFRABEAT CONTROL CENTER"


def test_app_has_all_spec_hotkeys():
    """All 12 ACTIONS-bar hotkeys from spec Section 3 must be registered."""
    from infrabeat_erp.presentation.tui_app import InfraBeatApp

    keys = {b.key for b in InfraBeatApp.BINDINGS}
    expected = {
        "p", "d", "b", "s", "l", "g", "r", "a", "m", "v",
        "slash", "question_mark", "q",
    }
    missing = expected - keys
    assert not missing, f"Missing keys: {missing}"


def test_vm_card_stores_name_and_ip():
    from infrabeat_erp.presentation.tui_app import VmCard

    card = VmCard("dev", "10.1.0.184")
    assert card.vm_name == "dev"
    assert card.ip == "10.1.0.184"


def test_run_entry_returns_int(monkeypatch):
    """run() should return 0 after the Textual app exits."""
    from infrabeat_erp.presentation import tui_app

    class FakeApp:
        def run(self):
            return None

    monkeypatch.setattr(tui_app, "InfraBeatApp", FakeApp)
    assert tui_app.run() == 0
'''


def patch_pyproject() -> bool:
    text = PYPROJECT.read_text(encoding="utf-8")
    if '"textual' in text or "'textual" in text:
        print("  SKIP: textual already present in pyproject.toml")
        return True
    m = re.search(r"^dependencies\s*=\s*\[([\s\S]*?)\]", text, re.MULTILINE)
    if not m:
        print("  FAIL: could not locate dependencies block in pyproject.toml")
        return False
    list_body = m.group(1)
    indent_match = re.search(r"\n(\s+)['\"]", list_body)
    indent = indent_match.group(1) if indent_match else "    "
    trimmed = list_body.rstrip()
    if not trimmed.endswith(","):
        trimmed += ","
    new_list = trimmed + f"\n{indent}\"textual>=0.50\",\n"
    new_text = text[: m.start(1)] + new_list + text[m.end(1) :]
    PYPROJECT.write_text(new_text, encoding="utf-8", newline="\n")
    print("  OK: added textual>=0.50 to dependencies")
    return True


def patch_ci() -> bool:
    if not CI.exists():
        print("  SKIP: CI workflow not found")
        return True
    text = CI.read_text(encoding="utf-8")
    old = "      - name: Smoke - infrabeat (TUI stub, Task C)\n        run: infrabeat"
    new = "      - name: Smoke - infrabeat --check (no TUI launch in CI)\n        run: infrabeat --check"
    if new in text:
        print("  SKIP: CI smoke test already updated")
        return True
    if old not in text:
        print("  FAIL: could not locate old infrabeat smoke test in CI workflow")
        return False
    text = text.replace(old, new, 1)
    CI.write_text(text, encoding="utf-8", newline="\n")
    print("  OK: updated infrabeat smoke test to --check")
    return True


def main_entry() -> int:
    print("Phase 7a Sprint 1 Task 3: Textual Console scaffold (C1)\n")
    print("Writing tui_app.py (Textual application)...")
    TUI_APP.parent.mkdir(parents=True, exist_ok=True)
    TUI_APP.write_text(TUI_APP_CONTENT, encoding="utf-8", newline="\n")
    print(f"  OK: {TUI_APP.relative_to(ROOT)}")

    print("\nRewriting tui.py (entry point with --check support)...")
    TUI_STUB.write_text(TUI_STUB_CONTENT, encoding="utf-8", newline="\n")
    print(f"  OK: {TUI_STUB.relative_to(ROOT)}")

    print("\nWriting test_tui_app.py...")
    TESTS.write_text(TESTS_CONTENT, encoding="utf-8", newline="\n")
    print(f"  OK: {TESTS.relative_to(ROOT)}")

    print("\nPatching pyproject.toml...")
    if not patch_pyproject():
        return 1

    print("\nPatching CI workflow...")
    if not patch_ci():
        return 1

    print("\nStaging files...")
    for f in [TUI_APP, TUI_STUB, TESTS, PYPROJECT, CI]:
        subprocess.run(
            ["git", "add", f.relative_to(ROOT).as_posix()],
            cwd=str(ROOT),
            check=True,
        )
    print("\nALL OK. Run `pip install -e tools/infrabeat_erp[test]` then pytest.")
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())