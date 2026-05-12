"""InfraBeat Console - Textual TUI with live SSH polling (Sprint 1 Task 4, spec C2)."""
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
                f"[bold]{self.vm_name.upper()}[/bold]\n"
                f"[dim]{self.ip}[/dim]\n\n"
                f"[yellow]Loading...[/yellow]"
            )
        s = self._status
        if not s.reachable:
            return (
                f"[bold red]{self.vm_name.upper()}[/bold red]\n"
                f"[dim]{self.ip}[/dim]\n\n"
                f"[red]UNREACHABLE[/red]\n"
                f"[dim]{(s.error or 'no detail')[:60]}[/dim]"
            )
        if s.error:
            return (
                f"[bold yellow]{self.vm_name.upper()}[/bold yellow]\n"
                f"[dim]{self.ip}[/dim]\n\n"
                f"[yellow]DEGRADED[/yellow]\n"
                f"[dim]{(s.error or '')[:60]}[/dim]\n"
                f"\nUpdated: {s.timestamp.strftime('%H:%M:%S')}"
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
            f"[bold green]{self.vm_name.upper()}[/bold green]{stale_badge}\n"
            f"[dim]{self.ip}[/dim]\n\n"
            f"Branch:    [cyan]{s.branch or '-'}[/cyan]\n"
            f"Commit:    [cyan]{s.commit_short or '-'}[/cyan]\n"
            f"\n"
            f"Last commit: {age_str}\n"
            f"\n"
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
