"""Phase 7a Sprint 2 Task 1: infrabeat-erp backup <vm> subcommand (MVP).

Scope (MVP):
  - staging + production only (dev deferred: SSH user != bench user, needs sudo path)
  - Database backup only (.sql.gz) — files-tar in Task 1b
  - SHA256 verification on local copy
  - No audit log integration yet (Task 1b)

Creates:
  - tools/infrabeat_erp/src/infrabeat_erp/application/backup.py            (NEW)
  - tools/infrabeat_erp/tests/test_backup.py                                (NEW)
Modifies:
  - tools/infrabeat_erp/src/infrabeat_erp/infrastructure/ssh_adapter.py    (+download_file)
  - tools/infrabeat_erp/src/infrabeat_erp/cli.py                            (+backup subcommand)
  - .gitignore                                                              (+.coverage)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp"
BACKUP_PY = SRC / "application" / "backup.py"
ADAPTER_PY = SRC / "infrastructure" / "ssh_adapter.py"
CLI_PY = SRC / "cli.py"
TESTS_PY = ROOT / "tools" / "infrabeat_erp" / "tests" / "test_backup.py"
GITIGNORE = ROOT / ".gitignore"


BACKUP_CONTENT = '''"""Backup subcommand: run bench backup remotely + SFTP download + verify SHA256.

Phase 7a Sprint 2 Task 1 MVP. Restrictions:
  - staging + production only (dev's SSH user erpadmin != bench user frappe)
  - database .sql.gz only (files-tar in Task 1b)
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .doctor import VMS


# VM-specific metadata not in VMS dict
VM_SITES = {
    "dev": "erp.local",
    "staging": "erp.staging",
    "production": "erp.production",
}

VM_BENCH_PATHS = {
    "dev": "/home/frappe/frappe-bench",
    "staging": "/home/erpadmin/frappe-bench",
    "production": "/home/erpadmin/frappe-bench",
}

# Task 1 MVP: dev deferred (SSH user erpadmin != bench user frappe; needs sudo path)
SUPPORTED_VMS = {"staging", "production"}

DEFAULT_BACKUP_DIR = Path.home() / ".infrabeat-erp" / "backups"


class BackupError(Exception):
    """Raised when backup workflow fails (any step)."""


@dataclass
class BackupResult:
    vm_name: str
    site: str
    timestamp: datetime
    remote_db_path: str
    local_db_path: Path
    db_size_bytes: int
    db_sha256: str
    duration_seconds: float


_BACKUP_PATH_PATTERNS = [
    re.compile(r"(/[^\\s]+\\d{8}_\\d{6}-[^\\s/]+-database\\.sql\\.gz)"),
    re.compile(r"(/[^\\s]+-database\\.sql\\.gz)"),
]


def _parse_backup_output(output: str) -> dict[str, str]:
    """Extract backup file paths from `bench backup` stdout."""
    paths: dict[str, str] = {}
    for line in output.splitlines():
        for pat in _BACKUP_PATH_PATTERNS:
            m = pat.search(line)
            if m and "database" not in paths:
                paths["database"] = m.group(1)
                break
    return paths


async def do_backup(
    vm_name: str,
    adapter,
    output_dir: Path = DEFAULT_BACKUP_DIR,
) -> BackupResult:
    """Run bench backup remotely, download db tarball, verify SHA256.

    Args:
        vm_name: One of staging|production (dev not yet supported in MVP).
        adapter: SshAdapter instance (must provide async exec() and download_file()).
        output_dir: Local base directory; per-run subdir created.

    Raises:
        BackupError: on unknown VM, bench failure, path-parse failure, or download failure.
    """
    if vm_name not in SUPPORTED_VMS:
        raise BackupError(
            f"VM '{vm_name}' not supported in Task 1 MVP. "
            f"Use one of: {sorted(SUPPORTED_VMS)}. "
            f"(dev backup requires sudo -u frappe; coming in Task 1b.)"
        )

    vm = next((v for v in VMS if v["name"] == vm_name), None)
    if not vm:
        raise BackupError(f"Unknown VM (not in VMS): {vm_name}")

    site = VM_SITES[vm_name]
    bench_path = VM_BENCH_PATHS[vm_name]

    cmd = f"cd {bench_path} && bench --site {site} backup 2>&1"
    loop = asyncio.get_event_loop()
    t0 = loop.time()
    exit_code, out, err = await adapter.exec(vm["host"], vm["user"], cmd, timeout=600)
    if exit_code != 0:
        raise BackupError(
            f"bench backup exit {exit_code} on {vm_name}: {(err or out)[:300]}"
        )

    paths = _parse_backup_output(out)
    if "database" not in paths:
        raise BackupError(
            f"could not find database backup path in bench output. Last 500 chars:\\n{out[-500:]}"
        )

    timestamp = datetime.now(timezone.utc)
    local_dir = output_dir / vm_name / timestamp.strftime("%Y%m%d_%H%M%S")
    local_dir.mkdir(parents=True, exist_ok=True)

    db_remote = paths["database"]
    db_local = local_dir / Path(db_remote).name

    await adapter.download_file(vm["host"], vm["user"], db_remote, db_local)

    if not db_local.exists():
        raise BackupError(f"download failed: {db_local} not created")

    sha256 = hashlib.sha256(db_local.read_bytes()).hexdigest()
    db_size = db_local.stat().st_size
    duration = loop.time() - t0

    return BackupResult(
        vm_name=vm_name,
        site=site,
        timestamp=timestamp,
        remote_db_path=db_remote,
        local_db_path=db_local,
        db_size_bytes=db_size,
        db_sha256=sha256,
        duration_seconds=duration,
    )
'''


# Patches for ssh_adapter.py (add download_file method)
ADAPTER_OLD = '''    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)'''

ADAPTER_NEW = '''    def _download_sync(
        self, host: str, user: str, remote_path: str, local_path: str, timeout: int
    ) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host,
                username=user,
                pkey=self._load_pkey(),
                timeout=10,
                banner_timeout=10,
                auth_timeout=5,
                allow_agent=False,
                look_for_keys=False,
            )
            sftp = client.open_sftp()
            try:
                sftp.get(remote_path, local_path)
            finally:
                sftp.close()
        finally:
            client.close()

    async def download_file(
        self,
        host: str,
        user: str,
        remote_path: str,
        local_path: Path,
        timeout: int = 300,
    ) -> None:
        """Async SFTP download. Blocks the executor thread for the duration."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            self._download_sync,
            host,
            user,
            remote_path,
            str(local_path),
            timeout,
        )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)'''


# Patches for cli.py - append backup subcommand at bottom
CLI_APPEND = '''

@main.command()
@click.argument("vm_name", type=click.Choice(["staging", "production"]))
@click.option("--output-dir", type=click.Path(), default=None, help="Local backup directory")
def backup(vm_name: str, output_dir):
    """Backup a VM's ERPNext site DB. Sprint 2 Task 1 MVP (staging/production only)."""
    import asyncio as _asyncio
    import sys as _sys
    from pathlib import Path as _Path

    from .application.backup import (
        DEFAULT_BACKUP_DIR,
        BackupError,
        do_backup,
    )
    from .application.doctor import INFRABEAT_SSH_KEY
    from .infrastructure.ssh_adapter import SshAdapter

    if not INFRABEAT_SSH_KEY.exists():
        click.echo(f"SSH key missing: {INFRABEAT_SSH_KEY}", err=True)
        click.echo("Run: python scripts/bootstrap_ssh_keys.py", err=True)
        _sys.exit(1)

    out_dir = _Path(output_dir) if output_dir else DEFAULT_BACKUP_DIR
    adapter = SshAdapter(INFRABEAT_SSH_KEY)
    click.echo(f"Backing up {vm_name}... (may take a few minutes)")
    try:
        result = _asyncio.run(do_backup(vm_name, adapter, out_dir))
        size_mb = result.db_size_bytes / 1024 / 1024
        click.echo(f"OK: {result.local_db_path}")
        click.echo(f"     {size_mb:.1f} MB | sha256={result.db_sha256[:16]}... | {result.duration_seconds:.1f}s")
    except BackupError as e:
        click.echo(f"Backup FAILED: {e}", err=True)
        _sys.exit(1)
    finally:
        adapter.shutdown()
