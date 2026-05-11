"""infrabeat-erp doctor: pre-flight checks for InfraBeat operational state.

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
    return "\n".join(lines)


def main(verbose: bool = False) -> int:
    results = run_all()
    print(format_results(results, verbose))
    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main(verbose="--verbose" in sys.argv or "-v" in sys.argv))
