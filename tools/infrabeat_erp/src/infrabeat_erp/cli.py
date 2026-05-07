"""infrabeat-erp CLI entry point.

Phase 6A: minimal click root group. Subcommands (register, login, smoke,
query, get, describe, search) wire up in sub-phase 6B.
"""

import click

from infrabeat_erp import __version__


@click.group(
    help="InfraBeat ERPNext CLI - discovery, OAuth, and MCP query bridge for FAC."
)
@click.version_option(version=__version__, prog_name="infrabeat-erp")
def main() -> None:
    """Root command group. Subcommands appear in sub-phase 6B."""


if __name__ == "__main__":
    main()