'''


TESTS_CONTENT = '''"""Tests for infrabeat-erp backup subcommand (Sprint 2 Task 1 MVP)."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from infrabeat_erp.application.backup import (
    BackupError,
    BackupResult,
    SUPPORTED_VMS,
    _parse_backup_output,
    do_backup,
)


class MockAdapter:
    """Mock SshAdapter that returns canned bench output + writes fake tarball."""

    def __init__(self, bench_output: str = "", exit_code: int = 0, download_bytes: bytes = b"fake_db_dump"):
        self.bench_output = bench_output
        self.exit_code = exit_code
        self.download_bytes = download_bytes
        self.exec_calls: list[dict] = []
        self.download_calls: list[dict] = []

    async def exec(self, host: str, user: str, command: str, timeout: int = 10):
        self.exec_calls.append({"host": host, "user": user, "command": command})
        return self.exit_code, self.bench_output, ""

    async def download_file(self, host: str, user: str, remote_path: str, local_path: Path, timeout: int = 300):
        self.download_calls.append({"remote": remote_path, "local": str(local_path)})
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_bytes(self.download_bytes)


def test_parse_backup_output_extracts_database_path():
    out = """Backup Summary for erp.staging
Config  : /home/erpadmin/frappe-bench/sites/erp.staging/site_config_backup.json
Database: /home/erpadmin/frappe-bench/sites/erp.staging/private/backups/20260512_120000-erp_staging-database.sql.gz
"""
    paths = _parse_backup_output(out)
    assert "database" in paths
    assert paths["database"].endswith("database.sql.gz")
    assert "20260512_120000" in paths["database"]


def test_parse_backup_output_empty_when_no_paths():
    assert _parse_backup_output("") == {}
    assert _parse_backup_output("nothing useful here") == {}


def test_do_backup_rejects_unsupported_vm():
    """dev is not yet supported in Task 1 MVP."""
    with pytest.raises(BackupError, match="not supported in Task 1 MVP"):
        asyncio.run(do_backup("dev", MockAdapter()))


def test_do_backup_rejects_unknown_vm():
    """A VM name not in SUPPORTED_VMS fails before reaching VMS lookup."""
    with pytest.raises(BackupError):
        asyncio.run(do_backup("nonexistent", MockAdapter()))


def test_do_backup_raises_on_bench_failure():
    adapter = MockAdapter(exit_code=1, bench_output="bench: command failed")
    with pytest.raises(BackupError, match="exit 1"):
        asyncio.run(do_backup("staging", adapter))


def test_do_backup_raises_when_path_not_in_output():
    adapter = MockAdapter(bench_output="bench succeeded but no path shown")
    with pytest.raises(BackupError, match="could not find database backup path"):
        asyncio.run(do_backup("staging", adapter))


def test_do_backup_success_returns_BackupResult(tmp_path):
    bench_out = (
        "Backup Summary\\n"
        "Database: /home/erpadmin/frappe-bench/sites/erp.staging/private/backups/"
        "20260512_120000-erp_staging-database.sql.gz\\n"
    )
    fake_bytes = b"this is a fake database dump"
    adapter = MockAdapter(bench_output=bench_out, download_bytes=fake_bytes)
    result = asyncio.run(do_backup("staging", adapter, output_dir=tmp_path))

    assert isinstance(result, BackupResult)
    assert result.vm_name == "staging"
    assert result.site == "erp.staging"
    assert result.remote_db_path.endswith("database.sql.gz")
    assert result.local_db_path.exists()
    assert result.local_db_path.read_bytes() == fake_bytes
    assert result.db_size_bytes == len(fake_bytes)
    assert result.db_sha256 == hashlib.sha256(fake_bytes).hexdigest()
    assert result.duration_seconds >= 0

    # Verify exec was called once with bench backup
    assert len(adapter.exec_calls) == 1
    assert "bench --site erp.staging backup" in adapter.exec_calls[0]["command"]
    # Verify download was called once
    assert len(adapter.download_calls) == 1
'''


def patch_adapter() -> bool:
    text = ADAPTER_PY.read_text(encoding="utf-8")
    if "def download_file" in text:
        print("  SKIP: download_file already present")
        return True
    if ADAPTER_OLD not in text:
        print("  FAIL: shutdown anchor not found in ssh_adapter.py")
        return False
    text = text.replace(ADAPTER_OLD, ADAPTER_NEW, 1)
    ADAPTER_PY.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", ADAPTER_PY.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    print("  OK: added download_file to ssh_adapter.py")
    return True


def patch_cli() -> bool:
    text = CLI_PY.read_text(encoding="utf-8")
    if "def backup(vm_name" in text:
        print("  SKIP: backup subcommand already present in cli.py")
        return True
    # Append at end of file
    if not text.endswith("\n"):
        text += "\n"
    text += CLI_APPEND
    CLI_PY.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", CLI_PY.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    print("  OK: appended backup subcommand to cli.py")
    return True


def patch_gitignore() -> bool:
    text = GITIGNORE.read_text(encoding="utf-8") if GITIGNORE.exists() else ""
    if ".coverage" in text:
        print("  SKIP: .coverage already in .gitignore")
        return True
    if text and not text.endswith("\n"):
        text += "\n"
    text += "\n# pytest-cov artifact\n.coverage\n.coverage.*\nhtmlcov/\n"
    GITIGNORE.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", GITIGNORE.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    print("  OK: added .coverage to .gitignore")
    return True


def main_entry() -> int:
    print("Phase 7a Sprint 2 Task 1 (MVP): infrabeat-erp backup <vm>\n")
    print("Writing application/backup.py...")
    BACKUP_PY.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_PY.write_text(BACKUP_CONTENT, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", BACKUP_PY.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    print(f"  OK: {BACKUP_PY.relative_to(ROOT)}")

    print("\nPatching infrastructure/ssh_adapter.py (+download_file)...")
    if not patch_adapter():
        return 1

    print("\nPatching cli.py (+backup subcommand)...")
    if not patch_cli():
        return 1

    print("\nWriting tests/test_backup.py...")
    TESTS_PY.write_text(TESTS_CONTENT, encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", "add", TESTS_PY.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    print(f"  OK: {TESTS_PY.relative_to(ROOT)}")

    print("\nPatching .gitignore (+.coverage)...")
    if not patch_gitignore():
        return 1

    print("\nALL OK. Run pytest next.")
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())