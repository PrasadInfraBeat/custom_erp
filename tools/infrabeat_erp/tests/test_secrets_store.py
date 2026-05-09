"""Tests for infrabeat_erp.secrets_store (Phase 6B.4a + 6C.1)."""

import base64
import json
import os
from pathlib import Path

import keyring
import keyring.errors
import pytest

from infrabeat_erp import secrets_store
from infrabeat_erp.secrets_store import (
    SecretsNotFound,
    SecretsStoreError,
    load_secrets,
    save_secrets,
)


_TEST_MASTER_KEY = base64.urlsafe_b64encode(b"\x00" * 32).decode("ascii")


@pytest.fixture(autouse=True)
def _isolate_keyring_and_master_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default isolation: keyring unavailable, deterministic master key.

    Forces tests to exercise the encrypted-JSON fallback path so they
    do not write to (or read from) the host's real Credential Manager /
    Keychain / Secret Service. Tests that need keyring behavior override
    these monkeypatches in their own body (last setattr wins).
    """
    def _raise(*_a: object, **_kw: object) -> None:
        raise keyring.errors.NoKeyringError("test isolation: keyring disabled")

    monkeypatch.setattr(keyring, "set_password", _raise)
    monkeypatch.setattr(keyring, "get_password", lambda *a, **k: None)
    monkeypatch.setenv("INFRABEAT_MASTER_KEY", _TEST_MASTER_KEY)


# === Phase 6B.4a (preserved; assertions updated for 6C.1 storage) =========


def test_save_writes_encrypted_when_keyring_unavailable(tmp_path: Path) -> None:
    payload = {"client_id": "abc", "token": "xyz"}
    save_secrets("dev", payload, tmp_path)
    encrypted = tmp_path / ".secrets" / "dev.json.enc"
    plaintext = tmp_path / ".secrets" / "dev.json"
    assert encrypted.exists()
    assert not plaintext.exists()
    assert load_secrets("dev", tmp_path) == payload


def test_save_creates_secrets_dir_if_missing(tmp_path: Path) -> None:
    secrets_dir = tmp_path / ".secrets"
    assert not secrets_dir.exists()
    save_secrets("dev", {"x": 1}, tmp_path)
    assert secrets_dir.exists()
    assert secrets_dir.is_dir()


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only mode bits")
def test_save_sets_mode_600_on_posix(tmp_path: Path) -> None:
    target = save_secrets("dev", {"x": 1}, tmp_path)
    assert target is not None
    assert (target.stat().st_mode & 0o777) == 0o600


def test_load_returns_saved_data(tmp_path: Path) -> None:
    original = {"a": 1, "b": "two"}
    save_secrets("dev", original, tmp_path)
    assert load_secrets("dev", tmp_path) == original


def test_load_raises_secrets_not_found(tmp_path: Path) -> None:
    with pytest.raises(SecretsNotFound) as exc:
        load_secrets("nonexistent", tmp_path)
    assert "register" in str(exc.value)
    assert isinstance(exc.value, SecretsStoreError)


# === Phase 6C.1 KEYRING PROMOTION TESTS ===================================


def _fake_keyring(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Wire keyring.{set,get}_password to an in-memory dict; return it."""
    store: dict[tuple[str, str], str] = {}

    def fake_set(service: str, user: str, value: str) -> None:
        store[(service, user)] = value

    def fake_get(service: str, user: str) -> str | None:
        return store.get((service, user))

    monkeypatch.setattr(keyring, "set_password", fake_set)
    monkeypatch.setattr(keyring, "get_password", fake_get)
    return store


def test_save_uses_keyring_when_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store = _fake_keyring(monkeypatch)
    monkeypatch.delenv("INFRABEAT_MASTER_KEY", raising=False)

    payload = {"client_id": "kabc", "access_token": "ktok"}
    result = save_secrets("dev", payload, tmp_path)

    assert result is None  # keyring path returns None (no file written)
    assert (secrets_store.KEYRING_SERVICE, "dev") in store
    assert json.loads(store[(secrets_store.KEYRING_SERVICE, "dev")]) == payload
    # No fallback file should have been created.
    assert not (tmp_path / ".secrets" / "dev.json.enc").exists()
    # And load round-trips through the keyring path.
    assert load_secrets("dev", tmp_path) == payload


def test_load_falls_back_to_encrypted_when_keyring_empty(
    tmp_path: Path,
) -> None:
    payload = {"client_id": "encabc"}
    # Autouse fixture has keyring disabled; this writes the .enc file.
    save_secrets("dev", payload, tmp_path)
    assert (tmp_path / ".secrets" / "dev.json.enc").exists()
    assert load_secrets("dev", tmp_path) == payload


def test_load_falls_back_to_legacy_when_neither_keyring_nor_encrypted(
    tmp_path: Path,
) -> None:
    # Seed only the legacy plaintext file, no keyring entry, no .enc.
    secrets_dir = tmp_path / ".secrets"
    secrets_dir.mkdir()
    legacy_payload = {"client_id": "legacy_abc", "access_token": "legacy_tok"}
    (secrets_dir / "dev.json").write_text(
        json.dumps(legacy_payload), encoding="utf-8"
    )

    assert load_secrets("dev", tmp_path) == legacy_payload


def test_save_when_keyring_unavailable_writes_encrypted(
    tmp_path: Path,
) -> None:
    payload = {"client_id": "fb_abc", "access_token": "fb_tok"}
    result = save_secrets("dev", payload, tmp_path)

    encrypted = tmp_path / ".secrets" / "dev.json.enc"
    assert result == encrypted
    assert encrypted.exists()
    # Bytes are Fernet-encrypted; verify they don't leak the plaintext.
    blob = encrypted.read_bytes()
    assert b"fb_abc" not in blob
    assert b"fb_tok" not in blob
    # And roundtrip via load() proves the master key flow works.
    assert load_secrets("dev", tmp_path) == payload


def test_migrate_renames_legacy_to_migrated_suffix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store = _fake_keyring(monkeypatch)
    monkeypatch.delenv("INFRABEAT_MASTER_KEY", raising=False)

    secrets_dir = tmp_path / ".secrets"
    secrets_dir.mkdir()
    legacy_payload = {"client_id": "mig_abc", "access_token": "mig_tok"}
    (secrets_dir / "dev.json").write_text(
        json.dumps(legacy_payload), encoding="utf-8"
    )

    status = secrets_store.migrate("dev", base_dir=tmp_path)

    assert status == "migrated"
    assert (secrets_dir / "dev.json.migrated").exists()
    assert not (secrets_dir / "dev.json").exists()
    # Data lives in the (fake) keyring now.
    assert (secrets_store.KEYRING_SERVICE, "dev") in store
    assert json.loads(store[(secrets_store.KEYRING_SERVICE, "dev")]) == legacy_payload


def test_migrate_idempotent(tmp_path: Path) -> None:
    secrets_dir = tmp_path / ".secrets"
    secrets_dir.mkdir()
    (secrets_dir / "dev.json").write_text(
        json.dumps({"client_id": "x"}), encoding="utf-8"
    )

    first = secrets_store.migrate("dev", base_dir=tmp_path)
    second = secrets_store.migrate("dev", base_dir=tmp_path)

    assert first == "migrated"
    assert second == "already-migrated"
    assert secrets_store.is_migrated("dev", base_dir=tmp_path)


def test_migrate_no_source(tmp_path: Path) -> None:
    status = secrets_store.migrate("dev", base_dir=tmp_path)
    assert status == "no-source"
    assert not secrets_store.is_migrated("dev", base_dir=tmp_path)
