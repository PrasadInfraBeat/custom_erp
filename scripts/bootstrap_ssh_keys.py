"""Phase 7a Sprint 1 Task 1: SSH key bootstrap for all 3 VMs.

Generates ed25519 keypair (if not present), distributes public key to each VM
via password auth (one-shot, using infrabeat-vm-creds keyring), verifies that
passwordless key auth then works.

Idempotent: re-running is safe. Skips key generation if exists; skips
authorized_keys append if already present (grep match); always re-verifies
the key-auth handshake.

Eliminates L72 password-paste-as-runtime-input class of friction. After this
runs successfully once, all future SSH ops on this laptop use key auth.
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

try:
    import keyring
    import paramiko
except ImportError as e:
    print(f"ERROR: missing dependency: {e.name}", file=sys.stderr)
    print("Run: pip install paramiko keyring", file=sys.stderr)
    sys.exit(2)

KEY_PATH = Path.home() / ".ssh" / "infrabeat_ed25519"
PUB_KEY_PATH = KEY_PATH.with_suffix(KEY_PATH.suffix + ".pub")

VMS = [
    {"name": "dev", "host": "10.1.0.184", "user": "erpadmin"},
    {"name": "staging", "host": "10.1.0.185", "user": "erpadmin"},
    {"name": "production", "host": "10.1.0.186", "user": "erpadmin"},
]

KEYRING_SERVICE = "infrabeat-vm-creds"


def ensure_keypair() -> str:
    """Generate ed25519 keypair if missing. Returns pub-key content."""
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if KEY_PATH.exists() and PUB_KEY_PATH.exists():
        print(f"  keypair exists: {KEY_PATH}")
    else:
        print(f"  generating ed25519 keypair: {KEY_PATH}")
        result = subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                "infrabeat-erp@laptop",
                "-f",
                str(KEY_PATH),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"ERROR: ssh-keygen failed: {result.stderr}", file=sys.stderr)
            sys.exit(1)
    pub = PUB_KEY_PATH.read_text(encoding="utf-8").strip()
    return pub


def distribute_to_vm(vm: dict, pub_key: str) -> bool:
    """Append public key to authorized_keys on VM (idempotent). Returns success."""
    print(f"\n  -> {vm['name']} ({vm['host']})")
    password = keyring.get_password(KEYRING_SERVICE, f"{vm['name']}-ssh-password")
    if not password:
        print(f"     SKIP: no keyring entry '{vm['name']}-ssh-password'")
        return False
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=vm["host"],
            username=vm["user"],
            password=password,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
    except Exception as e:
        print(f"     FAIL: password-auth connect: {e}")
        return False
    try:
        cmd = (
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
            "chmod 600 ~/.ssh/authorized_keys && "
            f"(grep -qxF '{pub_key}' ~/.ssh/authorized_keys || "
            f"echo '{pub_key}' >> ~/.ssh/authorized_keys)"
        )
        _, stdout, stderr = client.exec_command(cmd, timeout=10)
        exit_code = stdout.channel.recv_exit_status()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if exit_code != 0:
            print(f"     FAIL: append authorized_keys (exit {exit_code}): {err}")
            return False
        print("     OK: public key in authorized_keys")
    finally:
        client.close()
    return True


def verify_key_auth(vm: dict) -> bool:
    """Reconnect using only the private key. Returns True if passwordless works."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        pkey = paramiko.Ed25519Key.from_private_key(io.StringIO(KEY_PATH.read_text(encoding="utf-8")))
        client.connect(
            hostname=vm["host"],
            username=vm["user"],
            pkey=pkey,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        _, stdout, _ = client.exec_command("hostname", timeout=5)
        hostname = stdout.read().decode("utf-8", errors="replace").strip()
        print(f"     VERIFIED: passwordless auth works (hostname={hostname})")
        return True
    except Exception as e:
        print(f"     VERIFY FAIL: {e}")
        return False
    finally:
        client.close()


def main() -> int:
    print("Phase 7a Sprint 1 Task 1: SSH key bootstrap\n")
    print("Step 1: ensure laptop ed25519 keypair")
    pub_key = ensure_keypair()
    print(f"  pubkey: {pub_key[:60]}...")
    print("\nStep 2: distribute + verify per VM")
    results: dict[str, dict[str, bool]] = {}
    for vm in VMS:
        ok_dist = distribute_to_vm(vm, pub_key)
        ok_verify = verify_key_auth(vm) if ok_dist else False
        results[vm["name"]] = {"distribute": ok_dist, "verify": ok_verify}
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'VM':<12} {'distribute':<12} {'verify':<10}")
    print("-" * 60)
    all_ok = True
    for name, r in results.items():
        d = "OK" if r["distribute"] else "SKIP/FAIL"
        v = "OK" if r["verify"] else "FAIL"
        print(f"{name:<12} {d:<12} {v:<10}")
        if not r["verify"]:
            all_ok = False
    print("=" * 60)
    if all_ok:
        print("\nAll VMs passwordless via key. L72 password-paste class eliminated.")
        return 0
    print("\nOne or more VMs not verified. Production may not be provisioned (expected).")
    print("Treat dev + staging verification as the gate for Sprint 1 success.")
    return 0  # Don't fail on prod-not-provisioned; report and continue


if __name__ == "__main__":
    sys.exit(main())