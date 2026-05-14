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

import io
import time

import keyring
import paramiko

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

INFRABEAT_SSH_KEY = Path.home() / ".ssh" / "infrabeat_ed25519"

VMS = [
    {"name": "dev", "host": "10.1.0.184", "user": "erpadmin"},
    {"name": "staging", "host": "10.1.0.185", "user": "erpadmin"},
    {"name": "production", "host": "10.1.0.186", "user": "erpadmin"},
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


def check_github_pat() -> CheckResult:
    """Check if a GitHub PAT is stored for promote subcommand (Sprint 3 Task 3.1)."""
    try:
        from ..infrastructure.pat_store import has_pat
    except ImportError as exc:
        return CheckResult("github-pat", "FAIL", f"pat_store import failed: {exc}")
    if has_pat():
        return CheckResult(
            "github-pat", "PASS",
            "PAT stored in keyring (service=infrabeat-erp-github)",
        )
    return CheckResult(
        "github-pat", "INFO",
        "PAT not stored (run 'infrabeat-erp github-pat set' before promote)",
    )


CHECKS = [
    check_python_version,
    check_keyring_backend,
    check_vm_credentials,
    check_gh_cli,
    check_audit_dir,
    check_github_pat,
]


def check_vm_ssh() -> list[CheckResult]:
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


def check_token_ttl() -> list[CheckResult]:
    """Phase 7b Sprint 1 Task 2 (L92): report access_token TTL per VM.

    Reads cached OAuth tokens via secrets_store.load_secrets and computes
    remaining seconds against (issued_at + expires_in - now). Returns one
    CheckResult per VM in VMS. Status policy:
      INFO  - no cached secrets, or token lacks expiry metadata, or TTL > 5 min
      WARN  - TTL in (0, 5 min] minutes or already expired
    Never FAIL; absent tokens are normal pre-login state.
    """
    from infrabeat_erp.application.auth_retry import token_ttl_seconds
    from infrabeat_erp.infrastructure import secrets_store
    results: list[CheckResult] = []
    for vm in VMS:
        name = vm['name']
        try:
            secrets = secrets_store.load_secrets(name)
        except secrets_store.SecretsNotFound:
            results.append(CheckResult(
                f'token-ttl-{name}', 'INFO',
                'no cached secrets',
                f'infrabeat-erp login {name}',
            ))
            continue
        except Exception as exc:
            results.append(CheckResult(
                f'token-ttl-{name}', 'WARN',
                f'load_secrets error: {type(exc).__name__}: {exc}',
            ))
            continue
        ttl = token_ttl_seconds(secrets)
        if ttl is None:
            results.append(CheckResult(
                f'token-ttl-{name}', 'INFO',
                'token has no issued_at/expires_in fields',
            ))
        elif ttl < 0:
            results.append(CheckResult(
                f'token-ttl-{name}', 'WARN',
                f'expired {abs(ttl) // 60} min ago',
                f'infrabeat-erp login {name}',
            ))
        elif ttl < 300:
            results.append(CheckResult(
                f'token-ttl-{name}', 'WARN',
                f'{ttl // 60} min remaining (refresh soon)',
                f'infrabeat-erp login {name}',
            ))
        else:
            results.append(CheckResult(
                f'token-ttl-{name}', 'INFO',
                f'{ttl // 60} min remaining',
            ))
    return results


def check_oauth_client_liveness() -> list[CheckResult]:
    """Phase 7b Sprint 1 Task 3 (L95): OAuth client liveness probe per VM.

    Uses a 5-second HTTP GET against /.well-known/openid-configuration as a
    proxy for FAC OAuth readiness + server reachability. Status policy:
      PASS - HTTP 2xx (FAC alive, OAuth metadata served)
      INFO - no secrets cached or no client_id in secrets
      WARN - non-2xx response, timeout, or other network error
             (suggests stale client registration or service down)
    Never FAIL: probe failures are advisory, not blocking.
    """
    import httpx
    from infrabeat_erp.infrastructure import config, secrets_store
    results: list[CheckResult] = []
    for vm in VMS:
        name = vm['name']
        try:
            secrets = secrets_store.load_secrets(name)
        except secrets_store.SecretsNotFound:
            results.append(CheckResult(
                f'oauth-liveness-{name}', 'INFO',
                'not registered',
                f'infrabeat-erp register {name}',
            ))
            continue
        except Exception as exc:
            results.append(CheckResult(
                f'oauth-liveness-{name}', 'WARN',
                f'load_secrets error: {type(exc).__name__}: {exc}',
            ))
            continue
        if not secrets.get('client_id'):
            results.append(CheckResult(
                f'oauth-liveness-{name}', 'INFO',
                'no client_id in cached secrets',
                f'infrabeat-erp register {name}',
            ))
            continue
        try:
            vm_config = config.get_vm(name)
            base_url = vm_config.base_url
        except Exception as exc:
            results.append(CheckResult(
                f'oauth-liveness-{name}', 'WARN',
                f'config.get_vm failed: {type(exc).__name__}',
            ))
            continue
        try:
            with httpx.Client(base_url=base_url, timeout=5.0) as client:
                resp = client.get('/.well-known/openid-configuration')
            if 200 <= resp.status_code < 300:
                results.append(CheckResult(
                    f'oauth-liveness-{name}', 'PASS',
                    f'OIDC discovery {resp.status_code} ({resp.elapsed.total_seconds():.2f}s)',
                ))
            else:
                results.append(CheckResult(
                    f'oauth-liveness-{name}', 'WARN',
                    f'OIDC discovery returned HTTP {resp.status_code}',
                    f'infrabeat-erp register {name} --force',
                ))
        except Exception as exc:
            results.append(CheckResult(
                f'oauth-liveness-{name}', 'WARN',
                f'unreachable: {type(exc).__name__}',
                f'verify FAC on {vm["host"]} or re-register with --force',
            ))
    return results


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
    # Phase 7b Sprint 1 Task 2 (L92): per-VM token TTL
    try:
        results.extend(check_token_ttl())
    except Exception as exc:
        results.append(
            CheckResult(
                "token-ttl",
                "FAIL",
                f"check_token_ttl raised {type(exc).__name__}: {exc}",
                "internal bug; please report",
            )
        )
    # Phase 7b Sprint 1 Task 3 (L95): OAuth client liveness per VM
    try:
        results.extend(check_oauth_client_liveness())
    except Exception as exc:
        results.append(
            CheckResult(
                "oauth-liveness",
                "FAIL",
                f"check_oauth_client_liveness raised {type(exc).__name__}: {exc}",
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
