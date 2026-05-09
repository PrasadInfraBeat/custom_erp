"""Tests for infrabeat_erp.audit and CLI-level audit instrumentation."""

import builtins
import json
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from infrabeat_erp import audit, cli


def _today_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl"


def test_audit_dir_created_on_first_write(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First write_audit_record auto-creates .audit/ under cwd."""
    monkeypatch.chdir(tmp_path)
    record = audit.build_audit_record(
        subcommand="smoke",
        vm="dev",
        args=["smoke", "dev"],
        exit_code=0,
        duration_ms=12,
    )
    audit.write_audit_record(record)

    audit_dir = tmp_path / ".audit"
    assert audit_dir.is_dir()
    audit_file = audit_dir / _today_filename()
    assert audit_file.is_file()
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["subcommand"] == "smoke"


def test_audit_record_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_audit_record returns exactly the 9 documented keys with correct types."""
    record = audit.build_audit_record(
        subcommand="query",
        vm="staging",
        args=["query", "staging", "Sales Order"],
        exit_code=0,
        duration_ms=42,
    )

    expected_keys = {
        "timestamp_utc",
        "user",
        "cli_version",
        "pid",
        "subcommand",
        "vm",
        "args",
        "exit_code",
        "duration_ms",
    }
    assert set(record.keys()) == expected_keys

    assert isinstance(record["timestamp_utc"], str)
    assert isinstance(record["user"], str)
    assert isinstance(record["cli_version"], str)
    assert isinstance(record["pid"], int)
    assert isinstance(record["subcommand"], str)
    assert record["vm"] is None or isinstance(record["vm"], str)
    assert isinstance(record["args"], list)
    assert all(isinstance(a, str) for a in record["args"])
    assert isinstance(record["exit_code"], int)
    assert isinstance(record["duration_ms"], int)


def test_audit_record_isoformat() -> None:
    """timestamp_utc is ISO 8601 UTC ending in 'Z' and parseable."""
    record = audit.build_audit_record(
        subcommand="smoke",
        vm=None,
        args=["smoke"],
        exit_code=0,
        duration_ms=1,
    )
    ts = record["timestamp_utc"]
    assert ts.endswith("Z")
    assert "T" in ts
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.tzinfo.utcoffset(parsed) == timezone.utc.utcoffset(parsed)


def test_audit_write_failure_warns_and_returns(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Write errors print 'audit warning:' to stderr and never raise."""
    monkeypatch.chdir(tmp_path)
    real_open = builtins.open

    def boom(path, *args, **kwargs):
        # Only fail when audit module tries to open the JSONL file; let other
        # opens (e.g. mkdir internals) pass through unchanged.
        if str(path).endswith(".jsonl"):
            raise OSError("disk full")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", boom)

    result = audit.write_audit_record({"smoke": "test"})
    assert result is None
    captured = capsys.readouterr()
    assert "audit warning:" in captured.err
    assert "disk full" in captured.err


def test_audit_invoked_via_cli(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CliRunner --help invocation produces exactly one JSONL audit record."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0

    audit_file = tmp_path / ".audit" / _today_filename()
    assert audit_file.is_file()
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["subcommand"] == "help"
    assert parsed["exit_code"] == 0
    assert parsed["vm"] is None
