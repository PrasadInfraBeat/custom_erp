"""Phase 7a Sprint 1 Task 4: async SSH polling for live VM status (spec C2).

Creates:
  - tools/infrabeat_erp/src/infrabeat_erp/domain/vm_status.py             (NEW: VmStatus dataclass)
  - tools/infrabeat_erp/src/infrabeat_erp/infrastructure/ssh_adapter.py   (NEW: async SSH wrapper)
  - tools/infrabeat_erp/src/infrabeat_erp/application/vm_status_poller.py (NEW: poll orchestration)
  - tools/infrabeat_erp/src/infrabeat_erp/presentation/tui_app.py         (REWRITE: live polling)
  - tools/infrabeat_erp/tests/test_vm_status.py                           (NEW: 6 tests)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp"
DOMAIN = SRC / "domain" / "vm_status.py"
ADAPTER = SRC / "infrastructure" / "ssh_adapter.py"
POLLER = SRC / "application" / "vm_status_poller.py"
TUI_APP = SRC / "presentation" / "tui_app.py"
TESTS = ROOT / "tools" / "infrabeat_erp" / "tests" / "test_vm_status.py"


DOMAIN_CONTENT = '''"""Domain model: VM status snapshot (Sprint 1 Task 4, spec C2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class VmStatus:
    """Immutable snapshot of one VM's state at a point in time.

    Task 4 MVP fields. Additional fields (services_ok, site_up, mcp_ok,
    disk_usage_pct) added in Sprint 2/3 per spec F1 visual design.
    """

    name: str
    host: str
    timestamp: datetime
    reachable: bool

    branch: Optional[str] = None
    commit_short: Optional[str] = None
    last_commit_age_seconds: Optional[int] = None
    error: Optional[str] = None

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        n = now if now is not None else datetime.now(timezone.utc)
        return (n - self.timestamp).total_seconds()

    def is_stale(self, max_age_seconds: int = 30) -> bool:
        return self.age_seconds() > max_age_seconds
'''


ADAPTER_CONTENT = '''"""Async SSH adapter: paramiko in a thread pool (Sprint 1 Task 4)."""
from __future__ import annotations

import asyncio
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Tuple

import paramiko


class SshAdapter:
    """Wraps paramiko in a ThreadPoolExecutor for asyncio-friendly use.

    paramiko is sync-only. asyncio.run_in_executor moves blocking calls
    off the event loop. One adapter shared across all VM polls.
    """

    def __init__(
        self,
        key_path: Path,
        executor: Optional[ThreadPoolExecutor] = None,
        max_workers: int = 6,
    ) -> None:
        self.key_path = key_path
        self._executor = executor or ThreadPoolExecutor(max_workers=max_workers)
        self._pkey: Optional[paramiko.Ed25519Key] = None

    def _load_pkey(self) -> paramiko.Ed25519Key:
        if self._pkey is None:
            self._pkey = paramiko.Ed25519Key.from_private_key(
                io.StringIO(self.key_path.read_text(encoding="utf-8"))
            )
        return self._pkey

    def _exec_sync(
        self, host: str, user: str, command: str, timeout: int
    ) -> Tuple[int, str, str]:
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
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            return exit_code, out, err
        finally:
            client.close()

    async def exec(
        self, host: str, user: str, command: str, timeout: int = 10
    ) -> Tuple[int, str, str]:
        """Async wrapper. Returns (exit_code, stdout, stderr)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, self._exec_sync, host, user, command, timeout
        )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
'''


POLLER_CONTENT = '''"""VM status poller: queries each VM in parallel, builds VmStatus snapshots."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Protocol

from ..domain.vm_status import VmStatus


# Custom_erp repo paths per VM (the actual git repo, not the bench)
VM_REPO_PATHS = {
    "dev": "/home/frappe/frappe-bench/apps/custom_erp",
    "staging": "/home/erpadmin/frappe-bench/apps/custom_erp",
    "production": "/home/erpadmin/frappe-bench/apps/custom_erp",
}


class _SupportsExec(Protocol):
    async def exec(self, host: str, user: str, command: str, timeout: int = 10): ...


def _build_status_query(repo_path: str) -> str:
    """Compose one-shot status query (single SSH round-trip per VM)."""
    return (
        f"cd {repo_path} 2>/dev/null && "
        f"echo BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo NA) && "
        f"echo COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo NA) && "
        f"echo LAST_COMMIT_TS=$(git log -1 --format=%ct 2>/dev/null || echo 0)"
    )


def _parse_status(name: str, host: str, now: datetime, output: str) -> VmStatus:
    """Parse k=v lines from status query output."""
    fields: dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            k, _, v = line.strip().partition("=")
            fields[k] = v
    branch = fields.get("BRANCH")
    if branch == "NA":
        branch = None
    commit = fields.get("COMMIT")
    if commit == "NA":
        commit = None
    try:
        last_ts = int(fields.get("LAST_COMMIT_TS", "0"))
    except ValueError:
        last_ts = 0
    last_age: int | None = None
    if last_ts > 0:
        last_age = max(0, int(now.timestamp() - last_ts))
    return VmStatus(
        name=name,
        host=host,
        timestamp=now,
        reachable=True,
        branch=branch,
        commit_short=commit,
        last_commit_age_seconds=last_age,
    )


async def poll_vm(
    adapter: _SupportsExec, name: str, host: str, user: str
) -> VmStatus:
    """Poll a single VM. Always returns a VmStatus (FAIL path captures errors)."""
    now = datetime.now(timezone.utc)
    repo = VM_REPO_PATHS.get(name, "/home/erpadmin/frappe-bench/apps/custom_erp")
    cmd = _build_status_query(repo)
    try:
        exit_code, out, err = await adapter.exec(host, user, cmd, timeout=10)
        if exit_code != 0:
            return VmStatus(
                name=name,
                host=host,
                timestamp=now,
                reachable=True,
                error=f"exit {exit_code}: {err.strip()[:80]}",
            )
        return _parse_status(name, host, now, out)
    except Exception as e:
        return VmStatus(
            name=name,
            host=host,
            timestamp=now,
            reachable=False,
            error=f"{type(e).__name__}: {e}",
        )


async def poll_all(adapter: _SupportsExec, vms: list[dict]) -> list[VmStatus]:
    """Poll all VMs concurrently. Order matches input order."""
    tasks = [poll_vm(adapter, vm["name"], vm["host"], vm["user"]) for vm in vms]
    return await asyncio.gather(*tasks)
'''


TUI_APP_CONTENT = '''"""InfraBeat Console - Textual TUI with live SSH polling (Sprint 1 Task 4, spec C2)."""
from __future__ import annotations

import asyncio
import sys
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from ..application.doctor import INFRABEAT_SSH_KEY, VMS
from ..application.vm_status_poller import poll_all
from ..domain.vm_status import VmStatus
from ..infrastructure.ssh_adapter import SshAdapter


class VmCard(Static):
    """Stateful card displaying live VM status. Refreshes on update_status()."""

    DEFAULT_CSS = """
    VmCard {
        width: 1fr;
        height: 100%;
        border: solid $accent;
        padding: 1;
    }
    """

    def __init__(self, name: str, ip: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.vm_name = name
        self.ip = ip
        self._status: Optional[VmStatus] = None

    def update_status(self, status: VmStatus) -> None:
        self._status = status
        self.refresh()

    def render(self) -> str:
        if self._status is None:
            return (
                f"[bold]{self.vm_name.upper()}[/bold]\\n"
                f"[dim]{self.ip}[/dim]\\n\\n"
                f"[yellow]Loading...[/yellow]"
            )
        s = self._status
        if not s.reachable:
            return (
                f"[bold red]{self.vm_name.upper()}[/bold red]\\n"
                f"[dim]{self.ip}[/dim]\\n\\n"
                f"[red]UNREACHABLE[/red]\\n"
                f"[dim]{(s.error or 'no detail')[:60]}[/dim]"
            )
        if s.error:
            return (
                f"[bold yellow]{self.vm_name.upper()}[/bold yellow]\\n"
                f"[dim]{self.ip}[/dim]\\n\\n"
                f"[yellow]DEGRADED[/yellow]\\n"
                f"[dim]{(s.error or '')[:60]}[/dim]\\n"
                f"\\nUpdated: {s.timestamp.strftime('%H:%M:%S')}"
            )
        age_str = "-"
        if s.last_commit_age_seconds is not None:
            mins = s.last_commit_age_seconds // 60
            if mins < 60:
                age_str = f"{mins}m ago"
            elif mins < 1440:
                age_str = f"{mins // 60}h ago"
            else:
                age_str = f"{mins // 1440}d ago"
        stale_badge = " [yellow](stale)[/yellow]" if s.is_stale(max_age_seconds=15) else ""
        return (
            f"[bold green]{self.vm_name.upper()}[/bold green]{stale_badge}\\n"
            f"[dim]{self.ip}[/dim]\\n\\n"
            f"Branch:    [cyan]{s.branch or '-'}[/cyan]\\n"
            f"Commit:    [cyan]{s.commit_short or '-'}[/cyan]\\n"
            f"\\n"
            f"Last commit: {age_str}\\n"
            f"\\n"
            f"Updated:   [dim]{s.timestamp.strftime('%H:%M:%S')}[/dim]"
        )


class InfraBeatApp(App):
    """InfraBeat Control Center: live 3-VM TUI."""

    TITLE = "INFRABEAT CONTROL CENTER"
    SUB_TITLE = "Phase 7a Sprint 1 (C2: live SSH polling)"

    POLL_INTERVAL_SECONDS = 5.0

    CSS = """
    #vm_grid {
        height: 1fr;
        layout: horizontal;
    }
    """

    BINDINGS = [
        Binding("p", "promote", "[P]romote", show=True),
        Binding("d", "deploy", "[D]eploy", show=True),
        Binding("b", "backup", "[B]ackup", show=True),
        Binding("s", "smoke", "[S]moke", show=True),
        Binding("l", "logs", "[L]ogs", show=True),
        Binding("g", "github", "[G]itHub", show=True),
        Binding("r", "rollback", "[R]ollback", show=True),
        Binding("a", "audit", "[A]udit", show=True),
        Binding("m", "mcp", "[M]CP", show=True),
        Binding("v", "provision", "[V]Provision", show=True),
        Binding("slash", "search", "[/]Search", show=True),
        Binding("question_mark", "help", "[?]Help", show=True),
        Binding("q", "quit", "[Q]uit", show=True, priority=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._ssh_adapter: Optional[SshAdapter] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._cards: dict[str, VmCard] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="vm_grid"):
            for vm in VMS:
                card = VmCard(vm["name"], vm["host"])
                self._cards[vm["name"]] = card
                yield card
        yield Footer()

    async def on_mount(self) -> None:
        if not INFRABEAT_SSH_KEY.exists():
            self.notify(
                "InfraBeat SSH key missing - run scripts/bootstrap_ssh_keys.py",
                severity="warning",
                timeout=10,
            )
            return
        self._ssh_adapter = SshAdapter(INFRABEAT_SSH_KEY)
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        while True:
            try:
                statuses = await poll_all(self._ssh_adapter, VMS)
                for status in statuses:
                    if status.name in self._cards:
                        self._cards[status.name].update_status(status)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.notify(
                    f"Poll error: {type(e).__name__}: {e}",
                    severity="error",
                    timeout=5,
                )
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    async def on_unmount(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
        if self._ssh_adapter:
            self._ssh_adapter.shutdown()

    # ====== Action handlers (placeholders, wired in later C-phases) ======

    def action_promote(self) -> None:
        self.notify("Promote dev->staging (Sprint 2 C3)", severity="information")

    def action_deploy(self) -> None:
        self.notify("Deploy staging->prod (Sprint 2 C4)", severity="information")

    def action_backup(self) -> None:
        self.notify("Backup (Sprint 2 C5)", severity="information")

    def action_smoke(self) -> None:
        self.notify("Smoke tests (Sprint 2 C5)", severity="information")

    def action_logs(self) -> None:
        self.notify("Live logs (Phase 7b C6)", severity="information")

    def action_github(self) -> None:
        self.notify("GitHub status (Sprint 3 C7)", severity="information")

    def action_rollback(self) -> None:
        self.notify("Rollback (Phase 7b C9)", severity="information")

    def action_audit(self) -> None:
        self.notify("Audit log (Sprint 3 C7)", severity="information")

    def action_mcp(self) -> None:
        self.notify("MCP health (Phase 7b C8)", severity="information")

    def action_provision(self) -> None:
        self.notify("Provision VM (deferred)", severity="warning")

    def action_search(self) -> None:
        self.notify("Search (Phase 7b C10)", severity="information")

    def action_help(self) -> None:
        self.notify("Help (placeholder)", severity="information")


def run() -> int:
    """Entry point for `infrabeat` console-script."""
    app = InfraBeatApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(run())
'''


TESTS_CONTENT = '''"""Tests for VM status polling (Sprint 1 Task 4, spec C2).

Mocks SshAdapter so tests run without real network calls.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from infrabeat_erp.application.vm_status_poller import (
    _build_status_query,
    _parse_status,
    poll_all,
    poll_vm,
)
from infrabeat_erp.domain.vm_status import VmStatus


def test_vm_status_age_seconds_near_zero():
    now = datetime.now(timezone.utc)
    s = VmStatus(name="dev", host="10.1.0.184", timestamp=now, reachable=True)
    assert s.age_seconds(now) == 0.0


def test_vm_status_is_stale_when_old():
    now = datetime.now(timezone.utc)
    past = now - timedelta(seconds=60)
    s = VmStatus(name="dev", host="10.1.0.184", timestamp=past, reachable=True)
    assert s.is_stale(max_age_seconds=30) is True


def test_build_status_query_uses_repo_path():
    q = _build_status_query("/some/path/apps/custom_erp")
    assert "cd /some/path/apps/custom_erp" in q
    assert "git rev-parse --abbrev-ref HEAD" in q
    assert "git log -1 --format=%ct" in q


def test_parse_status_with_valid_output():
    now = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    # last_ts = 1 hour before now in UTC
    last_ts = int(now.timestamp() - 3600)
    output = f"""BRANCH=dev
COMMIT=abc1234
LAST_COMMIT_TS={last_ts}"""
    s = _parse_status("dev", "10.1.0.184", now, output)
    assert s.reachable is True
    assert s.branch == "dev"
    assert s.commit_short == "abc1234"
    assert s.last_commit_age_seconds == 3600


def test_parse_status_treats_NA_as_none():
    now = datetime.now(timezone.utc)
    output = "BRANCH=NA\\nCOMMIT=NA\\nLAST_COMMIT_TS=0"
    s = _parse_status("dev", "10.1.0.184", now, output)
    assert s.branch is None
    assert s.commit_short is None
    assert s.last_commit_age_seconds is None


def test_poll_vm_returns_unreachable_on_exception():
    class FailingAdapter:
        async def exec(self, host, user, command, timeout=10):
            raise ConnectionError("simulated network error")

    s = asyncio.run(poll_vm(FailingAdapter(), "dev", "10.1.0.184", "erpadmin"))
    assert s.reachable is False
    assert "ConnectionError" in (s.error or "")


def test_poll_vm_returns_degraded_on_nonzero_exit():
    class BadExitAdapter:
        async def exec(self, host, user, command, timeout=10):
            return 1, "", "permission denied"

    s = asyncio.run(poll_vm(BadExitAdapter(), "dev", "10.1.0.184", "erpadmin"))
    assert s.reachable is True
    assert "exit 1" in (s.error or "")


def test_poll_all_returns_one_status_per_vm():
    now = datetime.now(timezone.utc)

    class SuccessAdapter:
        async def exec(self, host, user, command, timeout=10):
            return 0, f"BRANCH=dev\\nCOMMIT=abc1234\\nLAST_COMMIT_TS={int(now.timestamp())}\\n", ""

    vms = [
        {"name": "dev", "host": "10.1.0.184", "user": "erpadmin"},
        {"name": "staging", "host": "10.1.0.185", "user": "erpadmin"},
    ]
    results = asyncio.run(poll_all(SuccessAdapter(), vms))
    assert len(results) == 2
    assert all(r.reachable for r in results)
    assert all(r.branch == "dev" for r in results)
'''


def main_entry() -> int:
    print("Phase 7a Sprint 1 Task 4: async SSH polling (spec C2)\\n")
    files = [
        (DOMAIN, DOMAIN_CONTENT, "domain/vm_status.py (NEW: VmStatus dataclass)"),
        (ADAPTER, ADAPTER_CONTENT, "infrastructure/ssh_adapter.py (NEW: async SSH wrapper)"),
        (POLLER, POLLER_CONTENT, "application/vm_status_poller.py (NEW: poll orchestration)"),
        (TUI_APP, TUI_APP_CONTENT, "presentation/tui_app.py (REWRITE: live polling)"),
        (TESTS, TESTS_CONTENT, "tests/test_vm_status.py (NEW: 8 tests)"),
    ]
    for path, content, label in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"  OK: {label}")
    subprocess.run(
        ["git", "add"]
        + [f[0].relative_to(ROOT).as_posix() for f in files],
        cwd=str(ROOT),
        check=True,
    )
    print("\nStaged all 5 files. Run pytest + visual smoke next.")
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())