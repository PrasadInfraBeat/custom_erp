"""Tests for GitHub PAT keyring storage (Task 3)."""
from __future__ import annotations

import pytest

from infrabeat_erp.infrastructure.pat_store import (
    KEYRING_SERVICE_GITHUB,
    KEYRING_USERNAME_PAT,
    PatNotFound,
    clear_pat,
    has_pat,
    load_pat,
    store_pat,
)


def test_store_and_load_pat_roundtrip(monkeypatch):
    store = {}
    monkeypatch.setattr(
        "keyring.set_password",
        lambda svc, user, val: store.update({(svc, user): val}),
    )
    monkeypatch.setattr(
        "keyring.get_password",
        lambda svc, user: store.get((svc, user)),
    )
    store_pat("ghp_test_token_123")
    assert load_pat() == "ghp_test_token_123"


def test_load_pat_raises_when_missing(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda svc, user: None)
    with pytest.raises(PatNotFound):
        load_pat()


def test_store_pat_rejects_empty():
    with pytest.raises(ValueError):
        store_pat("")
    with pytest.raises(ValueError):
        store_pat("   ")


def test_has_pat_returns_false_when_missing(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda svc, user: None)
    assert has_pat() is False


def test_has_pat_returns_true_when_present(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda svc, user: "ghp_xxx")
    assert has_pat() is True


def test_clear_pat_returns_true_when_removed(monkeypatch):
    monkeypatch.setattr("keyring.delete_password", lambda svc, user: None)
    assert clear_pat() is True


def test_clear_pat_returns_false_when_not_present(monkeypatch):
    import keyring.errors
    def raise_err(svc, user):
        raise keyring.errors.PasswordDeleteError("not found")
    monkeypatch.setattr("keyring.delete_password", raise_err)
    assert clear_pat() is False


def test_keyring_service_constants():
    assert KEYRING_SERVICE_GITHUB == "infrabeat-erp-github"
    assert KEYRING_USERNAME_PAT == "pat"
