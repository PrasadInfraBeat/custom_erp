"""Task 1b rewriter: dev VM support + 3-tarball downloads + new tests.

Atomic, self-verifying. Per L74+L81, every write is read back and checked.
Run from repo root: python scripts/task1b_backup_rewriter.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKUP_PY = REPO / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "application" / "backup.py"
CLI_PY = REPO / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "cli.py"
TEST_PY = REPO / "tools" / "infrabeat_erp" / "tests" / "test_backup.py"


NEW_BACKUP_PY = '''"""Backup subcommand: run bench backup remotely + SFTP download + verify SHA256.

Phase 7a Sprint 2 Task 1b: full backup capability across all 3 VMs.
  - dev VM uses sudo -n -u frappe to switch to bench user
  - --with-files downloads database + files-tar + private-files-tar (3 tarballs)
  - --no-files (or with_files=False) restricts to database only
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .doctor import VMS


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

# Bench user on each VM. On dev: SSH user erpadmin != bench user frappe.
VM_BENCH_USER = {
    "dev": "frappe",
    "staging": "erpadmin",
    "production": "erpadmin",
}

SUPPORTED_VMS = {"dev", "staging", "production"}

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
    # Task 1b additions (None when --no-files or files absent at source)
    remote_files_path: Optional[str] = None
    local_files_path: Optional[Path] = None
    files_size_bytes: Optional[int] = None
    files_sha256: Optional[str] = None
    remote_private_files_path: Optional[str] = None
    local_private_files_path: Optional[Path] = None
    private_files_size_bytes: Optional[int] = None
    private_files_sha256: Optional[str] = None


_BACKUP_PATH_PATTERNS = [
    re.compile(r"(/[^\\s]+\\d{8}_\\d{6}-[^\\s/]+-database\\.sql\\.gz)"),
    re.compile(r"(/[^\\s]+-database\\.sql\\.gz)"),
]


def _parse_backup_output(output: str) -> dict[str, str]:
    """Extract backup file paths from `bench backup` stdout (legacy; superseded by ls)."""
    paths: dict[str, str] = {}
    for line in output.splitlines():
        for pat in _BACKUP_PATH_PATTERNS:
            m = pat.search(line)
            if m and "database" not in paths:
                paths["database"] = m.group(1)
                break
    return paths


def _needs_sudo(vm_name: str, ssh_user: str) -> bool:
    return ssh_user != VM_BENCH_USER[vm_name]


def _wrap_for_sudo(command: str, bench_user: str) -> str:
    """sudo -n: non-interactive, fails fast if password required."""
    escaped = command.replace("'", "'\\\\''")
    return f"sudo -n -u {bench_user} bash -c '{escaped}'"


def _build_bench_command(vm_name, ssh_user, site, bench_path, with_files):
    files_flag = " --with-files" if with_files else ""
    inner = f"cd {bench_path} && bench --site {site} backup{files_flag} 2>&1"
    if _needs_sudo(vm_name, ssh_user):
        return _wrap_for_sudo(inner, VM_BENCH_USER[vm_name])
    return inner


def _build_ls_command(vm_name, ssh_user, bench_path, site, glob_suffix):
    backups_dir = f"{bench_path}/sites/{site}/private/backups"
    inner = f"ls -t {backups_dir}/*{glob_suffix} 2>/dev/null | head -1"
    if _needs_sudo(vm_name, ssh_user):
        return _wrap_for_sudo(inner, VM_BENCH_USER[vm_name])
    return inner


def _build_chmod_command(vm_name, ssh_user, remote_path):
    if not _needs_sudo(vm_name, ssh_user):
        return None
    return _wrap_for_sudo(f"chmod 644 {remote_path}", VM_BENCH_USER[vm_name])


