"""Tests for infrabeat_erp.secrets_store (Phase 6B.4a)."""

import json
import os
from pathlib import Path

import pytest

from infrabeat_erp.secrets_store import (
    SecretsNotFound,
    SecretsStoreError,
    load_secrets,
    save_secrets,
)


def test_save_writes_json_with_correct_content(tmp_path: Path) -> None:
    payload = {"client_id": "abc", "token": "xyz"}
    save_secrets("dev", payload, tmp_path)
    target = tmp_path / ".secrets" / "dev.json"
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_save_creates_secrets_dir_if_missing(tmp_path: Path) -> None:
    secrets_dir = tmp_path / ".secrets"
    assert not secrets_dir.exists()
    save_secrets("dev", {"x": 1}, tmp_path)
    assert secrets_dir.exists()
    assert secrets_dir.is_dir()


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only mode bits")
def test_save_sets_mode_600_on_posix(tmp_path: Path) -> None:
    target = save_secrets("dev", {"x": 1}, tmp_path)
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
