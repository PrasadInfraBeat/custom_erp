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

# === Sprint 4 Task 1a: TUI wiring for [B]ackup + [P]romote ===
from textual.screen import ModalScreen
from textual.widgets import RichLog, Button, Label
from textual.containers import Vertical
from textual import work
from infrabeat_erp.application.backup import do_backup
from infrabeat_erp.application.promote import do_promote
from infrabeat_erp.application.smoke import smoke_vm


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


class VmSelectModal(ModalScreen[Optional[str]]):
    """Pick a VM from dev/staging/production. Dismisses with VM name or None."""

    DEFAULT_CSS = """
    VmSelectModal {
        align: center middle;
    }

    VmSelectModal > Vertical {
        width: 50;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    VmSelectModal Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def __init__(self, action_label: str) -> None:
        super().__init__()
        self.action_label = action_label

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Select VM for [bold]{self.action_label}[/bold]:")
            yield Button("Dev (10.1.0.184)", id="dev", variant="primary")
            yield Button("Staging (10.1.0.185)", id="staging", variant="primary")
            yield Button("Production (10.1.0.186)", id="production", variant="error")
            yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            self.dismiss(event.button.id)


class PromoteTargetModal(ModalScreen[Optional[str]]):
    """Pick promotion target: staging or production."""

    DEFAULT_CSS = """
    PromoteTargetModal {
        align: center middle;
    }

    PromoteTargetModal > Vertical {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    PromoteTargetModal Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Select promotion target:")
            yield Label("  staging: dev -> staging")
            yield Label("  production: staging -> production (LIVE)")
            yield Button("Promote to STAGING", id="staging", variant="primary")
            yield Button("Promote to PRODUCTION", id="production", variant="error")
            yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            self.dismiss(event.button.id)


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
        yield RichLog(id="output_log", wrap=True, max_lines=500, highlight=True, markup=True)
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

    # ====== Sprint 4 Task 1a: Live workers for [B]ackup and [P]romote ======

    @work(exclusive=True, group="ops")
    async def _run_backup_worker(self, vm: str) -> None:
        """Run do_backup(vm) async; stream to RichLog; notify on completion."""
        log = self.query_one("#output_log", RichLog)
        log.write(f"[bold cyan][backup][/bold cyan] starting on [bold]{vm}[/bold]...")
        self.notify(f"Backup of {vm} started", severity="information", timeout=3)
        try:
            result = await do_backup(vm)
            log.write("[bold green][backup][/bold green] complete:")
            log.write(f"  result = {result}")
            self.notify(f"Backup of {vm} OK", severity="information", timeout=5)
        except Exception as e:
            log.write(f"[bold red][backup ERROR][/bold red] {type(e).__name__}: {e}")
            self.notify(f"Backup of {vm} failed: {e}", severity="error", timeout=10)

    @work(exclusive=True, group="ops")
    async def _run_promote_worker(self, target: str) -> None:
        """Run do_promote(target) async; stream to RichLog; notify on completion."""
        log = self.query_one("#output_log", RichLog)
        log.write(f"[bold cyan][promote][/bold cyan] starting to [bold]{target}[/bold]...")
        self.notify(f"Promote to {target} started", severity="information", timeout=3)
        try:
            result = await do_promote(target)
            log.write("[bold green][promote][/bold green] complete:")
            log.write(f"  result = {result}")
            self.notify(f"Promote to {target} OK", severity="information", timeout=5)
        except Exception as e:
            log.write(f"[bold red][promote ERROR][/bold red] {type(e).__name__}: {e}")
            self.notify(f"Promote to {target} failed: {e}", severity="error", timeout=10)

    @work(exclusive=True, group="ops", thread=True)
    def _run_smoke_worker(self, vm: str) -> None:
        """Run smoke_vm(vm) in thread; UI updates via call_from_thread."""
        log = self.query_one("#output_log", RichLog)
        self.call_from_thread(log.write, f"[bold cyan][smoke][/bold cyan] starting on [bold]{vm}[/bold]...")
        self.call_from_thread(self.notify, f"Smoke on {vm} started", severity="information", timeout=3)
        try:
            result = smoke_vm(vm)
            self.call_from_thread(log.write, "[bold green][smoke][/bold green] complete:")
            self.call_from_thread(log.write, f"  server = {result.server_name} {result.server_version}")
            self.call_from_thread(log.write, f"  protocol = {result.protocol_version}")
            self.call_from_thread(log.write, f"  tools = {result.tool_count}")
            self.call_from_thread(self.notify, f"Smoke {vm}: {result.tool_count} tools OK", severity="information", timeout=5)
        except Exception as e:
            self.call_from_thread(log.write, f"[bold red][smoke ERROR][/bold red] {type(e).__name__}: {e}")
            self.call_from_thread(self.notify, f"Smoke {vm} failed: {e}", severity="error", timeout=10)

    # ====== Action handlers (LIVE for [B][S][P], stubs for others) ======

    def action_promote(self) -> None:
        """[P] -> Target picker -> spawn promote worker."""
        def _on_target_selected(target: Optional[str]) -> None:
            if target:
                self._run_promote_worker(target)

        self.push_screen(PromoteTargetModal(), _on_target_selected)

    def action_deploy(self) -> None:
        self.notify("Deploy staging->prod (Sprint 2 C4)", severity="information")

    def action_backup(self) -> None:
        """[B] -> VM picker -> spawn backup worker."""
        def _on_vm_selected(vm: Optional[str]) -> None:
            if vm:
                self._run_backup_worker(vm)

        self.push_screen(VmSelectModal("Backup"), _on_vm_selected)

    def action_smoke(self) -> None:
        """[S] -> VM picker -> spawn smoke worker (thread, since smoke_vm is sync)."""
        def _on_vm_selected(vm: Optional[str]) -> None:
            if vm:
                self._run_smoke_worker(vm)

        self.push_screen(VmSelectModal("Smoke"), _on_vm_selected)

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
