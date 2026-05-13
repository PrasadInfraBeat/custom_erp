#!/usr/bin/env python
"""Sprint 4 Task 1a: TUI wiring for [B]ackup and [P]romote.

L83 atomic rewriter:
  1. Read tui_app.py + test_tui_app.py
  2. Verify all 6 anchor strings exist (fail fast if missing)
  3. Apply replacements in memory
  4. Write back (utf-8, no BOM)
  5. Re-read + ast.parse() + verify replacements landed
  6. Print summary
"""

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TUI = REPO / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "presentation" / "tui_app.py"
TEST = REPO / "tools" / "infrabeat_erp" / "tests" / "test_tui_app.py"


def write_file(path: Path, content: str) -> None:
    """Write, re-read, verify content matches, ast.parse to confirm valid Python."""
    path.write_text(content, encoding="utf-8", newline="\n")
    readback = path.read_text(encoding="utf-8")
    assert readback == content, f"Read-back mismatch on {path}"
    ast.parse(readback)
    print(f"  wrote {path.relative_to(REPO)} ({len(content)} bytes, ast OK)")


def patch_tui() -> None:
    content = TUI.read_text(encoding="utf-8")

    # === Anchor 1: replace action_backup stub ===
    OLD_BACKUP = (
        '    def action_backup(self) -> None:\n'
        '        self.notify("Backup (Sprint 2 C5)", severity="information")'
    )
    assert OLD_BACKUP in content, "MISSING anchor: action_backup stub"
    NEW_BACKUP = (
        '    def action_backup(self) -> None:\n'
        '        """[B] -> VM picker -> spawn backup worker."""\n'
        '        def _on_vm_selected(vm: Optional[str]) -> None:\n'
        '            if vm:\n'
        '                self._run_backup_worker(vm)\n'
        '\n'
        '        self.push_screen(VmSelectModal("Backup"), _on_vm_selected)'
    )
    content = content.replace(OLD_BACKUP, NEW_BACKUP)

    # === Anchor 2: replace action_promote stub ===
    OLD_PROMOTE = (
        '    def action_promote(self) -> None:\n'
        '        self.notify("Promote dev->staging (Sprint 2 C3)", severity="information")'
    )
    assert OLD_PROMOTE in content, "MISSING anchor: action_promote stub"
    NEW_PROMOTE = (
        '    def action_promote(self) -> None:\n'
        '        """[P] -> Target picker -> spawn promote worker."""\n'
        '        def _on_target_selected(target: Optional[str]) -> None:\n'
        '            if target:\n'
        '                self._run_promote_worker(target)\n'
        '\n'
        '        self.push_screen(PromoteTargetModal(), _on_target_selected)'
    )
    content = content.replace(OLD_PROMOTE, NEW_PROMOTE)

    # === Anchor 3: inject RichLog before yield Footer() in compose() ===
    OLD_FOOTER = '        yield Footer()'
    count = content.count(OLD_FOOTER)
    assert count == 1, f"Expected exactly 1 'yield Footer()', got {count}"
    NEW_FOOTER = (
        '        yield RichLog(id="output_log", wrap=True, max_lines=500, highlight=True, markup=True)\n'
        '        yield Footer()'
    )
    content = content.replace(OLD_FOOTER, NEW_FOOTER)

    # === Anchor 4: insert worker block before "# ====== Action handlers" comment ===
    OLD_HEADER = '    # ====== Action handlers (placeholders, wired in later C-phases) ======'
    assert OLD_HEADER in content, "MISSING anchor: action handlers header comment"
    WORKERS = (
        '    # ====== Sprint 4 Task 1a: Live workers for [B]ackup and [P]romote ======\n'
        '\n'
        '    @work(exclusive=True, group="ops")\n'
        '    async def _run_backup_worker(self, vm: str) -> None:\n'
        '        """Run do_backup(vm) async; stream to RichLog; notify on completion."""\n'
        '        log = self.query_one("#output_log", RichLog)\n'
        '        log.write(f"[bold cyan][backup][/bold cyan] starting on [bold]{vm}[/bold]...")\n'
        '        self.notify(f"Backup of {vm} started", severity="information", timeout=3)\n'
        '        try:\n'
        '            result = await do_backup(vm)\n'
        '            log.write("[bold green][backup][/bold green] complete:")\n'
        '            log.write(f"  result = {result}")\n'
        '            self.notify(f"Backup of {vm} OK", severity="information", timeout=5)\n'
        '        except Exception as e:\n'
        '            log.write(f"[bold red][backup ERROR][/bold red] {type(e).__name__}: {e}")\n'
        '            self.notify(f"Backup of {vm} failed: {e}", severity="error", timeout=10)\n'
        '\n'
        '    @work(exclusive=True, group="ops")\n'
        '    async def _run_promote_worker(self, target: str) -> None:\n'
        '        """Run do_promote(target) async; stream to RichLog; notify on completion."""\n'
        '        log = self.query_one("#output_log", RichLog)\n'
        '        log.write(f"[bold cyan][promote][/bold cyan] starting to [bold]{target}[/bold]...")\n'
        '        self.notify(f"Promote to {target} started", severity="information", timeout=3)\n'
        '        try:\n'
        '            result = await do_promote(target)\n'
        '            log.write("[bold green][promote][/bold green] complete:")\n'
        '            log.write(f"  result = {result}")\n'
        '            self.notify(f"Promote to {target} OK", severity="information", timeout=5)\n'
        '        except Exception as e:\n'
        '            log.write(f"[bold red][promote ERROR][/bold red] {type(e).__name__}: {e}")\n'
        '            self.notify(f"Promote to {target} failed: {e}", severity="error", timeout=10)\n'
        '\n'
        '    # ====== Action handlers (LIVE for [B][P], stubs for others) ======'
    )
    content = content.replace(OLD_HEADER, WORKERS)

    # === Anchor 5: insert ModalScreen classes BEFORE class InfraBeatApp(App): ===
    OLD_APP = 'class InfraBeatApp(App):'
    assert OLD_APP in content, "MISSING anchor: class InfraBeatApp(App):"
    MODALS = (
        'class VmSelectModal(ModalScreen[Optional[str]]):\n'
        '    """Pick a VM from dev/staging/production. Dismisses with VM name or None."""\n'
        '\n'
        '    DEFAULT_CSS = """\n'
        '    VmSelectModal {\n'
        '        align: center middle;\n'
        '    }\n'
        '\n'
        '    VmSelectModal > Vertical {\n'
        '        width: 50;\n'
        '        height: auto;\n'
        '        border: thick $accent;\n'
        '        background: $surface;\n'
        '        padding: 1 2;\n'
        '    }\n'
        '\n'
        '    VmSelectModal Button {\n'
        '        width: 100%;\n'
        '        margin-bottom: 1;\n'
        '    }\n'
        '    """\n'
        '\n'
        '    def __init__(self, action_label: str) -> None:\n'
        '        super().__init__()\n'
        '        self.action_label = action_label\n'
        '\n'
        '    def compose(self) -> ComposeResult:\n'
        '        with Vertical():\n'
        '            yield Label(f"Select VM for [bold]{self.action_label}[/bold]:")\n'
        '            yield Button("Dev (10.1.0.184)", id="dev", variant="primary")\n'
        '            yield Button("Staging (10.1.0.185)", id="staging", variant="primary")\n'
        '            yield Button("Production (10.1.0.186)", id="production", variant="error")\n'
        '            yield Button("Cancel", id="cancel", variant="default")\n'
        '\n'
        '    def on_button_pressed(self, event: Button.Pressed) -> None:\n'
        '        if event.button.id == "cancel":\n'
        '            self.dismiss(None)\n'
        '        else:\n'
        '            self.dismiss(event.button.id)\n'
        '\n'
        '\n'
        'class PromoteTargetModal(ModalScreen[Optional[str]]):\n'
        '    """Pick promotion target: staging or production."""\n'
        '\n'
        '    DEFAULT_CSS = """\n'
        '    PromoteTargetModal {\n'
        '        align: center middle;\n'
        '    }\n'
        '\n'
        '    PromoteTargetModal > Vertical {\n'
        '        width: 60;\n'
        '        height: auto;\n'
        '        border: thick $accent;\n'
        '        background: $surface;\n'
        '        padding: 1 2;\n'
        '    }\n'
        '\n'
        '    PromoteTargetModal Button {\n'
        '        width: 100%;\n'
        '        margin-bottom: 1;\n'
        '    }\n'
        '    """\n'
        '\n'
        '    def compose(self) -> ComposeResult:\n'
        '        with Vertical():\n'
        '            yield Label("Select promotion target:")\n'
        '            yield Label("  staging: dev -> staging")\n'
        '            yield Label("  production: staging -> production (LIVE)")\n'
        '            yield Button("Promote to STAGING", id="staging", variant="primary")\n'
        '            yield Button("Promote to PRODUCTION", id="production", variant="error")\n'
        '            yield Button("Cancel", id="cancel", variant="default")\n'
        '\n'
        '    def on_button_pressed(self, event: Button.Pressed) -> None:\n'
        '        if event.button.id == "cancel":\n'
        '            self.dismiss(None)\n'
        '        else:\n'
        '            self.dismiss(event.button.id)\n'
        '\n'
        '\n'
        'class InfraBeatApp(App):'
    )
    content = content.replace(OLD_APP, MODALS)

    # === Anchor 6: add new imports after the last top-of-file import ===
    lines = content.splitlines(keepends=True)
    last_import_idx = -1
    for i, line in enumerate(lines[:40]):
        stripped = line.lstrip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            last_import_idx = i
    assert last_import_idx >= 0, "MISSING anchor: no imports found in first 40 lines"

    NEW_IMPORTS = (
        '\n'
        '# === Sprint 4 Task 1a: TUI wiring for [B]ackup + [P]romote ===\n'
        'from textual.screen import ModalScreen\n'
        'from textual.widgets import RichLog, Button, Label\n'
        'from textual.containers import Vertical\n'
        'from textual import work\n'
        'from infrabeat_erp.application.backup import do_backup\n'
        'from infrabeat_erp.application.promote import do_promote\n'
    )
    lines.insert(last_import_idx + 1, NEW_IMPORTS)
    content = "".join(lines)

    write_file(TUI, content)

    # Post-write assertions
    assert "class VmSelectModal(ModalScreen[Optional[str]]):" in content
    assert "class PromoteTargetModal(ModalScreen[Optional[str]]):" in content
    assert "def _run_backup_worker" in content
    assert "def _run_promote_worker" in content
    assert OLD_BACKUP not in content, "Old action_backup stub still present!"
    assert OLD_PROMOTE not in content, "Old action_promote stub still present!"
    print("  tui_app.py: 6 anchors patched, 2 modals + 2 workers + RichLog added")