async def _locate_and_download(vm, vm_name, bench_path, site, glob_suffix, local_dir, adapter):
    """ls -t + chmod 644 (if dev) + SFTP + sha256. Returns 4-tuple or all-None if ls empty."""
    ls_cmd = _build_ls_command(vm_name, vm["user"], bench_path, site, glob_suffix)
    ls_exit, ls_out, _ = await adapter.exec(vm["host"], vm["user"], ls_cmd, timeout=30)
    remote_path = ls_out.strip()
    if ls_exit != 0 or not remote_path:
        return None, None, None, None

    chmod_cmd = _build_chmod_command(vm_name, vm["user"], remote_path)
    if chmod_cmd:
        await adapter.exec(vm["host"], vm["user"], chmod_cmd, timeout=10)

    local_path = local_dir / Path(remote_path).name
    await adapter.download_file(vm["host"], vm["user"], remote_path, local_path)
    if not local_path.exists():
        raise BackupError(f"download failed: {local_path} not created")

    sha = hashlib.sha256(local_path.read_bytes()).hexdigest()
    size = local_path.stat().st_size
    return remote_path, local_path, size, sha


async def do_backup(
    vm_name: str,
    adapter,
    output_dir: Path = DEFAULT_BACKUP_DIR,
    with_files: bool = True,
) -> BackupResult:
    """Run bench backup, download tarballs, verify SHA256.

    Args:
        vm_name: One of dev|staging|production.
        adapter: SshAdapter (async exec() + download_file()).
        output_dir: Local base; per-run subdir created.
        with_files: When True (default), also download files-tar + private-files-tar.

    Raises:
        BackupError: on unknown VM, bench failure, db-not-found, or download failure.
    """
    if vm_name not in SUPPORTED_VMS:
        raise BackupError(
            f"VM '{vm_name}' not supported. Use one of: {sorted(SUPPORTED_VMS)}."
        )

    vm = next((v for v in VMS if v["name"] == vm_name), None)
    if not vm:
        raise BackupError(f"Unknown VM (not in VMS): {vm_name}")

    site = VM_SITES[vm_name]
    bench_path = VM_BENCH_PATHS[vm_name]
    t_start = time.perf_counter()

    # 1) bench backup
    cmd = _build_bench_command(vm_name, vm["user"], site, bench_path, with_files)
    bench_exit, bench_out, bench_err = await adapter.exec(
        vm["host"], vm["user"], cmd, timeout=900
    )
    if bench_exit != 0:
        raise BackupError(
            f"bench backup exit {bench_exit} on {vm_name}: "
            f"{(bench_err or bench_out)[:300]}"
        )

    # 2) prepare local output dir
    timestamp = datetime.now(timezone.utc)
    local_dir = output_dir / vm_name / timestamp.strftime("%Y%m%d_%H%M%S")
    local_dir.mkdir(parents=True, exist_ok=True)

    # 3) locate + download database (required)
    db_remote, db_local, db_size, db_sha = await _locate_and_download(
        vm, vm_name, bench_path, site, "-database.sql.gz", local_dir, adapter
    )
    if not db_remote:
        raise BackupError(
            f"could not locate database backup file in "
            f"{bench_path}/sites/{site}/private/backups/"
        )

    # 4) optional: files-tar + private-files-tar (no error if absent)
    files_remote = files_local = files_size = files_sha = None
    priv_remote = priv_local = priv_size = priv_sha = None
    if with_files:
        files_remote, files_local, files_size, files_sha = await _locate_and_download(
            vm, vm_name, bench_path, site, "-files.tar", local_dir, adapter
        )
        priv_remote, priv_local, priv_size, priv_sha = await _locate_and_download(
            vm, vm_name, bench_path, site, "-private-files.tar", local_dir, adapter
        )

    duration = time.perf_counter() - t_start
    return BackupResult(
        vm_name=vm_name,
        site=site,
        timestamp=timestamp,
        remote_db_path=db_remote,
        local_db_path=db_local,
        db_size_bytes=db_size,
        db_sha256=db_sha,
        duration_seconds=duration,
        remote_files_path=files_remote,
        local_files_path=files_local,
        files_size_bytes=files_size,
        files_sha256=files_sha,
        remote_private_files_path=priv_remote,
        local_private_files_path=priv_local,
        private_files_size_bytes=priv_size,
        private_files_sha256=priv_sha,
    )
