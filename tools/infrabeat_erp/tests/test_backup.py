"""Tests for infrabeat-erp backup subcommand (Sprint 2 Task 1 MVP)."""
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
    """Mock SshAdapter that routes exec by command (bench vs ls) + writes fake tarball."""

    def __init__(
        self,
        bench_output: str = "",
        exit_code: int = 0,
        download_bytes: bytes = b"fake_db_dump",
        ls_output: str = "/home/erpadmin/frappe-bench/sites/erp.staging/private/backups/20260512_120000-erp_staging-database.sql.gz",
    ):
        self.bench_output = bench_output
        self.exit_code = exit_code
        self.download_bytes = download_bytes
        self.ls_output = ls_output
        self.exec_calls: list[dict] = []
        self.download_calls: list[dict] = []

    async def exec(self, host: str, user: str, command: str, timeout: int = 10):
        self.exec_calls.append({"host": host, "user": user, "command": command})
        if "ls -t" in command:
            return 0, self.ls_output, ""
        if "bench --site" in command:
            return self.exit_code, self.bench_output, ""
        return 0, "", ""

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


def test_do_backup_raises_when_ls_finds_no_backup():
    """When ls returns empty (no backup file present), raise BackupError."""
    adapter = MockAdapter(bench_output="bench succeeded", ls_output="")
    with pytest.raises(BackupError, match="could not locate database backup file"):
        asyncio.run(do_backup("staging", adapter))


def test_do_backup_success_returns_BackupResult(tmp_path):
    bench_out = (
        "Backup Summary\n"
        "Database: /home/erpadmin/frappe-bench/sites/erp.staging/private/backups/"
        "20260512_120000-erp_staging-database.sql.gz\n"
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
    assert len(adapter.exec_calls) == 2  # bench + ls
    assert "bench --site erp.staging backup" in adapter.exec_calls[0]["command"]
    # Verify download was called once
    assert len(adapter.download_calls) == 1
