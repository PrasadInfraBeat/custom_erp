"""Task 1 amend: switch path resolution from bench-output parsing to `ls -t`.

The original parser captured the relative-path portion of bench output as if
absolute, causing SFTP ENOENT. New approach: after bench succeeds, run
`ls -t <bench>/sites/<site>/private/backups/*-database.sql.gz | head -1` to
get the absolute path of the most-recent backup file. No more regex parsing
of bench output, no version drift surface.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP = ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp" / "application" / "backup.py"
TESTS = ROOT / "tools" / "infrabeat_erp" / "tests" / "test_backup.py"


# === backup.py patch: replace the path-resolution block ===

BACKUP_OLD = '''    paths = _parse_backup_output(out)
    if "database" not in paths:
        raise BackupError(
            f"could not find database backup path in bench output. Last 500 chars:\\n{out[-500:]}"
        )

    timestamp = datetime.now(timezone.utc)
    local_dir = output_dir / vm_name / timestamp.strftime("%Y%m%d_%H%M%S")
    local_dir.mkdir(parents=True, exist_ok=True)

    db_remote = paths["database"]
    db_local = local_dir / Path(db_remote).name'''

BACKUP_NEW = '''    # Resolve absolute path of most-recent database backup via ls (robust across bench versions)
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
    db_local = local_dir / Path(db_remote).name'''


# === test_backup.py patch: MockAdapter now routes by command + replace stale path-fail test ===

TESTS_MOCK_OLD = '''class MockAdapter:
    """Mock SshAdapter that returns canned bench output + writes fake tarball."""

    def __init__(self, bench_output: str = "", exit_code: int = 0, download_bytes: bytes = b"fake_db_dump"):
        self.bench_output = bench_output
        self.exit_code = exit_code
        self.download_bytes = download_bytes
        self.exec_calls: list[dict] = []
        self.download_calls: list[dict] = []

    async def exec(self, host: str, user: str, command: str, timeout: int = 10):
        self.exec_calls.append({"host": host, "user": user, "command": command})
        return self.exit_code, self.bench_output, ""'''

TESTS_MOCK_NEW = '''class MockAdapter:
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
        if "bench" in command and "backup" in command:
            return self.exit_code, self.bench_output, ""
        if "ls -t" in command:
            return 0, self.ls_output, ""
        return 0, "", ""'''


TESTS_OLD_FAIL_TEST = '''def test_do_backup_raises_when_path_not_in_output():
    adapter = MockAdapter(bench_output="bench succeeded but no path shown")
    with pytest.raises(BackupError, match="could not find database backup path"):
        asyncio.run(do_backup("staging", adapter))'''

TESTS_NEW_FAIL_TEST = '''def test_do_backup_raises_when_ls_finds_no_backup():
    """When ls returns empty (no backup file present), raise BackupError."""
    adapter = MockAdapter(bench_output="bench succeeded", ls_output="")
    with pytest.raises(BackupError, match="could not locate database backup file"):
        asyncio.run(do_backup("staging", adapter))'''


TESTS_SUCCESS_OLD = '''def test_do_backup_success_returns_BackupResult(tmp_path):
    bench_out = (
        "Backup Summary\\\\n"
        "Database: /home/erpadmin/frappe-bench/sites/erp.staging/private/backups/"
        "20260512_120000-erp_staging-database.sql.gz\\\\n"
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
    assert len(adapter.download_calls) == 1'''

TESTS_SUCCESS_NEW = '''def test_do_backup_success_returns_BackupResult(tmp_path):
    fake_bytes = b"this is a fake database dump"
    ls_path = "/home/erpadmin/frappe-bench/sites/erp.staging/private/backups/20260512_120000-erp_staging-database.sql.gz"
    adapter = MockAdapter(
        bench_output="bench backup OK",
        download_bytes=fake_bytes,
        ls_output=ls_path,
    )
    result = asyncio.run(do_backup("staging", adapter, output_dir=tmp_path))

    assert isinstance(result, BackupResult)
    assert result.vm_name == "staging"
    assert result.site == "erp.staging"
    assert result.remote_db_path == ls_path
    assert result.local_db_path.exists()
    assert result.local_db_path.read_bytes() == fake_bytes
    assert result.db_size_bytes == len(fake_bytes)
    assert result.db_sha256 == hashlib.sha256(fake_bytes).hexdigest()
    assert result.duration_seconds >= 0

    # Verify TWO exec calls now: bench backup + ls -t
    assert len(adapter.exec_calls) == 2
    assert "bench --site erp.staging backup" in adapter.exec_calls[0]["command"]
    assert "ls -t" in adapter.exec_calls[1]["command"]
    # Verify download was called once
    assert len(adapter.download_calls) == 1'''


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"  SKIP (marker present): {label}")
        return True
    if old not in text:
        print(f"  FAIL anchor missing: {label}")
        return False
    if text.count(old) > 1:
        print(f"  FAIL ambiguous: {label}")
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print(f"  OK: {label}")
    return True


def main_entry() -> int:
    print("Sprint 2 Task 1 AMEND: ls-based path resolution\n")
    print("Patching backup.py...")
    if not replace_once(BACKUP, BACKUP_OLD, BACKUP_NEW, "ls -t ", "path-resolution via ls"):
        return 1
    print("\nPatching test_backup.py (MockAdapter routes by command)...")
    if not replace_once(TESTS, TESTS_MOCK_OLD, TESTS_MOCK_NEW, "ls_output: str =", "MockAdapter routing"):
        return 1
    print("\nReplacing stale 'path-not-in-output' test...")
    if not replace_once(
        TESTS,
        TESTS_OLD_FAIL_TEST,
        TESTS_NEW_FAIL_TEST,
        "test_do_backup_raises_when_ls_finds_no_backup",
        "stale failure test replaced",
    ):
        return 1
    print("\nUpdating success-path test (2 exec calls expected)...")
    if not replace_once(
        TESTS,
        TESTS_SUCCESS_OLD,
        TESTS_SUCCESS_NEW,
        "len(adapter.exec_calls) == 2",
        "success test updated",
    ):
        return 1
    subprocess.run(
        ["git", "add",
         BACKUP.relative_to(ROOT).as_posix(),
         TESTS.relative_to(ROOT).as_posix()],
        cwd=str(ROOT),
        check=True,
    )
    print("\nALL OK. Staged backup.py + test_backup.py")
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())