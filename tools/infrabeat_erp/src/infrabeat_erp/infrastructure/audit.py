"""JSONL audit log for every infrabeat-erp CLI invocation (Phase 6C.3).

Captures one JSON record per invocation under a platform-appropriate user-home
directory: ~/.local/share/infrabeat-erp/audit/<YYYY-MM-DD>.jsonl on Linux/macOS
and %APPDATA%/infrabeat-erp/audit/<YYYY-MM-DD>.jsonl on Windows. Phase 6E.6
(L50) moved this off the CWD-relative .audit/ path to stop polluting the repo
root when CLI tests run via CliRunner.

Stdlib only - no click imports - so Phase 7 InfraBeat Console code can read
these JSONL files for the audit viewer pane without dragging the CLI in.

Public surface:
    write_audit_record(record: dict) -> None
    build_audit_record(subcommand, vm, args, exit_code, duration_ms) -> dict

Failure mode: write errors emit a single 'audit warning:' line on stderr and
return None. Audit MUST NEVER raise, MUST NEVER block the CLI.
"""

import json
import os
import sys
from datetime import datetime, timezone
from importlib import metadata as _metadata
from pathlib import Path


def _get_audit_dir() -> Path:
    """Return the platform-appropriate user-home directory for audit logs."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(
            Path.home() / "AppData" / "Roaming"
        )
        return Path(appdata) / "infrabeat-erp" / "audit"
    return Path.home() / ".local" / "share" / "infrabeat-erp" / "audit"


def _audit_file_for_today() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _get_audit_dir() / f"{today}.jsonl"


def _resolve_user() -> str:
    try:
        return os.getlogin()
    except OSError:
        return (
            os.environ.get("USERNAME")
            or os.environ.get("USER")
            or "unknown"
        )


def _resolve_cli_version() -> str:
    try:
        return _metadata.version("infrabeat-erp")
    except _metadata.PackageNotFoundError:
        return "unknown"


def build_audit_record(
    subcommand: str,
    vm: str | None,
    args: list[str],
    exit_code: int,
    duration_ms: int,
) -> dict:
    """Assemble the 9-field audit record for one CLI invocation."""
    return {
        "timestamp_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "user": _resolve_user(),
        "cli_version": _resolve_cli_version(),
        "pid": os.getpid(),
        "subcommand": subcommand,
        "vm": vm,
        "args": list(args),
        "exit_code": int(exit_code),
        "duration_ms": int(duration_ms),
    }


def write_audit_record(record: dict) -> None:
    """Append one JSONL record to today's audit file. Fail-silent on errors."""
    try:
        path = _audit_file_for_today()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:
        try:
            sys.stderr.write(f"audit warning: {exc}\n")
        except Exception:
            pass
        return None
