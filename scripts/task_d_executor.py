"""Phase 7a Sprint 0 Task (D) executor: infrabeat-erp doctor subcommand.

Deliverables:
  1. src/infrabeat_erp/application/doctor.py - 5-check pre-flight orchestrator
  2. tests/test_doctor.py - unit tests with mocks
  3. src/infrabeat_erp/cli.py - add `doctor` subparser + dispatch

Reinstalls editable, runs pytest, invokes `infrabeat-erp doctor` for live demo.

Idempotent: safe to re-run.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = REPO_ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp"
TESTS_ROOT = REPO_ROOT / "tools" / "infrabeat_erp" / "tests"
APP_DIR = PKG_ROOT / "application"
CLI_FILE = PKG_ROOT / "cli.py"


DOCTOR_PY = '''"""infrabeat-erp doctor: pre-flight checks for InfraBeat operational state.

Sprint 0 MVP (5 checks). Scope per Phase 7a Sprint 0 closure doc Section 3:
  - F1 mitigation: gh CLI auth status
  - F2 mitigation: keyring credential lookup by canonical names
  - F3 mitigation: enumerate all 9 expected VM credentials
  - F7 reporting: Python version

VM-side checks (SSH connectivity, FAC service status, sudoers) defer to Sprint 1.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import keyring

EXPECTED_VM_CREDENTIALS = [
    "dev-ssh-password",
    "staging-ssh-password",
    "production-ssh-password",
    "dev-admin-password",
    "staging-admin-password",
    "production-admin-password",
    "dev-mariadb-root",
    "staging-mariadb-root",
    "production-mariadb-root",
]

EXPECTED_KEYRING_SERVICES = [
    "infrabeat-vm-creds",
    "infrabeat-erp",
    "infrabeat-erp-master",
]


class CheckResult(NamedTuple):
    name: str
    status: str  # PASS | FAIL | WARN | INFO
    detail: str
    remediation: str = ""


def check_python_version() -> CheckResult:
    v = sys.version_info
    return CheckResult(
        "Python version",
        "INFO",
        f"{v.major}.{v.minor}.{v.micro} ({sys.executable})",
    )


def check_keyring_backend() -> CheckResult:
    try:
        kr = keyring.get_keyring()
        backend = f"{kr.__class__.__module__}.{kr.__class__.__name__}"
        if "fail" in backend.lower() or "null" in backend.lower():
            return CheckResult(
                "Keyring backend",
                "FAIL",
                f"degraded backend: {backend}",
                "pip install --upgrade keyring",
            )
        return CheckResult("Keyring backend", "PASS", backend)
    except Exception as exc:
        return CheckResult(
            "Keyring backend",
            "FAIL",
            f"{type(exc).__name__}: {exc}",
            "pip install --upgrade keyring",
        )


def check_vm_credentials() -> CheckResult:
    """F2 + F3: enumerate all 9 expected VM credentials by canonical name."""
    found, missing = [], []
    for name in EXPECTED_VM_CREDENTIALS:
        try:
            pw = keyring.get_password("infrabeat-vm-creds", name)
        except Exception:
            pw = None
        if pw:
            found.append(name)
        else:
            missing.append(name)
    if missing:
        return CheckResult(
            "VM credentials",
            "FAIL",
            f"{len(found)}/{len(EXPECTED_VM_CREDENTIALS)} present; missing: {', '.join(missing)}",
            "see docs/closures/21_PHASE_7A_SPRINT_0_CLOSURE.md F2/F3",
        )
    return CheckResult(
        "VM credentials",
        "PASS",
        f"all {len(EXPECTED_VM_CREDENTIALS)} present under canonical names",
    )


def check_gh_cli() -> CheckResult:
    """F1: gh CLI binary present + authenticated."""
    gh = shutil.which("gh")
    if not gh:
        return CheckResult(
            "gh CLI",
            "FAIL",
            "binary not on PATH",
            "install from https://cli.github.com/",
        )
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return CheckResult(
            "gh CLI auth",
            "FAIL",
            f"{type(exc).__name__}: {exc}",
            "gh auth login --hostname github.com --web",
        )
    if proc.returncode == 0:
        return CheckResult("gh CLI auth", "PASS", "authenticated")
    return CheckResult(
        "gh CLI auth",
        "FAIL",
        "not authenticated (F1)",
        "gh auth login --hostname github.com --web",
    )


def check_audit_dir() -> CheckResult:
    audit_dir = Path.home() / ".infrabeat-erp" / "audit"
    try:
        audit_dir.mkdir(parents=True, exist_ok=True)
        probe = audit_dir / ".doctor_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return CheckResult("Audit dir", "PASS", str(audit_dir))
    except Exception as exc:
        return CheckResult(
            "Audit dir",
            "FAIL",
            f"{audit_dir} not writable: {exc}",
            f"manually create {audit_dir} with write permissions",
        )


CHECKS = [
    check_python_version,
    check_keyring_backend,
    check_vm_credentials,
    check_gh_cli,
    check_audit_dir,
]


def run_all() -> list[CheckResult]:
    results = []
    for fn in CHECKS:
        try:
            results.append(fn())
        except Exception as exc:
            results.append(
                CheckResult(
                    fn.__name__,
                    "FAIL",
                    f"check raised {type(exc).__name__}: {exc}",
                    "internal bug; please report",
                )
            )
    return results


SYMBOLS = {"PASS": "[ ok  ]", "FAIL": "[FAIL ]", "WARN": "[WARN ]", "INFO": "[ i   ]"}


