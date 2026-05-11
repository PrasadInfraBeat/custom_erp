"""Tests for infrabeat-erp doctor subcommand."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from infrabeat_erp.application.doctor import (
    EXPECTED_VM_CREDENTIALS,
    CheckResult,
    check_audit_dir,
    check_gh_cli,
    check_keyring_backend,
    check_python_version,
    check_vm_credentials,
    format_results,
    main,
    run_all,
)


def test_python_version_returns_info():
    r = check_python_version()
    assert r.status == "INFO"
    assert r.name == "Python version"
    assert r.detail


def test_keyring_backend_pass(monkeypatch):
    class FakeKeyring:
        pass

    FakeKeyring.__module__ = "keyring.backends.Windows"
    FakeKeyring.__name__ = "WinVaultKeyring"
    monkeypatch.setattr("keyring.get_keyring", lambda: FakeKeyring())
    r = check_keyring_backend()
    assert r.status == "PASS"


def test_keyring_backend_degraded(monkeypatch):
    class NullKeyring:
        pass

    NullKeyring.__module__ = "keyring.backends.fail"
    NullKeyring.__name__ = "Keyring"
    monkeypatch.setattr("keyring.get_keyring", lambda: NullKeyring())
    r = check_keyring_backend()
    assert r.status == "FAIL"
    assert "fail" in r.detail.lower()


def test_vm_credentials_all_present(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda svc, user: "secret_value_22chars")
    r = check_vm_credentials()
    assert r.status == "PASS"
    assert "all 9" in r.detail


def test_vm_credentials_all_missing(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda svc, user: None)
    r = check_vm_credentials()
    assert r.status == "FAIL"
    assert "0/9" in r.detail
    for cred in EXPECTED_VM_CREDENTIALS:
        assert cred in r.detail


def test_vm_credentials_partial(monkeypatch):
    def fake_get(svc, user):
        return "secret" if "staging" in user else None

    monkeypatch.setattr("keyring.get_password", fake_get)
    r = check_vm_credentials()
    assert r.status == "FAIL"
    assert "3/9" in r.detail


def test_gh_cli_not_installed(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda x: None)
    r = check_gh_cli()
    assert r.status == "FAIL"
    assert "not on PATH" in r.detail


def test_audit_dir_writable(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    r = check_audit_dir()
    assert r.status == "PASS"
    assert (tmp_path / ".infrabeat-erp" / "audit").exists()


def test_format_results_includes_summary():
    results = [
        CheckResult("test1", "PASS", "ok"),
        CheckResult("test2", "FAIL", "broken", "fix it"),
    ]
    output = format_results(results)
    assert "1 PASS" in output
    assert "1 FAIL" in output
    assert "fix it" in output


def test_run_all_returns_5_checks():
    with patch("infrabeat_erp.application.doctor.keyring.get_password", return_value=None), \
         patch("infrabeat_erp.application.doctor.keyring.get_keyring") as kr_mock, \
         patch("infrabeat_erp.application.doctor.shutil.which", return_value=None):
        kr_mock.return_value.__class__.__module__ = "keyring.backends.Windows"
        kr_mock.return_value.__class__.__name__ = "WinVaultKeyring"
        results = run_all()
    assert len(results) == 5


def test_main_returns_1_if_any_fail(capsys, monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda *a: None)
    monkeypatch.setattr("shutil.which", lambda x: None)
    rc = main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "FAIL" in captured.out