def patch_test_tui() -> None:
    content = TEST.read_text(encoding="utf-8")

    NEW_TESTS = '''


def test_action_backup_pushes_vm_modal(monkeypatch):
    """action_backup pushes a VmSelectModal screen with a callback."""
    from infrabeat_erp.presentation import tui_app

    app = tui_app.InfraBeatApp()
    pushed = []

    def fake_push(screen, callback=None):
        pushed.append((type(screen).__name__, callback))

    monkeypatch.setattr(app, "push_screen", fake_push)
    app.action_backup()

    assert len(pushed) == 1
    assert pushed[0][0] == "VmSelectModal"
    assert pushed[0][1] is not None


def test_action_promote_pushes_target_modal(monkeypatch):
    """action_promote pushes a PromoteTargetModal screen with a callback."""
    from infrabeat_erp.presentation import tui_app

    app = tui_app.InfraBeatApp()
    pushed = []

    def fake_push(screen, callback=None):
        pushed.append((type(screen).__name__, callback))

    monkeypatch.setattr(app, "push_screen", fake_push)
    app.action_promote()

    assert len(pushed) == 1
    assert pushed[0][0] == "PromoteTargetModal"
    assert pushed[0][1] is not None


def test_vm_select_modal_dismisses_with_button_id(monkeypatch):
    """VmSelectModal.on_button_pressed(staging) -> dismiss('staging')."""
    from infrabeat_erp.presentation.tui_app import VmSelectModal

    modal = VmSelectModal("test")
    captured = []
    monkeypatch.setattr(modal, "dismiss", lambda v: captured.append(v))

    class FakeButton:
        id = "staging"

    class FakeEvent:
        button = FakeButton()

    modal.on_button_pressed(FakeEvent())
    assert captured == ["staging"]


def test_vm_select_modal_cancel_dismisses_none(monkeypatch):
    """VmSelectModal cancel button -> dismiss(None)."""
    from infrabeat_erp.presentation.tui_app import VmSelectModal

    modal = VmSelectModal("test")
    captured = []
    monkeypatch.setattr(modal, "dismiss", lambda v: captured.append(v))

    class FakeButton:
        id = "cancel"

    class FakeEvent:
        button = FakeButton()

    modal.on_button_pressed(FakeEvent())
    assert captured == [None]


def test_promote_target_modal_dismisses_with_button_id(monkeypatch):
    """PromoteTargetModal.on_button_pressed(production) -> dismiss('production')."""
    from infrabeat_erp.presentation.tui_app import PromoteTargetModal

    modal = PromoteTargetModal()
    captured = []
    monkeypatch.setattr(modal, "dismiss", lambda v: captured.append(v))

    class FakeButton:
        id = "production"

    class FakeEvent:
        button = FakeButton()

    modal.on_button_pressed(FakeEvent())
    assert captured == ["production"]
'''

    content = content.rstrip() + NEW_TESTS
    write_file(TEST, content)

    assert "test_action_backup_pushes_vm_modal" in content
    assert "test_action_promote_pushes_target_modal" in content
    assert "test_vm_select_modal_dismisses_with_button_id" in content
    assert "test_vm_select_modal_cancel_dismisses_none" in content
    assert "test_promote_target_modal_dismisses_with_button_id" in content
    print("  test_tui_app.py: 5 new tests appended")


def main() -> int:
    print("=== Sprint 4 Task 1a: TUI wiring for [B]ackup + [P]romote ===\n")
    print("Patching tui_app.py...")
    patch_tui()
    print()
    print("Patching test_tui_app.py...")
    patch_test_tui()
    print()
    print("=== SUCCESS ===")
    print("Next: python -m pytest tools/infrabeat_erp/tests/test_tui_app.py -v")
    return 0


if __name__ == "__main__":
    sys.exit(main())