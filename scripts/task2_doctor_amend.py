"""Phase 7a Sprint 1 Task 2 AMEND: surgical doctor.py + test_doctor.py fix.

The original task2_doctor_vm_expansion.py used regex anchors that didn't match
the actual doctor.py structure (CHECKS constant + run_all loop). This script
uses verbatim string replacement against the exact observed code.

After this runs successfully -> `git commit --amend --no-edit` folds the
doctor.py changes into the existing Task 2 commit (9753973).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "application" / "doctor.py"
TESTS = ROOT / "tools" / "infrabeat_erp" / "tests" / "test_doctor.py"


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> bool:
    """Verbatim replace. Idempotent via marker; loud on ambiguity."""
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"  SKIP (marker present): {label}")
        return True
    count = text.count(old)
    if count == 0:
        print(f"  FAIL anchor not found: {label}")
        return False
    if count > 1:
        print(f"  FAIL ambiguous ({count} matches): {label}")
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print(f"  OK: {label}")
    return True


# === doctor.py edits ===

EDIT1_OLD = "import keyring"
EDIT1_NEW = """import io
import time

import keyring
import paramiko"""

EDIT2_OLD = '''EXPECTED_KEYRING_SERVICES = [
    "infrabeat-vm-creds",
    "infrabeat-erp",
    "infrabeat-erp-master",
]'''
EDIT2_NEW = '''EXPECTED_KEYRING_SERVICES = [
    "infrabeat-vm-creds",
    "infrabeat-erp",
    "infrabeat-erp-master",
]

INFRABEAT_SSH_KEY = Path.home() / ".ssh" / "infrabeat_ed25519"

VMS = [
    {"name": "dev", "host": "10.1.0.184", "user": "erpadmin"},
    {"name": "staging", "host": "10.1.0.185", "user": "erpadmin"},
    {"name": "production", "host": "10.1.0.186", "user": "erpadmin"},
]'''

EDIT3_OLD = "def run_all() -> list[CheckResult]:"
EDIT3_NEW = '''def check_vm_ssh() -> list[CheckResult]:
    """Verify passwordless SSH to each VM using InfraBeat ed25519 key.

    Returns one CheckResult per VM (3 total). PASS includes the hostname
    returned by `hostname` over SSH plus round-trip duration. FAIL captures
    exception type+message and points to bootstrap_ssh_keys.py for remediation.
    """
    if not INFRABEAT_SSH_KEY.exists():
        return [
            CheckResult(
                name=f"vm-ssh-{vm['name']}",
                status="FAIL",
                detail=f"InfraBeat SSH key missing at {INFRABEAT_SSH_KEY}",
                remediation="Run: python scripts/bootstrap_ssh_keys.py",
            )
            for vm in VMS
        ]
    try:
        pkey = paramiko.Ed25519Key.from_private_key(
            io.StringIO(INFRABEAT_SSH_KEY.read_text(encoding="utf-8"))
        )
    except Exception as e:
        return [
            CheckResult(
                name=f"vm-ssh-{vm['name']}",
                status="FAIL",
                detail=f"Failed to load SSH key: {type(e).__name__}: {e}",
                remediation="Verify ~/.ssh/infrabeat_ed25519 is valid ed25519",
            )
            for vm in VMS
        ]
    results: list[CheckResult] = []
    for vm in VMS:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        t0 = time.time()
        try:
            client.connect(
                hostname=vm["host"],
                username=vm["user"],
                pkey=pkey,
                timeout=15,
                banner_timeout=15,
                auth_timeout=10,
                allow_agent=False,
                look_for_keys=False,
            )
            _, stdout, _ = client.exec_command("hostname", timeout=5)
            hn = stdout.read().decode("utf-8", errors="replace").strip()
            results.append(
                CheckResult(
                    name=f"vm-ssh-{vm['name']}",
                    status="PASS",
                    detail=f"{vm['user']}@{vm['host']} -> {hn} ({time.time()-t0:.2f}s)",
                    remediation="",
                )
            )
        except Exception as e:
            results.append(
                CheckResult(
                    name=f"vm-ssh-{vm['name']}",
                    status="FAIL",
                    detail=f"{vm['host']}: {type(e).__name__}: {e} (after {time.time()-t0:.2f}s)",
                    remediation="Verify reachability and re-run scripts/bootstrap_ssh_keys.py",
                )
            )
        finally:
            client.close()
    return results


def run_all() -> list[CheckResult]:'''

EDIT4_OLD = '''        except Exception as exc:
            results.append(
                CheckResult(
                    fn.__name__,
                    "FAIL",
                    f"check raised {type(exc).__name__}: {exc}",
                    "internal bug; please report",
                )
            )
    return results'''
EDIT4_NEW = '''        except Exception as exc:
            results.append(
                CheckResult(
                    fn.__name__,
                    "FAIL",
                    f"check raised {type(exc).__name__}: {exc}",
                    "internal bug; please report",
                )
            )
    # Sprint 1 Task 2: VM-side SSH reachability checks (returns list, so extend)
    try:
        results.extend(check_vm_ssh())
    except Exception as exc:
        results.append(
            CheckResult(
                "vm-ssh",
                "FAIL",
                f"check_vm_ssh raised {type(exc).__name__}: {exc}",
                "internal bug; please report",
            )
        )
    return results'''

# === test_doctor.py edits ===

TEST_EDIT1_OLD = '''from infrabeat_erp.application.doctor import (
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
)'''
TEST_EDIT1_NEW = '''from infrabeat_erp.application.doctor import (
    EXPECTED_VM_CREDENTIALS,
    INFRABEAT_SSH_KEY,
    VMS,
    CheckResult,
    check_audit_dir,
    check_gh_cli,
    check_keyring_backend,
    check_python_version,
    check_vm_credentials,
    check_vm_ssh,
    format_results,
    main,
    run_all,
)
from infrabeat_erp.application import doctor'''


def main_entry() -> int:
    print("Phase 7a Sprint 1 Task 2 AMEND\n")
    print("doctor.py edits:")
    edits = [
        (EDIT1_OLD, EDIT1_NEW, "import paramiko", "imports (io, time, paramiko)"),
        (EDIT2_OLD, EDIT2_NEW, "INFRABEAT_SSH_KEY = Path.home()", "VMS + INFRABEAT_SSH_KEY constants"),
        (EDIT3_OLD, EDIT3_NEW, "def check_vm_ssh() -> list[CheckResult]:", "check_vm_ssh function"),
        (EDIT4_OLD, EDIT4_NEW, "results.extend(check_vm_ssh())", "run_all extended"),
    ]
    all_ok = True
    for old, new, marker, label in edits:
        if not replace_once(DOCTOR, old, new, marker, label):
            all_ok = False
    print("\ntest_doctor.py edits:")
    if not replace_once(
        TESTS,
        TEST_EDIT1_OLD,
        TEST_EDIT1_NEW,
        "from infrabeat_erp.application import doctor",
        "extended imports + module import",
    ):
        all_ok = False
    if not all_ok:
        print("\nFAIL: one or more edits did not apply")
        return 1
    subprocess.run(
        [
            "git",
            "add",
            DOCTOR.relative_to(ROOT).as_posix(),
            TESTS.relative_to(ROOT).as_posix(),
        ],
        cwd=str(ROOT),
        check=True,
    )
    print("\nALL OK. Staged doctor.py + test_doctor.py")
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())