"""Tests for InfraBeat Console TUI (Sprint 1 Task 3, spec C1).

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


def test_action_smoke_pushes_vm_modal(monkeypatch):
    """action_smoke pushes a VmSelectModal screen with a callback."""
    from infrabeat_erp.presentation import tui_app

    app = tui_app.InfraBeatApp()
    pushed = []

    def fake_push(screen, callback=None):
        pushed.append((type(screen).__name__, callback))

    monkeypatch.setattr(app, "push_screen", fake_push)
    app.action_smoke()

    assert len(pushed) == 1
    assert pushed[0][0] == "VmSelectModal"
    assert pushed[0][1] is not None