def format_results(results: list[CheckResult], verbose: bool = False) -> str:
    lines = ["", "InfraBeat doctor - pre-flight checks", "=" * 70]
    counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "INFO": 0}
    for r in results:
        sym = SYMBOLS.get(r.status, "[ ?   ]")
        lines.append(f"{sym} {r.name:24s} {r.detail}")
        if r.remediation and (verbose or r.status in ("FAIL", "WARN")):
            lines.append(f"        > {r.remediation}")
        counts[r.status] = counts.get(r.status, 0) + 1
    lines.append("=" * 70)
    summary = ", ".join(f"{counts[k]} {k}" for k in ["PASS", "FAIL", "WARN", "INFO"])
    lines.append(f"Summary: {summary}")
    lines.append("")
    return "\\n".join(lines)


def main(verbose: bool = False) -> int:
    results = run_all()
    print(format_results(results, verbose))
    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main(verbose="--verbose" in sys.argv or "-v" in sys.argv))
'''


TEST_DOCTOR_PY = '''"""Tests for infrabeat-erp doctor subcommand."""
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
    with patch("infrabeat_erp.application.doctor.keyring.get_password", return_value=None), \\
         patch("infrabeat_erp.application.doctor.keyring.get_keyring") as kr_mock, \\
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
'''


def write_doctor_module() -> bool:
    target = APP_DIR / "doctor.py"
    if target.exists() and target.read_text(encoding="utf-8") == DOCTOR_PY:
        print("Step 1: application/doctor.py already up-to-date")
        return False
    target.write_text(DOCTOR_PY, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", target.relative_to(REPO_ROOT).as_posix()],
        cwd=str(REPO_ROOT),
        check=True,
    )
    print(f"Step 1: wrote {target.relative_to(REPO_ROOT).as_posix()}")
    return True


def write_test_doctor() -> bool:
    target = TESTS_ROOT / "test_doctor.py"
    if target.exists() and target.read_text(encoding="utf-8") == TEST_DOCTOR_PY:
        print("Step 2: tests/test_doctor.py already up-to-date")
        return False
    target.write_text(TEST_DOCTOR_PY, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", target.relative_to(REPO_ROOT).as_posix()],
        cwd=str(REPO_ROOT),
        check=True,
    )
    print(f"Step 2: wrote {target.relative_to(REPO_ROOT).as_posix()}")
    return True


def patch_cli() -> bool:
    """Inject doctor subparser + dispatch into cli.py.

    Detection: if 'doctor' already a subcommand, skip.
    Otherwise: find the subparsers.add_parser block and append our parser,
    plus add an elif branch in the dispatcher.
    """
    text = CLI_FILE.read_text(encoding="utf-8")
    if 'add_parser("doctor"' in text or "add_parser('doctor'" in text:
        print("Step 3: cli.py already has doctor subparser (skip)")
        return False

    matches = list(re.finditer(r'(\w+)_parser = subparsers\.add_parser\(', text))
    if not matches:
        raise RuntimeError("No subparsers.add_parser pattern in cli.py")
    last = matches[-1]
    rest = text[last.start():]
    block_end_match = re.search(r'\n\n', rest)
    if not block_end_match:
        raise RuntimeError("Could not locate end of last subparser block")
    insert_pos = last.start() + block_end_match.start()
    doctor_block = (
        '\n\n    doctor_parser = subparsers.add_parser('
        '"doctor", help="run pre-flight checks for InfraBeat state")'
        '\n    doctor_parser.add_argument('
        '"--verbose", "-v", action="store_true", '
        'help="show remediation hints for all checks")'
    )
    text_new = text[:insert_pos] + doctor_block + text[insert_pos:]

    disp_match = re.search(r'(\s+)(elif args\.command == "\w+":\s*\n[^\n]+\n)', text_new)
    if not disp_match:
        raise RuntimeError("Cannot locate command dispatch (elif args.command) in cli.py")
    indent = disp_match.group(1)
    elif_block = (
        f'{indent}elif args.command == "doctor":\n'
        f'{indent}    from .application.doctor import main as doctor_main\n'
        f'{indent}    return doctor_main(verbose=args.verbose)\n'
    )
    text_new = text_new[:disp_match.start()] + indent + elif_block.lstrip() + text_new[disp_match.start():]

    CLI_FILE.write_text(text_new, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", CLI_FILE.relative_to(REPO_ROOT).as_posix()],
        cwd=str(REPO_ROOT),
        check=True,
    )
    print("Step 3: patched cli.py with doctor subparser + dispatch")
    return True


def main() -> int:
    print("=== Phase 7a Sprint 0 Task (D) executor ===\n")
    write_doctor_module()
    write_test_doctor()
    patch_cli()
    print()

    print("Step 4: pip install -e (refresh) ...")
    subprocess.run(
        ["pip", "install", "-e", "tools/infrabeat_erp/", "--quiet"],
        cwd=str(REPO_ROOT),
        check=True,
    )
    print("  OK\n")

    print("Step 5: pytest (with new doctor tests) ...")
    proc = subprocess.run(
        ["python", "-m", "pytest", "tools/infrabeat_erp/tests/", "-q", "--tb=line"],
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        print("\nFATAL: pytest failed")
        return proc.returncode
    print()

    print("Step 6: live invocation of `infrabeat-erp doctor` ...")
    proc = subprocess.run(
        ["infrabeat-erp", "doctor"],
        capture_output=True,
        text=True,
    )
    print(f"  exit code: {proc.returncode}")
    print("  ---")
    for line in proc.stdout.splitlines():
        print(f"  {line}")
    if proc.stderr.strip():
        for line in proc.stderr.splitlines()[:5]:
            print(f"  [stderr] {line}")
    print()

    print("=== Task (D) complete ===")
    print()
    print("Final staged state:")
    subprocess.run(["git", "status", "--short"], cwd=str(REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())