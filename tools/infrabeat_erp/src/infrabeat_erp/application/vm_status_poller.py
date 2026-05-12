"""VM status poller: queries each VM in parallel, builds VmStatus snapshots."""
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
