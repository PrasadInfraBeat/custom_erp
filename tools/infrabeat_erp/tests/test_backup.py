"""Tests for infrabeat-erp backup subcommand (Sprint 2 Task 1b)."""
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
        "Backup Summary for erp.staging\n"
        "Database: /home/erpadmin/frappe-bench/sites/erp.staging/private/backups/"
        "20260512_120000-erp_staging-database.sql.gz\n"
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
