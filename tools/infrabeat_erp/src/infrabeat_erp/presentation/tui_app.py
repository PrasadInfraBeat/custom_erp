"""InfraBeat Console - Textual TUI application.

Phase 7a Sprint 1 Task 3 (spec C1): static 3-VM dashboard with hotkey grid.
Live data wiring comes in Sprint 1 Task 4 (spec C2): async SSH polling.

Spec reference: docs/12_INFRABEAT_CONSOLE_SPEC.md Section 3 (Visual Design).
"""
from __future__ import annotations

import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static


class VmCard(Static):
    """Card displaying status of one VM. Static placeholders for Sprint 1 Task 3."""

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

    def render(self) -> str:
        return (
            f"[bold]{self.vm_name.upper()}[/bold]\n"
            f"[dim]{self.ip}[/dim]\n"
            f"\n"
            f"Branch:    [yellow]-[/yellow]\n"
            f"Commit:    [yellow]-[/yellow]\n"
            f"Status:    [yellow]Loading...[/yellow]\n"
            f"\n"
            f"Services:  [yellow]-/7[/yellow]\n"
            f"Site:      [yellow]-[/yellow]\n"
            f"MCP:       [yellow]-[/yellow]\n"
            f"Disk:      [yellow]-[/yellow]\n"
            f"\n"
            f"Last deploy: [yellow]-[/yellow]"
        )


class InfraBeatApp(App):
    """InfraBeat Control Center: single-pane TUI for 3-VM ERPNext."""

    TITLE = "INFRABEAT CONTROL CENTER"
    SUB_TITLE = "Phase 7a Sprint 1 (C1: static dashboard)"

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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="vm_grid"):
            yield VmCard("dev", "10.1.0.184")
            yield VmCard("staging", "10.1.0.185")
            yield VmCard("production", "10.1.0.186")
        yield Footer()

    # ====== Action handlers (placeholders, wired in later C-phases) ======

    def action_promote(self) -> None:
        self.notify("Promote dev->staging (Task 4 C3)", severity="information")

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
    """Entry point for `infrabeat` console-script when not --check mode."""
    app = InfraBeatApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(run())