'''


NEW_TEST_PY = '''"""Tests for infrabeat-erp backup subcommand (Sprint 2 Task 1b)."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Optional

import pytest

from infrabeat_erp.application.backup import (
    BackupError,
    BackupResult,
    SUPPORTED_VMS,
    _parse_backup_output,
    do_backup,
)


class MockAdapter:
    """Mock SshAdapter that routes exec by command keywords and writes fake tarballs."""

    def __init__(
        self,
        bench_output: str = "",
        bench_exit: int = 0,
        ls_db: Optional[str] = "/home/erpadmin/frappe-bench/sites/erp.staging/private/backups/20260512_120000-erp_staging-database.sql.gz",
        ls_files: Optional[str] = None,
        ls_private_files: Optional[str] = None,
        download_bytes: bytes = b"fake_db_dump",
    ):
        self.bench_output = bench_output
        self.bench_exit = bench_exit
        self.ls_db = ls_db
        self.ls_files = ls_files
        self.ls_private_files = ls_private_files
        self.download_bytes = download_bytes
        self.exec_calls: list[dict] = []
        self.download_calls: list[dict] = []

    async def exec(self, host, user, command, timeout=10):
        self.exec_calls.append({"host": host, "user": user, "command": command, "timeout": timeout})
        # Most-specific patterns first
        if "ls -t" in command and "-private-files.tar" in command:
            return 0, self.ls_private_files or "", ""
        if "ls -t" in command and "-files.tar" in command:
            return 0, self.ls_files or "", ""
        if "ls -t" in command and "-database.sql.gz" in command:
            return 0, self.ls_db or "", ""
        if "chmod 644" in command:
            return 0, "", ""
        if "bench --site" in command:
            return self.bench_exit, self.bench_output, ""
        return 0, "", ""

    async def download_file(self, host, user, remote_path, local_path, timeout=300):
        self.download_calls.append({"remote": remote_path, "local": str(local_path)})
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_bytes(self.download_bytes)


# parser tests (carryover)

def test_parse_backup_output_extracts_database_path():
    out = (
        "Backup Summary for erp.staging\\n"
        "Database: /home/erpadmin/frappe-bench/sites/erp.staging/private/backups/"
        "20260512_120000-erp_staging-database.sql.gz\\n"
    )
    paths = _parse_backup_output(out)
    assert "database" in paths
    assert paths["database"].endswith("database.sql.gz")


def test_parse_backup_output_empty_when_no_paths():
    assert _parse_backup_output("") == {}
    assert _parse_backup_output("nothing useful here") == {}


# validation + error tests

def test_do_backup_rejects_unknown_vm():
    with pytest.raises(BackupError, match="not supported"):
        asyncio.run(do_backup("nonexistent", MockAdapter()))


def test_do_backup_raises_on_bench_failure():
    adapter = MockAdapter(bench_exit=1, bench_output="bench: command failed")
    with pytest.raises(BackupError, match="exit 1"):
        asyncio.run(do_backup("staging", adapter))


def test_do_backup_raises_when_ls_finds_no_backup():
    adapter = MockAdapter(bench_output="bench succeeded", ls_db="")
    with pytest.raises(BackupError, match="could not locate database backup file"):
        asyncio.run(do_backup("staging", adapter))


# happy path (db only)

def test_do_backup_success_returns_BackupResult(tmp_path):
    fake_bytes = b"this is a fake database dump"
    adapter = MockAdapter(bench_output="ok", download_bytes=fake_bytes)
    result = asyncio.run(
        do_backup("staging", adapter, output_dir=tmp_path, with_files=False)
    )
    assert isinstance(result, BackupResult)
    assert result.vm_name == "staging"
    assert result.site == "erp.staging"
    assert result.db_sha256 == hashlib.sha256(fake_bytes).hexdigest()
    assert result.db_size_bytes == len(fake_bytes)
    assert result.duration_seconds >= 0
    assert result.local_db_path.exists()
    assert result.remote_files_path is None
    assert result.local_files_path is None


# Task 1b: dev VM sudo wrapping

def test_do_backup_dev_uses_sudo_prefix(tmp_path):
    adapter = MockAdapter(
        bench_output="ok",
        ls_db="/home/frappe/frappe-bench/sites/erp.local/private/backups/x-database.sql.gz",
    )
    asyncio.run(do_backup("dev", adapter, output_dir=tmp_path, with_files=False))
    bench_call = next(c for c in adapter.exec_calls if "bench --site erp.local" in c["command"])
    assert "sudo -n -u frappe" in bench_call["command"], (
        f"Dev bench cmd missing sudo: {bench_call['command']}"
    )


def test_do_backup_staging_does_not_use_sudo(tmp_path):
    adapter = MockAdapter(bench_output="ok")
    asyncio.run(do_backup("staging", adapter, output_dir=tmp_path, with_files=False))
    bench_call = next(c for c in adapter.exec_calls if "bench --site erp.staging" in c["command"])
    assert "sudo" not in bench_call["command"]


# Task 1b: 3-tarball downloads

def test_do_backup_with_files_downloads_3_tarballs(tmp_path):
    db_path = "/home/erpadmin/frappe-bench/sites/erp.staging/private/backups/x-database.sql.gz"
    files_path = "/home/erpadmin/frappe-bench/sites/erp.staging/private/backups/x-files.tar"
    priv_path = "/home/erpadmin/frappe-bench/sites/erp.staging/private/backups/x-private-files.tar"
    adapter = MockAdapter(
        bench_output="ok",
        ls_db=db_path,
        ls_files=files_path,
        ls_private_files=priv_path,
    )
    result = asyncio.run(do_backup("staging", adapter, output_dir=tmp_path, with_files=True))
    assert len(adapter.download_calls) == 3
    assert result.remote_files_path == files_path
    assert result.remote_private_files_path == priv_path
    assert result.files_sha256 is not None
    assert result.private_files_sha256 is not None


def test_do_backup_with_files_handles_missing_files_tar(tmp_path):
    """Clean site (no files yet): ls empty for files-tar, no error, fields stay None."""
    adapter = MockAdapter(bench_output="ok", ls_files=None, ls_private_files=None)
    result = asyncio.run(do_backup("staging", adapter, output_dir=tmp_path, with_files=True))
    assert len(adapter.download_calls) == 1
    assert result.remote_files_path is None
    assert result.files_sha256 is None


def test_do_backup_no_files_skips_extra_downloads(tmp_path):
    adapter = MockAdapter(bench_output="ok")
    asyncio.run(do_backup("staging", adapter, output_dir=tmp_path, with_files=False))
    bench_call = next(c for c in adapter.exec_calls if "bench --site" in c["command"])
    assert "--with-files" not in bench_call["command"]
    assert len(adapter.download_calls) == 1


def test_supported_vms_contains_all_three():
    assert SUPPORTED_VMS == {"dev", "staging", "production"}
'''


CLI_PATCHES = [
    {
        "label": "Click decorators + signature + docstring",
        "old": (
            '@click.argument("vm_name", type=click.Choice(["staging", "production"]))\n'
            '@click.option("--output-dir", type=click.Path(), default=None, help="Local backup directory")\n'
            'def backup(vm_name: str, output_dir):\n'
            '    """Backup a VM\'s ERPNext site DB. Sprint 2 Task 1 MVP (staging/production only)."""'
        ),
        "new": (
            '@click.argument("vm_name", type=click.Choice(["dev", "staging", "production"]))\n'
            '@click.option("--output-dir", type=click.Path(), default=None, help="Local backup directory")\n'
            '@click.option("--no-files", is_flag=True, default=False, help="Skip files-tar and private-files-tar; database only.")\n'
            'def backup(vm_name: str, output_dir, no_files: bool):\n'
            '    """Backup a VM\'s ERPNext site (DB + files-tar + private-files-tar). Sprint 2 Task 1b (all 3 VMs)."""'
        ),
    },
    {
        "label": "do_backup call + result echo",
        "old": (
            '        result = _asyncio.run(do_backup(vm_name, adapter, out_dir))\n'
            '        size_mb = result.db_size_bytes / 1024 / 1024\n'
            '        click.echo(f"OK: {result.local_db_path}")\n'
            '        click.echo(f"     {size_mb:.1f} MB | sha256={result.db_sha256[:16]}... | {result.duration_seconds:.1f}s")'
        ),
        "new": (
            '        result = _asyncio.run(do_backup(vm_name, adapter, out_dir, with_files=not no_files))\n'
            '        size_mb = result.db_size_bytes / 1024 / 1024\n'
            '        click.echo(f"OK: {result.local_db_path}")\n'
            '        click.echo(f"     {size_mb:.1f} MB | sha256={result.db_sha256[:16]}... | {result.duration_seconds:.1f}s")\n'
            '        if result.local_files_path:\n'
            '            files_mb = (result.files_size_bytes or 0) / 1024 / 1024\n'
            '            click.echo(f"     files-tar: {result.local_files_path.name} ({files_mb:.1f} MB | sha256={(result.files_sha256 or \'\')[:16]}...)")\n'
            '        if result.local_private_files_path:\n'
            '            priv_mb = (result.private_files_size_bytes or 0) / 1024 / 1024\n'
            '            click.echo(f"     private-files-tar: {result.local_private_files_path.name} ({priv_mb:.1f} MB | sha256={(result.private_files_sha256 or \'\')[:16]}...)")'
        ),
    },
]


