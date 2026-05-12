"""Phase 7a Sprint 1 Task 2: extend doctor with VM-side SSH reachability checks.

Patches:
  - tools/infrabeat_erp/src/infrabeat_erp/application/doctor.py
      * adds imports: io, time, paramiko
      * adds constants: INFRABEAT_SSH_KEY, VMS
      * adds check_vm_ssh() function returning list[CheckResult] (3 results)
      * modifies main() to extend results with check_vm_ssh() output
  - tools/infrabeat_erp/tests/test_doctor.py
      * appends 4 unit tests: missing-key, corrupt-key, all-pass, one-timeout

Idempotent: skips if changes already applied. Defensive: refuses to write if anchors missing.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "application" / "doctor.py"
TESTS = ROOT / "tools" / "infrabeat_erp" / "tests" / "test_doctor.py"

NEW_IMPORTS = "import io\nimport time\n\nimport paramiko"

NEW_CONSTANTS = '''
INFRABEAT_SSH_KEY = Path.home() / ".ssh" / "infrabeat_ed25519"

VMS = [
    {"name": "dev", "host": "10.1.0.184", "user": "erpadmin"},
    {"name": "staging", "host": "10.1.0.185", "user": "erpadmin"},
    {"name": "production", "host": "10.1.0.186", "user": "erpadmin"},
]
'''

NEW_FUNCTION = '''def check_vm_ssh() -> list[CheckResult]:
    """Verify passwordless SSH connectivity to each VM using InfraBeat ed25519 key.

    Returns one CheckResult per VM (3 total). PASS includes the hostname returned
    by `hostname` over SSH and the round-trip duration. FAIL captures the exception
    type and message plus remediation pointing to the bootstrap script.
    """
    if not INFRABEAT_SSH_KEY.exists():
        return [
            CheckResult(
                name=f"vm-ssh-{vm['name']}",
                status="FAIL",
                detail=f"InfraBeat SSH key missing at {INFRABEAT_SSH_KEY}",
                remediation="Run: python scripts/bootstrap_ssh_keys.py to distribute keys to all 3 VMs",
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
                remediation="Verify ~/.ssh/infrabeat_ed25519 is a valid ed25519 private key",
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
            hostname = stdout.read().decode("utf-8", errors="replace").strip()
            elapsed = time.time() - t0
            results.append(
                CheckResult(
                    name=f"vm-ssh-{vm['name']}",
                    status="PASS",
                    detail=f"{vm['user']}@{vm['host']} -> {hostname} ({elapsed:.2f}s)",
                    remediation=None,
                )
            )
        except Exception as e:
            elapsed = time.time() - t0
            results.append(
                CheckResult(
                    name=f"vm-ssh-{vm['name']}",
                    status="FAIL",
                    detail=f"{vm['host']}: {type(e).__name__}: {e} (after {elapsed:.2f}s)",
                    remediation="Verify network reachability and re-run scripts/bootstrap_ssh_keys.py",
                )
            )
        finally:
            client.close()
    return results


'''

NEW_TESTS = '''

# ---- VM SSH reachability tests (Sprint 1 Task 2) ----


def test_check_vm_ssh_missing_key(tmp_path, monkeypatch):
    """When SSH key file is missing, all 3 VMs report FAIL with bootstrap remediation."""
    monkeypatch.setattr(doctor, "INFRABEAT_SSH_KEY", tmp_path / "nonexistent_key")
    results = doctor.check_vm_ssh()
    assert len(results) == 3
    assert all(r.status == "FAIL" for r in results)
    assert all("bootstrap_ssh_keys.py" in (r.remediation or "") for r in results)


def test_check_vm_ssh_corrupt_key(tmp_path, monkeypatch):
    """When SSH key file is unreadable as ed25519, all 3 VMs report FAIL."""
    bad_key = tmp_path / "bad_key"
    bad_key.write_text("not a real key")
    monkeypatch.setattr(doctor, "INFRABEAT_SSH_KEY", bad_key)
    results = doctor.check_vm_ssh()
    assert len(results) == 3
    assert all(r.status == "FAIL" for r in results)
    assert all("Failed to load SSH key" in r.detail for r in results)


def test_check_vm_ssh_all_pass(monkeypatch, tmp_path):
    """When paramiko connects successfully for all 3 VMs, all report PASS."""
    key = tmp_path / "fake_key"
    key.write_text("anything")
    monkeypatch.setattr(doctor, "INFRABEAT_SSH_KEY", key)
    monkeypatch.setattr(
        doctor.paramiko.Ed25519Key, "from_private_key", staticmethod(lambda _: "FAKE_PKEY")
    )

    class FakeStdout:
        def read(self):
            return b"erp-vm\\n"

    class FakeClient:
        def set_missing_host_key_policy(self, *_):
            pass

        def connect(self, **_):
            pass

        def exec_command(self, *_, **__):
            return None, FakeStdout(), None

        def close(self):
            pass

    monkeypatch.setattr(doctor.paramiko, "SSHClient", lambda: FakeClient())
    results = doctor.check_vm_ssh()
    assert len(results) == 3
    assert all(r.status == "PASS" for r in results)
    assert all("erp-vm" in r.detail for r in results)


def test_check_vm_ssh_one_timeout(monkeypatch, tmp_path):
    """When paramiko raises socket.timeout on connect, that VM reports FAIL with retry remediation."""
    import socket

    key = tmp_path / "fake_key"
    key.write_text("anything")
    monkeypatch.setattr(doctor, "INFRABEAT_SSH_KEY", key)
    monkeypatch.setattr(
        doctor.paramiko.Ed25519Key, "from_private_key", staticmethod(lambda _: "FAKE_PKEY")
    )

    class FakeClient:
        def set_missing_host_key_policy(self, *_):
            pass

        def connect(self, **_):
            raise socket.timeout("timed out")

        def exec_command(self, *_, **__):
            return None, None, None

        def close(self):
            pass

    monkeypatch.setattr(doctor.paramiko, "SSHClient", lambda: FakeClient())
    results = doctor.check_vm_ssh()
    assert len(results) == 3
    assert all(r.status == "FAIL" for r in results)
    assert all("timed out" in r.detail for r in results)
    assert all("bootstrap_ssh_keys.py" in (r.remediation or "") for r in results)
'''


def patch_doctor() -> tuple[bool, list[str]]:
    if not DOCTOR.exists():
        return False, [f"doctor.py not found at {DOCTOR}"]
    text = DOCTOR.read_text(encoding="utf-8")
    applied: list[str] = []
    already_present = "def check_vm_ssh" in text

    if already_present:
        return False, ["check_vm_ssh already present - skip"]

    # 1. Insert imports after last `import`/`from` statement
    if "import paramiko" not in text:
        import_lines = list(re.finditer(r"^(?:import |from )[^\n]+", text, re.MULTILINE))
        if not import_lines:
            return False, ["could not locate imports block"]
        insert_pos = import_lines[-1].end()
        text = text[:insert_pos] + "\n" + NEW_IMPORTS + text[insert_pos:]
        applied.append("added imports (io, time, paramiko)")

    # 2. Add VMS + INFRABEAT_SSH_KEY constants after EXPECTED_VM_CREDENTIALS list
    if "VMS = [" not in text:
        m = re.search(r"EXPECTED_VM_CREDENTIALS\s*=\s*\[[\s\S]*?\n\]", text)
        if not m:
            return False, ["could not locate EXPECTED_VM_CREDENTIALS list"]
        insert_pos = m.end()
        text = text[:insert_pos] + NEW_CONSTANTS + text[insert_pos:]
        applied.append("added VMS + INFRABEAT_SSH_KEY constants")

    # 3. Insert check_vm_ssh function before format_results / main
    inserted_fn = False
    for anchor in ("def format_results", "def main("):
        m = re.search(rf"^{re.escape(anchor)}", text, re.MULTILINE)
        if m:
            insert_pos = m.start()
            text = text[:insert_pos] + NEW_FUNCTION + text[insert_pos:]
            applied.append(f"added check_vm_ssh() before {anchor}")
            inserted_fn = True
            break
    if not inserted_fn:
        return False, ["could not locate format_results or main function"]

    # 4. Wire check_vm_ssh into main() — add results.extend after last results.append(check_*())
    matches = list(re.finditer(r"^(\s+)results\.append\(check_\w+\(\)\)\s*$", text, re.MULTILINE))
    if not matches:
        return False, ["could not locate results.append(check_*()) lines in main"]
    last_match = matches[-1]
    indent = last_match.group(1)
    new_line = f"\n{indent}results.extend(check_vm_ssh())"
    text = text[: last_match.end()] + new_line + text[last_match.end() :]
    applied.append("wired check_vm_ssh into main()")

    DOCTOR.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", DOCTOR.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    return True, applied


def patch_tests() -> tuple[bool, list[str]]:
    if not TESTS.exists():
        return False, [f"test_doctor.py not found at {TESTS}"]
    text = TESTS.read_text(encoding="utf-8")
    if "test_check_vm_ssh_missing_key" in text:
        return False, ["VM SSH tests already present - skip"]
    if not text.endswith("\n"):
        text += "\n"
    text += NEW_TESTS
    TESTS.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", TESTS.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    return True, ["appended 4 new unit tests"]


def main() -> int:
    print("Phase 7a Sprint 1 Task 2: doctor VM-side SSH expansion\n")
    print("Patching doctor.py...")
    ok, msgs = patch_doctor()
    for m in msgs:
        print(f"  {'OK' if ok else 'SKIP'}: {m}")
    print("\nPatching test_doctor.py...")
    ok2, msgs2 = patch_tests()
    for m in msgs2:
        print(f"  {'OK' if ok2 else 'SKIP'}: {m}")
    print("\nDone. Review: git diff --cached")
    return 0


if __name__ == "__main__":
    sys.exit(main())