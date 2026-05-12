"""Backup subcommand: run bench backup remotely + SFTP download + verify SHA256.

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
    re.compile(r"(/[^\s]+\d{8}_\d{6}-[^\s/]+-database\.sql\.gz)"),
    re.compile(r"(/[^\s]+-database\.sql\.gz)"),
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

    # Resolve absolute path of most-recent database backup via ls (robust across bench versions)
    ls_cmd = (
        f"ls -t {bench_path}/sites/{site}/private/backups/*-database.sql.gz 2>/dev/null | head -1"
    )
    ls_exit, ls_out, ls_err = await adapter.exec(vm["host"], vm["user"], ls_cmd, timeout=30)
    db_remote = ls_out.strip()
    if ls_exit != 0 or not db_remote:
        raise BackupError(
            f"could not locate database backup file in "
            f"{bench_path}/sites/{site}/private/backups/ "
            f"(ls exit {ls_exit}, output: {ls_out[:200]!r})"
        )

    timestamp = datetime.now(timezone.utc)
    local_dir = output_dir / vm_name / timestamp.strftime("%Y%m%d_%H%M%S")
    local_dir.mkdir(parents=True, exist_ok=True)
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