def main():
    print(f"REPO root: {REPO}")
    print(f"Targets:")
    print(f"  {BACKUP_PY.relative_to(REPO)}")
    print(f"  {CLI_PY.relative_to(REPO)}")
    print(f"  {TEST_PY.relative_to(REPO)}")
    print("")

    # [1/4] Rewrite backup.py
    print("[1/4] Rewriting backup.py ...")
    BACKUP_PY.write_text(NEW_BACKUP_PY, encoding="utf-8")
    written = BACKUP_PY.read_text(encoding="utf-8")
    if written != NEW_BACKUP_PY:
        print("  FAIL: write mismatch")
        sys.exit(2)
    for marker in [
        "VM_BENCH_USER",
        'SUPPORTED_VMS = {"dev", "staging", "production"}',
        "with_files: bool = True",
        "_wrap_for_sudo",
        "sudo -n -u",
        "_locate_and_download",
    ]:
        if marker not in written:
            print(f"  FAIL: missing marker '{marker}'")
            sys.exit(2)
    print(f"  OK ({len(written)} bytes, {written.count(chr(10))} lines, all 6 markers found)")

    # [2/4] Patch cli.py
    print("[2/4] Patching cli.py (2 surgical str_replace) ...")
    cli_src = CLI_PY.read_text(encoding="utf-8")
    for patch in CLI_PATCHES:
        if patch["old"] not in cli_src:
            print(f"  FAIL: anchor missing for '{patch['label']}'")
            print(f"  Looking for first 100 chars: {patch['old'][:100]!r}")
            sys.exit(2)
        cli_src = cli_src.replace(patch["old"], patch["new"], 1)
        print(f"  OK: {patch['label']}")
    CLI_PY.write_text(cli_src, encoding="utf-8")
    re_read = CLI_PY.read_text(encoding="utf-8")
    for marker in [
        '"--no-files"',
        'click.Choice(["dev", "staging", "production"])',
        'with_files=not no_files',
        'files-tar:',
    ]:
        if marker not in re_read:
            print(f"  FAIL: post-write marker missing '{marker}'")
            sys.exit(2)
    print(f"  cli.py now {len(re_read)} bytes (all 4 markers verified)")

    # [3/4] Rewrite test_backup.py
    print("[3/4] Rewriting test_backup.py ...")
    TEST_PY.write_text(NEW_TEST_PY, encoding="utf-8")
    tw = TEST_PY.read_text(encoding="utf-8")
    if tw != NEW_TEST_PY:
        print("  FAIL: write mismatch")
        sys.exit(2)
    test_count = tw.count("\ndef test_")
    print(f"  OK ({len(tw)} bytes, {test_count} test_ functions)")
    if test_count != 12:
        print(f"  WARN: expected 12 tests, got {test_count}")

    # [4/4] Summary
    print("[4/4] Verification complete.")
    print("")
    print("Next: python -m pytest tools/infrabeat_erp/tests/test_backup.py -v")


if __name__ == "__main__":
    main()