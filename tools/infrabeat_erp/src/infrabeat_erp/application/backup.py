"""Backup subcommand: run bench backup remotely + SFTP download + verify SHA256.

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
    re.compile(r"(/[^\s]+\d{8}_\d{6}-[^\s/]+-database\.sql\.gz)"),
    re.compile(r"(/[^\s]+-database\.sql\.gz)"),
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
    escaped = command.replace("'", "'\\''")
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
