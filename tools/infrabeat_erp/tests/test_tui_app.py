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
